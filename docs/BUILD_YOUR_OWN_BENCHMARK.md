# Build Your Own Benchmark

This repository can be used as a benchmark harness for your own model, retrieval pipeline, or
agentic workflow. The core pattern is:

1. define a dataset and scoring harness
2. host the MetivtaEval stack
3. let users register, obtain API keys, and submit their system endpoints
4. publish the leaderboard produced by the evaluation service

Everything in this guide maps to files and routes that exist in the current repository state.

Important:

- this guide is for the runnable self-hosted stack
- the public `metivta.co` site is documentation-only and is not the execution surface

## 1. Launch Locally Before Production

### Local development stack

```bash
make compose-dev
```

Use this for the normal product surface without the demo answer service or demo seeder.

### Seeded local UX check

```bash
make compose-demo
```

This starts the full local experience:

- gateway
- FastAPI v2
- Flask compatibility API
- Celery worker
- Postgres
- Redis
- demo answer service
- demo seeder

Important:

- `make compose-demo` sets `METIVTA_DATASET_MAX_EXAMPLES=2` so local verification finishes quickly.
- For a full local benchmark run, launch the same stack without that cap:

```bash
docker compose --profile legacy --profile demo up -d --build
```

### Live fault verification

```bash
make compose-faults
```

Use this before production to confirm that dataset misconfiguration, Redis outages, Postgres
outages, and invalid user endpoints degrade cleanly in the live stack.

### Stop the local stack

```bash
make compose-dev-down
```

For the seeded demo stack:

```bash
make compose-demo-down
```

### Useful local URLs

- gateway root: `http://localhost:18000`
- gateway health: `http://localhost:18000/health`
- gateway readiness: `http://localhost:18000/ready`
- Scalar docs: `http://localhost:18000/api/v2/docs`
- OpenAPI JSON: `http://localhost:18000/api/v2/openapi.json`
- runtime signup page: `http://localhost:18080/signup`
- legacy leaderboard page: `http://localhost:18080/leaderboard`
- dataset info: `http://localhost:18080/dataset-info`

### Change local host ports

If you want different local ports without editing code, override them at launch:

```bash
GATEWAY_PORT=28000 FLASK_PORT=28080 docker compose --profile legacy --profile demo up -d --build
```

That changes the host-facing URLs while leaving container-internal routing untouched.

### Inject a custom benchmark through Docker

If you do not want to edit `config.toml` for a one-off launch, Compose now passes through the
dataset and evaluator override environment variables used by the Python services:

```bash
METIVTA_DATASET_NAME=My-Benchmark \
METIVTA_DATASET_LOCAL_PATH=/app/custom-dataset \
METIVTA_DATASET_FILES_QUESTIONS=questions.json \
METIVTA_DATASET_FILES_QUESTIONS_ONLY=questions-only.json \
METIVTA_DATASET_FILES_FORMAT_RUBRIC=format_rubric.json \
METIVTA_EVALUATION_DAAT_EVALUATORS=hebrew_presence,url_format,response_length,daat_score \
docker compose --profile legacy --profile demo up -d --build
```

## 2. Pre-Production Checks

Before exposing the system publicly, verify these locally:

### Readiness

```bash
curl -fsS http://localhost:18000/ready | jq .
```

### Runtime signup page

```bash
curl -fsS http://localhost:18080/signup >/dev/null && echo signup_ok
```

### Dataset metadata

```bash
curl -fsS http://localhost:18080/dataset-info | jq .
```

### Endpoint validation

Use this to check whether a DAAT answer endpoint behaves like the configured dataset harness
expects:

```bash
curl -fsS \
  -X POST http://localhost:18080/validate-endpoint \
  -H 'Content-Type: application/json' \
  -d '{"endpoint_url":"http://demo-answer:5001/answer"}' | jq .
```

If you are validating a host-side service instead of a container service, use
`http://host.docker.internal:<port>/<path>` so the Flask container can reach it.

## 3. Where Users Get API Keys

The public documentation site does not issue API keys. There are two supported onboarding paths in
the runnable stack.

### Browser flow

- page: `GET /signup`
- submit: `POST /register`

This issues an API key immediately. That makes it the easiest onboarding flow when you want a
public submission page.

Verified legacy registration payload:

```json
{
  "email": "team@example.com",
  "name": "Team Name",
  "organization": "Optional Org"
}
```

### API-first flow

Users can also create accounts and issue scoped keys programmatically:

1. `POST /api/v2/auth/register`
2. `POST /api/v2/auth/login`
3. `POST /api/v2/auth/api-keys`

Use this path for first-party clients, automation, or productized integrations.

## 3A. What To Change For Common Customizations

| If you want to change... | Change this |
| --- | --- |
| benchmark name and version | `config.toml` -> `[dataset].name`, `[dataset].version` |
| DAAT questions and ground truth | `config.toml` -> `[dataset.files].questions` |
| public question-only export | `config.toml` -> `[dataset.files].questions_only` |
| scholarly rubric | `config.toml` -> `[dataset.files].format_rubric` |
| MTEB benchmark corpus/queries/qrels | `config.toml` -> `[dataset.mteb]` |
| default script target | `config.toml` -> `[evaluation].endpoint_url` |
| enabled DAAT evaluators | `config.toml` -> `[evaluation.daat].evaluators` |
| DAAT weight mix | `config.toml` -> `[evaluation.daat.weights]` |
| web validation behavior | `config.toml` -> `[evaluation.web_validator]` |
| scoring implementation | `src/metivta_eval/evaluators/` |

## 4. Which Endpoint Your Users Submit

There are two benchmark modes, and each has a different system contract.

### DAAT submission target

