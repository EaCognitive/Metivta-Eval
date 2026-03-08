# MetivtaEval API Specification

This document reflects the currently implemented API surfaces in this repository.

## Canonical Sources

- FastAPI OpenAPI JSON: `/api/v2/openapi.json`
- FastAPI Scalar API reference: `/api/v2/docs`
- Flask compatibility endpoint: `POST /submit`

## Service Surfaces

### FastAPI v2 (primary)

- Auth: `/api/v2/auth/*`
- Evaluations: `/api/v2/eval/*`
- Leaderboard: `/api/v2/leaderboard/*`
- WebSocket: `/ws/events`
- Health: `/health`, `/ready`

### Flask compatibility (legacy)

- `POST /submit` (contract preserved for existing integrators)

## Authentication

FastAPI:

- `Authorization: Bearer <access_token>`
- or `X-API-Key: <api_key>`

Flask `/submit`:

- `Authorization: Bearer <api_key>`

## Contract Stability Notes

- `/submit` is intentionally retained for backward compatibility.
- New clients should use `/api/v2/*`.
- DAAT runtime reads the configured local JSON dataset; a remote LangSmith dataset is optional.
- `make compose-demo` is the supported Docker E2E verification path for this API surface.
- Schema/migration state is managed under `migrations/`.

## Example: submit compatibility request

```bash
curl -X POST http://localhost:8080/submit \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "author": "Your Name",
    "system_name": "Your System",
    "endpoint_url": "https://your-system.example.com/answer"
  }'
```
