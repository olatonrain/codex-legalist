# Testing

## Test Suite Overview

123 test functions across 8 test files covering all major modules.

## Running Tests

```bash
make test            # pytest -v --tb=short
pytest               # same, via pytest.ini config
pytest tests/        # run all tests in tests/ directory
pytest -x            # stop on first failure
pytest --tb=long     # full traceback on failures
```

## Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_security.py` | 16 | Prompt injection detection — all known attack patterns |
| `tests/test_agents.py` | 12 | Agent name normalization, content sanitization, trial step routing |
| `tests/test_nodes.py` | 10 | Opening statements, evidence, witness, jury deliberation nodes with LLM mocks |
| `tests/test_comprehensive.py` | 71 | Phase transitions, routing logic, edge cases, error handling |
| `tests/test_server.py` | 6 | API endpoints — health, jurisdictions, file upload, injection detection |
| `tests/test_parser.py` | 3 | File extraction from TXT, empty files, unknown extensions |
| `test_graph.py` | 1 | LangGraph state graph construction |
| `test_trial_safety.py` | 4 | Insufficient record gate, speculative content prevention |

## Test Infrastructure

- **Framework:** pytest
- **Mocking:** `unittest.mock` with `MagicMock` — LLM calls mocked via `mock_llm` and `mock_structured_llm` fixtures in `tests/conftest.py`
- **API testing:** `fastapi.testclient.TestClient` for server endpoint tests
- **State fixture:** `mock_state` fixture provides a base `TrialState` with a simple car-theft case description

### Mock LLM Fixtures

LLM-dependent modules (`src.trial_phases`, `src.evidence`, `src.witness`, `src.jury`) have their `get_llm`/`get_structured_llm` imports patched:

```python
@pytest.fixture
def mock_llm():
    mock_instance = MagicMock()
    mock_instance.invoke.return_value = AIMessage(content="Mocked LLM response")
    ...
```

The mock returns `AIMessage(content="Mocked LLM response")` for all invocations. Tests verify routing logic, not LLM output quality.

## Linting

```bash
make lint            # ruff check src/ legalist/ server.py
make format          # ruff format src/ legalist/ server.py
make format-check    # ruff format --check src/ legalist/ server.py
```

Config in `pyproject.toml`: target `py310`, line-length `120`, rules `F, E, W, I, N` (E501 ignored).
