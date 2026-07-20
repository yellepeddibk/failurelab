# FailureLab

Deterministic AI reliability analysis for RAG and agent traces. FailureLab finds concentrated failure slices, produces evidence-backed root-cause hypotheses, and drafts replayable regression tests. It runs entirely offline, with no LLM, network, or database dependency.

Use it as a Python library or from the command line.

## Install

```bash
python -m pip install "failurelab>=0.2.0"
```

## Where to go next

- New here? Start with the [Quickstart](quickstart.md).
- Reference: the [Python API](api.md) and the [CLI](cli.md).
- Concepts: [metrics](metrics.md), [architecture](architecture.md), [regression tests](regression-tests.md), and [privacy](privacy.md).

## Why

Averages hide failure concentration by model, prompt, retriever, or tool sequence. FailureLab keeps deterministic metric logic in typed services and returns typed report objects you can inspect in code. The CLI is a thin wrapper over the same engine.
