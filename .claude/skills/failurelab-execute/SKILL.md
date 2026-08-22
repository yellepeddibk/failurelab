---
name: failurelab-execute
description: Implement one approved FailureLab task on a fresh local branch, validate behavior and generated artifacts, and commit locally at each engineering boundary without contacting a remote repository. Invoke manually with /failurelab-execute followed by the task.
disable-model-invocation: true
argument-hint: "[approved task, correction, or goal]"
---

# /failurelab-execute: single-task implementation loop

You are implementing one approved task in the `failurelab` repository. Work through the phases in order. Preserve FailureLab's determinism, semantic contracts, privacy defaults, and the maintainer's existing work.

**Stop after the last local commit. All remote Git operations, including the final push and PR creation, are performed manually by the maintainer.**

Never fetch, pull, push, merge, rebase published history, open a pull request, contact a remote repository, or alter authentication.

Read `CLAUDE.md` first. It is the index for this repository and lists the semantic contracts referenced below. Cross-repo maintainer preferences are intentionally omitted; this skill covers only FailureLab-specific procedure.

## Input priority

Determine the task using this order:

1. `$ARGUMENTS`, when provided.
2. A file, issue text, or document explicitly referenced by the user.
3. The most recently approved goal in the conversation.

`$ARGUMENTS` may contain a feature request, a defect report, a correction to earlier work, a documentation task, or a pasted issue. If no usable task exists, ask the user for one, then stop.

## Phase 1: Interpret the task

Read the task completely before modifying anything. Classify its content:

- Confirmed scope: what the task clearly asks to add, change, fix, or document.
- Tentative ideas: suggestions phrased as maybe, could, might, or worth considering. Do not implement these unless explicitly included in the request.
- Open questions: anything requiring maintainer input, missing data, or a product decision.
- Constraints: affected semantic domains (ingestion, metrics, slices, root cause, regression, comparison, reports, privacy, CLI), compatibility expectations, and output formats.

## Phase 2: Define the work

Before editing files:

1. State the implementation goal in one sentence.
2. List the specific action items being implemented.
3. List tentative ideas and open questions that will not be implemented.
4. Derive concrete acceptance criteria, including observable behavior.
5. Identify assumptions needed to proceed.

Use the smallest conservative assumption that matches existing repository patterns. Stop and ask the user only when ambiguity could materially affect:

- A semantic contract listed in `CLAUDE.md`
- Metric definitions, denominators, or eligibility
- Slice, root-cause, regression, or comparison semantics
- Privacy or content exposure
- Determinism or reproducibility
- The public CLI or output schema
- Destructive operations

Do not stop for naming, formatting, or implementation details resolvable from neighboring files.

## Mandatory pre-edit gate

Before creating a branch or modifying any file, output a block containing:

1. Task source used
2. Confirmed scope
3. Action items selected for this run
4. Tentative ideas excluded
5. Open questions
6. Assumptions
7. Acceptance criteria
8. Files likely to change

State plainly:

```text
Do not create an implementation branch or modify repository files until this block has been completed.
```

This block does not require additional approval unless an ambiguity triggers the stop conditions in Phase 2.

## Phase 3: Choose a branch

Use the prefixes from `CONTRIBUTING.md`:

- `feat/` for new functionality
- `fix/` for defects or incorrect results
- `docs/` for documentation-only changes
- `test/` for tests or validation-only work
- `refactor/` for internal restructuring without behavior changes
- `chore/` for tooling, housekeeping, or metadata
- `ci/` for continuous-integration changes

Choose a short kebab-case name: `<prefix><short-description>`. Do not include private information in the branch name.

## Phase 4: Preconditions

### 4.1 Clean working tree

```bash
git status --short
```

The working tree must be clean. If it is not: stop, report the modified and untracked files, and do not stash, discard, stage, or commit the user's existing changes. A file the user explicitly supplied as task input is not a blocker; handle it as the task directs.

### 4.2 Confirm repository and branch

```bash
git rev-parse --show-toplevel
git rev-parse --abbrev-ref HEAD
git status --branch --short
```

Confirm the repository root is `failurelab`. If not, stop without changing anything.

### 4.3 Local branch information only

Use only locally available Git information. Prohibited: `git fetch`, `git pull`, `git push`, `git ls-remote`, `git remote update`. Do not assume the local `origin/main` reference is current.

If local `main` is behind the locally known `origin/main`, tell the user to synchronize manually and stop. If local `main` is ahead, list the local-only commits and stop unless the user explicitly approves branching from that state. If currency cannot be determined without contacting the remote, say the check is based on local information only and continue when the other preconditions hold.

### 4.4 Create the branch

```bash
git switch main
git switch -c <branch>
```

Never create the implementation branch from another feature branch.

## Phase 5: Inspect the repository

Read `CLAUDE.md` and the files it points to for the affected area before implementing. Follow existing patterns for typing, naming, error handling, test organization, and docs. Do not invent conventions when existing files answer the question. Typical references: the relevant module under `src/failurelab/`, its tests under `tests/`, the matching `docs/*.md`, and `examples/` fixtures.

## Phase 6: Implement

Make the smallest complete change that satisfies the acceptance criteria.

Do not:

- Reformat, rename, or rewrite unrelated code or docs
- Upgrade dependencies without necessity
- Add an LLM dependency, network call, database, web server, frontend, or agent framework
- Weaken tests, typing, linting, security checks, or CI
- Change the public CLI, output schema, or exit codes outside the approved scope
- Perform drive-by cleanup

### Semantic protection rules

Do not regress the contracts in `CLAUDE.md`. In particular:

