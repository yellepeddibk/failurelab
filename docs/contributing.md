# Contributing

FailureLab welcomes focused, well-tested contributions. See the repository's
[CONTRIBUTING.md](https://github.com/yellepeddibk/failurelab/blob/main/CONTRIBUTING.md)
and [Code of Conduct](https://github.com/yellepeddibk/failurelab/blob/main/CODE_OF_CONDUCT.md)
for the full workflow, and the
[releasing guide](https://github.com/yellepeddibk/failurelab/blob/main/docs/RELEASING.md)
for maintainers.

Core principles:

- Deterministic and offline by default: no LLM, network, database, or server in the core analysis.
- Never weaken tests, typing, linting, or security checks.
- Prefer the smallest complete change; no drive-by cleanup.
- No causal, significance, or production-readiness claims.

## Local checks

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy src
pytest
```

## Building the docs

```bash
python -m pip install -e ".[docs]"
mkdocs serve      # live preview at http://127.0.0.1:8000
mkdocs build --strict
```
