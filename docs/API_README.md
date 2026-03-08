# MetivtaEval API Reference (Repository State)

This document summarizes the API surfaces currently implemented in this repository.

## Services

- FastAPI v2 (primary): `api/fastapi_app/main.py`
- Flask compatibility API (legacy): `api/server.py`

## FastAPI v2 Base Paths

- `/health`, `/ready`, `/`
- `/api/v2/auth/*`
- `/api/v2/eval/*`
- `/api/v2/leaderboard/*`
- `/ws/events`

Interactive docs:

- `/api/v2/docs` (Scalar)
- `/api/v2/openapi.json`

## Flask Compatibility Endpoint

- `POST /submit`
- `GET /status/<task_id>` for async submission polling

This route remains available for backward compatibility and keeps the historical request/response contract.

## Authentication

FastAPI supports:

- Bearer access token (`Authorization: Bearer <token>`)
- API key (`X-API-Key: <key>`)

Flask `/submit` currently expects:

- API key in Bearer format (`Authorization: Bearer <api_key>`)

## Example: Register + Login + List Evaluations

```bash
curl -X POST http://localhost:8001/api/v2/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email":"user@example.com",
    "name":"User Name",
    "password":"<your-local-password>"
  }'

TOKENS=$(curl -s -X POST http://localhost:8001/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"<your-local-password>"}')

ACCESS=$(echo "$TOKENS" | jq -r '.access_token')

API_KEY=$(curl -s -X POST http://localhost:8001/api/v2/auth/api-keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS" \
  -d '{"name":"default","scopes":["eval:read","eval:write"]}' | jq -r '.key')

curl -H "Authorization: Bearer $ACCESS" \
  http://localhost:8001/api/v2/eval/
```

## Example: `/submit` Compatibility

```bash
curl -X POST http://localhost:8080/submit \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <api_key>" \
  -d '{
    "author": "Your Name",
    "system_name": "Your System",
    "endpoint_url": "https://your-system.example.com/answer"
  }'
```

Async variant:

```bash
curl -X POST \"http://localhost:8080/submit?async=true\" \
  -H \"Content-Type: application/json\" \
  -H \"Authorization: Bearer <api_key>\" \
  -d '{\n    \"author\": \"Your Name\",\n    \"system_name\": \"Your System\",\n    \"endpoint_url\": \"https://your-system.example.com/answer\"\n  }'
```

## Notes

- New integrations should target `/api/v2/*`.
- `/submit` should be preserved for existing integrations and migration safety.
- DAAT evaluations load the configured local JSON dataset at runtime.
- LangSmith is optional and is used only for explicit dataset sync or tracing flows.
- `make compose-demo` is the repo's verified Docker E2E deployment check.
- Render and Docker deployment manifests live in `deploy/` and `docker-compose.yml`.