- Keep metrics honest: correct numerators, denominators, eligibility, and exclusions. Observation-dependent statistics with no eligible observations are `null` with an `unavailable_reason`, never a fake value.
- Failure slices remain elevated-failure only. Neutral and protective groups stay in breakdowns.
- Root-cause hypotheses only for explicitly failed traces, deterministic and evidence-based, with limitations stated.
- Regression drafts only from failed traces with concrete nonempty replay input, deterministic IDs and ordering, and source provenance.
- Comparison gates stay tri-state and Markdown output never shows raw Python values.
- Privacy defaults hold: no raw content in reports unless `include_content` is explicitly enabled, no absolute local paths in manifests.
- Determinism holds: stable ordering, stable IDs, no wall-clock or randomness in analysis output. Never fabricate results, counts, or validation outcomes.

## Phase 7: Validate

Run the checks that apply to the changed files:

```bash
ruff check .
ruff format --check .
mypy src
pytest -q
pre-commit run --all-files
```

If `pre-commit` cannot install or run its hooks in this environment, run the equivalent
checks directly (ruff, ruff format, codespell, and the file hygiene checks), and report that
`pre-commit` itself did not run rather than implying it passed. Do not treat the branch as
fully validated until CI has run the hooks.

For packaging or metadata changes, also run `python -m build` and `twine check dist/*`.

### Behavior verification

When the change affects ingestion, analysis, comparison, reports, or the CLI, do not rely on tests alone. Run the real workflow against a fixture and inspect the artifacts:

```bash
failurelab validate examples/rag_traces.jsonl
failurelab analyze examples/mixed_traces.jsonl --output <temp-dir> --overwrite
failurelab compare examples/baseline_traces.jsonl examples/candidate_traces.jsonl --output <temp-dir> --overwrite
```

Open the generated files (`metrics.json`, `findings.json`, `report.md`, `regression_tests.yaml`, `run_manifest.json`, comparison outputs) and confirm the acceptance criteria are visible in the actual output, including unavailable-metric semantics and privacy behavior. Write temporary outputs outside the repository or delete them before committing.

### Validation failure

If a check fails, determine whether the current change introduced it. Fix what the change broke and rerun. Do not hide, skip, or relabel a failure. Do not commit while a required check is red. If a pre-existing failure unrelated to the change blocks validation, stop and report it.

Do not claim a check passed unless it was actually executed in this run. Report commands and real outcomes. Coverage is collected but has no enforced threshold; report the observed number without inventing a target.

## Phase 8: Review the complete diff

```bash
git diff
git status --short
```

Review every changed line. Confirm:

- Only the approved action items are addressed
- No unrelated formatting or cleanup
- No credentials, tokens, machine-specific paths, or private data
- No `.venv/`, `__pycache__/`, cache directories, or generated artifacts
- No debugging prints or temporary code

## Phase 9: Commit

A branch is not one commit. Commit at each real engineering boundary reached during Phase 6, then run this phase again for the final boundary. Keep a commit when it answers "what did this accomplish"; fold it into the one it repairs when it answers "what mistake did I make while building this". Do not collapse legitimate commits to reduce the count, and do not manufacture commits to inflate it. Let the work decide how many there are.

Every commit must be independently valid. Before each substantive commit, run `ruff check .`, `mypy src`, and `pytest`; the suite takes roughly 12 seconds. The full Phase 7 sequence is required before the branch is reported as ready, not before every intermediate commit.

Stage the complete logical unit. A clean working tree does not make a partially staged commit correct, because imports split across commits poison `git bisect`. Untested but working code in a commit is acceptable; broken code is not.

All required checks must be green.

```bash
git add <path> [<path> ...]
git diff --cached --check
git diff --cached --stat
git diff --cached
```

Review the staged diff, then commit with a single-line imperative message matching repository history, for example `Add retrieval latency percentile metrics`. A conventional type prefix (`feat:`, `fix:`, etc.) is acceptable per `CONTRIBUTING.md`.

Verify:

```bash
git log -1 --format=full
```

Confirm the commit contains only the intended files.

## Phase 10: Report and stop

Scan the report itself for em dashes before producing it. Report:

- Task interpretation: source, confirmed scope, implemented items, excluded ideas, open questions, assumptions
- Git summary: branch, every commit hash and message on it (`git log --oneline main..HEAD`), and `git show --stat --oneline HEAD`
- Per-file changes: what changed, why, and which acceptance criterion it satisfies
- Validation: every command run and its actual result, including behavior verification and artifact inspection
- CI expectation: which jobs (`lint`, `type-check`, `tests`, `cross-platform-smoke`, `build`, `docs-and-metadata`, `security-check`, `quality-gate`, CodeQL) will validate the change after push
- The exact manual push command, without executing it:

```bash
git push -u origin <branch>
```

- Suggested PR title, and a body that follows `.github/pull_request_template.md` exactly: a `## Summary` section, the `## Validation` checklist, and the `## Sensitive data check` box. Do not invent a different structure, and do not tick a checklist box for a command that was not actually run. No attribution footer.
- The merge signal, as the last line: `Ready to Rebase and Merge.` or `Recommend Squash and Merge this time: <reason>`. Never choose squash silently.

When the report also contains text for a GitHub issue, label each block explicitly (`PR description:` versus `New issue:`) so they are not pasted into the wrong field.

Then stop and wait for the user. The maintainer pushes, opens the PR on the GitHub compare page, and merges.

## Remote and authentication rules

Local work does not require SSH. If any command unexpectedly requests a passphrase, host confirmation, credentials, or remote access: stop and hand the exact command to the user.

## Final prohibitions

During this skill, never: contact a Git remote in any form, delete or stash the maintainer's work, modify raw example fixtures outside the approved scope, or fabricate results or validation outcomes.
