"""Run the RAG example and write FailureLab traces.

Two modes:

``--generator scripted`` (default)
    Deterministic. Reproduces the committed datasets exactly and needs no model.

``--generator ollama --model <name>``
    The live path. Requires a running Ollama server and a pulled model. Output is
    not reproducible, because the model is not.

Run:

    python examples/rag_pipeline/run.py --list
    python examples/rag_pipeline/run.py --output ./rag-out
    python examples/rag_pipeline/run.py --generator ollama --model gemma3 --output ./rag-out

Nothing is written into the repository unless ``--output`` points there.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

# Allow running this file directly, without installing the example.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_pipeline.datasets import (
    DATASETS,
    DatasetSpec,
    generate,
    partition,
    scripted_generator,
)
from rag_pipeline.datasets import load_all_questions as _load_questions
from rag_pipeline.generation import Generator
from rag_pipeline.ollama_generator import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_TIMEOUT,
    OllamaGenerator,
)
from rag_pipeline.pipeline import Clock, FixedClock, RealClock, write_traces


def _build_generator(
    spec: DatasetSpec, name: str, model: str | None, timeout: float, max_output_tokens: int
) -> tuple[Generator, Clock]:
    """Choose the generator and the matching clock.

    The scripted path pairs with a fixed clock so runs stay byte-reproducible. A
    live run records real timestamps and measured latency, because pretending a
    model call took a fixed 100 milliseconds would be a lie in the trace.
    """
    if name == "scripted":
        questions = partition(_load_questions(), answerable=spec.answerable)
        return scripted_generator(questions), FixedClock()
    if not model:
        raise SystemExit("--model is required when --generator ollama is used")
    return (
        OllamaGenerator(model=model, timeout=timeout, max_output_tokens=max_output_tokens),
        RealClock(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generator", choices=("scripted", "ollama"), default="scripted")
    parser.add_argument("--model", default=None, help="model name, required for ollama")
    parser.add_argument("--output", type=Path, default=None, help="directory for the JSONL files")
    parser.add_argument(
        "--dataset",
        action="append",
        choices=[spec.filename for spec in DATASETS],
        help="generate only this dataset; repeatable",
    )
    parser.add_argument(
        "--include-context",
        action="store_true",
        help="record raw retrieved context in the traces (off by default)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="per-question timeout in seconds for the live generator",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help="upper bound on generated tokens per answer",
    )
    parser.add_argument("--list", action="store_true", help="list the datasets and exit")
    args = parser.parse_args(argv)

    if args.list:
        for spec in DATASETS:
            partition_name = "answerable" if spec.answerable else "abstention"
            print(f"{spec.filename}: retriever={spec.retriever} partition={partition_name}")
        return 0

    selected = [spec for spec in DATASETS if not args.dataset or spec.filename in args.dataset]
    with tempfile.TemporaryDirectory(prefix="failurelab-rag-") as scratch:
        destination = args.output or Path(scratch)
        destination.mkdir(parents=True, exist_ok=True)
        for spec in selected:
            generator, clock = _build_generator(
                spec, args.generator, args.model, args.timeout, args.max_output_tokens
            )
            traces = generate(
                spec,
                generator=generator,
                clock=clock,
                include_context=args.include_context,
            )
            path = write_traces(traces, destination / spec.filename)
            failures = sum(1 for trace in traces if trace.success is False)
            print(f"{path}: {len(traces)} traces, {failures} failures")
        if args.output is None:
            print("no --output given, so the files above were written to a temporary directory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
