"""Explain a RAG analysis with the optional interpretation layer.

This is opt-in and never runs in continuous integration. It makes exactly one call
to a provider you construct yourself, and it is the only part of this example that
sends anything anywhere.

What is sent is the structured evidence FailureLab already computed: metric names
and values, slice shapes, and pseudonymous hypothesis identifiers. Raw queries,
answers, retrieved context, and real trace identifiers are excluded by default, so
the corpus text never leaves the machine unless you opt in.

Run:

    python examples/rag_pipeline/interpret_run.py --model gemma3
    python examples/rag_pipeline/interpret_run.py --model gemma3 --dataset rag_v2.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import failurelab as fl
from failurelab.llm import OllamaProvider
from rag_pipeline.datasets import DATASETS, analysis_config, example_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="an Ollama model you have pulled")
    parser.add_argument(
        "--dataset",
        default="rag_v1.jsonl",
        choices=[spec.filename for spec in DATASETS],
    )
    parser.add_argument("--host", default=None, help="override the Ollama host")
    parser.add_argument(
        "--include-trace-ids",
        action="store_true",
        help="send real trace identifiers instead of pseudonyms",
    )
    args = parser.parse_args(argv)

    dataset = example_dir() / "data" / args.dataset
    report = fl.analyze(dataset, config=analysis_config())

    failures = sum(1 for hypothesis in report.root_cause_hypotheses)
    print(f"{args.dataset}: {failures} failed traces with hypotheses")
    print("sending structured evidence only, no raw content, one provider call")

    provider = OllamaProvider(model=args.model, **({"host": args.host} if args.host else {}))
    interpretation = fl.interpret(
        report,
        provider=provider,
        include_trace_ids=args.include_trace_ids,
    )

    print()
    print(interpretation.to_markdown())
    print()
    metadata = interpretation.generation_metadata
    print(f"provider={metadata.provider} model={metadata.model}")
    print(f"latency_ms={metadata.provider_latency_ms:.0f}")
    payload = interpretation.to_dict()
    print(f"serializable: {len(json.dumps(payload))} bytes, aliases omitted by default")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
