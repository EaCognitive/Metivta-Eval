"""
MetivitaEval FastAPI Application.

This is the modern Python API service that provides:
- RESTful evaluation endpoints
- WebSocket real-time updates
- OpenAPI documentation
- Prometheus metrics
- OpenTelemetry tracing
"""

from .main import app

__all__ = ["app"]
__version__ = "2.0.0"
