"""Verify Docker deployment failure modes and recovery behavior."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NamedTuple
from uuid import uuid4

import requests


class FaultVerifierConfig(NamedTuple):
    """Configuration for the Docker fault verifier."""

    repo_root: Path
    gateway_base: str
    flask_base: str
    timeout_seconds: int
    poll_interval: float
    build_images: bool


class DockerFaultVerifier:
    """Run deployment fault checks against the local Docker stack."""

    def __init__(self, config: FaultVerifierConfig) -> None:
        """Store verifier configuration."""
        self.config = config

    def run(self) -> list[str]:
        """Execute all fault scenarios and restore a healthy stack afterwards."""
        results: list[str] = []
        try:
            print("[step 1] Restoring healthy demo stack")
            self.restore_demo_stack(build=self.config.build_images)
            print("[step 2] Verifying dataset misconfiguration behavior")
            results.append(self._verify_dataset_failure_mode())

            print("[step 3] Restoring healthy demo stack")
            self.restore_demo_stack()
            print("[step 4] Verifying Redis outage behavior")
            results.append(self._verify_redis_outage())

            print("[step 5] Restoring healthy demo stack")
            self.restore_demo_stack()
            print("[step 6] Verifying Postgres outage behavior")
            results.append(self._verify_postgres_outage())

            print("[step 7] Restoring healthy demo stack")
            self.restore_demo_stack()
            print("[step 8] Verifying invalid endpoint behavior")
            results.append(self._verify_invalid_endpoint_behavior())
        finally:
            print("[final] Restoring healthy demo stack")
            self.restore_demo_stack()
        return results

    def restore_demo_stack(self, *, build: bool = False) -> None:
        """Recreate the healthy demo stack and wait for seeded verification."""
        self._compose_down()
        env_overrides = {
            "METIVTA_DATASET_MAX_EXAMPLES": os.getenv("METIVTA_DATASET_MAX_EXAMPLES", "2"),
        }
        self._compose_up(
            profiles=("legacy", "demo"),
            build=build,
            force_recreate=True,
            env_overrides=env_overrides,
        )
        self._wait_for_http_ok(f"{self.config.gateway_base}/health")
        self._wait_for_http_ok(f"{self.config.flask_base}/")
        self._wait_for_json(
            f"{self.config.gateway_base}/ready",
            lambda payload: bool(payload.get("ready")),
            description="gateway readiness to become healthy",
        )
        self._wait_for_demo_seeder_success()

    def _verify_dataset_failure_mode(self) -> str:
        """Verify dataset misconfiguration degrades cleanly."""
        self._compose_down()
        env_overrides = {
            "METIVTA_DATASET_LOCAL_PATH": "/app/missing-dataset",
            "METIVTA_DATASET_FILES_QUESTIONS": "missing.json",
            "METIVTA_DATASET_FILES_QUESTIONS_ONLY": "missing-questions.json",
        }
        self._compose_up(
            profiles=("legacy",),
            force_recreate=True,
            env_overrides=env_overrides,
        )
        self._wait_for_http_ok(f"{self.config.gateway_base}/health")
        self._wait_for_http_ok(f"{self.config.flask_base}/")

        ready_payload = self._wait_for_json(
            f"{self.config.gateway_base}/ready",
            lambda payload: (
                payload.get("ready") is False
                and payload.get("checks", {}).get("daat_dataset") is False
            ),
            description="dataset readiness failure",
        )
        details = ready_payload.get("details", {})
        dataset_detail = str(details.get("daat_dataset", ""))
        if "missing.json" not in dataset_detail:
            raise RuntimeError(f"Unexpected DAAT dataset failure detail: {ready_payload}")

        dataset_info = requests.get(f"{self.config.flask_base}/dataset-info", timeout=30)
        self._assert_status_code(dataset_info, 503, "dataset-info with missing dataset")

        validate_endpoint = requests.post(
            f"{self.config.flask_base}/validate-endpoint",
            json={"endpoint_url": "https://example.com/answer"},
            timeout=30,
        )
        self._assert_status_code(validate_endpoint, 503, "validate-endpoint with missing dataset")

        fastapi_headers = self._register_and_login_fastapi("dataset-failure")
        submit_response = requests.post(
            f"{self.config.gateway_base}/api/v2/eval/",
            json={
                "system_name": "dataset-failure-system",
                "endpoint_url": "https://example.com/answer",
                "mode": "daat",
                "async_mode": False,
            },
            headers=fastapi_headers,
            timeout=30,
        )
        self._assert_status_code(submit_response, 503, "FastAPI submission with missing dataset")

        legacy_key = self._register_legacy_user("dataset-failure")
        legacy_submit = requests.post(
            f"{self.config.flask_base}/submit",
            json={
                "author": "Dataset Failure",
                "system_name": "dataset-failure-system",
                "endpoint_url": "https://example.com/answer",
            },
            headers={"Authorization": f"Bearer {legacy_key}"},
            timeout=30,
        )
        self._assert_status_code(legacy_submit, 503, "legacy submit with missing dataset")
        return "Dataset misconfiguration fails fast across readiness and submission routes."

    def _verify_redis_outage(self) -> str:
        """Verify Redis outages surface through readiness and async submission."""
        self._compose_service("stop", "redis")
        ready_payload = self._wait_for_json(
            f"{self.config.gateway_base}/ready",
            lambda payload: (
                payload.get("ready") is False and payload.get("checks", {}).get("redis") is False
            ),
            description="redis readiness failure",
        )
        if ready_payload.get("checks", {}).get("database") is not True:
            raise RuntimeError(f"Redis outage unexpectedly broke database check: {ready_payload}")

        legacy_key = self._register_legacy_user("redis-outage")
        async_submit = requests.post(
            f"{self.config.flask_base}/submit?async=true",
            json={
                "author": "Redis Outage",
                "system_name": "redis-outage-system",
                "endpoint_url": "http://demo-answer:5001/answer",
            },
            headers={"Authorization": f"Bearer {legacy_key}"},
            timeout=30,
        )
        self._assert_status_code(async_submit, 503, "legacy async submit during redis outage")
        response_payload = async_submit.json()
        if response_payload.get("error") != "Async evaluation backend unavailable":
            raise RuntimeError(f"Unexpected async outage payload: {response_payload}")

        self._compose_service("start", "redis")
        self._wait_for_json(
            f"{self.config.gateway_base}/ready",
            lambda payload: bool(payload.get("ready")),
            description="redis recovery",
        )
        return "Redis outage is visible in readiness and blocks legacy async submission cleanly."

    def _verify_postgres_outage(self) -> str:
        """Verify database outages surface through readiness and auth routes."""
        local_password = _resolve_local_demo_password("postgres-outage")
        self._compose_service("stop", "postgres")
        ready_payload = self._wait_for_json(
            f"{self.config.gateway_base}/ready",
            lambda payload: (
                payload.get("ready") is False and payload.get("checks", {}).get("database") is False
            ),
            description="database readiness failure",
        )
        if ready_payload.get("checks", {}).get("redis") is not True:
            raise RuntimeError(f"Database outage unexpectedly broke redis check: {ready_payload}")

        register_response = requests.post(
            f"{self.config.gateway_base}/api/v2/auth/register",
            json={
                "email": f"postgres-outage-{uuid4().hex[:8]}@example.com",
                "name": "Postgres Outage",
                "password": local_password,
            },
            timeout=30,
        )
        if register_response.status_code < 500:
            raise RuntimeError(
                "FastAPI register unexpectedly succeeded during database outage: "
                f"{register_response.status_code} {register_response.text}"
            )

        self._compose_service("start", "postgres")
        self._wait_for_json(
            f"{self.config.gateway_base}/ready",
            lambda payload: bool(payload.get("ready")),
            description="database recovery",
        )
        return "Postgres outage is visible in readiness and prevents new auth writes."

    def _verify_invalid_endpoint_behavior(self) -> str:
        """Verify bad user endpoints do not crash the evaluation harness."""
        validate_endpoint = requests.post(
            f"{self.config.flask_base}/validate-endpoint",
            json={"endpoint_url": "http://demo-answer:5001/health"},
            timeout=30,
        )
        self._assert_status_code(validate_endpoint, 400, "validate-endpoint on invalid contract")
        validate_payload = validate_endpoint.json()
        if validate_payload.get("valid") is not False:
            raise RuntimeError(f"Unexpected invalid endpoint payload: {validate_payload}")

        fastapi_headers = self._register_and_login_fastapi("bad-endpoint")
        eval_response = requests.post(
            f"{self.config.gateway_base}/api/v2/eval/",
            json={
                "system_name": "bad-endpoint-system",
                "endpoint_url": "http://demo-answer:5001/health",
                "mode": "daat",
                "async_mode": False,
            },
            headers=fastapi_headers,
            timeout=max(self.config.timeout_seconds, 60),
        )
        eval_response.raise_for_status()
        eval_payload = eval_response.json()
        if eval_payload.get("status") != "completed":
            raise RuntimeError(f"Invalid endpoint evaluation did not complete: {eval_payload}")

        results_response = requests.get(
            f"{self.config.gateway_base}/api/v2/eval/{eval_payload['id']}/results",
            headers=fastapi_headers,
            timeout=30,
        )
        results_response.raise_for_status()
        results_payload = results_response.json()
        if results_payload.get("status") != "completed":
            raise RuntimeError(f"Invalid endpoint results were not completed: {results_payload}")
        if results_payload.get("metrics") is None:
            raise RuntimeError(f"Invalid endpoint results lacked metrics: {results_payload}")
        return "Invalid user endpoints are rejected by validation and do not crash live evaluation."

    def _compose_up(
        self,
        *,
        profiles: tuple[str, ...],
        build: bool = False,
        force_recreate: bool = False,
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        """Start Docker Compose services with the given profiles."""
        args = []
        for profile in profiles:
            args.extend(["--profile", profile])
        args.extend(["up", "-d"])
        if build:
            args.append("--build")
        if force_recreate:
            args.append("--force-recreate")
        self._run_compose(*args, env_overrides=env_overrides)

    def _compose_down(self) -> None:
        """Stop the Docker Compose stack without deleting volumes."""
        self._run_compose("--profile", "legacy", "--profile", "demo", "down")

    def _compose_service(self, action: str, service: str) -> None:
        """Run a service-level Docker Compose action."""
        self._run_compose(action, service)

    def _run_compose(
        self,
        *args: str,
        env_overrides: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run one Docker Compose command in the repository root."""
        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)
        command = ["docker", "compose", *args]
        print(f"$ {' '.join(command)}")
        completed = subprocess.run(
            command,
            cwd=self.config.repo_root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Docker Compose command failed: {' '.join(command)}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        return completed

    def _wait_for_demo_seeder_success(self) -> None:
        """Wait for the one-shot demo seeder to exit successfully."""
        deadline = time.monotonic() + self.config.timeout_seconds
        last_state = "not-created"
        while time.monotonic() < deadline:
            completed = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "-f",
                    "{{.State.Status}} {{.State.ExitCode}}",
                    "metivta-demo-seeder",
                ],
                cwd=self.config.repo_root,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode == 0:
                state_parts = completed.stdout.strip().split()
                if len(state_parts) == 2:
                    status, exit_code = state_parts
                    last_state = completed.stdout.strip()
                    if status == "exited" and exit_code == "0":
                        return
                    if status == "exited":
                        raise RuntimeError(
                            f"Demo seeder failed with state {completed.stdout.strip()}"
                        )
            time.sleep(self.config.poll_interval)
        raise RuntimeError(f"Timed out waiting for demo seeder: {last_state}")

    def _wait_for_http_ok(self, url: str) -> None:
        """Wait for a simple HTTP 2xx/3xx response."""
        self._wait_for_json_or_status(
            url,
            lambda response: response.status_code < 400,
            description=f"HTTP success from {url}",
        )

    def _wait_for_json(
        self,
        url: str,
        predicate: Any,
        *,
        description: str,
    ) -> dict[str, Any]:
        """Wait for a JSON response that satisfies the given predicate."""
        response = self._wait_for_json_or_status(
            url,
            lambda candidate: (
                candidate.status_code < 500 and self._json_predicate(candidate, predicate)
            ),
            description=description,
        )
        return response.json()

    @staticmethod
    def _json_predicate(response: requests.Response, predicate: Any) -> bool:
        """Apply a JSON predicate while treating invalid JSON as a failed poll."""
        try:
            payload = response.json()
        except ValueError:
            return False
        return bool(predicate(payload))

    def _wait_for_json_or_status(
        self,
        url: str,
        predicate: Any,
        *,
        description: str,
    ) -> requests.Response:
        """Poll a URL until the response satisfies the provided predicate."""
        deadline = time.monotonic() + self.config.timeout_seconds
        last_error = "no response"
        while time.monotonic() < deadline:
            try:
                response = requests.get(url, timeout=5)
                if predicate(response):
                    return response
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            except requests.RequestException as exc:
                last_error = str(exc)
            time.sleep(self.config.poll_interval)
        raise RuntimeError(f"Timed out waiting for {description}: {last_error}")

    def _register_and_login_fastapi(self, scenario: str) -> dict[str, str]:
        """Register one FastAPI user and return bearer auth headers."""
        suffix = uuid4().hex[:8]
        local_password = _resolve_local_demo_password(scenario)
        email = f"{scenario}-{suffix}@example.com"
        register_response = requests.post(
            f"{self.config.gateway_base}/api/v2/auth/register",
            json={
                "email": email,
                "name": f"{scenario}-{suffix}",
                "password": local_password,
            },
            timeout=30,
        )
        register_response.raise_for_status()

        login_response = requests.post(
            f"{self.config.gateway_base}/api/v2/auth/login",
            json={"email": email, "password": local_password},
            timeout=30,
        )
        login_response.raise_for_status()
        access_token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {access_token}"}

    def _register_legacy_user(self, scenario: str) -> str:
        """Register one legacy Flask user and return the issued API key."""
        suffix = uuid4().hex[:8]
        response = requests.post(
            f"{self.config.flask_base}/register",
            json={
                "email": f"{scenario}-{suffix}@example.com",
                "name": f"{scenario}-{suffix}",
            },
            timeout=30,
        )
        response.raise_for_status()
        return str(response.json()["api_key"])

    @staticmethod
    def _assert_status_code(
        response: requests.Response,
        expected_status: int,
        description: str,
    ) -> None:
        """Assert a response status code matches the expected value."""
        if response.status_code != expected_status:
            raise RuntimeError(
                f"Unexpected status for {description}: {response.status_code} {response.text}"
            )


