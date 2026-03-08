"""HTTP entrypoint for simple serverless DAAT evaluation requests."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any

from dotenv import load_dotenv

from api.workers.evaluation_tasks import compute_submission_scores
from metivta_eval.langsmith_utils import ensure_daat_dependencies

load_dotenv(override=True)

_JSON_HEADERS = {"Content-Type": "application/json"}
_REQUIRED_FIELDS = ("author", "system_name", "endpoint_url")


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    """Decode the current request body as JSON."""
    content_length = int(handler.headers.get("Content-Length", "0"))
    if content_length <= 0:
        raise ValueError("Request body is required.")

    payload = handler.rfile.read(content_length)
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object.")
    return data


def _validate_payload(data: dict[str, Any]) -> None:
    """Validate the minimal submission payload."""
    missing_fields = [field for field in _REQUIRED_FIELDS if not data.get(field)]
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise ValueError(f"Missing required field(s): {missing}.")


class Handler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for serverless-compatible evaluation requests."""

    server_version = "MetivtaEvalServerless/1.0"

    def handle_post(self) -> None:
        """Evaluate a submitted endpoint and return aggregate scores."""
        try:
            data = _read_json_body(self)
            _validate_payload(data)
            dataset_name = ensure_daat_dependencies(force_refresh=True)
            scores = compute_submission_scores(data, dataset_name)
            self._write_json(
                HTTPStatus.OK,
                {
                    "status": "success",
                    "dataset_name": dataset_name,
                    "scores": scores,
                    "evaluators": sorted(scores),
                },
            )
        except (ValueError, json.JSONDecodeError) as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": str(exc)})
        except RuntimeError as exc:
            self._write_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"status": "error", "error": "DAAT evaluation unavailable", "details": str(exc)},
            )
        except (OSError, TypeError, KeyError) as exc:
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"status": "error", "error": "Evaluation failed", "details": str(exc)},
            )

    def handle_get(self) -> None:
        """Return serverless health metadata."""
        try:
            dataset_name = ensure_daat_dependencies(force_refresh=True)
            payload = {
                "service": "MetivtaEval API",
                "status": "healthy",
                "dataset_name": dataset_name,
                "platform": "serverless",
            }
            self._write_json(HTTPStatus.OK, payload)
        except RuntimeError as exc:
            self._write_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "service": "MetivtaEval API",
                    "status": "degraded",
                    "error": str(exc),
                    "platform": "serverless",
                },
            )

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        """Write a JSON response body."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(int(status))
        for header, value in _JSON_HEADERS.items():
            self.send_header(header, value)
        self.end_headers()
        self.wfile.write(body)


Handler.do_GET = Handler.handle_get
Handler.do_POST = Handler.handle_post
