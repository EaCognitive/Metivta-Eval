"""
MetivitaEval FastAPI Application.

This is the main entry point for the FastAPI service.
"""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from html import escape
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

# Import config
from metivta_eval.config.toml_config import config
from metivta_eval.langsmith_utils import get_daat_dependency_status

# Import routers
from .routers import auth, evaluation, health, leaderboard, websocket

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError:
    trace = None
    OTLPSpanExporter = None
    FastAPIInstrumentor = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None

OPENAPI_DESCRIPTION = """
## MetivtaEval - AI Benchmarking Platform

MetivtaEval provides evaluation services for Torah AI systems across DAAT and MTEB modes.

### Features

- **DAAT Scoring**: Deterministic Attribution & Agentic Traceability
- **MTEB Metrics**: Standard information retrieval metrics
- **Leaderboard APIs**: Ranked public and user-specific evaluation views
- **WebSocket Events**: Authenticated progress and leaderboard update streams

### Runtime Notes

- **DAAT Dataset**: Loaded from the configured local JSON dataset in Docker and local dev
- **LangSmith**: Optional for dataset sync and tracing when credentials are configured
- **External Evaluators**: Anthropic and Browserless integrations activate when their keys are set

### Authentication

All protected endpoints accept:
- **Bearer Token**: JWT in the `Authorization` header
- **API Key**: `X-API-Key` header
""".strip()


def _build_scalar_config(server_url: str) -> dict[str, object]:
    """Build the Scalar configuration used by the interactive API reference."""
    return {
        "theme": "default",
        "layout": "modern",
        "showSidebar": True,
        "defaultOpenFirstTag": True,
        "defaultOpenAllTags": True,
        "showDeveloperTools": "never",
        "documentDownloadType": "json",
        "hideDownloadButton": False,
        "defaultHttpClient": {
            "targetKey": "shell",
            "clientKey": "curl",
        },
        "servers": [
            {
                "url": server_url,
                "description": "Current gateway",
            }
        ],
    }


# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Manage application startup and shutdown.

    This handles:
    - Database connection pool
    - Redis connection
    - OpenTelemetry setup
    - Background task cleanup
    """
    # Startup
    print(f"Starting MetivitaEval FastAPI v{application.version}")
    print(f"Environment: {config.meta.environment}")
    daat_status = get_daat_dependency_status(force_refresh=True)
    if daat_status.ready:
        print(daat_status.message)
    else:
        print(f"WARNING: {daat_status.message}")

    # Setup OpenTelemetry if enabled
    if config.observability.tracing.enabled:
        setup_tracing(application)

    yield

    # Shutdown
    print("Shutting down MetivitaEval FastAPI...")


# ============================================================================
# APPLICATION FACTORY
# ============================================================================


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    application = FastAPI(
        title="MetivtaEval API",
        description=OPENAPI_DESCRIPTION,
        version="2.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v2/openapi.json",
        lifespan=lifespan,
    )

    @application.get("/api/v2/docs", include_in_schema=False)
    async def scalar_docs(request: Request) -> HTMLResponse:
        """Serve Scalar API reference instead of Swagger UI."""
        openapi_url = str(request.url_for("openapi"))
        server_url = str(request.base_url).rstrip("/")
        scalar_config = json.dumps(_build_scalar_config(server_url))
        html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>MetivtaEval API Reference</title>
  </head>
  <body>
    <script
      id="api-reference"
      data-url="{escape(openapi_url)}"
      data-configuration='{escape(scalar_config)}'></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </body>
</html>"""
        return HTMLResponse(html)

    # Configure CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors.allowed_origins,
        allow_credentials=True,
        allow_methods=config.server.cors.allowed_methods,
        allow_headers=config.server.cors.allowed_headers,
        max_age=config.server.cors.max_age_seconds,
    )

    # Add custom middleware
    @application.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        """Add processing time to response headers."""
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        return response

    @application.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Add request ID for tracing."""
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Include routers
    application.include_router(
        health.router,
        tags=["Health"],
    )
    application.include_router(
        auth.router,
        prefix="/api/v2/auth",
        tags=["Authentication"],
    )
    application.include_router(
        evaluation.router,
        prefix="/api/v2/eval",
        tags=["Evaluation"],
    )
    application.include_router(
        leaderboard.router,
        prefix="/api/v2/leaderboard",
        tags=["Leaderboard"],
    )
    application.include_router(
        websocket.router,
        prefix="/ws",
        tags=["WebSocket"],
    )

    # Global exception handler
    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all unhandled exceptions."""
        # Log the error
        print(f"Unhandled exception: {exc}")

        # Don't expose internal errors in production
        if config.is_production:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "internal_error",
                    "message": "An unexpected error occurred",
                    "request_id": getattr(request.state, "request_id", None),
                },
            )

        # In development, show more details
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": str(exc),
                "type": type(exc).__name__,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    return application


# ============================================================================
# TRACING SETUP
# ============================================================================


def setup_tracing(application: FastAPI) -> None:
    """Setup OpenTelemetry tracing."""
    try:
        tracing_dependencies = (
            trace,
            OTLPSpanExporter,
            FastAPIInstrumentor,
            Resource,
            TracerProvider,
            BatchSpanProcessor,
        )
        if any(dependency is None for dependency in tracing_dependencies):
            raise ImportError

        # Create resource
        resource = Resource.create(
            {
                "service.name": config.observability.service_name,
                "service.version": "2.0.0",
                "deployment.environment": config.meta.environment,
            }
        )

        # Setup provider
        provider = TracerProvider(resource=resource)

        # Setup exporter
        exporter = OTLPSpanExporter(
            endpoint=config.observability.tracing.endpoint,
            insecure=True,  # Use TLS in production
        )

        # Add processor
        provider.add_span_processor(BatchSpanProcessor(exporter))

        # Set global provider
        trace.set_tracer_provider(provider)

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(application)

        print(f"OpenTelemetry tracing enabled: {config.observability.tracing.endpoint}")

    except ImportError:
        print("OpenTelemetry not installed, tracing disabled")
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        print(f"Failed to setup tracing: {exc}")


# ============================================================================
# APPLICATION INSTANCE
# ============================================================================

app = create_app()


# ============================================================================
# DEVELOPMENT SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.fastapi_app.main:app",
        host=config.server.host,
        port=config.server.fastapi_port,
        reload=config.is_development,
        log_level=config.observability.logging.level,
    )