def _load_config() -> FaultVerifierConfig:
    """Load the verifier configuration from the environment."""
    repo_root = Path(__file__).resolve().parents[3]
    return FaultVerifierConfig(
        repo_root=repo_root,
        gateway_base=os.getenv("HOST_GATEWAY_URL", "http://localhost:18000"),
        flask_base=os.getenv("HOST_FLASK_URL", "http://localhost:18080"),
        timeout_seconds=int(os.getenv("DOCKER_FAULT_TIMEOUT_SECONDS", "240")),
        poll_interval=float(os.getenv("DOCKER_FAULT_POLL_INTERVAL_SECONDS", "2")),
        build_images=os.getenv("DOCKER_FAULT_BUILD_IMAGES", "true").lower()
        not in {"0", "false", "no"},
    )


def _resolve_local_demo_password(scenario: str) -> str:
    """Return a local password override or generated fallback for test flows."""
    configured = os.getenv("METIVTA_DEMO_PASSWORD", "").strip()
    if configured:
        return configured
    suffix = scenario.replace(" ", "-").lower()
    return f"Demo-{suffix}-{uuid4().hex[:6]}!"


def main() -> int:
    """Run the Docker fault verifier and print a concise summary."""
    verifier = DockerFaultVerifier(_load_config())
    results = verifier.run()
    print("Docker fault verification passed.")
    for result in results:
        print(f"- {result}")
    print("Healthy demo stack restored at the end of the run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
