# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-08-29
### Added
- Opt-in interpretation layer (`failurelab.interpret`) that turns a deterministic analysis into a written explanation. It is disabled by default, is never activated by the presence of an environment variable, makes exactly one provider call with no agent loop, and validates every response against a strict schema. Observations that cite evidence not present in the analysis are dropped, and a summary that does so is rejected outright.
- `InterpretationProvider` protocol plus a `FakeProvider` for testing, so the layer can be exercised without a model.
- Local Ollama provider using only the standard library, adding no dependency to an install.
- Anthropic provider behind the optional `failurelab[anthropic]` extra. The model must be named explicitly, the API key is read once at construction and never appears in a `repr`, provenance, or exception, and the client is built with retries disabled so one call means one billable request.
- Provider-neutral `provider_latency_ms`, measured with a monotonic clock around the single generate call.
- End-to-end RAG example under `examples/rag_pipeline/`: a Markdown corpus, deterministic chunking, BM25 retrieval with a title-boosted variant, an example-local generator protocol with scripted and Ollama implementations, and a citation-grounded evaluation that classifies each answer into exactly one outcome. It adds no dependencies, emits FailureLab-compatible traces, and ships three generated datasets that a test regenerates and compares byte for byte.
- Documentation site built with MkDocs and published to GitHub Pages, including a page for the RAG example and one for the interpretation layer.
- Public API additions: `failurelab.interpret` and `failurelab.InterpretationReport`. The rest of the public surface (`analyze`, `compare`, `validate`, and the report objects) is unchanged from 0.2.0.

### Changed
- Evidence sent to a provider excludes raw content and real trace identifiers by default. Hypotheses are referenced by pseudonym, and the alias map that resolves them stays local: `to_dict()` omits it unless aliases are explicitly requested.
- Continuous integration pins the exact versions of the tools whose rules gate it (ruff, mypy, bandit, codespell), so a new release of one of them arrives as a reviewable dependency update rather than turning open pull requests red with no change to review.
- Dependabot updates are grouped, which keeps interdependent actions such as CodeQL `init` and `analyze` moving together instead of deadlocking at mismatched versions.
- Branch protection is no longer mirrored in the repository. The exported ruleset JSON and its administrative documentation were removed, because a checked-in snapshot drifts silently from the live configuration. Contributor-facing expectations moved to `CONTRIBUTING.md`.

### Security
- `SECURITY.md` records the supported version line and states plainly that the interpretation layer transmits data to a third party when a hosted provider is configured.

## [0.2.0] - 2026-07-20
### Added
- Public Python API: `failurelab.analyze`, `failurelab.compare`, and `failurelab.validate`, returning in-memory `AnalysisReport`, `ComparisonReport`, and `ValidationReport` objects that perform no filesystem writes unless `write()` is called explicitly.
- Report projections (`to_dict`, `to_markdown`, and typed `to_*_dict` accessors), plus `data_quality.analyzable` and `ComparisonReport.is_comparable` signals so zero-usable-trace inputs are reported honestly rather than raising.
- In-memory ingestion that accepts an iterable of `TraceRecord` objects or mappings through a single normalization boundary, with a reproducible canonical SHA-256 digest recorded for in-memory inputs.
- Public exception types `FailureLabError`, `InvalidTraceDataError` (carrying the full issue list), and `ConfigError`.

### Changed
- The CLI `analyze` and `compare` commands now delegate to the public API. On-disk outputs, stdout, and exit codes are unchanged.
- `load_config` now raises `ConfigError`, a subclass of `ValueError`, so existing `except ValueError` handlers keep working.

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
