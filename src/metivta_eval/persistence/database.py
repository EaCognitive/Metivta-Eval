"""Canonical SQL repository used by Flask and FastAPI services."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import create_engine, distinct, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.functions import count

from metivta_eval.config.toml_config import config

from .models import APIKey, Base, EvaluationRun, SessionToken, UsageLog, User


@dataclass(frozen=True)
class UserCreateRequest:
    """Parameters required to create a user account."""

    email: str
    name: str
    organization: str | None
    password: str
    role: str = "user"


@dataclass(frozen=True)
class EvaluationCreateRequest:
    """Parameters required to create an evaluation run."""

    identity: EvaluationIdentity
    descriptor: EvaluationDescriptor
    lifecycle: EvaluationLifecycle


@dataclass(frozen=True)
class EvaluationIdentity:
    """Identifiers attached to an evaluation run."""

    user_id: str | UUID
    evaluation_id: str | UUID | None = None
    api_key_id: str | UUID | None = None


@dataclass(frozen=True)
class EvaluationDescriptor:
    """Business metadata describing an evaluation run."""

    system_name: str
    system_version: str | None
    author: str
    endpoint_url: str
    mode: str
    dataset_name: str


@dataclass(frozen=True)
class EvaluationLifecycle:
    """Initial execution state for an evaluation run."""

    status: str = "pending"
    progress: int = 0


@dataclass(frozen=True)
class EvaluationUpdateRequest:
    """Mutable fields that can be updated for an evaluation run."""

    status: str | None = None
    progress: int | None = None
    error_message: str | None = None
    scores: dict[str, float] | None = None
    metrics: dict[str, Any] | None = None
    langsmith_run_id: str | None = None
    trace_url: str | None = None


@dataclass(frozen=True)
class EvaluationListRequest:
    """Filters and pagination for evaluation-run listings."""

    user_id: str | UUID
    status_filter: str | None
    mode_filter: str | None
    page: int
    page_size: int


def _utcnow() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


def _coerce_uuid(value: str | UUID | None) -> UUID | None:
    """Normalize a UUID-like value for database reads and writes."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid UUID value: {value}") from exc


