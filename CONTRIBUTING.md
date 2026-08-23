# Contributing to FailureLab

## Mission

Help build deterministic, trustworthy AI reliability tooling for RAG and agent systems.

## Contribution guidelines

- Open an issue first for large changes.
- Never include sensitive or proprietary traces.
- Review generated code before submitting.

## Setup

```bash
python -m pip install -e ".[dev]"
pre-commit install
```

## Commands

```bash
ruff check .
ruff format --check .
mypy src
pytest
python -m build
twine check dist/*
```

## Architecture principles

- Deterministic metrics and transforms under typed contracts
- Agent layer consumes deterministic skills instead of duplicating metric logic
- Keep null as null; do not fabricate missing values

## Adding functionality

- New metrics must include clear denominators and eligibility logic.
- New trace fields require typed model updates and tests.
- New skills must use typed payload/result and deterministic behavior.

## Branch and commit conventions

- Branch prefixes: `feat/`, `fix/`, `docs/`, `test/`, `refactor/`, `chore/`, `ci/`
- Conventional-style commits are encouraged (`feat:`, `fix:`, etc.).
- Changes reach `main` only through a pull request. Direct commits are not accepted.
- Required CI checks must pass before a pull request can merge.
- History on `main` is linear.
- Rebase and Merge is the default, so the branch history is preserved. Squash and Merge is
  the exception, used when the branch history should not be kept.

## PR checklist

- Tests added/updated
- Lint/type/tests/build pass locally
- Docs updated
- No sensitive data in fixtures

See also [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md), and [SUPPORT.md](SUPPORT.md).
