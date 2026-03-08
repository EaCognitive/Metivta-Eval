"""Flask compatibility API for legacy MetivtaEval routes and HTML surfaces."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from api.database.supabase_manager import DatabaseManager, LegacySubmissionRecord
from api.handlers.async_handler import get_task_status, submit_evaluation
from api.handlers.generate_leaderboard import generate_leaderboard
from api.utils.dataset_validator import get_validator
from api.workers.evaluation_tasks import compute_submission_scores
from metivta_eval.config.config_loader import get_config_section
from metivta_eval.dataset_loader import load_questions_only_examples
from metivta_eval.langsmith_utils import ensure_daat_dependencies
from metivta_eval.persistence.database import (
    EvaluationCreateRequest,
    EvaluationDescriptor,
    EvaluationIdentity,
    EvaluationLifecycle,
)

# Load all environment files (override=True to replace any cached env vars)
load_dotenv(override=True)  # Load .env

# Configure logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)
load_dotenv(".env.supabase", override=True)  # Load Supabase credentials
app = Flask(__name__, static_folder="static", static_url_path="/static")

# Initialize database manager
db = DatabaseManager()

api_config = get_config_section("api")
DATA_FILE = api_config.get("data_file", "api/leaderboard_data.json")


def _load_leaderboard_submissions() -> list[dict[str, object]]:
    """Load leaderboard data from the canonical DB with file fallback."""
    submissions = db.get_leaderboard_data()
    if submissions:
        return submissions

    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if isinstance(payload, list):
        return payload
    return []


def _json_response(payload: dict[str, Any], status_code: int) -> tuple[Response, int]:
    """Build a JSON Flask response tuple."""
    return jsonify(payload), status_code


def _authenticate_submission_request() -> tuple[dict[str, Any], str] | tuple[Response, int]:
    """Authenticate a legacy `/submit` request."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return _json_response({"error": "Missing or invalid authorization header"}, 401)

    api_key = auth_header.removeprefix("Bearer ").strip()
    user_info = db.validate_api_key(api_key)
    if not user_info:
        return _json_response({"error": "Invalid API key"}, 401)

    api_key_id = user_info["api_key_id"]
    within_limit, requests_made = db.check_rate_limit(api_key_id)
    if not within_limit:
        return _json_response(
            {
                "error": "Rate limit exceeded",
                "limit": user_info["rate_limit"],
                "requests_made": requests_made,
            },
            429,
        )
    return user_info, api_key_id


def _validate_submission_payload() -> dict[str, Any] | tuple[Response, int]:
    """Validate the legacy submission payload."""
    data = request.get_json()
    required_fields = ("author", "system_name", "endpoint_url")
    if not data or any(not data.get(field) for field in required_fields):
        return _json_response(
            {"error": "Request must include 'author', 'system_name', and 'endpoint_url'."},
            400,
        )
    return data


