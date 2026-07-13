# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-07-12
### Added
- Typed trace and agent-step contracts using Pydantic v2, with strict JSON validation
- Incremental JSONL ingestion with strict and skip-invalid modes, reporting invalid rows separately
- Deterministic metrics with explicit numerator, denominator, eligibility, and unavailable-reason semantics
- Deterministic failure-slice discovery restricted to elevated-failure segments
- Deterministic root-cause heuristics generated only for explicitly failed traces
- Draft regression test generation in YAML, tied to failed traces with concrete replay input and source provenance
- Baseline vs candidate comparison with full-dataset and matched-ID scopes, metric deltas, and tri-state gates
- Typer CLI (`validate`, `analyze`, `compare`) with defined exit codes
- JSON, Markdown, and YAML report outputs, plus run manifests recording the effective resolved configuration
- Deterministic skill interfaces and a routing investigation agent
- Privacy-conscious defaults: raw prompts, answers, retrieved context, and tool arguments excluded from reports unless explicitly enabled
- GitHub Actions CI covering lint, type checking, tests across Python 3.11 to 3.14, cross-platform smoke tests, packaging checks, and security scanning (pip-audit, Bandit, CodeQL)
- Branch protection through a GitHub ruleset (protect-main), tracked in the repository as a version-controlled export snapshot
- PyPI publishing through GitHub Actions trusted publishing (OIDC), with no stored tokens
- CLAUDE.md and the `/failurelab-execute` skill for a consistent project-scoped implementation workflow
