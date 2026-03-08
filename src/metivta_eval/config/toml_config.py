"""
Centralized TOML Configuration Loader for MetivitaEval.

This module provides a unified configuration system that:
1. Reads from config.toml as the single source of truth
2. Supports environment variable overrides (METIVTA_SECTION_KEY pattern)
3. Validates configuration with Pydantic
4. Provides type-safe access to all configuration values
5. Supports hot-reloading in development mode

Usage:
    from metivta_eval.config.toml_config import config

    # Access configuration
    port = config.server.port
    api_key = config.models.anthropic.api_key
"""

from __future__ import annotations

import json
import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr

# ============================================================================
# TYPE DEFINITIONS
# ============================================================================

Environment = Literal["development", "staging", "production"]
LogLevel = Literal["debug", "info", "warn", "error"]
LogFormat = Literal["json", "text"]
DatabaseProvider = Literal["postgresql", "supabase", "sqlite"]
CacheProvider = Literal["memory", "redis", "memcached"]
StorageProvider = Literal["local", "s3", "digitalocean_spaces"]
SecretsProvider = Literal["env", "vault", "onepassword"]


# ============================================================================
# CONFIGURATION MODELS
# ============================================================================


class MetaConfig(BaseModel):
    """Metadata configuration."""

    version: str = "2.0.0"
    environment: Environment = "development"


class CORSConfig(BaseModel):
    """CORS configuration."""

    allowed_origins: list[str] = ["*"]
    allowed_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allowed_headers: list[str] = ["*"]
    max_age_seconds: int = 86400


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = 8080
    gateway_port: int = 8000
    fastapi_port: int = 8001
    workers: int = 4
    timeout_seconds: int = 300
    graceful_shutdown_seconds: int = 30
    cors: CORSConfig = CORSConfig()


class MTLSConfig(BaseModel):
    """mTLS configuration."""

    enabled: bool = False
    ca_cert_path: str = "certs/ca.crt"
    server_cert_path: str = "certs/server.crt"
    server_key_path: str = "certs/server.key"
    client_cert_required: bool = True
    min_tls_version: str = "1.3"


class JWTConfig(BaseModel):
    """JWT configuration."""

    enabled: bool = True
    algorithm: str = "RS256"
    issuer: str = "metivta-eval"
    audience: str = "metivta-api"
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_days: int = 7
    public_key_path: str = "certs/jwt_public.pem"
    private_key_path: str = "certs/jwt_private.pem"


class RateLimitingConfig(BaseModel):
    """Rate limiting configuration."""

    enabled: bool = True
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10
    storage: Literal["memory", "redis"] = "redis"


class APIKeysConfig(BaseModel):
    """API keys configuration."""

    prefix: str = "mtv_"
    length: int = 32
    hash_algorithm: str = "argon2id"
    rotation_days: int = 90


class SecurityConfig(BaseModel):
    """Security configuration."""

    enabled: bool = True
    secret_key: SecretStr = SecretStr("")
    mtls: MTLSConfig = MTLSConfig()
    jwt: JWTConfig = JWTConfig()
    rate_limiting: RateLimitingConfig = RateLimitingConfig()
    api_keys: APIKeysConfig = APIKeysConfig()


class PostgreSQLConfig(BaseModel):
    """PostgreSQL configuration."""

    host: str = "localhost"
    port: int = 5432
    database: str = "metivta"
    user: str = "metivta"
    password: SecretStr = SecretStr("")
    ssl_mode: str = "prefer"

    @property
    def dsn(self) -> str:
        """Build PostgreSQL DSN."""
        password = self.password.get_secret_value()
        return (
            f"postgresql://{self.user}:{password}@{self.host}:{self.port}/"
            f"{self.database}?sslmode={self.ssl_mode}"
        )


class SupabaseConfig(BaseModel):
    """Supabase configuration."""

    url: str = ""
    anon_key: SecretStr = SecretStr("")
    service_role_key: SecretStr = SecretStr("")


class MigrationsConfig(BaseModel):
    """Database migrations configuration."""

    auto_migrate: bool = True
    directory: str = "migrations"


class DatabaseConfig(BaseModel):
    """Database configuration."""

    provider: DatabaseProvider = "postgresql"
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout_seconds: int = 30
    echo_sql: bool = False
    postgresql: PostgreSQLConfig = PostgreSQLConfig()
    supabase: SupabaseConfig = SupabaseConfig()
    migrations: MigrationsConfig = MigrationsConfig()


