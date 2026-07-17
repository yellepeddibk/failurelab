from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import failurelab
from failurelab import (
    AnalysisReport,
    ComparisonReport,
    InvalidTraceDataError,
    TraceRecord,
    ValidationReport,
    analyze,
    compare,
    validate,
)

VALID = {
    "schema_version": "0.1",
    "trace_id": "a",
    "timestamp": "2026-01-01T00:00:00+00:00",
    "success": True,
}
FAILED = {
    "schema_version": "0.1",
    "trace_id": "b",
    "timestamp": "2026-01-01T00:00:00+00:00",
    "success": False,
    "query": "why did retrieval miss?",
    "failure_type": "retrieval_failure",
}
INVALID = {"schema_version": "0.1"}  # missing required trace_id


def test_public_names_exported() -> None:
    for name in ("analyze", "compare", "validate", "AnalysisReport"):
        assert name in failurelab.__all__


def test_analyze_from_path_returns_report() -> None:
    report = analyze("examples/rag_traces.jsonl", strict=False)
    assert isinstance(report, AnalysisReport)
    assert report.metric("failure_rate") is not None
    assert report.provenance.source == "rag_traces.jsonl"


def test_analyze_accepts_dicts_records_and_mixed() -> None:
    record = TraceRecord.model_validate(VALID)
    for source in ([VALID, FAILED], [record], [record, dict(FAILED)]):
        report = analyze(list(source), strict=False)
        assert isinstance(report, AnalysisReport)
        assert report.data_quality.analyzable


def test_analyze_accepts_generator() -> None:
    report = analyze((row for row in [VALID, FAILED]), strict=False)
    assert report.data_quality.valid_count == 2


def test_analyze_bad_item_type_raises_typeerror() -> None:
    with pytest.raises(TypeError):
        analyze([VALID, 123], strict=False)


def test_analyze_strict_raises_invalid_trace_data() -> None:
    with pytest.raises(InvalidTraceDataError) as excinfo:
        analyze([VALID, INVALID])  # default strict
    assert excinfo.value.issues
    assert excinfo.value.issues[0].error_type == "schema_error"


def test_analyze_skip_invalid_collects_issues() -> None:
    report = analyze([VALID, INVALID], strict=False)
    assert report.data_quality.valid_count == 1
    assert report.data_quality.invalid_count == 1
    assert report.issues[0].error_type == "schema_error"


def test_analyze_detects_duplicate_ids() -> None:
    report = analyze([VALID, dict(VALID)], strict=False)
    assert report.data_quality.valid_count == 1
    assert report.data_quality.duplicate_ids == 1


def test_analyze_empty_input_is_not_analyzable() -> None:
    report = analyze([], strict=False)
    assert report.data_quality.valid_count == 0
    assert report.data_quality.analyzable is False


def test_analyze_all_invalid_skip_invalid_is_not_analyzable() -> None:
    report = analyze([INVALID, {"schema_version": "0.1"}], strict=False)
    assert report.data_quality.analyzable is False
    assert report.data_quality.invalid_count == 2


def test_report_projections_match_written_files(tmp_path: Path) -> None:
    report = analyze("examples/mixed_traces.jsonl", strict=False)
    out = tmp_path / "out"
    written = report.write(out)
    assert (out / "run_manifest.json") in written

    assert (
        json.loads((out / "metrics.json").read_text(encoding="utf-8")) == report.to_metrics_dict()
    )
    assert (
        json.loads((out / "findings.json").read_text(encoding="utf-8")) == report.to_findings_dict()
    )
    assert (out / "report.md").read_text(encoding="utf-8") == report.to_markdown()


def test_analysis_to_dict_is_json_serializable() -> None:
    report = analyze([VALID, FAILED], strict=False)
    payload = report.to_dict()
    assert {
        "schema_version",
        "data_quality",
        "metrics",
        "breakdowns",
        "failure_slices",
        "root_cause_hypotheses",
        "regression_tests",
    } <= set(payload)
    json.dumps(payload)


def test_write_collision_requires_overwrite(tmp_path: Path) -> None:
    report = analyze("examples/rag_traces.jsonl", strict=False)
    out = tmp_path / "out"
    report.write(out)
    with pytest.raises(FileExistsError):
        report.write(out)
    report.write(out, overwrite=True)


def test_report_is_frozen() -> None:
    report = analyze([VALID], strict=False)
    with pytest.raises(FrozenInstanceError):
        report.metrics = ()  # type: ignore[misc]


def test_in_memory_digest_is_reproducible() -> None:
    first = analyze([VALID, FAILED], strict=False)
    second = analyze([VALID, FAILED], strict=False)
    assert first.provenance.source == "<in-memory>"
    assert first.provenance.sha256 is not None
    assert first.provenance.sha256 == second.provenance.sha256


def test_validate_collects_all_issues_without_raising() -> None:
    report = validate([VALID, INVALID, INVALID])
    assert isinstance(report, ValidationReport)
    assert report.is_valid is False
    assert len(report.issues) == 2
    assert report.data_quality.valid_count == 1


def test_validate_all_valid() -> None:
    report = validate([VALID, FAILED])
    assert report.is_valid
    assert len(report.valid_traces) == 2


def test_compare_returns_report_and_writes(tmp_path: Path) -> None:
    report = compare("examples/baseline_traces.jsonl", "examples/candidate_traces.jsonl")
    assert isinstance(report, ComparisonReport)
    assert report.gate_status == "not_configured"
    assert report.gate_passed is None
    assert report.is_comparable
    out = tmp_path / "cmp"
    report.write(out)
    assert (out / "comparison.json").exists()
    assert (out / "comparison.md").read_text(encoding="utf-8") == report.to_markdown()


def test_compare_strict_raises_on_invalid() -> None:
    with pytest.raises(InvalidTraceDataError):
        compare("examples/invalid_traces.jsonl", "examples/candidate_traces.jsonl")


def test_compare_not_comparable_when_side_empty() -> None:
    report = compare([], [VALID])
    assert report.baseline_data_quality.analyzable is False
    assert report.is_comparable is False


def test_analysis_to_dict_includes_issues_provenance_and_config() -> None:
    report = analyze([VALID, INVALID], strict=False)
    payload = report.to_dict()
    assert payload["issues"] and payload["issues"][0]["error_type"] == "schema_error"
    assert payload["provenance"]["source"] == "<in-memory>"
    assert payload["config"]["ingestion"]["mode"] == "skip_invalid"
    json.dumps(payload)


def test_comparison_to_dict_includes_signals_and_provenance() -> None:
    report = compare([], [VALID])
    payload = report.to_dict()
    assert payload["is_comparable"] is False
    assert payload["baseline_data_quality"]["valid_count"] == 0
    assert payload["candidate_data_quality"]["valid_count"] == 1
    assert "source" in payload["baseline_provenance"]
    assert payload["config"]["comparison"]["scope"] == "all_valid_traces"
    json.dumps(payload)


def test_input_metadata_from_path_handles_oserror(tmp_path: Path, monkeypatch) -> None:
    from failurelab.reports.models import InputMetadata

    target = tmp_path / "x.jsonl"
    target.write_text("{}", encoding="utf-8")

    def boom(self: Path) -> bytes:
        raise OSError("locked")

    monkeypatch.setattr(Path, "read_bytes", boom)
    meta = InputMetadata.from_path(target)
    assert meta.source == "x.jsonl"
    assert meta.sha256 is None
