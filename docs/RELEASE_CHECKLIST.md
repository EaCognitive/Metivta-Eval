# Public Release Checklist

## Security

- [ ] `gitleaks` scan passes on full repo.
- [ ] No tracked `.env` files contain real credentials.
- [ ] All previously exposed credentials rotated.
- [ ] API keys stored hashed-only in database.

## Quality Gates

- [ ] `uv run ruff check .`
- [ ] `uv run ruff format --check .`
- [ ] `uv run mypy src/`
- [ ] `uv run pytest -q`
- [ ] `go test -race ./...`
- [ ] `golangci-lint run ./...`

## Runtime and Deployment

- [ ] FastAPI app starts and serves `/api/v2/docs`.
- [ ] Flask app starts and serves `/submit`.
- [ ] Docker Compose local profile is healthy.
- [ ] Render staging smoke tests pass.

## Documentation

- [ ] README architecture matches shipped code.
- [ ] API docs include `/submit` compatibility and `/api/v2/*`.
- [ ] Environment variable documentation is current.

## Launch

- [ ] Create release tag with changelog.
- [ ] Push sanitized public repository.
