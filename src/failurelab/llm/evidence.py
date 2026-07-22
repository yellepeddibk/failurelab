"""Privacy-filtered structured evidence packaging.

Builds the deterministic evidence sent to a provider from an ``AnalysisReport``.
By default it sends metric descriptors, slice descriptors, hypothesis labels, and
data-quality counts only. It never sends raw trace IDs, prompts, answers,
retrieved context, tool arguments, or regression inputs unless the caller opts
in. Trace-scoped findings are referenced by local aliases (``slice-001``,
``hypothesis-001``) whose mapping is kept client-side.
"""

from __future__ import annotations

from dataclasses import dataclass

from failurelab.reports.models import AnalysisReport

PROMPT_TEMPLATE_VERSION = "interpretation-1"


@dataclass(frozen=True, slots=True)
class PackagedEvidence:
    evidence: dict[str, object]
    aliases: dict[str, str]
    allowed_references: frozenset[tuple[str, str]]


def pack_evidence(
    report: AnalysisReport,
    *,
    include_content: bool,
    include_trace_ids: bool,
    max_items: int,
) -> PackagedEvidence:
    aliases: dict[str, str] = {}
    allowed: set[tuple[str, str]] = set()

    metrics: dict[str, object] = {}
    for metric in report.metrics:
        metrics[metric.name] = {
            "value": metric.value,
            "direction": metric.direction,
            "unavailable_reason": metric.unavailable_reason,
        }
        allowed.add(("metric", metric.name))

    slices: list[dict[str, object]] = []
    for index, finding in enumerate(report.failure_slices[:max_items], start=1):
        ref = f"slice-{index:03d}"
        aliases[ref] = f"{finding.name}={finding.value}"
        allowed.add(("slice", ref))
        entry: dict[str, object] = {
            "ref": ref,
            "field": finding.name,
            "value": finding.value,
            "support": finding.support,
            "failure_rate": finding.failure_rate,
            "absolute_uplift": finding.absolute_uplift,
            "relative_risk": finding.relative_risk,
        }
        if include_trace_ids:
            entry["evidence_trace_ids"] = list(finding.evidence_trace_ids)
        slices.append(entry)

    hypotheses: list[dict[str, object]] = []
    for index, hypothesis in enumerate(report.root_cause_hypotheses[:max_items], start=1):
        ref = f"hypothesis-{index:03d}"
        aliases[ref] = hypothesis.source_trace_id
        allowed.add(("hypothesis", ref))
        entry = {
            "ref": ref,
            "hypothesis": hypothesis.hypothesis,
            "confidence": hypothesis.confidence,
            "rule_id": hypothesis.rule_id,
        }
        if include_content:
            entry["evidence"] = list(hypothesis.evidence)
        if include_trace_ids:
            entry["source_trace_id"] = hypothesis.source_trace_id
        hypotheses.append(entry)

    data_quality = {
        "valid_count": report.data_quality.valid_count,
        "invalid_count": report.data_quality.invalid_count,
        "duplicate_ids": report.data_quality.duplicate_ids,
        "blank_rows": report.data_quality.blank_rows,
        "analyzable": report.data_quality.analyzable,
    }
    allowed.add(("data_quality", "data_quality"))

    regression: dict[str, object] = {"count": len(report.regression_tests)}
    if include_content:
        regression["cases"] = [
            {"id": case.id, "input": case.input} for case in report.regression_tests[:max_items]
        ]

    evidence: dict[str, object] = {
        "metrics": metrics,
        "failure_slices": slices,
        "root_cause_hypotheses": hypotheses,
        "data_quality": data_quality,
        "regression_tests": regression,
    }
    return PackagedEvidence(
        evidence=evidence, aliases=aliases, allowed_references=frozenset(allowed)
    )
