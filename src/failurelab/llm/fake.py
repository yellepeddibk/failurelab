"""Deterministic in-memory provider for tests and offline demonstration.

Makes no network call and needs no API key. It returns grounded JSON derived
from the evidence in the request, so ``interpret`` produces a realistic,
deterministic ``InterpretationReport`` without any provider dependency.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from failurelab.llm.protocol import InterpretationRequest, ProviderResponse


@dataclass(slots=True)
class FakeProvider:
    name: str = "fake"
    model: str = "fake-model-1"
    response_text: str | None = None
    calls: int = 0

    def generate(self, request: InterpretationRequest) -> ProviderResponse:
        self.calls += 1
        text = self.response_text if self.response_text is not None else _synthesize(request)
        return ProviderResponse(
            text=text, model=self.model, token_usage={"input_tokens": 0, "output_tokens": 0}
        )


def _synthesize(request: InterpretationRequest) -> str:
    evidence = request.evidence
    observations: list[dict[str, object]] = []

    metric_name = _first_metric(evidence)
    if metric_name is not None:
        observations.append(
            {
                "statement": "The deterministic metrics report an overall failure rate.",
                "evidence": [{"kind": "metric", "id": metric_name}],
                "confidence": "medium",
            }
        )

    slice_ref = _first_ref(evidence, "failure_slices")
    if slice_ref is not None:
        observations.append(
            {
                "statement": "One segment shows failure elevated above the global rate.",
                "evidence": [{"kind": "slice", "id": slice_ref}],
                "confidence": "medium",
            }
        )

    hypothesis_ref = _first_ref(evidence, "root_cause_hypotheses")
    if hypothesis_ref is not None:
        observations.append(
            {
                "statement": (
                    "A deterministic root-cause hypothesis was recorded for a failed trace."
                ),
                "evidence": [{"kind": "hypothesis", "id": hypothesis_ref}],
                "confidence": "low",
            }
        )

    summary_evidence: list[dict[str, object]] = []
    if metric_name is not None:
        summary_evidence.append({"kind": "metric", "id": metric_name})
    else:
        summary_evidence.append({"kind": "data_quality", "id": "data_quality"})

    payload = {
        "summary": {
            "text": "Summary derived from the supplied deterministic evidence.",
            "evidence": summary_evidence,
        },
        "observations": observations,
        "caveats": ["Interpretation derived only from the supplied structured evidence."],
    }
    return json.dumps(payload)


def _first_metric(evidence: object) -> str | None:
    if not isinstance(evidence, dict):
        return None
    metrics = evidence.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        return None
    if "failure_rate" in metrics:
        return "failure_rate"
    first = next(iter(metrics))
    return first if isinstance(first, str) else None


def _first_ref(evidence: object, key: str) -> str | None:
    if not isinstance(evidence, dict):
        return None
    items = evidence.get(key)
    if not isinstance(items, list) or not items:
        return None
    first = items[0]
    if not isinstance(first, dict):
        return None
    ref = first.get("ref")
    return ref if isinstance(ref, str) else None
