# Contributing

## Code Conventions

- **Python:** Follow PEP 8 with a max line length of 120 characters.
- **Type hints:** Use `from __future__ import annotations` in all Python files. Use `TrialState` typed dict for state mutations.
- **Imports:** Standard library first, then third-party, then local. Use absolute imports.
- **Error handling:** Use `logger.error` with `exc_info=True`. All API errors must return JSON, never HTML.
- **Security:** Never hardcode secrets. Use `.env` with `QWEN_API_KEY`. Always run `detect_prompt_injection` on user input.

## Build/Test/Lint/Deploy Commands

All commands are verified from the project's `Makefile`, `requirements.txt`, `Dockerfile`, and shell scripts:

```bash
# Setup
make setup                    # pip install -r requirements.txt
python3 -m venv venv          # or create venv manually

# Test
make test                     # pytest
pytest                        # direct invocation

# Lint
make lint                     # ruff check src/ legalist/ server.py --max-line-length=120

# Run locally
make run                      # uvicorn server:app --reload --port 8000
uvicorn server:app --reload --port 8000   # direct invocation

# Deploy (manual)
./deploy.sh                   # local deployment with venv setup
./deploy.sh --port 8080       # custom port
./deploy.sh --no-reload       # production mode (no hot-reload)

# Deploy (Docker)
./deploy-docker.sh            # builds image, replaces container

# Benchmark
make benchmark                # live (requires QWEN_API_KEY)
make benchmark-mock           # mock mode (no API key needed)
python legalist/benchmark.py --mock
```

## PR Workflow

1. Create a feature branch from `main`.
2. Make changes, following code conventions above.
3. Run tests: `make test`.
4. Run lint: `make lint`.
5. Update relevant documentation files (see `AGENTS.md` "Documentation Sync" table).
6. Mark AI-generated additions with `<!-- agent-updated -->` inline.
7. Commit with a descriptive message.
8. Push and open a pull request against `main`.

## Tests

- Tests live in `tests/` or root-level `test_*.py` files.
- Configured via `pytest.ini`: `testpaths = tests .`, verbose output with short tracebacks.
- Run with `make test` or `pytest`.
- Benchmark: `make benchmark` or `make benchmark-mock`.