class RedisConfig(BaseModel):
    """Redis configuration."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: SecretStr = SecretStr("")
    pool_size: int = 10
    ssl: bool = False

    @property
    def url(self) -> str:
        """Build Redis URL."""
        password = self.password.get_secret_value()
        auth = f":{password}@" if password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class CacheConfig(BaseModel):
    """Cache configuration."""

    provider: CacheProvider = "redis"
    default_ttl_seconds: int = 3600
    redis: RedisConfig = RedisConfig()


class AnthropicConfig(BaseModel):
    """Anthropic configuration."""

    api_key: SecretStr = SecretStr("")
    max_tokens: int = 4096
    temperature: float = 0.0


class OpenAIConfig(BaseModel):
    """OpenAI configuration."""

    api_key: SecretStr = SecretStr("")
    organization: str = ""


class LangSmithConfig(BaseModel):
    """LangSmith configuration."""

    api_key: SecretStr = SecretStr("")
    project: str = "metivta-eval"
    tracing_enabled: bool = True


class ModelsConfig(BaseModel):
    """AI models configuration."""

    primary: str = "claude-sonnet-4-20250514"
    fast: str = "claude-sonnet-4-20250514"
    embedding: str = "text-embedding-3-small"
    anthropic: AnthropicConfig = AnthropicConfig()
    openai: OpenAIConfig = OpenAIConfig()
    langsmith: LangSmithConfig = LangSmithConfig()


class DAATWeightsConfig(BaseModel):
    """DAAT weights configuration."""

    dai: float = 0.60
    mla: float = 0.40


class DAATConfig(BaseModel):
    """DAAT evaluation configuration."""

    enabled: bool = True
    evaluators: list[str] = Field(default_factory=lambda: ["all"])
    weights: DAATWeightsConfig = DAATWeightsConfig()


class MTEBConfig(BaseModel):
    """MTEB evaluation configuration."""

    enabled: bool = True
    batch_size: int = 100
    metrics: list[str] = Field(
        default_factory=lambda: ["ndcg@10", "map@100", "mrr@10", "recall@100", "precision@10"]
    )


class WebValidatorConfig(BaseModel):
    """Web validator configuration."""

    enabled: bool = True
    timeout_ms: int = 15000
    min_keyword_matches: int = 15
    concurrency: int = 5
    cache_enabled: bool = True
    browserless_token: SecretStr = SecretStr("")


class EvaluationConfig(BaseModel):
    """Evaluation configuration."""

    target: str = "endpoint"
    endpoint_url: str = "http://localhost:5001/answer"
    dev_mode: bool = False
    async_enabled: bool = True
    max_concurrent_evaluations: int = 5
    daat: DAATConfig = DAATConfig()
    mteb: MTEBConfig = MTEBConfig()
    web_validator: WebValidatorConfig = WebValidatorConfig()


class DatasetFilesConfig(BaseModel):
    """Dataset files configuration."""

    questions: str = "Q1-dataset.json"
    questions_only: str = "Q1-questions-only.json"
    holdback: str = "Q1-holdback.json"
    format_rubric: str = "format_rubric.json"
    maturity_rubric: str = "maturity_rubric.json"


class MTEBDatasetConfig(BaseModel):
    """MTEB dataset configuration."""

    corpus: str = "mteb/corpus.jsonl"
    queries: str = "mteb/queries.jsonl"
    qrels: str = "mteb/qrels.tsv"


class DatasetConfig(BaseModel):
    """Dataset configuration."""

    name: str = "Metivta-Eval"
    version: str = "1.0"
    local_path: str = "src/metivta_eval/dataset"
    files: DatasetFilesConfig = DatasetFilesConfig()
    mteb: MTEBDatasetConfig = MTEBDatasetConfig()


class S3Config(BaseModel):
    """S3-compatible storage configuration."""

    bucket: str = "metivta-datasets"
    region: str = "nyc3"
    endpoint: str = ""
    access_key: SecretStr = SecretStr("")
    secret_key: SecretStr = SecretStr("")
    cdn_url: str = ""


class StorageConfig(BaseModel):
    """Storage configuration."""

    provider: StorageProvider = "local"
    local_path: str = "data"
    s3: S3Config = S3Config()


class VaultConfig(BaseModel):
    """HashiCorp Vault configuration."""

    address: str = "http://localhost:8200"
    token: SecretStr = SecretStr("")
    mount_path: str = "secret"
    secret_path: str = "metivta"


class OnePasswordConfig(BaseModel):
    """1Password configuration."""

    vault: str = "metivta-dev"
    service_account_token: SecretStr = SecretStr("")


class SecretsConfig(BaseModel):
    """Secrets management configuration."""

    provider: SecretsProvider = "env"
    vault: VaultConfig = VaultConfig()
    onepassword: OnePasswordConfig = OnePasswordConfig()


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: LogLevel = "info"
    format: LogFormat = "json"
    output: Literal["stdout", "file", "both"] = "stdout"
    file_path: str = "logs/metivta.log"
    max_size_mb: int = 100
    max_backups: int = 5
    max_age_days: int = 30
    compress: bool = True


class TracingConfig(BaseModel):
    """Tracing configuration."""

    enabled: bool = True
    provider: Literal["otlp", "jaeger", "zipkin"] = "otlp"
    endpoint: str = "http://localhost:4317"
    sample_rate: float = 1.0


class MetricsConfig(BaseModel):
    """Metrics configuration."""

    enabled: bool = True
    provider: str = "prometheus"
    port: int = 9090
    path: str = "/metrics"


class SentryConfig(BaseModel):
    """Sentry configuration."""

    enabled: bool = False
    dsn: SecretStr = SecretStr("")
    environment: str = "development"
    traces_sample_rate: float = 0.1


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    service_name: str = "metivta-eval"
    logging: LoggingConfig = LoggingConfig()
    tracing: TracingConfig = TracingConfig()
    metrics: MetricsConfig = MetricsConfig()
    sentry: SentryConfig = SentryConfig()


class WorkerQueuesConfig(BaseModel):
    """Worker queues configuration."""

    default: str = "metivta.default"
    evaluation: str = "metivta.evaluation"
    notifications: str = "metivta.notifications"


class WorkerConfig(BaseModel):
    """Worker configuration."""

    enabled: bool = True
    broker: str = "redis://localhost:6379/1"
    result_backend: str = "redis://localhost:6379/2"
    concurrency: int = 4
    prefetch_multiplier: int = 1
    task_acks_late: bool = True
    task_reject_on_worker_lost: bool = True
    queues: WorkerQueuesConfig = WorkerQueuesConfig()


class EmailConfig(BaseModel):
    """Email configuration."""

    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    from_address: str = "noreply@metivta.ai"


class SlackConfig(BaseModel):
    """Slack configuration."""

    enabled: bool = False
    webhook_url: SecretStr = SecretStr("")


class NotificationsConfig(BaseModel):
    """Notifications configuration."""

    enabled: bool = False
    email: EmailConfig = EmailConfig()
    slack: SlackConfig = SlackConfig()


class FeaturesConfig(BaseModel):
    """Feature flags configuration."""

    mteb_evaluation: bool = True
    async_evaluation: bool = True
    websocket_updates: bool = True
    graphql_api: bool = False
    legacy_flask_routes: bool = True
    new_user_management: bool = True


# ============================================================================
# ROOT CONFIGURATION
# ============================================================================


class MetivtaConfig(BaseModel):
    """Root configuration model for MetivitaEval."""

    meta: MetaConfig = MetaConfig()
    server: ServerConfig = ServerConfig()
    security: SecurityConfig = SecurityConfig()
    database: DatabaseConfig = DatabaseConfig()
    cache: CacheConfig = CacheConfig()
    models: ModelsConfig = ModelsConfig()
    evaluation: EvaluationConfig = EvaluationConfig()
    dataset: DatasetConfig = DatasetConfig()
    storage: StorageConfig = StorageConfig()
    secrets: SecretsConfig = SecretsConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    worker: WorkerConfig = WorkerConfig()
    notifications: NotificationsConfig = NotificationsConfig()
    features: FeaturesConfig = FeaturesConfig()

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.meta.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.meta.environment == "development"


# ============================================================================
# CONFIGURATION LOADER
# ============================================================================


def _find_config_file() -> Path:
    """Find config.toml file, searching from current directory up to root."""
    # Check explicit env var first
    if env_path := os.environ.get("METIVTA_CONFIG_PATH"):
        path = Path(env_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"Config file not found at METIVTA_CONFIG_PATH: {env_path}")

    # Search from current directory up
    current = Path.cwd()
    for parent in [current, *current.parents]:
        config_path = parent / "config.toml"
        if config_path.exists():
            return config_path

    # Default location
    default_path = Path(__file__).parent.parent.parent.parent / "config.toml"
    if default_path.exists():
        return default_path

    raise FileNotFoundError(
        "config.toml not found. Create one or set METIVTA_CONFIG_PATH environment variable."
    )


def _apply_env_overrides(data: dict[str, Any], prefix: str = "METIVTA") -> dict[str, Any]:
    """
    Recursively apply environment variable overrides.

    Pattern: METIVTA_SECTION_SUBSECTION_KEY
    Example: METIVTA_SERVER_PORT=9000
    """
    result = data.copy()

    for key, value in result.items():
        env_key = f"{prefix}_{key}".upper()

        if isinstance(value, dict):
            result[key] = _apply_env_overrides(value, env_key)
        else:
            if env_value := os.environ.get(env_key):
                # Type coercion
                if isinstance(value, bool):
                    result[key] = env_value.lower() in ("true", "1", "yes")
                elif isinstance(value, int):
                    result[key] = int(env_value)
                elif isinstance(value, float):
                    result[key] = float(env_value)
                elif isinstance(value, list):
                    result[key] = env_value.split(",")
                else:
                    result[key] = env_value

    return result


def _load_toml_config() -> dict[str, Any]:
    """Load and parse config.toml file."""
    config_path = _find_config_file()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    return _apply_env_overrides(data)


@lru_cache(maxsize=1)
def load_config() -> MetivtaConfig:
    """
    Load and cache the configuration.

    Returns:
        MetivtaConfig: The validated configuration object.
    """
    data = _load_toml_config()
    return MetivtaConfig(**data)


def reload_config() -> MetivtaConfig:
    """
    Force reload the configuration (clears cache).

    Returns:
        MetivtaConfig: Fresh configuration object.
    """
    load_config.cache_clear()
    return load_config()


# ============================================================================
# SINGLETON ACCESS
# ============================================================================


# Lazy singleton - only loads when accessed
class _ConfigProxy:
    """Lazy proxy for configuration access."""

    _instance: MetivtaConfig | None = None

    def __getattr__(self, name: str) -> Any:
        if self._instance is None:
            self._instance = load_config()
        return getattr(self._instance, name)

    def reload(self) -> MetivtaConfig:
        """Reload configuration."""
        self._instance = reload_config()
        return self._instance


# Export singleton
config = _ConfigProxy()


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================


def get_legacy_config() -> dict[str, Any]:
    """
    Get configuration in legacy format for backward compatibility.

    This maps the new TOML config to the old YAML structure.
    """
    legacy_config = load_config()

    return {
        "evaluation": {
            "target": legacy_config.evaluation.target,
            "endpoint_url": legacy_config.evaluation.endpoint_url,
            "dev_mode": legacy_config.evaluation.dev_mode,
        },
        "models": {
            "primary": legacy_config.models.primary,
            "fast": legacy_config.models.fast,
            "claude": legacy_config.models.primary,
        },
        "playwright_validator": {
            "timeout_ms": legacy_config.evaluation.web_validator.timeout_ms,
            "min_keyword_matches": legacy_config.evaluation.web_validator.min_keyword_matches,
            "enable_cache": legacy_config.evaluation.web_validator.cache_enabled,
            "concurrency": legacy_config.evaluation.web_validator.concurrency,
        },
        "dataset": {
            "name": legacy_config.dataset.name,
            "local_file": (
                f"{legacy_config.dataset.local_path}/{legacy_config.dataset.files.questions}"
            ),
        },
        "api": {
            "host": legacy_config.server.host,
            "port": legacy_config.server.port,
            "secret_key": legacy_config.security.secret_key.get_secret_value(),
            "data_file": "api/leaderboard_data.json",
        },
        "evaluators": {
            "enable_llm_feedback": True,
            "daat_config": {
                "composite_weights": {
                    "dai": legacy_config.evaluation.daat.weights.dai,
                    "mla": legacy_config.evaluation.daat.weights.mla,
                },
            },
        },
    }


# ============================================================================
# CLI HELPERS
# ============================================================================


def print_config(section: str | None = None) -> None:
    """Print configuration for debugging."""
    current_config = load_config()

    if section:
        data = getattr(current_config, section, None)
        if data is None:
            print(f"Unknown section: {section}")
            return
        print(json.dumps(data.model_dump(), indent=2, default=str))
    else:
        # Print all (mask secrets)
        dump = current_config.model_dump()
        print(json.dumps(dump, indent=2, default=str))


if __name__ == "__main__":
    # Quick test
    loaded_config = load_config()
    print(f"Environment: {loaded_config.meta.environment}")
    print(f"Server port: {loaded_config.server.port}")
    print(f"Database provider: {loaded_config.database.provider}")