def _append_legacy_leaderboard_row(data: dict[str, Any], scores: dict[str, float]) -> None:
    """Append one completed submission to the legacy file-backed leaderboard."""
    leaderboard_data = _load_leaderboard_file()
    leaderboard_data.append(
        {
            "id": str(uuid4())[:8],
            "system": data["system_name"],
            "author": data["author"],
            "timestamp": datetime.now(UTC).isoformat(),
            "scores": scores,
        }
    )
    with open(DATA_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(leaderboard_data, file_obj, indent=2)


def _load_leaderboard_file() -> list[dict[str, Any]]:
    """Load the file-backed leaderboard payload."""
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if isinstance(payload, list):
        return payload
    return []


def _build_async_evaluation(
    data: dict[str, Any],
    user_info: dict[str, Any],
    api_key_id: str,
    dataset_name: str,
) -> dict[str, Any]:
    """Create the persisted evaluation row used by the async path."""
    return db.create_evaluation(
        EvaluationCreateRequest(
            identity=EvaluationIdentity(
                user_id=user_info["user_id"],
                evaluation_id=str(uuid4()),
                api_key_id=api_key_id,
            ),
            descriptor=EvaluationDescriptor(
                system_name=data["system_name"],
                system_version=None,
                author=data["author"],
                endpoint_url=data["endpoint_url"],
                mode="daat",
                dataset_name=dataset_name,
            ),
            lifecycle=EvaluationLifecycle(status="pending", progress=0),
        )
    )


def _handle_async_submission(
    data: dict[str, Any],
    user_info: dict[str, Any],
    api_key_id: str,
    dataset_name: str,
) -> tuple[Response, int]:
    """Queue a legacy submission for async processing."""
    logger.info("Async mode requested for /submit")
    evaluation = _build_async_evaluation(data, user_info, api_key_id, dataset_name)
    try:
        task_id = submit_evaluation(data, api_key_id, evaluation["id"], dataset_name)
    except RuntimeError as exc:
        db.update_evaluation(
            evaluation["id"],
            status="failed",
            progress=100,
            error_message=str(exc),
        )
        return _json_response(
            {
                "error": "Async evaluation backend unavailable",
                "details": str(exc),
            },
            503,
        )

    db.log_usage(api_key_id, "/submit", 202)
    return _json_response(
        {
            "message": "Submission accepted for async processing.",
            "task_id": task_id,
            "status_url": f"/status/{task_id}",
            "status": "queued",
        },
        202,
    )


def _handle_sync_submission(
    data: dict[str, Any],
    api_key_id: str,
    dataset_name: str,
) -> tuple[Response, int]:
    """Execute a legacy submission synchronously."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not found in environment")

    scores = compute_submission_scores(submission_data=data, dataset_name=dataset_name)
    db.save_submission(
        LegacySubmissionRecord(
            api_key_id=api_key_id,
            system_name=data["system_name"],
            author=data["author"],
            endpoint_url=data["endpoint_url"],
            scores=scores,
        )
    )
    db.log_usage(api_key_id, "/submit", 200)
    _append_legacy_leaderboard_row(data, scores)
    generate_leaderboard()
    return _json_response(
        {"message": "Submission successful! Leaderboard updated.", "scores": scores},
        200,
    )


@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({"status": "healthy", "service": "Metivta Eval - The Open Torah"}), 200


@app.route("/signup", methods=["GET"])
def signup_page():
    """Serve the registration page"""
    return render_template("register.html")


@app.route("/docs", methods=["GET"])
def api_docs():
    """Serve the API documentation"""
    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    return send_from_directory(docs_dir, "index-api.html")


@app.route("/docs/<path:filename>", methods=["GET"])
def serve_docs_files(filename):
    """Serve static files from docs directory"""
    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    return send_from_directory(docs_dir, filename)


@app.route("/dataset-info", methods=["GET"])
def dataset_info():
    """Get information about the evaluation dataset"""
    try:
        validator = get_validator()
        info = validator.get_dataset_info()
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return (
            jsonify(
                {
                    "error": "Dataset information is unavailable",
                    "details": str(exc),
                }
            ),
            503,
        )
    return jsonify(info), 200


@app.route("/validate-endpoint", methods=["POST"])
def validate_endpoint():
    """Validate that an endpoint only answers dataset questions"""
    data = request.json

    if not data or "endpoint_url" not in data:
        return jsonify({"error": "endpoint_url is required"}), 400

    try:
        validator = get_validator()
        result = validator.validate_submission(data["endpoint_url"])
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return (
            jsonify(
                {
                    "valid": False,
                    "message": "Endpoint validation is unavailable",
                    "errors": [str(exc)],
                }
            ),
            503,
        )

    if not result["valid"]:
        return jsonify(
            {"valid": False, "message": "Endpoint validation failed", "errors": result["errors"]}
        ), 400

    return jsonify(
        {
            "valid": True,
            "message": f"Endpoint validated successfully for {result['dataset_size']} questions",
        }
    ), 200


@app.route("/register", methods=["POST"])
def register():
    """Register a new user and get API key"""
    data = request.json

    if not data or not all(k in data for k in ["email", "name"]):
        return jsonify({"error": "Email and name are required"}), 400

    try:
        result = db.create_user_with_api_key(
            email=data["email"],
            name=data["name"],
            organization=data.get("organization"),
            description=data.get("description"),
        )

        if "error" in result:
            return jsonify(result), 400

        return jsonify(
            {
                "message": "Registration successful! Save your API key - it won't be shown again.",
                "api_key": result["api_key"],
                "key_prefix": result["key_prefix"],
            }
        ), 201

    except (TypeError, ValueError, KeyError, OSError) as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/submit", methods=["POST"])
def submit_run():
    """Submit evaluation for async processing."""
    use_async = request.args.get("async", "false").lower() == "true"
    auth_result = _authenticate_submission_request()
    if isinstance(auth_result[0], Response):
        return auth_result

    user_info, api_key_id = auth_result
    payload_result = _validate_submission_payload()
    if isinstance(payload_result, tuple):
        return payload_result

    data = payload_result

    try:
        dataset_name = ensure_daat_dependencies(force_refresh=True)
    except RuntimeError as exc:
        return _json_response({"error": "DAAT evaluation unavailable", "details": str(exc)}, 503)

    try:
        if use_async:
            return _handle_async_submission(data, user_info, api_key_id, dataset_name)
        return _handle_sync_submission(data, api_key_id, dataset_name)
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        db.log_usage(api_key_id, "/submit", 500)
        return _json_response(
            {"error": "An internal error occurred during evaluation.", "details": str(exc)},
            500,
        )


@app.route("/status/<task_id>", methods=["GET"])
def check_status(task_id):
    """Check the status of an async evaluation task."""
    try:
        task_status = get_task_status(task_id)

        if not task_status:
            return jsonify({"error": "Task not found"}), 404

        response = {
            "state": task_status["state"],
            "status": task_status.get("status", ""),
        }

        if "progress" in task_status:
            response["progress"] = task_status["progress"]

        if task_status["state"] == "SUCCESS" and task_status.get("result"):
            response["result"] = task_status["result"]

        if task_status["state"] == "FAILURE" and task_status.get("error"):
            response["error"] = task_status["error"]
        return jsonify(response), 200
    except (TypeError, ValueError, KeyError, OSError) as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/questions", methods=["GET"])
def get_questions():
    """Get evaluation questions for testing"""
    try:
        questions_data = load_questions_only_examples()

        # Extract just the questions
        questions = []
        for idx, item in enumerate(questions_data):
            questions.append({"id": idx + 1, "question": item["inputs"]["question"]})
        return jsonify({"questions": questions, "total": len(questions)}), 200
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        logger.error("Error getting questions: %s", exc)
        return jsonify({"error": "Failed to retrieve questions"}), 500


@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    """Get current leaderboard data or HTML view"""
    # Check if client wants JSON (API call) or HTML (browser)
    if request.headers.get("Accept", "").startswith("application/json"):
        # Return JSON data
        try:
            submissions = _load_leaderboard_submissions()
            return jsonify({"submissions": submissions}), 200
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            # If DB not available, try to read from file
            if os.path.exists(DATA_FILE):
                data = _load_leaderboard_file()
                return jsonify({"submissions": data}), 200
            return jsonify({"error": str(exc)}), 500
    else:
        # Return HTML leaderboard
        try:
            submissions = _load_leaderboard_submissions()
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            submissions = []
        return render_template("leaderboard.html", initial_submissions=submissions)


if __name__ == "__main__":
    # Use Railway's PORT if available, otherwise use config
    port = int(os.environ.get("PORT", api_config["port"]))
    app.run(host="0.0.0.0", port=port)
