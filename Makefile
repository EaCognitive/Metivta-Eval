.PHONY: \
	help setup clean \
	lint format typecheck pylint \
	test-py test-go test test-all test-cov \
	check \
	run-fastapi run-flask run-gateway \
	run-api run-mock-api run-evaluation \
	build-cli build-gateway \
	site-build site-preview \
	dataset-upload sync-dataset show-questions validate-submission evaluate-submission \
	generate-leaderboard test-pipeline test-100 \
	compose-dev compose-dev-down compose-dev-logs \
	compose-up compose-down compose-logs \
	compose-demo compose-demo-down compose-demo-logs compose-faults \
	openapi-generate

help:
	@echo "MetivitaEval Make Targets"
	@echo "========================="
	@echo ""
	@echo "Setup"
	@echo "  setup             Install Python dependencies and editable package"
	@echo "  clean             Remove local cache and transient files"
	@echo ""
	@echo "Quality"
	@echo "  lint              Run Ruff, Pylint, and golangci-lint"
	@echo "  format            Format Python and Go sources"
	@echo "  typecheck         Run mypy on src/"
	@echo "  pylint            Run repo Pylint gate"
	@echo ""
	@echo "Tests"
	@echo "  test-py           Run Python pytest suite"
	@echo "  test-go           Run Go race tests"
	@echo "  test              Run Python + Go tests"
	@echo "  test-cov          Run Python tests with coverage"
	@echo "  check             Run full local quality gate set"
	@echo ""
	@echo "Run Services"
	@echo "  run-fastapi       Start FastAPI on :8001"
	@echo "  run-flask         Start Flask compatibility API on :8080"
	@echo "  run-gateway       Start Go gateway on :8000"
	@echo "  run-api           Alias for run-flask"
	@echo "  run-mock-api      Start mock user API on :5001"
	@echo "  run-evaluation    Run script-based LangSmith evaluation"
	@echo ""
	@echo "Build"
	@echo "  build-cli         Build metivta CLI binary"
	@echo "  build-gateway     Build metivta-gateway binary"
	@echo "  site-build        Build the internal promo/docs site into dist/static-site"
	@echo "  site-preview      Preview the internal promo/docs site locally on :4080"
	@echo ""
	@echo "Legacy Helpers"
	@echo "  dataset-upload    Upload configured dataset to LangSmith"
	@echo "  sync-dataset      Alias for dataset-upload"
	@echo "  show-questions    Print local question template"
	@echo "  validate-submission FILE=<path>   Validate submission structure"
	@echo "  evaluate-submission FILE=<path>   Validate then prepare submission"
	@echo "  generate-leaderboard  Build static leaderboard HTML from local file"
	@echo "  test-pipeline     Run evaluation with ground_truth target"
	@echo "  test-100          Alias for test-pipeline"
	@echo ""
	@echo "Docker Compose"
	@echo "  compose-dev       Start local development stack"
	@echo "  compose-dev-down  Stop local development stack"
	@echo "  compose-dev-logs  Tail local development stack logs"
	@echo "  compose-demo      Start seeded demo stack with leaderboard dashboard"
	@echo "  compose-demo-down Stop seeded demo stack"
	@echo "  compose-demo-logs Tail demo seeder logs"
	@echo "  compose-faults    Run live Docker fault-injection verification and restore demo stack"
	@echo "  compose-up        Compatibility alias for compose-dev"
	@echo "  compose-down      Compatibility alias for compose-dev-down"
	@echo "  compose-logs      Compatibility alias for compose-dev-logs"
	@echo ""
	@echo "Docs"
	@echo "  openapi-generate  Regenerate api/docs/openapi-spec.yaml from FastAPI"

setup:
	uv sync --dev
	uv pip install -e .

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

lint:
	uv run ruff check .
	PYTHONPATH=src:. uv run pylint api src tests
	golangci-lint run ./...

format:
	uv run ruff format .
	gofmt -w $$(find . -name '*.go' -not -path './.git/*' -not -path './.venv/*')

typecheck:
	uv run mypy src/

pylint:
	PYTHONPATH=src:. uv run pylint api src tests

test-py:
	uv run pytest -q

test-go:
	go test -race ./...

test: test-py test-go

test-all: test

test-cov:
	uv run pytest --cov=src --cov-report=term --cov-report=xml:/tmp/metivta_coverage.xml -q

check:
	uv run ruff check .
	uv run ruff format --check .
	PYTHONPATH=src:. uv run pylint api src tests
	uv run mypy src/
	uv run pytest -q
	golangci-lint run ./...
	go test -race ./...

run-fastapi:
	PYTHONPATH=src:. uv run uvicorn api.fastapi_app.main:app --host 0.0.0.0 --port 8001

run-flask:
	PYTHONPATH=src:. uv run python api/server.py

run-gateway:
	go run ./cmd/metivta-gateway

run-api: run-flask

run-mock-api:
	uv run python tests/mock_user_api.py

run-evaluation:
	uv run python -m metivta_eval.scripts.run_evaluation unified all

build-cli:
	go build -o metivta ./cmd/metivta

build-gateway:
	go build -o metivta-gateway ./cmd/metivta-gateway

site-build:
	rm -rf dist/static-site
	mkdir -p dist/static-site
	cp -R cmd/metivta-gateway/public/. dist/static-site/

site-preview: site-build
	cd dist/static-site && python3 -m http.server 4080

compose-dev:
	docker compose --profile legacy up -d --build

compose-up: compose-dev

compose-dev-down:
	docker compose --profile legacy down

compose-down: compose-dev-down

compose-dev-logs:
	docker compose --profile legacy logs -f

compose-logs: compose-dev-logs

compose-demo:
	METIVTA_DATASET_MAX_EXAMPLES=$${METIVTA_DATASET_MAX_EXAMPLES:-2} \
	docker compose --profile legacy --profile demo up -d --build

compose-demo-down:
	docker compose --profile legacy --profile demo down

compose-demo-logs:
	docker compose --profile legacy --profile demo logs -f demo-seeder

compose-faults:
	uv run python -m metivta_eval.scripts.verify_docker_faults

dataset-upload:
	uv run python -m metivta_eval.scripts.upload_dataset

sync-dataset: dataset-upload

show-questions:
	uv run python -m metivta_eval.scripts.show_questions

validate-submission:
	@if [ -z "$(FILE)" ]; then \
		echo "FILE is required. Example: make validate-submission FILE=dataset/test-user-submissions.json"; \
		exit 1; \
	fi
	uv run python -m metivta_eval.scripts.prepare_submission $(FILE)

evaluate-submission: validate-submission

generate-leaderboard:
	uv run python -m api.handlers.generate_leaderboard

test-pipeline:
	METIVTA_EVALUATION_TARGET=ground_truth \
	uv run python -m metivta_eval.scripts.run_evaluation unified all

test-100: test-pipeline

openapi-generate:
	METIVTA_DATABASE_URL=sqlite:////tmp/metivta_openapi.db \
	uv run python -c "import json, yaml; from pathlib import Path; from api.fastapi_app.main import create_app; spec=create_app().openapi(); Path('api/docs').mkdir(parents=True, exist_ok=True); Path('cmd/metivta-gateway/public/api/v2').mkdir(parents=True, exist_ok=True); Path('api/docs/openapi-spec.yaml').write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding='utf-8'); Path('api/docs/openapi-spec.json').write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8'); Path('cmd/metivta-gateway/public/api/v2/openapi.json').write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')"
