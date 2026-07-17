"""Public report objects returned by the FailureLab Python API.

These wrappers hold the deterministic analysis output in memory. They perform
no filesystem writes unless ``write`` is called explicitly, which keeps the
Python API side-effect free while the CLI opts into persistence. The rendered
payloads are projections of the same domain objects, so the on-disk output is
identical whether it is produced through the CLI or through ``write``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, cast

from failurelab.comparison.service import ComparisonResult, GateViolation
from failurelab.config.settings import FailureLabConfig
from failurelab.discovery.slices import FailureSlice
from failurelab.evals.metrics import EvaluationBundle, MetricResult, metric_dict
from failurelab.ingestion.jsonl import IngestionResult
from failurelab.ingestion.records import IN_MEMORY_SOURCE
from failurelab.models.trace import SCHEMA_VERSION, TraceRecord, ValidationIssue
from failurelab.regression.generator import RegressionBundle, RegressionCase
from failurelab.reports.writers import (
    assert_output_path_safe,
    render_comparison_markdown,
    render_findings_payload,
    render_gate_payload,
    render_markdown_report,
    render_metrics_payload,
    render_run_manifest,
    write_invalid_traces,
    write_json_atomic,
    write_text_atomic,
    write_yaml_atomic,
)
from failurelab.root_cause.analyzer import RootCauseHypothesis
from failurelab.utilities.serialization import stable_dumps

GateStatus = Literal["not_configured", "passed", "failed"]
GateScope = Literal["all_valid_traces", "matched_ids"]


@dataclass(slots=True)
class AnalysisComputation:
    """Internal bundle of deterministic analysis output for one dataset."""

    metrics: EvaluationBundle
    findings: list[FailureSlice]
    hypotheses: list[RootCauseHypothesis]
    regression: RegressionBundle


@dataclass(frozen=True, slots=True)
class DataQualitySummary:
    valid_count: int
    invalid_count: int
    duplicate_ids: int
    blank_rows: int

    @property
    def analyzable(self) -> bool:
        return self.valid_count > 0

    def to_dict(self) -> dict[str, int]:
        return {
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "duplicate_ids": self.duplicate_ids,
            "blank_rows": self.blank_rows,
        }


@dataclass(frozen=True, slots=True)
class InputMetadata:
    """Provenance for one analyzed dataset.

    ``sha256`` is the digest of the input file bytes for path inputs (``None``
    only when the path cannot be read), and the digest of the canonical
    serialization of the normalized traces for in-memory inputs.
    """

    source: str
    sha256: str | None

    @classmethod
    def from_path(cls, path: Path) -> InputMetadata:
        try:
            digest: str | None = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            # Missing, a directory, or unreadable (permissions, locking, race).
            digest = None
        return cls(source=path.name, sha256=digest)

    @classmethod
    def from_records(cls, traces: list[TraceRecord]) -> InputMetadata:
        canonical = stable_dumps([trace.model_dump(mode="json") for trace in traces])
        return cls(
            source=IN_MEMORY_SOURCE, sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )

    def to_dict(self) -> dict[str, str | None]:
        return {"source": self.source, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    metrics: tuple[MetricResult, ...]
    breakdowns: Mapping[str, list[dict[str, object]]]
    failure_slices: tuple[FailureSlice, ...]
    root_cause_hypotheses: tuple[RootCauseHypothesis, ...]
    regression_tests: tuple[RegressionCase, ...]
    data_quality: DataQualitySummary
    issues: tuple[ValidationIssue, ...]
    provenance: InputMetadata
    config: FailureLabConfig

    def metric(self, name: str) -> MetricResult | None:
        return next((item for item in self.metrics if item.name == name), None)

    def to_metrics_dict(self) -> dict[str, Any]:
        return render_metrics_payload(list(self.metrics), dict(self.breakdowns))

    def to_findings_dict(self) -> dict[str, Any]:
        return render_findings_payload(list(self.failure_slices), list(self.root_cause_hypotheses))

    def to_regression_list(self) -> list[dict[str, Any]]:
        return [case.model_dump(exclude_none=True) for case in self.regression_tests]

    def to_markdown(self) -> str:
        return render_markdown_report(
            list(self.metrics),
            list(self.failure_slices),
            list(self.root_cause_hypotheses),
            RegressionBundle(tests=list(self.regression_tests)),
            list(self.issues),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "data_quality": self.data_quality.to_dict(),
            "issues": [issue.model_dump(exclude_none=True) for issue in self.issues],
            "provenance": self.provenance.to_dict(),
            "config": self.config.model_dump(mode="json"),
            "metrics": metric_dict(list(self.metrics)),
            "breakdowns": dict(self.breakdowns),
            "failure_slices": [asdict(finding) for finding in self.failure_slices],
            "root_cause_hypotheses": [asdict(item) for item in self.root_cause_hypotheses],
            "regression_tests": self.to_regression_list(),
        }

    def write(self, output_dir: str | Path, *, overwrite: bool = False) -> list[Path]:
        output = Path(output_dir)
        assert_output_path_safe(output, overwrite)

        metrics_path = output / "metrics.json"
        findings_path = output / "findings.json"
        markdown_path = output / "report.md"
        regression_path = output / "regression_tests.yaml"
        manifest_path = output / "run_manifest.json"

        write_json_atomic(metrics_path, self.to_metrics_dict())
        write_json_atomic(findings_path, self.to_findings_dict())
        write_text_atomic(markdown_path, self.to_markdown())
        write_yaml_atomic(regression_path, self.to_regression_list())

        generated_files = [
            "metrics.json",
            "findings.json",
            "report.md",
            "regression_tests.yaml",
            "run_manifest.json",
        ]
        if self.issues:
            generated_files.append("invalid_traces.jsonl")
        write_json_atomic(
            manifest_path,
            render_run_manifest(
                input_name=self.provenance.source,
                input_sha256=self.provenance.sha256,
                resolved_config=self.config.model_dump(),
                valid_count=self.data_quality.valid_count,
                invalid_count=self.data_quality.invalid_count,
                generated_files=generated_files,
            ),
        )

        written = [metrics_path, findings_path, markdown_path, regression_path, manifest_path]
        if self.issues:
            invalid_path = output / "invalid_traces.jsonl"
            write_invalid_traces(invalid_path, list(self.issues))
            written.append(invalid_path)
        return written


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    summary: Mapping[str, object]
    gate_status: GateStatus
    gate_scope: GateScope
    gate_passed: bool | None
    violations: tuple[GateViolation, ...]
    baseline_data_quality: DataQualitySummary
    candidate_data_quality: DataQualitySummary
    baseline_provenance: InputMetadata
    candidate_provenance: InputMetadata
    config: FailureLabConfig

    @property
    def is_comparable(self) -> bool:
        return self.baseline_data_quality.analyzable and self.candidate_data_quality.analyzable

    def _result(self) -> ComparisonResult:
        return ComparisonResult(
            summary=dict(self.summary),
            gate_status=self.gate_status,
            gate_scope=self.gate_scope,
            gate_passed=self.gate_passed,
            violations=list(self.violations),
        )

    def to_summary_dict(self) -> dict[str, Any]:
        return dict(self.summary)

    def to_gate_dict(self) -> dict[str, Any]:
        return render_gate_payload(self._result(), self.config)

    def to_markdown(self) -> str:
        return render_comparison_markdown(self._result(), self.config)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": dict(self.summary),
            "gate": self.to_gate_dict(),
            "baseline_data_quality": self.baseline_data_quality.to_dict(),
            "candidate_data_quality": self.candidate_data_quality.to_dict(),
            "baseline_provenance": self.baseline_provenance.to_dict(),
            "candidate_provenance": self.candidate_provenance.to_dict(),
            "is_comparable": self.is_comparable,
            "config": self.config.model_dump(mode="json"),
        }

    def write(self, output_dir: str | Path, *, overwrite: bool = False) -> list[Path]:
        output = Path(output_dir)
        assert_output_path_safe(output, overwrite)

        comparison_json = output / "comparison.json"
        comparison_md = output / "comparison.md"
        gate_json = output / "gate_result.json"

        write_json_atomic(comparison_json, dict(self.summary))
        write_text_atomic(comparison_md, self.to_markdown())
        write_json_atomic(gate_json, self.to_gate_dict())
        return [comparison_json, comparison_md, gate_json]


@dataclass(frozen=True, slots=True)
class ValidationReport:
    valid_traces: tuple[TraceRecord, ...]
    issues: tuple[ValidationIssue, ...]
    data_quality: DataQualitySummary

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_quality": self.data_quality.to_dict(),
            "issues": [issue.model_dump(exclude_none=True) for issue in self.issues],
        }


def _data_quality(ingestion: IngestionResult) -> DataQualitySummary:
    return DataQualitySummary(
        valid_count=len(ingestion.traces),
        invalid_count=len(ingestion.issues),
        duplicate_ids=ingestion.duplicate_ids,
        blank_rows=ingestion.blank_rows,
    )


def analysis_report(
    computation: AnalysisComputation,
    ingestion: IngestionResult,
    provenance: InputMetadata,
    config: FailureLabConfig,
) -> AnalysisReport:
    return AnalysisReport(
        metrics=tuple(computation.metrics.metrics),
        breakdowns=MappingProxyType(dict(computation.metrics.breakdowns)),
        failure_slices=tuple(computation.findings),
        root_cause_hypotheses=tuple(computation.hypotheses),
        regression_tests=tuple(computation.regression.tests),
        data_quality=_data_quality(ingestion),
        issues=tuple(ingestion.issues),
        provenance=provenance,
        config=config,
    )


def comparison_report(
    result: ComparisonResult,
    baseline: IngestionResult,
    candidate: IngestionResult,
    baseline_provenance: InputMetadata,
    candidate_provenance: InputMetadata,
    config: FailureLabConfig,
) -> ComparisonReport:
    return ComparisonReport(
        summary=MappingProxyType(dict(result.summary)),
        gate_status=cast(GateStatus, result.gate_status),
        gate_scope=cast(GateScope, result.gate_scope),
        gate_passed=result.gate_passed,
        violations=tuple(result.violations),
        baseline_data_quality=_data_quality(baseline),
        candidate_data_quality=_data_quality(candidate),
        baseline_provenance=baseline_provenance,
        candidate_provenance=candidate_provenance,
        config=config,
    )


def validation_report(ingestion: IngestionResult) -> ValidationReport:
    return ValidationReport(
        valid_traces=tuple(ingestion.traces),
        issues=tuple(ingestion.issues),
        data_quality=_data_quality(ingestion),
    )
