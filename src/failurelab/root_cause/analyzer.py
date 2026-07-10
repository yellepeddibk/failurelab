"""Deterministic root-cause hypothesis generation."""

from __future__ import annotations

from dataclasses import dataclass

from failurelab.models.trace import TraceRecord
from failurelab.utilities.serialization import stable_dumps


@dataclass(slots=True)
class RootCauseHypothesis:
    source_trace_id: str
    hypothesis: str
    confidence: str
    rule_id: str
    evidence: list[str]
    limitations: list[str]


class RootCauseAnalyzer:
    def analyze(
        self,
        traces: list[TraceRecord],
        retrieval_k: int,
        repeated_tool_threshold: int,
        excessive_steps_threshold: int,
    ) -> list[RootCauseHypothesis]:
        raise NotImplementedError


class DeterministicRootCauseAnalyzer(RootCauseAnalyzer):
    def analyze(
        self,
        traces: list[TraceRecord],
        retrieval_k: int,
        repeated_tool_threshold: int,
        excessive_steps_threshold: int,
    ) -> list[RootCauseHypothesis]:
        output: list[RootCauseHypothesis] = []
        for trace in sorted(traces, key=lambda item: item.trace_id):
            output.append(
                self._classify_trace(
                    trace, retrieval_k, repeated_tool_threshold, excessive_steps_threshold
                )
            )
        return output

    def _classify_trace(
        self,
        trace: TraceRecord,
        retrieval_k: int,
        repeated_tool_threshold: int,
        excessive_steps_threshold: int,
    ) -> RootCauseHypothesis:
        expected = {s.strip() for s in (trace.expected_sources or []) if s.strip()}
        retrieved = [s.strip() for s in (trace.retrieved_sources or []) if s.strip()]
        retrieved_unique = []
        for source in retrieved:
            if source not in retrieved_unique:
                retrieved_unique.append(source)
        top_k = retrieved_unique[:retrieval_k]

        if expected and not expected.intersection(retrieved_unique):
            return _hyp(
                trace.trace_id,
                "retrieval_failure",
                "high",
                "RC001",
                ["Expected sources absent from all retrieved sources."],
            )
        if (
            expected
            and expected.intersection(retrieved_unique)
            and not expected.intersection(top_k)
        ):
            return _hyp(
                trace.trace_id,
                "ranking_failure",
                "high",
                "RC002",
                ["Expected source present only below retrieval_k."],
            )
        if (
            (trace.answer and trace.answer.strip())
            and retrieved_unique
            and not any(c.strip() for c in (trace.citations or []))
        ):
            return _hyp(
                trace.trace_id,
                "citation_missing",
                "medium",
                "RC003",
                ["Answer and retrieved sources exist but citations are empty."],
            )

        steps = trace.agent_steps or []
        failed_step = next((step for step in steps if step.success is False), None)
        if failed_step is not None:
            if failed_step.error and failed_step.error.category == "invalid_tool_arguments":
                return _hyp(
                    trace.trace_id,
                    "invalid_tool_arguments",
                    "high",
                    "RC005",
                    ["Tool step error category indicates invalid arguments."],
                )
            return _hyp(
                trace.trace_id,
                "tool_execution_failure",
                "high",
                "RC004",
                ["Agent step contains explicit failed tool outcome."],
            )

        if len(steps) > excessive_steps_threshold:
            return _hyp(
                trace.trace_id,
                "excessive_agent_steps",
                "medium",
                "RC006",
                [f"Step count exceeded threshold {excessive_steps_threshold}."],
            )

        if steps:
            seen: dict[str, int] = {}
            for step in steps:
                if not step.tool_name:
                    continue
                key = stable_dumps(
                    {"tool": step.tool_name.strip().lower(), "arguments": step.tool_arguments or {}}
                )
                seen[key] = seen.get(key, 0) + 1
            if any(count > repeated_tool_threshold for count in seen.values()):
                return _hyp(
                    trace.trace_id,
                    "repeated_tool_pattern",
                    "medium",
                    "RC007",
                    ["Repeated normalized tool+arguments pattern detected."],
                )

        if trace.success is False and expected.intersection(top_k):
            return _hyp(
                trace.trace_id,
                "possible_reasoning_failure",
                "low",
                "RC008",
                ["Expected sources are within top-k and no explicit tool failure exists."],
            )

        if trace.success is False:
            return _hyp(
                trace.trace_id,
                "insufficient_evidence",
                "low",
                "RC009",
                ["Failure present but deterministic rules did not isolate cause."],
            )

        return _hyp(
            trace.trace_id,
            "unknown",
            "low",
            "RC010",
            ["No failure condition requiring root-cause hypothesis."],
        )


def _hyp(
    trace_id: str, name: str, confidence: str, rule_id: str, evidence: list[str]
) -> RootCauseHypothesis:
    return RootCauseHypothesis(
        source_trace_id=trace_id,
        hypothesis=name,
        confidence=confidence,
        rule_id=rule_id,
        evidence=evidence,
        limitations=[
            "Deterministic heuristic analysis only.",
            "No causal certainty or significance claims.",
        ],
    )
