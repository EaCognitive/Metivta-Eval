# Deployment Guide

This repository supports two deployment paths:

- hosted deployment: Azure Container Apps or Render
- self-hosted deployment: Docker Compose via [docker-compose.yml](/Users/macbook/Desktop/untitled%20folder/temp/MetivitaEval/docker-compose.yml)

For turning this into your own benchmark product, see
[BUILD_YOUR_OWN_BENCHMARK.md](/Users/macbook/Desktop/untitled%20folder/temp/MetivitaEval/docs/BUILD_YOUR_OWN_BENCHMARK.md).

## 1. Local Docker Deployment

### Local development stack

```bash
make compose-dev
```

This brings up the normal local product surface without the demo answer service or demo seeder.

### Fast demo launch

```bash
make compose-demo
```

This brings up the full local product surface and runs a seeded end-to-end verification pass.

### Live fault verification

```bash
make compose-faults
```

This runs controlled Docker fault injection against the local stack, verifies the live HTTP
outcomes, and restores the seeded demo deployment at the end.

### Full local benchmark launch

```bash
docker compose --profile legacy --profile demo up -d --build
```

Use this when you want the full dataset instead of the two-example demo cap set by `make compose-demo`.

### Override the benchmark through Docker environment

You can inject a different benchmark without editing code by passing dataset and evaluator overrides
at launch time:

```bash
METIVTA_DATASET_NAME=My-Benchmark \
METIVTA_DATASET_LOCAL_PATH=/app/custom-dataset \
METIVTA_DATASET_FILES_QUESTIONS=questions.json \
METIVTA_DATASET_FILES_QUESTIONS_ONLY=questions-only.json \
METIVTA_EVALUATION_DAAT_EVALUATORS=hebrew_presence,url_format,response_length,daat_score \
docker compose --profile legacy --profile demo up -d --build
```

### Stop the stack

```bash
make compose-dev-down
```

Or, if you started the seeded demo stack:

```bash
make compose-demo-down
```

### Local URLs

- gateway: `http://localhost:18000`
- health: `http://localhost:18000/health`
- readiness: `http://localhost:18000/ready`
- Scalar docs: `http://localhost:18000/api/v2/docs`
- runtime signup page: `http://localhost:18080/signup`
- legacy leaderboard page: `http://localhost:18080/leaderboard`
- dataset info: `http://localhost:18080/dataset-info`

## 2. Render Deployment

Render blueprint file:

- [render.yaml](/Users/macbook/Desktop/untitled%20folder/temp/MetivitaEval/deploy/render.yaml)

Defined services:

- `metivta-fastapi`
- `metivta-flask`
- `metivta-worker`

### Required environment variables

Set these in the Render dashboard for the relevant services:

- `DATABASE_URL`
- `METIVTA_SECURITY_SECRET_KEY`
- `METIVTA_WORKER_BROKER`
- `METIVTA_WORKER_RESULT_BACKEND`

Optional integrations:

- `ANTHROPIC_API_KEY`
- `LANGCHAIN_API_KEY`
- `BROWSERLESS_TOKEN`

## 3. Azure Container Apps Deployment (Verified)

Azure Container Apps is fully supported and was validated with live hosted E2E checks for DAAT
and MTEB flows.

### Required resources

- one Azure Resource Group
- one Azure Container Apps Environment
- one Azure Container Registry
- Container Apps for:
  - gateway
  - fastapi
  - redis
  - postgres

### Production topology

- `gateway` is external and serves the public domain
- `fastapi` should be internal-only
- `redis` and `postgres` should be internal-only

### Public docs-only launch mode

Set the gateway environment variable:

```bash
PUBLIC_DOCS_ONLY=true
```

In this mode, public traffic is intentionally limited to:

- `/`
- `/api/v2/docs`
- `/api/v2/openapi.json`

### Maintainer docs host bundle

If you only want a public homepage, API reference, and guide for a maintainer-run promotional site
such as `metivta.co`, build this static bundle instead of publishing the full application runtime:

```bash
make site-build
```

This writes deployable files to `dist/static-site/`:

- `index.html`
- `guide/index.html`
- `signup/index.html`
- `api/v2/docs/index.html`
- `api/v2/openapi.json`

This is the correct artifact for Azure Static Web Apps, Azure Storage static website, or any other
static host. This bundle is for the maintainer-operated docs/promotional site, not for benchmark
operators running the full stack. Keep Azure Container Apps only when you want the public edge to
proxy the live app during internal verification.

### Full application test mode

For temporary hosted E2E testing of auth/eval/leaderboard routes, set:

```bash
PUBLIC_DOCS_ONLY=false
```

After validation, set it back to `true` for docs-only public launch if desired.

### Custom domain DNS records

For apex + `www` on Azure Container Apps:

- `@` A -> `<gateway static IP>`
- `www` CNAME -> `<gateway container app fqdn>`
- `asuid` TXT -> `<customDomainVerificationId>`
- `asuid.www` TXT -> `<customDomainVerificationId>`

Both `asuid` and `asuid.www` are required for managed certificate validation on apex and `www`.

## 4. Launch Verification Checklist

### Runnable stack checklist

Before calling a full application deployment ready:

1. `uv run ruff check .`
2. `uv run mypy src`
3. `uv run pytest -q`
4. `go test -race ./...`
5. `GET /health` returns healthy
6. `GET /ready` returns all required dependencies as ready
7. `GET /api/v2/docs` loads
8. `GET /signup` loads
9. `GET /leaderboard` loads
10. register -> login -> create API key works
11. at least one DAAT evaluation works
12. at least one MTEB evaluation works if retrieval mode is enabled

### Docs-only site checklist

Before calling the public promo/docs site ready:

1. `GET /` loads
2. `GET /guide` loads
3. `GET /api/v2/docs` loads
4. `GET /api/v2/openapi.json` loads
5. the site does not expose runtime auth or evaluation routes publicly

## 5. Notes

- `/submit` is retained for compatibility; new integrations should target `/api/v2/*`
- keep full ground-truth datasets private and publish safe question-only views publicly
- when you customize the benchmark harness, update `config.toml`, dataset files, and rubric files together
