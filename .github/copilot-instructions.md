# Copilot instructions for FailureLab

- Prioritize: AI engineering, data science, data engineering, software engineering.
- Keep deterministic core logic in typed services and skills.
- Support Python 3.11-3.14.
- Commands:
  - `python -m pip install -e ".[dev]"`
  - `ruff check .`
  - `ruff format --check .`
  - `mypy src`
  - `pytest`
  - `python -m build`
- No network in core tests.
- Never fabricate metrics, significance, or causality.
- Exclude raw query/context content from reports by default.
- Never weaken CI, security checks, or coverage expectations.
- Never add AI signatures, co-author trailers, or AI authorship statements.
