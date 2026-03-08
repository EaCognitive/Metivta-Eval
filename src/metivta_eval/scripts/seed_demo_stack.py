"""Seed the Docker demo stack and verify end-to-end surfaces."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from html import unescape
from typing import Any
from uuid import uuid4

import requests
from langsmith import Client

from metivta_eval.langsmith_utils import resolve_daat_dataset_name
from metivta_eval.scripts.upload_dataset import upload_to_langsmith


@dataclass(frozen=True, slots=True)
class DemoConfig:
    """Environment-driven configuration for the seeded demo verifier."""

    gateway_base: str
    flask_base: str
    demo_endpoint_url: str
    demo_answer_health_url: str
    timeout_seconds: int
    poll_interval: float
    suffix: str


def main() -> int:
    """Seed the running stack and verify gateway, worker, and dashboards."""
    config = _load_demo_config()

    wait_for_http_ok(f"{config.gateway_base}/health", config.timeout_seconds)
    wait_for_http_ok(f"{config.gateway_base}/ready", config.timeout_seconds)
    wait_for_http_ok(f"{config.flask_base}/", config.timeout_seconds)
    verify_scalar_docs(config.gateway_base)
    verify_openapi_document(config.gateway_base)
    wait_for_http_ok(config.demo_answer_health_url, config.timeout_seconds)

    fastapi_email = f"demo-fastapi-{config.suffix}@example.com"
    fastapi_password = _resolve_demo_password(config.suffix)
    fastapi_headers = register_and_login_fastapi(
        gateway_base=config.gateway_base,
        email=fastapi_email,
        password=fastapi_password,
        suffix=config.suffix,
    )

    fastapi_eval_id = submit_fastapi_evaluation(
        gateway_base=config.gateway_base,
        endpoint_url=config.demo_endpoint_url,
        auth_headers=fastapi_headers,
        suffix=config.suffix,
        timeout_seconds=config.timeout_seconds,
    )
    fastapi_results = fetch_fastapi_results(
        gateway_base=config.gateway_base,
        auth_headers=fastapi_headers,
        evaluation_id=fastapi_eval_id,
    )
    assert_fastapi_results(fastapi_results)

    legacy_api_key = register_legacy_user(flask_base=config.flask_base, suffix=config.suffix)
    legacy_eval_id = submit_legacy_async_evaluation(
        flask_base=config.flask_base,
        api_key=legacy_api_key,
        endpoint_url=config.demo_endpoint_url,
        suffix=config.suffix,
    )
    wait_for_legacy_success(
        flask_base=config.flask_base,
        evaluation_id=legacy_eval_id,
        timeout_seconds=config.timeout_seconds,
        poll_interval=config.poll_interval,
    )

    _verify_leaderboard_surfaces(
        config=config,
        fastapi_headers=fastapi_headers,
        expected_systems={
            f"demo-fastapi-{config.suffix}",
            f"demo-legacy-{config.suffix}",
        },
    )
    integration_checks = verify_optional_integrations()

    print("Demo stack seeded successfully.")
    print(f"FastAPI evaluation: {fastapi_eval_id}")
    print(f"Legacy async evaluation: {legacy_eval_id}")
    print("Verified optional integrations:")
    for item in integration_checks:
        print(f"  - {item}")
    print("Host URLs:")
    print(f"  Gateway: {os.getenv('HOST_GATEWAY_URL', 'http://localhost:8000')}")
    print(
        f"  FastAPI Docs: {os.getenv('HOST_FASTAPI_DOCS_URL', 'http://localhost:8000/api/v2/docs')}"
    )
    print(
        "  Flask Leaderboard: "
        f"{os.getenv('HOST_FLASK_LEADERBOARD_URL', 'http://localhost:8080/leaderboard')}"
    )
    return 0


def _load_demo_config() -> DemoConfig:
    """Load demo verifier configuration from the environment."""
    return DemoConfig(
        gateway_base=os.getenv("DEMO_GATEWAY_URL", "http://gateway:8000"),
        flask_base=os.getenv("DEMO_FLASK_URL", "http://flask:8080"),
        demo_endpoint_url=os.getenv("DEMO_ANSWER_URL", "http://demo-answer:5001/answer"),
        demo_answer_health_url=os.getenv(
            "DEMO_ANSWER_HEALTH_URL",
            "http://demo-answer:5001/health",
        ),
        timeout_seconds=int(os.getenv("DEMO_WAIT_TIMEOUT_SECONDS", "180")),
        poll_interval=float(os.getenv("DEMO_POLL_INTERVAL_SECONDS", "2")),
        suffix=uuid4().hex[:8],
    )


def _resolve_demo_password(suffix: str) -> str:
    """Return a demo password from env or a generated local-only fallback."""
    configured = os.getenv("METIVTA_DEMO_PASSWORD", "").strip()
    if configured:
        return configured
    return f"Demo-{suffix}-Pass!"


def _verify_leaderboard_surfaces(
    *,
    config: DemoConfig,
    fastapi_headers: dict[str, str],
    expected_systems: set[str],
) -> None:
    """Verify the FastAPI and Flask leaderboard surfaces."""
    fastapi_leaderboard = requests.get(
        f"{config.gateway_base}/api/v2/leaderboard/",
        headers=fastapi_headers,
        timeout=30,
    )
    fastapi_leaderboard.raise_for_status()
    fastapi_entries = fastapi_leaderboard.json().get("entries", [])
    assert_contains_system(
        entries=fastapi_entries,
        expected_systems=expected_systems,
        field="system_name",
    )

    flask_leaderboard_json = requests.get(
        f"{config.flask_base}/leaderboard",
        headers={"Accept": "application/json"},
        timeout=30,
    )
    flask_leaderboard_json.raise_for_status()
    flask_submissions = flask_leaderboard_json.json().get("submissions", [])
    assert_contains_system(
        entries=flask_submissions,
        expected_systems=expected_systems,
        field="system",
    )

    flask_leaderboard_html = requests.get(f"{config.flask_base}/leaderboard", timeout=30)
    flask_leaderboard_html.raise_for_status()
    assert_dashboard_html(flask_leaderboard_html.text)


def wait_for_http_ok(url: str, timeout_seconds: int) -> None:
    """Wait for an HTTP endpoint to return a successful response."""
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code < 400:
                return
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def verify_scalar_docs(gateway_base: str) -> None:
    """Verify the hosted Scalar API reference renders the expected configuration."""
    response = requests.get(f"{gateway_base}/api/v2/docs", timeout=30)
    response.raise_for_status()
    html_body = unescape(response.text)
    required_markers = (
        "@scalar/api-reference",
        '"showSidebar": true',
        '"defaultOpenFirstTag": true',
        '"defaultOpenAllTags": true',
        '"showDeveloperTools": "never"',
    )
    for marker in required_markers:
        if marker not in html_body:
            raise RuntimeError(f"Scalar docs did not contain marker: {marker}")


def verify_openapi_document(gateway_base: str) -> None:
    """Verify the live OpenAPI document matches the public API surface."""
    response = requests.get(f"{gateway_base}/api/v2/openapi.json", timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("openapi") != "3.1.0":
        raise RuntimeError(f"Unexpected OpenAPI version: {payload.get('openapi')}")

    info = payload.get("info", {})
    title = str(info.get("title", ""))
    description = str(info.get("description", ""))
    if title != "MetivtaEval API":
        raise RuntimeError(f"Unexpected API title: {title}")
    required_description_markers = (
        "## MetivtaEval - AI Benchmarking Platform",
        "DAAT Dataset",
        "LangSmith",
        "WebSocket Events",
    )
    for marker in required_description_markers:
        if marker not in description:
            raise RuntimeError(f"OpenAPI description did not contain marker: {marker}")


def register_and_login_fastapi(
    gateway_base: str,
    email: str,
    password: str,
    suffix: str,
) -> dict[str, str]:
    """Register and login a FastAPI user through the gateway."""
    register_payload = {
        "email": email,
        "name": f"Demo FastAPI {suffix}",
        "password": password,
        "organization": "Metivta Demo",
    }
    register_response = requests.post(
        f"{gateway_base}/api/v2/auth/register",
        json=register_payload,
        timeout=30,
    )
    register_response.raise_for_status()

    login_response = requests.post(
        f"{gateway_base}/api/v2/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    login_response.raise_for_status()
    access_token = login_response.json()["access_token"]

    api_key_response = requests.post(
        f"{gateway_base}/api/v2/auth/api-keys",
        json={"name": f"demo-key-{suffix}", "scopes": ["eval:read", "eval:write"]},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    api_key_response.raise_for_status()
    return {"Authorization": f"Bearer {access_token}"}


def submit_fastapi_evaluation(
    gateway_base: str,
    endpoint_url: str,
    auth_headers: dict[str, str],
    suffix: str,
    timeout_seconds: int,
) -> str:
    """Submit one synchronous FastAPI evaluation via the gateway."""
    payload = {
        "system_name": f"demo-fastapi-{suffix}",
        "system_version": "docker-demo",
        "endpoint_url": endpoint_url,
        "mode": "daat",
        "dataset_name": "default",
        "async_mode": False,
    }
    response = requests.post(
        f"{gateway_base}/api/v2/eval/",
        json=payload,
        headers=auth_headers,
        timeout=max(timeout_seconds, 60),
    )
    response.raise_for_status()
    body = response.json()
    if body.get("status") != "completed":
        raise RuntimeError(f"FastAPI evaluation did not complete: {body}")
    return str(body["id"])


def fetch_fastapi_results(
    gateway_base: str,
    auth_headers: dict[str, str],
    evaluation_id: str,
) -> dict[str, Any]:
    """Fetch one completed FastAPI evaluation result payload."""
    response = requests.get(
        f"{gateway_base}/api/v2/eval/{evaluation_id}/results",
        headers=auth_headers,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def assert_fastapi_results(results_payload: dict[str, Any]) -> None:
    """Verify the FastAPI evaluation produced the expected score surfaces."""
    if results_payload.get("status") != "completed":
        raise RuntimeError(f"FastAPI results were not completed: {results_payload}")
    if results_payload.get("overall_score") is None:
        raise RuntimeError(f"FastAPI results did not include overall_score: {results_payload}")
    if results_payload.get("daat_score") is None:
        raise RuntimeError(f"FastAPI results did not include daat_score: {results_payload}")
    metrics = results_payload.get("metrics")
    if not isinstance(metrics, dict):
        raise RuntimeError(f"FastAPI results did not include metrics: {results_payload}")
    if "daat_score" not in metrics:
        raise RuntimeError(f"FastAPI metrics did not include daat_score: {results_payload}")

    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        for key in ("scholarly_format", "correctness"):
            if key not in metrics:
                raise RuntimeError(
                    f"FastAPI metrics did not include {key} with Anthropic configured: "
                    f"{results_payload}"
                )

    if os.getenv("BROWSERLESS_TOKEN", "").strip() and "web_validation" not in metrics:
        raise RuntimeError(
            "FastAPI metrics did not include web_validation with Browserless configured: "
            f"{results_payload}"
        )


def register_legacy_user(flask_base: str, suffix: str) -> str:
    """Register one legacy Flask user and return the API key."""
    response = requests.post(
        f"{flask_base}/register",
        json={
            "email": f"demo-legacy-{suffix}@example.com",
            "name": f"Demo Legacy {suffix}",
            "organization": "Metivta Demo",
        },
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["api_key"])


def submit_legacy_async_evaluation(
    flask_base: str,
    api_key: str,
    endpoint_url: str,
    suffix: str,
) -> str:
    """Submit one legacy async evaluation through the Flask compatibility API."""
    response = requests.post(
        f"{flask_base}/submit?async=true",
        json={
            "author": f"Demo Legacy {suffix}",
            "system_name": f"demo-legacy-{suffix}",
            "endpoint_url": endpoint_url,
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["task_id"])


def wait_for_legacy_success(
    flask_base: str,
    evaluation_id: str,
    timeout_seconds: int,
    poll_interval: float,
) -> None:
    """Poll the legacy status endpoint until evaluation completes."""
    deadline = time.monotonic() + timeout_seconds
    last_payload: dict[str, object] | None = None
    while time.monotonic() < deadline:
        response = requests.get(f"{flask_base}/status/{evaluation_id}", timeout=30)
        response.raise_for_status()
        payload = response.json()
        last_payload = payload
        state = payload.get("state")
        if state == "SUCCESS":
            return
        if state == "FAILURE":
            raise RuntimeError(f"Legacy async evaluation failed: {payload}")
        time.sleep(poll_interval)
    raise RuntimeError(f"Legacy async evaluation timed out: {last_payload}")


def assert_contains_system(
    entries: list[dict[str, object]],
    expected_systems: set[str],
    field: str,
) -> None:
    """Ensure all expected system names appear in a leaderboard payload."""
    actual = {str(item.get(field, "")) for item in entries}
    missing = sorted(expected_systems - actual)
    if missing:
        raise RuntimeError(f"Missing systems in leaderboard payload: {missing}")


def assert_dashboard_html(html_body: str) -> None:
    """Verify the public leaderboard page shell rendered successfully."""
    required_markers = (
        "Leaderboard - Metivta Eval",
        "Loading leaderboard data",
        "loadLeaderboard",
        "initialSubmissions",
    )
    for marker in required_markers:
        if marker not in html_body:
            raise RuntimeError(f"Leaderboard HTML did not contain marker: {marker}")


def verify_optional_integrations() -> list[str]:
    """Verify optional external integrations when credentials are configured."""
    results: list[str] = []
    if _langsmith_configured():
        dataset_name = resolve_daat_dataset_name()
        dataset_id = upload_to_langsmith(dataset_name=dataset_name)
        dataset = Client().read_dataset(dataset_name=dataset_name)
        if str(dataset.id) != dataset_id:
            raise RuntimeError(
                f"LangSmith dataset mismatch: uploaded {dataset_id}, loaded {dataset.id}"
            )
        results.append(f"LangSmith dataset sync verified for {dataset_name}.")
    else:
        results.append("LangSmith dataset sync skipped because no API key is configured.")

    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        results.append("Anthropic-backed evaluators verified through FastAPI DAAT results.")
    else:
        results.append("Anthropic-backed evaluators skipped because no API key is configured.")

    if os.getenv("BROWSERLESS_TOKEN", "").strip():
        results.append("Browserless-backed web validation verified through FastAPI DAAT results.")
    else:
        results.append("Browserless-backed web validation skipped because no token is configured.")
    return results


def _langsmith_configured() -> bool:
    """Return whether LangSmith credentials are available for sync checks."""
    return bool(
        os.getenv("LANGSMITH_API_KEY", "").strip() or os.getenv("LANGCHAIN_API_KEY", "").strip()
    )


if __name__ == "__main__":
    sys.exit(main())
