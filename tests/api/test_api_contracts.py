"""API contract tests for FastAPI v2 and Flask /submit compatibility."""

from __future__ import annotations

from html import unescape
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import api.fastapi_app.main as fastapi_main
import api.server as flask_server
from api.database import supabase_manager
from api.fastapi_app.routers import evaluation as evaluation_router
from api.fastapi_app.routers import health as health_router
from metivta_eval import daat_runtime
from metivta_eval.config.toml_config import config
from metivta_eval.langsmith_utils import (
    DaatDependencyStatus,
    clear_daat_dependency_cache,
    get_daat_dependency_status,
    resolve_daat_evaluation_data,
)
from metivta_eval.persistence.database import (
    EvaluationCreateRequest,
    EvaluationDescriptor,
    EvaluationIdentity,
    EvaluationLifecycle,
)


def _dispose_repository(db_manager: Any) -> None:
    """Dispose active SQLAlchemy engine in tests to avoid resource leaks."""
    db_manager.reset_repository()


def _set_sqlite_db(monkeypatch, db_path: Path) -> None:
    """Configure in-process services to use a temporary sqlite database."""
    monkeypatch.setenv("METIVTA_DATABASE_URL", f"sqlite:///{db_path}")
    _dispose_repository(supabase_manager.db)
    _dispose_repository(flask_server.db)


def _set_fastapi_daat_status(
    monkeypatch,
    status: DaatDependencyStatus,
    *,
    include_health_router: bool = False,
) -> None:
    """Patch FastAPI DAAT dependency lookups to a controlled status."""
    monkeypatch.setattr(
        fastapi_main,
        "get_daat_dependency_status",
        lambda force_refresh=False: status,
    )
    if include_health_router:
        monkeypatch.setattr(
            health_router,
            "get_daat_dependency_status",
            lambda force_refresh=False: status,
        )


