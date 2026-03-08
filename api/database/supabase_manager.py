"""Database manager backed by the canonical SQL repository."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC
from typing import Any
from uuid import UUID

from sqlalchemy import select

from metivta_eval.langsmith_utils import resolve_daat_dataset_name
from metivta_eval.persistence import DatabaseRepository
from metivta_eval.persistence.database import (
    EvaluationCreateRequest,
    EvaluationDescriptor,
    EvaluationIdentity,
    EvaluationLifecycle,
    EvaluationListRequest,
    EvaluationUpdateRequest,
    UserCreateRequest,
)
from metivta_eval.persistence.models import APIKey, User


@dataclass(frozen=True)
class LegacySubmissionRecord:
    """Parameters required to persist a legacy Flask submission."""

    api_key_id: str
    system_name: str
    author: str
    endpoint_url: str
    scores: dict[str, float]


def _coerce_uuid(value: str | UUID) -> UUID:
    """Normalize UUID-like values for direct ORM comparisons."""
    if isinstance(value, UUID):
        return value
    return UUID(value)


def _lookup_user_by_email(repo: DatabaseRepository, email: str) -> dict[str, Any] | None:
    """Look up a user by email without expanding the repository public surface."""
    normalized_email = email.lower()
    with repo.session_scope() as session:
        user = session.execute(
            select(User).where(User.email == normalized_email)
        ).scalar_one_or_none()
        if user is None:
            return None
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "organization": user.organization,
            "role": user.role,
            "created_at": user.created_at,
        }


class _RepositoryBacked:
    """Shared lazy repository holder for manager mixins."""

    def __init__(self) -> None:
        self._repo: DatabaseRepository | None = None

    @property
    def repo(self) -> DatabaseRepository:
        """Initialize repository lazily to avoid import-time DB failures."""
        if self._repo is None:
            self._repo = DatabaseRepository()
        return self._repo

    def reset_repository(self) -> None:
        """Dispose the current repository so tests can rebuild it with new settings."""
        if self._repo is None:
            return
        self._repo.engine.dispose()
        self._repo = None


class _APIKeyFacade(_RepositoryBacked):
    """API-key management operations."""

    def verify_api_key(self, api_key: str) -> dict[str, Any] | None:
        """Verify API key and return identity payload."""
        return self.repo.verify_api_key(api_key)

    def validate_api_key(self, api_key: str) -> dict[str, Any] | None:
        """Alias preserved for Flask compatibility."""
        return self.verify_api_key(api_key)

    def check_rate_limit(self, key_id: str, limit: int | None = None) -> tuple[bool, int]:
        """Check rate limit usage for the key."""
        return self.repo.check_rate_limit(key_id, limit)

    def create_user_with_api_key(
        self,
        email: str,
        name: str,
        organization: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a user and an API key for `/register` compatibility."""
        del description
        user = _lookup_user_by_email(self.repo, email)
        if user is None:
            user = self.repo.create_user(
                UserCreateRequest(
                    email=email,
                    name=name,
                    organization=organization,
                    password=secrets.token_urlsafe(24),
                )
            )

        key = self.repo.create_api_key(
            user_id=user["id"],
            name="default",
            scopes=["eval:read", "eval:write", "leaderboard:read"],
            expires_in_days=None,
        )
        return {"api_key": key["key"], "key_prefix": key["key_prefix"]}

    def log_usage(self, key_id: str, endpoint: str, status_code: int) -> None:
        """Log endpoint usage."""
        self.repo.log_usage(endpoint=endpoint, status_code=status_code, api_key_id=key_id)

    def create_api_key(self, user_name: str, user_email: str) -> str:
        """Legacy utility API key generator."""
        user = _lookup_user_by_email(self.repo, user_email)
        if user is None:
            user = self.repo.create_user(
                UserCreateRequest(
                    email=user_email,
                    name=user_name,
                    organization=None,
                    password=secrets.token_urlsafe(24),
                )
            )
        key = self.repo.create_api_key(
            user_id=user["id"],
            name="legacy",
            scopes=["eval:read", "eval:write"],
            expires_in_days=None,
        )
        return str(key["key"])

    def create_scoped_api_key(
        self,
        user_id: str,
        name: str,
        scopes: list[str],
        expires_in_days: int | None,
    ) -> dict[str, Any]:
        """Create API key for a user."""
        return self.repo.create_api_key(
            user_id=user_id,
            name=name,
            scopes=scopes,
            expires_in_days=expires_in_days,
        )

    def list_user_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        """List all API keys owned by user."""
        return self.repo.list_api_keys(user_id)

    def revoke_user_api_key(self, user_id: str, key_id: str) -> bool:
        """Revoke a user API key."""
        return self.repo.revoke_api_key(user_id, key_id)


