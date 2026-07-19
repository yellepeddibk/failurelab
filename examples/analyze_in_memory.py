"""Analyze in-memory traces with the FailureLab Python API.

Run:

    python examples/analyze_in_memory.py
    python examples/analyze_in_memory.py --output ./reports

This script needs no files from the repository. Without ``--output`` it writes
report artifacts to a temporary directory, so a normal run leaves your working
tree unchanged.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import failurelab as fl

TRACES = [
    {
        "schema_version": "0.1",
        "trace_id": "trace-1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "success": True,
    },
    {
        "schema_version": "0.1",
        "trace_id": "trace-2",
        "timestamp": "2026-01-01T00:01:00+00:00",
        "success": False,
        "query": "Who owns this incident?",
        "failure_type": "retrieval_failure",
    },
]


def main(output: Path | None) -> None:
    # validate() inspects the whole input and never raises for invalid data.
    validation = fl.validate(TRACES)
    print(
        f"valid={validation.data_quality.valid_count} "
        f"invalid={validation.data_quality.invalid_count}"
    )

    # analyze() runs entirely in memory. Nothing is written to disk yet.
    report = fl.analyze(TRACES)

    failure_rate = report.metric("failure_rate")
    assert failure_rate is not None  # known outcomes are present in this dataset
    print(f"failure_rate={failure_rate.value}")
    print(f"analyzable={report.data_quality.analyzable}")
    for slice_ in report.failure_slices:
        print(f"slice {slice_.name}={slice_.value} failure_rate={slice_.failure_rate}")

    # Report projections are pure and side-effect free.
    print(report.to_markdown())

    # Persistence is explicit and opt-in.
    if output is not None:
        written = report.write(output, overwrite=True)
        print(f"wrote {len(written)} report files to {output}")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            written = report.write(Path(tmp) / "reports", overwrite=True)
            print(f"wrote {len(written)} report files to a temporary directory")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Directory for report artifacts (default: a temporary directory).",
    )
    main(parser.parse_args().output)