def _register_and_login_user(
    client: TestClient,
    *,
    email: str,
    name: str,
    organization: str | None = None,
) -> tuple[dict[str, str], str]:
    """Create a user and return authenticated headers plus the user ID."""
    email_prefix = email.split("@", maxsplit=1)[0].replace(".", "-")
    password = f"Metivta-{email_prefix}-1!"
    register_response = client.post(
        "/api/v2/auth/register",
        json={
            "email": email,
            "name": name,
            "password": password,
            "organization": organization,
        },
    )
    assert register_response.status_code == 201, register_response.text

    login_response = client.post(
        "/api/v2/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}, register_response.json()["id"]


def _assert_scalar_docs_contract(client: TestClient) -> None:
    """Assert the live API docs expose the expected Scalar configuration."""
    docs_response = client.get("/api/v2/docs")
    assert docs_response.status_code == 200, docs_response.text
    docs_html = unescape(docs_response.text)
    assert "@scalar/api-reference" in docs_html
    assert "/api/v2/openapi.json" in docs_html
    assert '"showSidebar": true' in docs_html
    assert '"defaultOpenFirstTag": true' in docs_html
    assert '"defaultOpenAllTags": true' in docs_html
    assert '"showDeveloperTools": "never"' in docs_html

    openapi_response = client.get("/api/v2/openapi.json")
    assert openapi_response.status_code == 200, openapi_response.text
    openapi_info = openapi_response.json()["info"]
    assert openapi_info["title"] == "MetivtaEval API"
    assert "## MetivtaEval - AI Benchmarking Platform" in openapi_info["description"]
    assert "LangSmith" in openapi_info["description"]
    assert "Rate Limiting" not in openapi_info["description"]


def _create_legacy_api_key(email: str, name: str) -> str:
    """Create a legacy API key for Flask compatibility tests."""
    registration = flask_server.db.create_user_with_api_key(email=email, name=name)
    return str(registration["api_key"])


def test_daat_dependency_uses_local_dataset_without_langsmith(monkeypatch) -> None:
    """DAAT should stay runnable from the local JSON dataset without LangSmith."""
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("METIVTA_MODELS_LANGSMITH_API_KEY", raising=False)
    clear_daat_dependency_cache()

    status = get_daat_dependency_status(force_refresh=True)

    assert status.ready is True
    assert status.dataset_path is not None
    assert status.example_count > 0
    assert "Loaded" in status.message
    assert "Local DAAT evaluation is ready" in status.message
    assert status.langsmith_enabled is False

    dataset_name, dataset_examples = resolve_daat_evaluation_data()
    assert dataset_name == status.dataset_name
    assert len(dataset_examples) == status.example_count
    assert hasattr(dataset_examples[0], "dataset_id")


def test_daat_dependency_reports_dataset_io_failures(monkeypatch, tmp_path: Path) -> None:
    """DAAT readiness should degrade cleanly when the dataset cannot be read."""
    broken_path = tmp_path / "restricted.json"
    clear_daat_dependency_cache()
    monkeypatch.setattr(daat_runtime, "resolve_dataset_file_path", lambda: broken_path)

    def _raise_io_error(file_path: str | None = None) -> list[dict[str, object]]:
        del file_path
        raise PermissionError("permission denied while opening dataset")

    monkeypatch.setattr(daat_runtime, "load_dataset_examples", _raise_io_error)

    status = daat_runtime.get_daat_dependency_status(force_refresh=True)

    assert status.ready is False
    assert status.dataset_path == str(broken_path)
    assert "permission denied while opening dataset" in status.message


def test_fastapi_v2_auth_eval_leaderboard_contract(monkeypatch, tmp_path: Path) -> None:
    """Auth + eval + leaderboard contract should be functional with canonical DB."""
    _set_sqlite_db(monkeypatch, tmp_path / "fastapi_contract.db")

    async def fake_run_evaluation_task(**kwargs) -> None:
        del kwargs

    _set_fastapi_daat_status(
        monkeypatch,
        DaatDependencyStatus(
            ready=True,
            dataset_name="Metivta-Eval",
            message="LangSmith dataset 'Metivta-Eval' is available.",
        ),
    )
    monkeypatch.setattr(
        evaluation_router,
        "ensure_daat_dependencies",
        lambda dataset_name="default", force_refresh=False: "Metivta-Eval",
    )
    monkeypatch.setattr(evaluation_router, "run_evaluation_task", fake_run_evaluation_task)
    client = TestClient(fastapi_main.create_app())
    _assert_scalar_docs_contract(client)
    auth_headers, _ = _register_and_login_user(
        client,
        email="contract-user@example.com",
        name="Contract User",
        organization="Metivta",
    )

    create_key_response = client.post(
        "/api/v2/auth/api-keys",
        json={"name": "contract-key", "scopes": ["eval:read", "eval:write"]},
        headers=auth_headers,
    )
    assert create_key_response.status_code == 201, create_key_response.text
    assert create_key_response.json()["key_prefix"].startswith(config.security.api_keys.prefix)

    eval_payload = {
        "system_name": "contract-system",
        "system_version": "1.0.0",
        "endpoint_url": "https://example.com/qa",
        "mode": "daat",
        "dataset_name": "Metivta-Eval",
        "async_mode": True,
    }
    submit_eval_response = client.post("/api/v2/eval/", json=eval_payload, headers=auth_headers)
    assert submit_eval_response.status_code == 202, submit_eval_response.text
    evaluation_id = submit_eval_response.json()["id"]

    eval_list_response = client.get("/api/v2/eval/", headers=auth_headers)
    assert eval_list_response.status_code == 200, eval_list_response.text
    assert eval_list_response.json()["total"] >= 1

    eval_status_response = client.get(f"/api/v2/eval/{evaluation_id}", headers=auth_headers)
    assert eval_status_response.status_code == 200, eval_status_response.text

    leaderboard_response = client.get("/api/v2/leaderboard/", headers=auth_headers)
    assert leaderboard_response.status_code == 200, leaderboard_response.text
    assert "entries" in leaderboard_response.json()

    _dispose_repository(supabase_manager.db)


def test_flask_submit_backward_compatibility_contract(monkeypatch, tmp_path: Path) -> None:
    """Legacy /submit should keep compatibility while persisting to canonical DB."""
    _set_sqlite_db(monkeypatch, tmp_path / "flask_contract.db")
    leaderboard_file = tmp_path / "leaderboard_data.json"
    monkeypatch.setattr(flask_server, "DATA_FILE", str(leaderboard_file))
    monkeypatch.setattr(flask_server, "generate_leaderboard", lambda: None)
    monkeypatch.setattr(
        flask_server,
        "ensure_daat_dependencies",
        lambda force_refresh=False: "Metivta-Eval",
    )
    monkeypatch.setattr(
        flask_server,
        "compute_submission_scores",
        lambda submission_data, dataset_name: {"daat_score": 0.91, "url_format": 1.0},
    )
    api_key = _create_legacy_api_key("legacy-user@example.com", "Legacy User")

    client = flask_server.app.test_client()
    response = client.post(
        "/submit",
        json={
            "author": "Legacy User",
            "system_name": "Legacy Contract System",
            "endpoint_url": "https://example.com/legacy",
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload is not None
    assert payload["message"] == "Submission successful! Leaderboard updated."
    assert payload["scores"]["daat_score"] == 0.91
    assert payload["scores"]["url_format"] == 1.0
    assert leaderboard_file.exists()

    leaderboard_entries = flask_server.db.get_leaderboard()
    assert leaderboard_entries
    _dispose_repository(flask_server.db)


def test_flask_submit_returns_503_when_daat_dependencies_are_unavailable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Legacy /submit should reject work when the configured dataset is unavailable."""
    _set_sqlite_db(monkeypatch, tmp_path / "flask_submit_503.db")

    def _raise_dependency_error(force_refresh: bool = False) -> str:
        del force_refresh
        raise RuntimeError("dataset file is unreadable")

    monkeypatch.setattr(flask_server, "ensure_daat_dependencies", _raise_dependency_error)
    api_key = _create_legacy_api_key("legacy-503@example.com", "Legacy Failure")

    client = flask_server.app.test_client()
    response = client.post(
        "/submit",
        json={
            "author": "Legacy Failure",
            "system_name": "Legacy Failure System",
            "endpoint_url": "https://example.com/legacy",
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 503, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload is not None
    assert payload["error"] == "DAAT evaluation unavailable"
    assert "dataset file is unreadable" in payload["details"]
    _dispose_repository(flask_server.db)


def test_flask_dataset_routes_report_dataset_load_failures(monkeypatch, tmp_path: Path) -> None:
    """Legacy dataset helper routes should surface dataset load failures clearly."""
    _set_sqlite_db(monkeypatch, tmp_path / "flask_dataset_503.db")

    def _raise_validator_error():
        raise ValueError("dataset file is invalid")

    monkeypatch.setattr(flask_server, "get_validator", _raise_validator_error)
    client = flask_server.app.test_client()

    info_response = client.get("/dataset-info")
    assert info_response.status_code == 503, info_response.get_data(as_text=True)
    info_payload = info_response.get_json()
    assert info_payload is not None
    assert info_payload["error"] == "Dataset information is unavailable"
    assert "dataset file is invalid" in info_payload["details"]

    validate_response = client.post(
        "/validate-endpoint",
        json={"endpoint_url": "https://example.com/answer"},
    )
    assert validate_response.status_code == 503, validate_response.get_data(as_text=True)
    validate_payload = validate_response.get_json()
    assert validate_payload is not None
    assert validate_payload["valid"] is False
    assert validate_payload["message"] == "Endpoint validation is unavailable"
    assert "dataset file is invalid" in validate_payload["errors"][0]
    _dispose_repository(flask_server.db)


def test_fastapi_readiness_reports_missing_daat_dependency(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Readiness should surface DAAT dependency failures."""
    _set_sqlite_db(monkeypatch, tmp_path / "fastapi_readiness.db")
    _set_fastapi_daat_status(
        monkeypatch,
        DaatDependencyStatus(
            ready=False,
            dataset_name="Metivta-Eval",
            message="Dataset Metivta-Eval not found",
        ),
        include_health_router=True,
    )

    client = TestClient(fastapi_main.create_app())
    response = client.get("/ready")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ready"] is False
    assert payload["checks"]["daat_dataset"] is False
    assert "Dataset Metivta-Eval not found" in payload["details"]["daat_dataset"]


def test_fastapi_submit_returns_503_when_daat_dependencies_are_unavailable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """FastAPI should reject DAAT jobs before persistence when the dataset is unavailable."""
    _set_sqlite_db(monkeypatch, tmp_path / "fastapi_submit_503.db")

    def _raise_dependency_error(
        dataset_name: str = "default",
        force_refresh: bool = False,
    ) -> str:
        del dataset_name, force_refresh
        raise RuntimeError("dataset file is unreadable")

    monkeypatch.setattr(evaluation_router, "ensure_daat_dependencies", _raise_dependency_error)

    client = TestClient(fastapi_main.create_app())
    auth_headers, _ = _register_and_login_user(
        client,
        email="submit-503@example.com",
        name="Submit Failure",
    )

    submit_eval_response = client.post(
        "/api/v2/eval/",
        json={
            "system_name": "submit-503-system",
            "endpoint_url": "https://example.com/qa",
            "mode": "daat",
            "async_mode": True,
        },
        headers=auth_headers,
    )
    assert submit_eval_response.status_code == 503, submit_eval_response.text
    assert "dataset file is unreadable" in submit_eval_response.json()["detail"]

    eval_list_response = client.get("/api/v2/eval/", headers=auth_headers)
    assert eval_list_response.status_code == 200, eval_list_response.text
    assert eval_list_response.json()["total"] == 0

    _dispose_repository(supabase_manager.db)


def test_fastapi_submit_rejects_unsupported_daat_dataset_name(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """FastAPI should reject unsupported DAAT dataset aliases before persistence."""
    _set_sqlite_db(monkeypatch, tmp_path / "fastapi_submit_unsupported_dataset.db")

    client = TestClient(fastapi_main.create_app())
    auth_headers, _ = _register_and_login_user(
        client,
        email="submit-unsupported@example.com",
        name="Submit Unsupported",
    )

    submit_eval_response = client.post(
        "/api/v2/eval/",
        json={
            "system_name": "submit-unsupported-system",
            "endpoint_url": "https://example.com/qa",
            "mode": "daat",
            "dataset_name": "non-existent-dataset",
            "async_mode": True,
        },
        headers=auth_headers,
    )
    assert submit_eval_response.status_code == 422, submit_eval_response.text
    assert "Unsupported DAAT dataset_name" in submit_eval_response.json()["detail"]

    eval_list_response = client.get("/api/v2/eval/", headers=auth_headers)
    assert eval_list_response.status_code == 200, eval_list_response.text
    assert eval_list_response.json()["total"] == 0

    _dispose_repository(supabase_manager.db)


def test_fastapi_results_preserve_zero_metrics(monkeypatch, tmp_path: Path) -> None:
    """Zero-valued retrieval metrics should remain numeric in API responses."""
    _set_sqlite_db(monkeypatch, tmp_path / "fastapi_zero_metrics.db")
    _set_fastapi_daat_status(
        monkeypatch,
        DaatDependencyStatus(
            ready=True,
            dataset_name="Metivta-Eval",
            message="LangSmith dataset 'Metivta-Eval' is available.",
        ),
    )

    client = TestClient(fastapi_main.create_app())
    auth_headers, user_id = _register_and_login_user(
        client,
        email="zero-metrics@example.com",
        name="Zero Metrics",
        organization="Metivta",
    )

    user = supabase_manager.db.get_user_by_id(user_id)
    assert user is not None
    evaluation = supabase_manager.db.create_evaluation(
        EvaluationCreateRequest(
            identity=EvaluationIdentity(user_id=user["id"]),
            descriptor=EvaluationDescriptor(
                system_name="zero-metric-system",
                system_version="1.0.0",
                author="Zero Metrics",
                endpoint_url="https://example.com/retrieve",
                mode="mteb",
                dataset_name="default",
            ),
            lifecycle=EvaluationLifecycle(status="completed", progress=100),
        )
    )
    supabase_manager.db.update_evaluation(
        evaluation["id"],
        scores={
            "ndcg_10": 0.0,
            "map_100": 0.0,
            "mrr_10": 0.0,
            "recall_100": 0.0,
            "precision_10": 0.0,
        },
        metrics={
            "ndcg_10": 0.0,
            "map_100": 0.0,
            "mrr_10": 0.0,
            "recall_100": 0.0,
            "precision_10": 0.0,
        },
    )

    results_response = client.get(
        f"/api/v2/eval/{evaluation['id']}/results",
        headers=auth_headers,
    )
    assert results_response.status_code == 200, results_response.text
    results_payload = results_response.json()
    assert results_payload["ndcg_10"] == 0.0
    assert results_payload["map_100"] == 0.0
    assert results_payload["mrr_10"] == 0.0
    assert results_payload["recall_100"] == 0.0
    assert results_payload["precision_10"] == 0.0

    leaderboard_response = client.get("/api/v2/leaderboard/")
    assert leaderboard_response.status_code == 200, leaderboard_response.text
    leaderboard_payload = leaderboard_response.json()
    assert leaderboard_payload["entries"][0]["ndcg_10"] == 0.0
    assert leaderboard_payload["entries"][0]["map_100"] == 0.0
    assert leaderboard_payload["entries"][0]["mrr_10"] == 0.0