class DatabaseRepository:
    """High-level repository API for persistence operations."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or self._build_database_url()
        connect_args: dict[str, Any] = {}
        if self.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        self.engine: Engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            future=True,
            connect_args=connect_args,
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._bootstrap()

    def _bootstrap(self) -> None:
        """Initialize schema idempotently."""
        Base.metadata.create_all(self.engine)

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password with PBKDF2-HMAC-SHA256."""
        iterations = 310_000
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return f"{iterations}${salt.hex()}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, stored_hash: str) -> bool:
        """Verify password against stored PBKDF2 hash."""
        try:
            iterations_s, salt_hex, digest_hex = stored_hash.split("$")
            iterations = int(iterations_s)
            salt = bytes.fromhex(salt_hex)
            digest = bytes.fromhex(digest_hex)
        except (TypeError, ValueError):
            return False

        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(candidate, digest)

    @staticmethod
    def _hash_token(token: str) -> str:
        """Return SHA256 hash of token."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _encode_json(data: dict[str, Any] | list[Any]) -> str:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode_json(payload: str) -> dict[str, Any]:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return decoded
        return {}

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        """Normalize datetimes loaded from DB drivers to timezone-aware UTC."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @contextmanager
    def session_scope(self):
        """Context manager for session lifecycle."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _build_database_url(self) -> str:
        """Build SQLAlchemy database URL from env/config."""
        if env_url := os.getenv("METIVTA_DATABASE_URL"):
            return env_url
        if env_url := os.getenv("DATABASE_URL"):
            if env_url.startswith("postgres://"):
                return env_url.replace("postgres://", "postgresql+psycopg://", 1)
            return env_url

        provider = config.database.provider
        if provider == "sqlite":
            return "sqlite:///metivta.db"

        pg = config.database.postgresql
        return (
            "postgresql+psycopg://"
            f"{pg.user}:{pg.password.get_secret_value()}@"
            f"{pg.host}:{pg.port}/{pg.database}"
            f"?sslmode={pg.ssl_mode}"
        )

    def create_user(self, request: UserCreateRequest) -> dict[str, Any]:
        """Create a new user."""
        with self.session_scope() as session:
            existing = session.execute(
                select(User).where(User.email == request.email.lower())
            ).scalar_one_or_none()
            if existing is not None:
                raise ValueError("user_already_exists")

            now = _utcnow()
            user = User(
                id=uuid4(),
                email=request.email.lower(),
                name=request.name,
                organization=request.organization,
                password_hash=self._hash_password(request.password),
                role=request.role,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            return self._user_dict(user)

    def _get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Return user by email."""
        with self.session_scope() as session:
            user = session.execute(
                select(User).where(User.email == email.lower())
            ).scalar_one_or_none()
            if user is None:
                return None
            return self._user_dict(user)

    def get_user_by_id(self, user_id: str | UUID) -> dict[str, Any] | None:
        """Return user by ID."""
        with self.session_scope() as session:
            user_uuid = _coerce_uuid(user_id)
            user = session.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
            if user is None:
                return None
            return self._user_dict(user)

    def verify_user_credentials(self, email: str, password: str) -> dict[str, Any] | None:
        """Validate credentials and return user."""
        with self.session_scope() as session:
            user = session.execute(
                select(User).where(User.email == email.lower())
            ).scalar_one_or_none()
            if user is None or not user.is_active:
                return None
            if not self._verify_password(password, user.password_hash):
                return None
            return self._user_dict(user)

    def _create_session_pair(self, user_id: str | UUID) -> dict[str, Any]:
        """Create access and refresh session tokens."""
        now = _utcnow()
        access_ttl = timedelta(minutes=config.security.jwt.access_token_ttl_minutes)
        refresh_ttl = timedelta(days=config.security.jwt.refresh_token_ttl_days)
        user_uuid = _coerce_uuid(user_id)

        access_token = secrets.token_urlsafe(48)
        refresh_token = secrets.token_urlsafe(56)

        access_row = SessionToken(
            id=uuid4(),
            user_id=user_uuid,
            token_type="access",
            token_hash=self._hash_token(access_token),
            created_at=now,
            expires_at=now + access_ttl,
            revoked_at=None,
        )
        refresh_row = SessionToken(
            id=uuid4(),
            user_id=user_uuid,
            token_type="refresh",
            token_hash=self._hash_token(refresh_token),
            created_at=now,
            expires_at=now + refresh_ttl,
            revoked_at=None,
        )

        with self.session_scope() as session:
            session.add(access_row)
            session.add(refresh_row)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": int(access_ttl.total_seconds()),
        }

    def create_session_pair(self, user_id: str | UUID) -> dict[str, Any]:
        """Create access and refresh session tokens."""
        return self._create_session_pair(user_id)

    def rotate_refresh_token(self, refresh_token: str) -> dict[str, Any] | None:
        """Rotate a refresh token and return a new token pair."""
        refresh_hash = self._hash_token(refresh_token)
        now = _utcnow()

        with self.session_scope() as session:
            token_row = session.execute(
                select(SessionToken).where(
                    SessionToken.token_hash == refresh_hash,
                    SessionToken.token_type == "refresh",
                    SessionToken.revoked_at.is_(None),
                )
            ).scalar_one_or_none()
            if token_row is None:
                return None
            expires_at = self._as_utc(token_row.expires_at)
            if expires_at is None or expires_at <= now:
                return None

            token_row.revoked_at = now
            user_id = token_row.user_id

        return self._create_session_pair(user_id)

    def validate_access_token(self, access_token: str) -> dict[str, Any] | None:
        """Resolve and validate bearer access token."""
        token_hash = self._hash_token(access_token)
        now = _utcnow()

        with self.session_scope() as session:
            token_row = session.execute(
                select(SessionToken).where(
                    SessionToken.token_hash == token_hash,
                    SessionToken.token_type == "access",
                    SessionToken.revoked_at.is_(None),
                )
            ).scalar_one_or_none()
            if token_row is None:
                return None
            expires_at = self._as_utc(token_row.expires_at)
            if expires_at is None or expires_at <= now:
                return None

            user = session.execute(
                select(User).where(User.id == token_row.user_id)
            ).scalar_one_or_none()
            if user is None or not user.is_active:
                return None
            return self._user_dict(user)

    def create_api_key(
        self,
        user_id: str | UUID,
        name: str,
        scopes: list[str],
        expires_in_days: int | None = None,
    ) -> dict[str, Any]:
        """Create and store a hashed API key."""
        key_body = secrets.token_urlsafe(config.security.api_keys.length)
        full_key = f"{config.security.api_keys.prefix}{key_body}"
        now = _utcnow()

        api_key = APIKey(
            id=uuid4(),
            user_id=_coerce_uuid(user_id),
            name=name,
            key_prefix=full_key[:12],
            key_hash=self._hash_token(full_key),
            scopes_json=self._encode_json(scopes),
            created_at=now,
            expires_at=now + timedelta(days=expires_in_days) if expires_in_days else None,
            last_used_at=None,
            revoked_at=None,
            is_active=True,
        )

        with self.session_scope() as session:
            session.add(api_key)

        return {
            "id": str(api_key.id),
            "name": api_key.name,
            "key": full_key,
            "key_prefix": api_key.key_prefix,
            "scopes": scopes,
            "created_at": api_key.created_at,
            "expires_at": api_key.expires_at,
            "last_used_at": api_key.last_used_at,
        }

    def list_api_keys(self, user_id: str | UUID) -> list[dict[str, Any]]:
        """List active API keys for a user."""
        user_uuid = _coerce_uuid(user_id)
        with self.session_scope() as session:
            rows = session.execute(
                select(APIKey)
                .where(APIKey.user_id == user_uuid, APIKey.is_active.is_(True))
                .order_by(APIKey.created_at.desc())
            ).scalars()
            return [self._api_key_dict(row) for row in rows]

    def revoke_api_key(self, user_id: str | UUID, key_id: str | UUID) -> bool:
        """Revoke API key belonging to a user."""
        user_uuid = _coerce_uuid(user_id)
        key_uuid = _coerce_uuid(key_id)
        with self.session_scope() as session:
            row = session.execute(
                select(APIKey).where(
                    APIKey.id == key_uuid,
                    APIKey.user_id == user_uuid,
                    APIKey.is_active.is_(True),
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            row.is_active = False
            row.revoked_at = _utcnow()
            return True

    def verify_api_key(self, raw_key: str) -> dict[str, Any] | None:
        """Verify API key and return principal information."""
        key_hash = self._hash_token(raw_key)
        now = _utcnow()

        with self.session_scope() as session:
            row = session.execute(
                select(APIKey).where(
                    APIKey.key_hash == key_hash,
                    APIKey.is_active.is_(True),
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            expires_at = self._as_utc(row.expires_at)
            if expires_at is not None and expires_at <= now:
                return None

            user = session.execute(select(User).where(User.id == row.user_id)).scalar_one_or_none()
            if user is None or not user.is_active:
                return None

            row.last_used_at = now
            return {
                "api_key_id": str(row.id),
                "user_id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "rate_limit": config.security.rate_limiting.requests_per_hour,
            }

    def check_rate_limit(
        self,
        api_key_id: str | UUID,
        limit: int | None = None,
    ) -> tuple[bool, int]:
        """Check hourly rate usage for an API key."""
        hourly_limit = limit or config.security.rate_limiting.requests_per_hour
        since = _utcnow() - timedelta(hours=1)
        api_key_uuid = _coerce_uuid(api_key_id)

        with self.session_scope() as session:
            used = session.execute(
                select(count(UsageLog.id)).where(
                    UsageLog.api_key_id == api_key_uuid,
                    UsageLog.created_at >= since,
                )
            ).scalar_one()

        return used < hourly_limit, int(used)

    def log_usage(
        self,
        endpoint: str,
        status_code: int,
        user_id: str | UUID | None = None,
        api_key_id: str | UUID | None = None,
    ) -> None:
        """Insert usage log entry."""
        row = UsageLog(
            user_id=_coerce_uuid(user_id),
            api_key_id=_coerce_uuid(api_key_id),
            endpoint=endpoint,
            status_code=status_code,
            created_at=_utcnow(),
        )
        with self.session_scope() as session:
            session.add(row)

    def create_evaluation_run(self, request: EvaluationCreateRequest) -> dict[str, Any]:
        """Create an evaluation run record."""
        now = _utcnow()
        identity = request.identity
        descriptor = request.descriptor
        lifecycle = request.lifecycle
        run = EvaluationRun(
            id=_coerce_uuid(identity.evaluation_id) or uuid4(),
            user_id=_coerce_uuid(identity.user_id),
            api_key_id=_coerce_uuid(identity.api_key_id),
            system_name=descriptor.system_name,
            system_version=descriptor.system_version,
            author=descriptor.author,
            endpoint_url=descriptor.endpoint_url,
            mode=descriptor.mode,
            dataset_name=descriptor.dataset_name,
            status=lifecycle.status,
            progress=lifecycle.progress,
            error_message=None,
            scores_json="{}",
            metrics_json="{}",
            langsmith_run_id=None,
            trace_url=None,
            created_at=now,
            started_at=now if lifecycle.status == "running" else None,
            completed_at=None,
            updated_at=now,
        )
        with self.session_scope() as session:
            session.add(run)
        return self._evaluation_dict(run)

    def update_evaluation_run(
        self,
        evaluation_id: str | UUID,
        request: EvaluationUpdateRequest,
    ) -> dict[str, Any] | None:
        """Update evaluation run state."""
        evaluation_uuid = _coerce_uuid(evaluation_id)
        with self.session_scope() as session:
            row = session.execute(
                select(EvaluationRun).where(EvaluationRun.id == evaluation_uuid)
            ).scalar_one_or_none()
            if row is None:
                return None

            now = _utcnow()
            if request.status is not None:
                row.status = request.status
                if request.status == "running" and row.started_at is None:
                    row.started_at = now
                if request.status in {"completed", "failed", "cancelled"}:
                    row.completed_at = now
            if request.progress is not None:
                row.progress = max(0, min(request.progress, 100))
            if request.error_message is not None:
                row.error_message = request.error_message
            if request.scores is not None:
                row.scores_json = self._encode_json(request.scores)
            if request.metrics is not None:
                row.metrics_json = self._encode_json(request.metrics)
            if request.langsmith_run_id is not None:
                row.langsmith_run_id = request.langsmith_run_id
            if request.trace_url is not None:
                row.trace_url = request.trace_url
            row.updated_at = now

            return self._evaluation_dict(row)

    def get_evaluation_run(
        self,
        evaluation_id: str | UUID,
        user_id: str | UUID | None = None,
    ) -> dict[str, Any] | None:
        """Fetch one evaluation run."""
        evaluation_uuid = _coerce_uuid(evaluation_id)
        user_uuid = _coerce_uuid(user_id)
        with self.session_scope() as session:
            stmt = select(EvaluationRun).where(EvaluationRun.id == evaluation_uuid)
            if user_uuid is not None:
                stmt = stmt.where(EvaluationRun.user_id == user_uuid)
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                return None
            return self._evaluation_dict(row)

    def list_evaluation_runs(
        self,
        request: EvaluationListRequest,
    ) -> tuple[list[dict[str, Any]], int]:
        """List evaluation runs with filters and pagination."""
        user_uuid = _coerce_uuid(request.user_id)
        with self.session_scope() as session:
            base = select(EvaluationRun).where(EvaluationRun.user_id == user_uuid)
            if request.status_filter:
                base = base.where(EvaluationRun.status == request.status_filter)
            if request.mode_filter:
                base = base.where(EvaluationRun.mode == request.mode_filter)

            total = session.execute(select(count()).select_from(base.subquery())).scalar_one()
            rows = session.execute(
                base.order_by(EvaluationRun.created_at.desc())
                .offset((request.page - 1) * request.page_size)
                .limit(request.page_size)
            ).scalars()
            return [self._evaluation_dict(row) for row in rows], int(total)

    def cancel_evaluation_run(
        self,
        evaluation_id: str | UUID,
        user_id: str | UUID,
    ) -> dict[str, Any] | None:
        """Cancel a pending or running evaluation run."""
        evaluation_uuid = _coerce_uuid(evaluation_id)
        user_uuid = _coerce_uuid(user_id)
        with self.session_scope() as session:
            row = session.execute(
                select(EvaluationRun).where(
                    EvaluationRun.id == evaluation_uuid,
                    EvaluationRun.user_id == user_uuid,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            if row.status not in {"pending", "running"}:
                return None

            now = _utcnow()
            row.status = "cancelled"
            row.progress = 100
            row.completed_at = now
            row.updated_at = now
            return self._evaluation_dict(row)

    def get_leaderboard(
        self, mode: str, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        """Fetch ranked leaderboard entries."""
        with self.session_scope() as session:
            stmt = select(EvaluationRun).where(EvaluationRun.status == "completed")
            if mode != "all":
                stmt = stmt.where(EvaluationRun.mode == mode)

            total = session.execute(select(count()).select_from(stmt.subquery())).scalar_one()
            rows = session.execute(stmt.order_by(EvaluationRun.completed_at.desc())).scalars().all()

        ranked: list[dict[str, Any]] = []
        for row in rows:
            scores = self._decode_json(row.scores_json)
            ranked.append(
                {
                    "system_id": str(row.id),
                    "system_name": row.system_name,
                    "system_version": row.system_version,
                    "author": row.author,
                    "organization": None,
                    "mode": row.mode,
                    "overall_score": self._overall_score(scores, row.mode),
                    "daat_score": float(scores.get("daat_score", 0.0))
                    if row.mode == "daat"
                    else None,
                    "ndcg_10": self._nullable_float(
                        self._score_value(scores, "ndcg_10", "NDCG@10")
                    ),
                    "map_100": self._nullable_float(
                        self._score_value(scores, "map_100", "MAP@100")
                    ),
                    "mrr_10": self._nullable_float(self._score_value(scores, "mrr_10", "MRR@10")),
                    "dataset_name": row.dataset_name,
                    "submitted_at": row.completed_at or row.updated_at,
                }
            )

        ranked.sort(
            key=lambda item: item["overall_score"] if item["overall_score"] is not None else 0.0,
            reverse=True,
        )

        for index, item in enumerate(ranked, start=1):
            item["rank"] = index

        start = (page - 1) * page_size
        end = start + page_size
        return ranked[start:end], int(total)

    def get_leaderboard_stats(self) -> dict[str, Any]:
        """Compute leaderboard aggregate statistics."""
        with self.session_scope() as session:
            total_users = session.execute(select(count(User.id))).scalar_one()
            total_eval = session.execute(select(count(EvaluationRun.id))).scalar_one()
            total_systems = session.execute(
                select(count(distinct(EvaluationRun.system_name))).where(
                    EvaluationRun.status == "completed"
                )
            ).scalar_one()
            last_eval = session.execute(
                select(func.max(EvaluationRun.completed_at)).where(
                    EvaluationRun.status == "completed"
                )
            ).scalar_one()
            completed = (
                session.execute(select(EvaluationRun).where(EvaluationRun.status == "completed"))
                .scalars()
                .all()
            )

        daat_scores: list[float] = []
        ndcg_scores: list[float] = []
        for row in completed:
            scores = self._decode_json(row.scores_json)
            if "daat_score" in scores:
                daat_scores.append(float(scores["daat_score"]))
            ndcg_value = self._score_value(scores, "ndcg_10", "NDCG@10")
            if ndcg_value is not None:
                ndcg_scores.append(float(ndcg_value))

        return {
            "total_systems": int(total_systems),
            "total_evaluations": int(total_eval),
            "total_users": int(total_users),
            "average_daat_score": self._mean_or_none(daat_scores),
            "average_ndcg_10": self._mean_or_none(ndcg_scores),
            "top_organization": None,
            "last_evaluation": last_eval,
        }

    def _user_dict(self, row: User) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "email": row.email,
            "name": row.name,
            "organization": row.organization,
            "role": row.role,
            "is_active": row.is_active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _api_key_dict(self, row: APIKey) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "name": row.name,
            "key_prefix": row.key_prefix,
            "scopes": json.loads(row.scopes_json),
            "created_at": row.created_at,
            "expires_at": row.expires_at,
            "last_used_at": row.last_used_at,
            "is_active": row.is_active,
        }

    def _evaluation_dict(self, row: EvaluationRun) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "user_id": str(row.user_id),
            "api_key_id": str(row.api_key_id) if row.api_key_id is not None else None,
            "system_name": row.system_name,
            "system_version": row.system_version,
            "author": row.author,
            "endpoint_url": row.endpoint_url,
            "mode": row.mode,
            "dataset_name": row.dataset_name,
            "status": row.status,
            "progress": row.progress,
            "error_message": row.error_message,
            "scores": self._decode_json(row.scores_json),
            "metrics": self._decode_json(row.metrics_json),
            "langsmith_run_id": row.langsmith_run_id,
            "trace_url": row.trace_url,
            "created_at": row.created_at,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _mean_or_none(values: list[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    @staticmethod
    def _nullable_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _score_value(scores: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in scores:
                return scores[key]
        return None

    def _overall_score(self, scores: dict[str, Any], mode: str) -> float | None:
        if not scores:
            return None
        if mode == "daat" and "daat_score" in scores:
            return float(scores["daat_score"])

        preferred = ["ndcg_10", "NDCG@10", "overall_score", "score"]
        for key in preferred:
            if key in scores:
                return float(scores[key])

        numeric_values: list[float] = []
        for value in scores.values():
            try:
                numeric_values.append(float(value))
            except (TypeError, ValueError):
                continue
        if not numeric_values:
            return None
        return sum(numeric_values) / len(numeric_values)
