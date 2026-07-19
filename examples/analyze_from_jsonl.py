"""Analyze and compare JSONL trace files with the FailureLab Python API.

Run from any working directory:

    python examples/analyze_from_jsonl.py
    python examples/analyze_from_jsonl.py --output ./reports

It reads the fixtures shipped in this examples/ directory (resolved relative to
this file, not the caller's current directory). Without ``--output`` it writes
report artifacts to a temporary directory. When ``--output`` is given, analysis
and comparison artifacts are written to ``<output>/analysis`` and
``<output>/comparison``.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import failurelab as fl

EXAMPLES_DIR = Path(__file__).resolve().parent


def _write_all(report: fl.AnalysisReport, comparison: fl.ComparisonReport, base: Path) -> None:
    report.write(base / "analysis", overwrite=True)
    comparison.write(base / "comparison", overwrite=True)
    print(f"wrote analysis and comparison artifacts under {base}")


def main(output: Path | None) -> None:
    rag = EXAMPLES_DIR / "rag_traces.jsonl"
    baseline = EXAMPLES_DIR / "baseline_traces.jsonl"
    candidate = EXAMPLES_DIR / "candidate_traces.jsonl"

    report = fl.analyze(rag)
    print(f"analyzed {report.data_quality.valid_count} traces from {rag.name}")
    failure_rate = report.metric("failure_rate")
    assert failure_rate is not None  # rag_traces.jsonl has known outcomes
    print(f"failure_rate={failure_rate.value}")

    comparison = fl.compare(baseline, candidate)
    print(
        f"gate_status={comparison.gate_status} "
        f"gate_passed={comparison.gate_passed} "
        f"comparable={comparison.is_comparable}"
    )

    if output is not None:
        _write_all(report, comparison, output)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            _write_all(report, comparison, Path(tmp))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Directory for report artifacts (default: a temporary directory).",
    )
    main(parser.parse_args().output)
