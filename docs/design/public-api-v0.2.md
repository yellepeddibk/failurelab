# ADR: Public Python API (v0.2.0)

Status: accepted. Supersedes the CLI-only usage model of v0.1.

## Context

Through v0.1 FailureLab was usable only through its Typer CLI. The analysis
pipeline was coupled to the filesystem: `services.pipeline.analyze` and
`compare` took an input path and forced writes to an output directory, and the
package root exported only `__version__`. There was no way to pass in-memory
traces or to obtain results without writing files, so FailureLab could not be
imported and used as a library (the pandas or numpy usage model).

## Decision

Introduce a typed, importable Python API that performs no filesystem writes.
Persistence becomes an explicit, opt-in `write()` on the returned report. The
CLI keeps its exact behavior by delegating to the API and then calling
`write()`. Existing CLI payloads, file ordering, stdout, and exit-code behavior
are preserved. Deterministic output content matches the tracked v0.1 samples;
physical line endings remain platform dependent, because the atomic writer uses
text mode and Windows normalizes `\n` to `\r\n` (unchanged from v0.1). The
manifest differs only in the expected package version and `run_timestamp`
fields. A literal cross-platform byte comparison would require running the old
and new implementations on the same platform and interpreter.

### Boundaries

```
input normalization -> pure analysis engine -> report objects -> persistence (opt-in)
   (api.py)              (services.pipeline)     (reports.models)    (report.write)
```

- `api.analyze`, `api.compare`, `api.validate` normalize input at one boundary
  and return report objects. They never write.
- `services.pipeline.run_analysis(traces, config)` is the pure, side-effect-free
  engine shared by the API and the CLI compatibility wrappers.
- `reports.models` holds the report classes. Their `write()` methods are the
  single disk-writing path; the CLI and the API converge on it, so there is no
  second implementation to diverge.

### Public surface

Top-level exports (`failurelab.__all__`): `analyze`, `compare`, `validate`,
`load_config`, `AnalysisReport`, `ComparisonReport`, `ValidationReport`,
`FailureLabConfig`, `TraceRecord`, `AgentStep`, `FailureLabError`,
`InvalidTraceDataError`, `ConfigError`, `__version__`.

Stability policy: the top-level exports, together with the documented result
types at their documented submodule paths (`MetricResult`, `FailureSlice`,
`RootCauseHypothesis`, `RegressionCase`, `ValidationIssue`, `GateViolation`),
are the public API, because they appear on public report attributes. All other
modules are internal and may change without notice.

### Signatures

```python
TraceInput = str | os.PathLike[str] | Iterable[TraceRecord | Mapping[str, Any]]

def validate(source: TraceInput) -> ValidationReport
def analyze(source: TraceInput, *, config: FailureLabConfig | None = None,
            strict: bool | None = None) -> AnalysisReport
def compare(baseline: TraceInput, candidate: TraceInput, *,
            config: FailureLabConfig | None = None) -> ComparisonReport
```

### Report objects

Frozen dataclasses with tuple-backed collections, so the top-level report is a
read-only view (the nested `breakdowns` mapping and contained dataclasses are
not deeply frozen; this is stated rather than overclaimed). `AnalysisReport`
deliberately does not retain raw traces: it exposes `data_quality`, `issues`,
and `provenance`, which also honors the privacy default that raw content stays
out of reports. `ComparisonReport` exposes typed `gate_status` / `gate_scope`
(Literals), `baseline_data_quality` / `candidate_data_quality`, and
`is_comparable`.

### Semantics decided during review

- Strict mode: `analyze` and `compare` raise `InvalidTraceDataError` (carrying the
  full issue list) when strict ingestion finds problems. Skip-invalid returns a
  report over the valid subset that carries the issues. `strict` defaults to
  `None`, inheriting the configured mode, which defaults to strict.
- Zero usable traces: signal, do not raise. Empty or all-invalid (under
  skip-invalid) input returns an honest report with unavailable statistics and
  `data_quality.analyzable == False`; `ComparisonReport.is_comparable` is false
  when either side is not analyzable. This preserves the existing
  unavailable-metrics contract and the CLI exit-0 behavior for empty input. No
  `on_empty` argument and no `raise_for_no_data()` helper were added.
- Provenance digest: file inputs keep their existing digest of file bytes
  (`None` only when the path cannot be read). In-memory inputs get a
  reproducible canonical SHA-256 over the normalized traces, so determinism
  holds for both input modes.
- `load_config` raises `ConfigError`, a `ValueError` subclass, so existing
  handlers keep working.

## Compatibility exception

The CLI `validate` command continues to call `ingest_jsonl` directly rather
than the public `validate`. This is intentional: the command's strict mode
stops at the first invalid row and reports counts that reflect that early stop,
whereas `failurelab.validate` always inspects the complete input and reports
every issue. Routing the command through the library `validate` would change
its printed counts, so the lower-level path is preserved for byte-identical
output.

## Deferred to a 0.2.x follow-up

Typed comparison models were intentionally not built in this change, to keep the
API-establishing PR reviewable and to avoid re-serializing the comparison
summary across a large surface. Tracked follow-up work:

- Replace the provisional `ComparisonReport.summary: Mapping[str, object]` with a
  typed `ComparisonSummary` model.
- Introduce a typed `MetricDelta` for `full_dataset_deltas` and
  `matched_id_deltas`.
- Define a typed model for `AnalysisReport.breakdowns` (currently a documented
  provisional structured mapping).

The rendered JSON must stay identical when these are introduced.

## Consequences

- Version bumps to 0.2.0 (new public API; no breaking change for CLI users).
- FailureLab can now be used from notebooks and pipelines without shelling out.
- Two entry points (API and CLI) share one engine and one write path, so
  outputs cannot drift between them.
