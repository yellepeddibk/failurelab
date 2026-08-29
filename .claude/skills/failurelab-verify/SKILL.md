---
name: failurelab-verify
description: Verify a FailureLab change against real generated artifacts rather than tests alone. Picks the smallest representative workflow for the affected surface, runs it, and inspects the output. Invoke manually with /failurelab-verify, optionally naming the area changed.
disable-model-invocation: true
argument-hint: "[area changed: ingestion, metrics, slices, root cause, regression, comparison, reports, CLI, RAG example]"
---

# /failurelab-verify: behavior verification against real output

This repository's always-on requirements live in `CLAUDE.md`. This skill covers the
FailureLab-specific procedure for proving that a change behaves correctly, by running the
real workflow and inspecting the artifacts it produces.

Tests with a fixture prove the code paths are right. They do not tell you a denominator
is misleading, a Markdown table prints a raw Python value, or a report leaks content it
should not. Only reading real output does that.

Run this when a change touches ingestion, metrics, slices, root cause, regression drafts,
comparison, reports, the CLI, or the RAG example. Skip it for changes with no runtime
surface, and say why you skipped it.

## Step 1: Identify the affected surface

Name what the change actually touches before choosing anything to run. Then pick the
**smallest representative workflow** that would expose a regression in that surface.

Do not run every fixture and every dataset on every invocation. A full sweep buries the
one artifact that matters and makes it likely you skim rather than read.

## Step 2: Choose fixtures that exercise that surface

Available targets, and what each is good for:

| Fixture | Verifies |
| --- | --- |
| `examples/rag_traces.jsonl` | ordinary RAG traces, ingestion and metrics |
| `examples/mixed_traces.jsonl` | mixed success and failure, slices and root cause |
| `examples/agent_traces.jsonl` | agent steps, tool success, step-level rules |
| `examples/invalid_traces.jsonl` | `strict` versus `skip_invalid`, invalid-row reporting |
| `examples/baseline_traces.jsonl` and `examples/candidate_traces.jsonl` | comparison, deltas, gate states |
| `examples/rag_pipeline/data/rag_v1.jsonl` and `rag_v2.jsonl` | retrieval metrics, and comparison across a real retriever change |
| `examples/rag_pipeline/data/rag_abstention.jsonl` | unavailable-metric semantics on real data |

The RAG datasets require their own configuration, because `retrieval_k` must match the
`k` the pipeline retrieved with. Without it, recall is computed over a truncated result
list and two different retrievers can score identically:

```bash
--config examples/rag_pipeline/config.yaml
```

Analyzing `rag_v1` and `rag_v2` together, rather than separately, is what makes a
`retriever_version` failure slice possible. Analyzed alone, every trace in a run shares
the same value and no slice can form.

## Step 3: Run the real workflow

Write outputs outside the repository, or delete them before committing.

```bash
failurelab validate <fixture>
failurelab analyze <fixture> [--config <config>] --output <temp-dir> --overwrite
failurelab compare <baseline> <candidate> [--config <config>] --output <temp-dir> --overwrite
```

The Python API is equally valid, and is the better choice when the check needs traces
combined in memory:

```python
import failurelab as fl

report = fl.analyze([*baseline_rows, *candidate_rows], config=config)
```

## Step 4: Read the artifacts

Open the files, do not just confirm the command exited zero. Which ones depend on the
surface:

| Artifact | Read it for |
| --- | --- |
| `metrics.json` | numerators, denominators, `eligible_count`, `excluded_count`, `unavailable_reason` |
| `findings.json` | slice membership, uplift, evidence trace IDs |
| `report.md` | human-readable rendering, and that no raw Python value appears |
| `regression_tests.yaml` | provenance, `draft` status, nonempty replay input |
| `run_manifest.json` | effective resolved configuration, `generated_files`, safe filenames |
| `comparison.md`, `comparison.json`, `gate_result.json` | deltas, direction, tri-state gate |

Confirm against the contracts in `CLAUDE.md` for the surface you touched. In particular,
when the change could affect them:

- an unavailable statistic is `null` with a real denominator and a reason, never a
  fabricated value
- Markdown never prints `None` or a binary float artifact
- no raw query, answer, or retrieved context appears unless `include_content` was
  explicitly enabled
- the manifest carries safe filenames, not absolute paths

## Step 5: Report what you actually observed

State which fixtures you ran and why those, which artifacts you opened, and what you saw
in them. Quote the specific value that demonstrates the acceptance criterion.

Reporting that a command exited zero is not behavior verification. Neither is asserting a
contract holds without having read the output that shows it.

If you skipped this verification, say so and say why.
