# CLAUDE.md

Guidance for Claude Code in this repository. Use this file as an index: read the pointed file before changing the area it covers, instead of rediscovering the repository each session. The procedure for verifying a change against real generated artifacts lives in `.claude/skills/failurelab-verify/SKILL.md`; this file does not duplicate it. Cross-repo maintainer preferences and the generic implementation lifecycle are intentionally omitted. This file contains only FailureLab-specific requirements.

## Project

FailureLab is a local-first, deterministic AI reliability toolkit for RAG and agent traces. It finds elevated failure slices, produces evidence-backed root-cause hypotheses, drafts replayable regression tests, and compares baseline and candidate runs. Python 3.11 to 3.14, MIT license, Typer CLI (`failurelab validate | analyze | compare`).

## Hard constraints

- Core analysis stays deterministic and offline: no network calls, database, web server, frontend, or agent framework in the core. The opt-in interpretation layer (`failurelab.interpret`, `src/failurelab/llm/`) may call a user-constructed LLM provider, but it is off by default, never activated by environment presence, sends no raw content or trace IDs by default, makes exactly one call with no agent loop, performs no network call in core CI, and keeps provider SDKs in optional per-provider extras. No other LLM, network, database, web server, frontend, or agent-framework additions unless the maintainer explicitly requests them.
- Never claim causal inference, statistical significance, guaranteed root-cause identification, or production readiness.
- Never weaken tests, typing, linting, security checks, or CI to make something pass.
- Prefer the smallest complete change. No drive-by cleanup, reformatting, or dependency bumps outside the task.

## Repository index

| Area | Path | Reference doc |
| --- | --- | --- |
| Trace contracts (Pydantic) | `src/failurelab/models/trace.py` | `docs/trace-schema.md` |
| JSONL ingestion, strict vs skip_invalid | `src/failurelab/ingestion/jsonl.py` | |
| Metrics with denominator semantics | `src/failurelab/evals/metrics.py` | `docs/metrics.md` |
| Failure-slice discovery | `src/failurelab/discovery/slices.py` | |
| Root-cause heuristics | `src/failurelab/root_cause/analyzer.py` | |
| Regression draft generation | `src/failurelab/regression/generator.py` | `docs/regression-tests.md` |
| Baseline vs candidate comparison, gates | `src/failurelab/comparison/service.py` | |
| Report writers, manifests | `src/failurelab/reports/writers.py` | `docs/privacy.md` |
| Orchestration for CLI commands | `src/failurelab/services/pipeline.py` | `docs/architecture.md` |
| Deterministic skills and investigation agent | `src/failurelab/agents/skills.py` | `docs/agent-architecture.md` |
| Optional interpretation layer (opt-in LLM) | `src/failurelab/llm/` | `docs/interpretation.md` |
| Typer CLI and exit codes | `src/failurelab/cli/app.py` | |
| Config models and loading | `src/failurelab/config/settings.py` | |
| Tests (unit, integration, golden, property, smoke) | `tests/` | |
| Sample traces and outputs | `examples/` | |
| Release process | | `docs/RELEASING.md` |

## Semantic contracts

These behaviors were deliberately designed and must not regress:

- Config precedence: built-in defaults, then config file, then explicit CLI overrides. `run_manifest.json` records the effective resolved configuration, not the raw file config.
- Ingestion: `strict` fails per the strict contract; `skip_invalid` continues past invalid rows and reports them. `generated_files` lists every file actually emitted; `invalid_traces.jsonl` appears only when generated.
- Failure slices contain only elevated failure: enough support, known outcomes, at least one failure, failure rate above global, positive uplift, relative risk above 1 when computable. Neutral and protective groups belong in breakdowns, never in `failure_slices`.
- Root-cause hypotheses are generated only for explicitly failed traces. Successful traces get no diagnosis. Specific rules beat the low-confidence fallback, which applies only to failed traces with no matching rule.
- Regression drafts require an explicitly failed source trace with concrete nonempty replay input, deterministic IDs and ordering, provenance (`source_trace_id`), and `draft` status. Never generate empty inputs, synthetic prompts, cases from successful traces, or duplicates.
- Unavailable metrics: counts may be 0, but observation-dependent statistics are `null` with a semantically correct denominator, `eligible_count: 0`, the real excluded count, and an `unavailable_reason`. Never fake a denominator of 1.
- Comparison gates are tri-state: `not_configured`, `passed`, `failed`. With no thresholds, `gate_passed` is `null` in JSON and Markdown says not evaluated / not applicable. Markdown must never print Python values such as `None`, and should avoid binary float artifacts.
- Privacy: `include_content` defaults to false. Raw prompts, answers, retrieved context, and tool arguments stay out of reports by default. Manifests use safe filenames, not absolute paths.
- Determinism of the core: the same input produces the same analysis output, with stable ordering and stable identifiers, and no dependence on wall-clock time or randomness. This guarantee covers the deterministic core only. The opt-in interpretation layer calls a live provider whose output is not reproducible; it is recorded with provenance rather than treated as stable.

## Commands

```bash
source .venv/Scripts/activate   # Git Bash on Windows
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy src
pytest -q
pre-commit run --all-files
python -m build
```

Coverage is collected (`--cov=failurelab --cov-branch`) but no fail-under threshold is enforced. Report actual coverage honestly; do not invent a threshold.

## Workflow

Cross-repo maintainer preferences are intentionally omitted here. This section covers only
FailureLab-specific requirements. General branch and commit conventions are in
`CONTRIBUTING.md`.

- Run `ruff check .`, `mypy src`, and `pytest` before each substantive commit; the suite
  takes roughly 12 seconds. The full gate before a pull request adds `ruff format --check .`,
  `python -m build`, and `pre-commit run --all-files`.
- Run `pre-commit run --all-files` whenever the environment can install and run the hooks.
  When it cannot, run the equivalent checks directly (ruff, ruff format, codespell, and the
  file hygiene checks), state plainly that `pre-commit` itself did not run, and treat a green
  CI run as required before merge rather than optional.
- `main` is protected: every change lands through a pull request with required checks green,
  never a direct commit.
- Do not commit generated outputs: report directories, `coverage.xml`, and `dist/` are
  gitignored. `examples/sample_output/` is the deliberately tracked sample.
- Validate behavior, not just exit codes: when a change affects analysis or reports, run the
  CLI against `examples/*.jsonl` and inspect the generated artifacts.

## Skill usage

Use `/failurelab-verify` after changing analysis, reports, or the CLI, to confirm the change against real generated artifacts rather than tests alone. The skill covers choosing a representative fixture for the affected surface, running the real workflow, and reading the output; it does not repeat the contracts above.