class _SubmissionFacade(_RepositoryBacked):
    """Legacy submission compatibility operations."""

    def save_submission(self, submission: LegacySubmissionRecord) -> str:
        """Persist a completed legacy `/submit` DAAT evaluation."""
        user_record = None
        api_key_uuid = _coerce_uuid(submission.api_key_id)
        with self.repo.session_scope() as session:
            key_row = session.execute(
                select(APIKey).where(APIKey.id == api_key_uuid)
            ).scalar_one_or_none()
            if key_row is not None:
                user_row = session.execute(
                    select(User).where(User.id == key_row.user_id)
                ).scalar_one_or_none()
                if user_row is not None:
                    user_record = {"id": user_row.id}

        user_id = user_record["id"] if user_record is not None else submission.api_key_id
        created = self.repo.create_evaluation_run(
            EvaluationCreateRequest(
                identity=EvaluationIdentity(user_id=user_id, api_key_id=submission.api_key_id),
                descriptor=EvaluationDescriptor(
                    system_name=submission.system_name,
                    system_version=None,
                    author=submission.author,
                    endpoint_url=submission.endpoint_url,
                    mode="daat",
                    dataset_name=resolve_daat_dataset_name(),
                ),
                lifecycle=EvaluationLifecycle(status="running", progress=40),
            )
        )
        updated = self.repo.update_evaluation_run(
            created["id"],
            EvaluationUpdateRequest(
                status="completed",
                progress=100,
                scores=submission.scores,
                metrics=submission.scores,
            ),
        )
        if updated is None:
            return created["id"]
        return updated["id"]


class _AuthFacade(_RepositoryBacked):
    """User and session operations."""

    def register_user(
        self,
        email: str,
        name: str,
        organization: str | None,
        password: str,
    ) -> dict[str, Any]:
        """Create a user account for the FastAPI auth router."""
        return self.repo.create_user(
            UserCreateRequest(
                email=email,
                name=name,
                organization=organization,
                password=password,
            )
        )

    def login_user(self, email: str, password: str) -> dict[str, Any] | None:
        """Validate credentials and create session tokens."""
        user = self.repo.verify_user_credentials(email=email, password=password)
        if user is None:
            return None
        tokens = self.repo.create_session_pair(user["id"])
        return {"user": user, "tokens": tokens}

    def refresh_user_session(self, refresh_token: str) -> dict[str, Any] | None:
        """Rotate refresh token and return new token pair."""
        return self.repo.rotate_refresh_token(refresh_token)

    def get_user_from_access_token(self, token: str) -> dict[str, Any] | None:
        """Resolve user from bearer access token."""
        return self.repo.validate_access_token(token)

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Get user by id."""
        return self.repo.get_user_by_id(user_id)


class _EvaluationFacade(_RepositoryBacked):
    """Evaluation lifecycle operations."""

    def create_evaluation(self, request: EvaluationCreateRequest) -> dict[str, Any]:
        """Create an evaluation record."""
        return self.repo.create_evaluation_run(request)

    def update_evaluation(self, evaluation_id: str, **kwargs: Any) -> dict[str, Any] | None:
        """Update an evaluation record."""
        return self.repo.update_evaluation_run(evaluation_id, EvaluationUpdateRequest(**kwargs))

    def list_evaluations(self, request: EvaluationListRequest) -> tuple[list[dict[str, Any]], int]:
        """List evaluation records."""
        return self.repo.list_evaluation_runs(request)

    def get_evaluation(
        self,
        evaluation_id: str,
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Get one evaluation record."""
        return self.repo.get_evaluation_run(evaluation_id, user_id)

    def cancel_evaluation(self, evaluation_id: str, user_id: str) -> dict[str, Any] | None:
        """Cancel an evaluation record."""
        return self.repo.cancel_evaluation_run(evaluation_id, user_id)


class _LeaderboardFacade(_RepositoryBacked):
    """Leaderboard and ranking operations."""

    def get_leaderboard(self) -> list[dict[str, Any]]:
        """Return leaderboard entries for compatibility views."""
        entries, _ = self.repo.get_leaderboard(mode="all", page=1, page_size=500)
        return entries

    def get_leaderboard_data(self) -> list[dict[str, Any]]:
        """Return legacy leaderboard payload expected by Flask templates."""
        entries, _ = self.repo.get_leaderboard(mode="all", page=1, page_size=500)
        formatted: list[dict[str, Any]] = []
        for entry in entries:
            scores: dict[str, float] = {}
            if entry.get("daat_score") is not None:
                scores["daat_score"] = float(entry["daat_score"])
            if entry.get("ndcg_10") is not None:
                scores["ndcg_10"] = float(entry["ndcg_10"])
            if entry.get("map_100") is not None:
                scores["map_100"] = float(entry["map_100"])
            if entry.get("mrr_10") is not None:
                scores["mrr_10"] = float(entry["mrr_10"])

            formatted.append(
                {
                    "system": entry["system_name"],
                    "author": entry["author"],
                    "timestamp": entry["submitted_at"].astimezone(UTC).isoformat(),
                    "scores": scores,
                }
            )
        return formatted

    def get_leaderboard_entries(
        self,
        mode: str,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get leaderboard rows."""
        return self.repo.get_leaderboard(mode=mode, page=page, page_size=page_size)

    def get_leaderboard_stats(self) -> dict[str, Any]:
        """Get aggregate leaderboard stats."""
        return self.repo.get_leaderboard_stats()


class DatabaseManager(
    _APIKeyFacade,
    _SubmissionFacade,
    _AuthFacade,
    _EvaluationFacade,
    _LeaderboardFacade,
):
    """High-level database façade for API services."""


db = DatabaseManager()