Your users submit an `endpoint_url` that accepts:

```http
POST /answer
Content-Type: application/json

{"question":"..."}
```

and returns:

```json
{"answer":"..."}
```

The submitted URL goes in the evaluation request body:

```json
{
  "system_name": "My QA System",
  "endpoint_url": "https://my-system.example.com/answer",
  "mode": "daat"
}
```

### MTEB submission target

Your users submit an `endpoint_url` that accepts:

```http
POST /retrieve
Content-Type: application/json

{"query":"...","top_k":100}
```

and returns:

```json
{
  "results": [
    {"id":"doc_1","score":0.91},
    {"id":"doc_2","score":0.77}
  ]
}
```

The submitted URL goes in the evaluation request body:

```json
{
  "system_name": "My Retriever",
  "endpoint_url": "https://my-system.example.com/retrieve",
  "mode": "mteb"
}
```

## 5. Where To Change the Dataset

The main control plane for datasets is [config.toml](/Users/macbook/Desktop/untitled%20folder/temp/MetivitaEval/config.toml).

### DAAT dataset settings

Change these keys:

```toml
[dataset]
name = "My-Benchmark"
version = "1.0"
local_path = "src/metivta_eval/dataset"

[dataset.files]
questions = "my-dataset.json"
questions_only = "my-questions-only.json"
format_rubric = "my-format-rubric.json"
```

What each file does:

- `questions`
  Main DAAT dataset used for runtime evaluation
- `questions_only`
  Safe question template for public distribution
- `format_rubric`
  Scholarly-format rubric used by the standards evaluator

Expected DAAT dataset shape:

```json
[
  {
    "inputs": {"question": "Your benchmark question"},
    "outputs": {"answer": "Ground-truth answer"}
  }
]
```

The loader also accepts simplified input like:

```json
[
  {
    "question": "Your benchmark question",
    "answer": "Ground-truth answer"
  }
]
```

### MTEB dataset settings

Change these keys:

```toml
[dataset.mteb]
corpus = "mteb/corpus.jsonl"
queries = "mteb/queries.jsonl"
qrels = "mteb/qrels.tsv"
```

That lets you publish your own retrieval benchmark and leaderboard.

## 6. Where To Change the Evaluation Harness

### DAAT evaluator profile

You can now choose the DAAT evaluator set from `config.toml`:

```toml
[evaluation.daat]
enabled = true
evaluators = ["all"]
```

Available evaluator keys in the current repo:

- `hebrew_presence`
- `url_format`
- `response_length`
- `scholarly_format`
- `correctness`
- `web_validation`
- `daat_score`

### Deterministic DAAT profile

If you want a more deterministic harness with no LLM-backed or remote-browser-backed scoring, use:

```toml
[evaluation.daat]
enabled = true
evaluators = ["hebrew_presence", "url_format", "response_length", "daat_score"]
```

That keeps the benchmark centered on:

- local dataset loading
- code-based checks
- deterministic DAAT attribution scoring

### DAAT weight tuning

You can tune the composite DAAT weighting here:

```toml
[evaluation.daat.weights]
dai = 0.60
mla = 0.40
```

### Web validation tuning

You can tune or disable web validation here:

```toml
[evaluation.web_validator]
enabled = true
timeout_ms = 15000
min_keyword_matches = 15
concurrency = 5
```

### Deeper scoring changes

If you want to change scoring logic itself, the main implementation points are:

- [code_evaluators.py](/Users/macbook/Desktop/untitled%20folder/temp/MetivitaEval/src/metivta_eval/evaluators/code_evaluators.py)
- [standards_evaluators.py](/Users/macbook/Desktop/untitled%20folder/temp/MetivitaEval/src/metivta_eval/evaluators/standards_evaluators.py)
- [controlled_evaluators.py](/Users/macbook/Desktop/untitled%20folder/temp/MetivitaEval/src/metivta_eval/evaluators/controlled_evaluators.py)
- [daat_evaluator.py](/Users/macbook/Desktop/untitled%20folder/temp/MetivitaEval/src/metivta_eval/evaluators/daat_evaluator.py)
- [mteb_evaluators.py](/Users/macbook/Desktop/untitled%20folder/temp/MetivitaEval/src/metivta_eval/evaluators/mteb_evaluators.py)

## 7. Where To Change Runtime Targets

There are two places people often confuse:

- the **submitted system URL**
  This is per-evaluation input and lives in the request body as `endpoint_url`
- the **local evaluation target**
  This is the default system target used by script-based local evaluation commands

The script-level target is configured here:

```toml
[evaluation]
target = "endpoint"
endpoint_url = "http://localhost:5001/answer"
dev_mode = false
```

Use that when you want to run local harness checks against a specific system without going through
the public submission path.

## 8. How To Launch Your Own Leaderboard

Once you have your dataset and evaluator profile set:

1. update `config.toml`
2. replace the dataset files under your chosen `dataset.local_path`
3. launch the stack locally
4. verify `/ready`, `/dataset-info`, `/signup`, `/api/v2/docs`, and `/leaderboard`
5. create a user and issue an API key
6. submit DAAT or MTEB systems
7. publish the leaderboard URL

The two leaderboard surfaces are:

- modern API: `/api/v2/leaderboard/`
- legacy browser dashboard: `/leaderboard`

## 9. Production Notes

- use the FastAPI v2 surface for new clients
- keep `/submit` only if you need backward compatibility
- keep full-answer datasets private and publish `questions_only` templates publicly
- pin your evaluator profile in `config.toml` so public submissions are scored consistently
- treat the README and this guide as operator contracts; verify every public instruction after
  changing dataset, evaluators, or routes
