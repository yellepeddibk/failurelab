# CLAUDE.md

Guidance for Claude Code in this repository. Use this file as an index: read the pointed file before changing the area it covers, instead of rediscovering the repository each session. Detailed rules for implementing an approved task live in `.claude/skills/failurelab-execute/SKILL.md`; this file does not duplicate them.

## Project

FailureLab is a local-first, deterministic AI reliability toolkit for RAG and agent traces. It finds elevated failure slices, produces evidence-backed root-cause hypotheses, drafts replayable regression tests, and compares baseline and candidate runs. Python 3.11 to 3.14, MIT license, Typer CLI (`failurelab validate | analyze | compare`).

## Hard constraints

- No LLM dependency, network calls, database, web server, frontend, or agent framework unless the maintainer explicitly requests it. Core analysis must stay deterministic and run offline.
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
| Typer CLI and exit codes | `src/failurelab/cli/app.py` | |
| Config models and loading | `src/failurelab/config/settings.py` | |
| Tests (unit, integration, golden, property, smoke) | `tests/` | |
| Sample traces and outputs | `examples/` | |
| Branch protection policy | `.github/rulesets/protect-main.json` | `docs/PROTECT_MAIN.md` |
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

- Never commit directly to `main`. Create branches and commits only for explicitly requested work. Branch prefixes: `feat/`, `fix/`, `docs/`, `test/`, `refactor/`, `chore/`, `ci/`.
- `main` is protected by the `protect-main` ruleset managed in the GitHub UI (squash-only, 1 approval, `quality-gate` and `CodeQL` required checks, branches must be up to date). See `docs/PROTECT_MAIN.md`. The tracked JSON is an export snapshot, not automation.
- The maintainer performs all remote operations (push, PR creation, merge) manually. Do not fetch, pull, push, merge, open PRs, or alter authentication from Claude sessions. Provide exact commands for the maintainer instead.
- Never commit while a required check is failing. Stage explicit paths only; never `git add -A`.
- Do not commit generated outputs: report directories, `coverage.xml`, and `dist/` are gitignored. `examples/sample_output/` is the deliberately tracked sample.
- Validate behavior, not just exit codes: when a change affects analysis or reports, run the CLI against `examples/*.jsonl` and inspect the generated artifacts.

## Skill usage

Use `/failurelab-execute <task>` to implement one approved task end to end (fresh branch, smallest complete change, validation, exactly one local commit). The skill owns the interpretation gate, acceptance criteria, validation sequence, commit rules, and report format; follow it rather than improvising an equivalent workflow inline.

## Writing rules

- No em dash characters in documentation, code comments, commit messages, or reports.
- No AI attribution: no `Co-Authored-By`, `Generated-By`, AI signatures, or tool credits in commits, code, or PR text.
- Be direct and technically honest. Do not exaggerate readiness, quality, or impact. State limitations plainly.

## Environment notes

- Checkouts inside cloud-synced directories (OneDrive, Dropbox, and similar) can hit file locking that breaks directory deletion and git housekeeping, especially on Windows. Avoid aggressive cleanup, garbage collection, and destructive git commands; `GIT_ASK_YESNO=false` avoids stuck retry prompts.
- Do not assume a `gh` command on PATH is the official GitHub CLI; verify what it is before using it. Remote operations remain manual regardless.
