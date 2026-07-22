from __future__ import annotations

import json
import traceback

import pytest

import failurelab as fl
from failurelab import llm
from failurelab.llm import FakeProvider, InterpretationReport
from failurelab.llm.errors import InterpretationParseError, ProviderError
from failurelab.llm.evidence import pack_evidence

FAILED = {
    "schema_version": "0.1",
    "trace_id": "trace-xyz",
    "timestamp": "2026-01-01T00:00:00+00:00",
    "success": False,
    "query": "who owns incident 42?",
    "failure_type": "retrieval_failure",
}


def _report(traces: list[dict] | None = None) -> fl.AnalysisReport:
    return fl.analyze(traces if traces is not None else [FAILED], strict=False)


def _valid_response(**overrides: object) -> str:
    payload: dict[str, object] = {
        "summary": {"text": "ok", "evidence": [{"kind": "metric", "id": "failure_rate"}]},
        "observations": [
            {"statement": "grounded", "evidence": [{"kind": "metric", "id": "failure_rate"}]}
        ],
        "caveats": ["c"],
    }
    payload.update(overrides)
    return json.dumps(payload)


class _BoomProvider:
    name = "boom"

    def generate(self, request):
        raise RuntimeError("secret sk-abc123 must not surface")


def test_top_level_exports() -> None:
    assert callable(fl.interpret)
    assert fl.InterpretationReport is InterpretationReport
    assert hasattr(llm, "FakeProvider")


def test_interpret_returns_grounded_report_with_one_call() -> None:
    provider = FakeProvider()
    interp = fl.interpret(_report(), provider=provider)
    assert isinstance(interp, InterpretationReport)
    assert provider.calls == 1  # exactly one provider call, no loop
    assert interp.observations
    assert interp.summary_evidence  # the summary is grounded too
    allowed = {("metric", m.name) for m in _report().metrics} | {("hypothesis", "hypothesis-001")}
    for reference in interp.evidence_references:
        assert (reference.kind, reference.id) in allowed


# --- privacy -----------------------------------------------------------------


def test_evidence_omits_trace_ids_and_content_by_default() -> None:
    packaged = pack_evidence(
        _report(), include_content=False, include_trace_ids=False, max_items=20
    )
    blob = json.dumps(packaged.evidence)
    assert "trace-xyz" not in blob  # raw trace id never sent
    assert "who owns incident 42?" not in blob  # raw query content never sent
    hypotheses = packaged.evidence["root_cause_hypotheses"]
    assert isinstance(hypotheses, list)
    assert "source_trace_id" not in hypotheses[0]
    assert packaged.evidence["regression_tests"] == {"count": 1}


def test_pseudonymized_alias_maps_locally_only() -> None:
    packaged = pack_evidence(
        _report(), include_content=False, include_trace_ids=False, max_items=20
    )
    assert packaged.aliases["hypothesis-001"] == "trace-xyz"
    assert "trace-xyz" not in json.dumps(packaged.evidence)


def test_to_dict_omits_aliases_by_default() -> None:
    interp = fl.interpret(_report(), provider=FakeProvider())
    default_payload = interp.to_dict()
    assert "aliases" not in default_payload
    assert "trace-xyz" not in json.dumps(default_payload)  # original id never serialized

    with_aliases = interp.to_dict(include_aliases=True)
    assert with_aliases["aliases"]["hypothesis-001"] == "trace-xyz"


def test_resolve_reference_maps_alias_locally() -> None:
    interp = fl.interpret(_report(), provider=FakeProvider())
    hypothesis_refs = [r for r in interp.evidence_references if r.kind == "hypothesis"]
    assert hypothesis_refs
    assert interp.resolve_reference(hypothesis_refs[0]) == "trace-xyz"
    metric_refs = [r for r in interp.evidence_references if r.kind == "metric"]
    assert interp.resolve_reference(metric_refs[0]) == metric_refs[0].id


def test_include_trace_ids_opt_in() -> None:
    packaged = pack_evidence(_report(), include_content=False, include_trace_ids=True, max_items=20)
    assert "trace-xyz" in json.dumps(packaged.evidence)


def test_include_content_opt_in() -> None:
    packaged = pack_evidence(_report(), include_content=True, include_trace_ids=False, max_items=20)
    assert "who owns incident 42?" in json.dumps(packaged.evidence)


def test_evidence_bounded_by_max_items() -> None:
    traces = [dict(FAILED, trace_id=f"tf{i}", query=f"q{i}") for i in range(3)]
    packaged = pack_evidence(
        _report(traces), include_content=False, include_trace_ids=False, max_items=1
    )
    assert len(packaged.evidence["root_cause_hypotheses"]) == 1


# --- provider failures -------------------------------------------------------


def test_provider_failure_does_not_leak_secret_in_traceback() -> None:
    formatted = ""
    try:
        fl.interpret(_report(), provider=_BoomProvider())
    except ProviderError as error:
        formatted = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    assert formatted
    assert "sk-abc123" not in formatted  # provider exception chain is suppressed
    assert "boom" in formatted


# --- response schema validation ---------------------------------------------


def test_malformed_response_raises_parse_error() -> None:
    with pytest.raises(InterpretationParseError):
        fl.interpret(_report(), provider=FakeProvider(response_text="totally not json"))


def test_empty_object_response_raises_parse_error() -> None:
    with pytest.raises(InterpretationParseError):
        fl.interpret(_report(), provider=FakeProvider(response_text="{}"))


@pytest.mark.parametrize(
    "response",
    [
        _valid_response(summary=123),
        _valid_response(summary={"text": "", "evidence": []}),
        _valid_response(summary={"text": "ok", "evidence": "wrong"}),
        _valid_response(observations="wrong"),
        _valid_response(observations=[{"statement": "", "evidence": []}]),
        _valid_response(observations=[{"statement": "s", "evidence": "wrong"}]),
        _valid_response(caveats=False),
        _valid_response(caveats=[1]),
    ],
)
def test_invalid_schema_raises_parse_error(response: str) -> None:
    with pytest.raises(InterpretationParseError):
        fl.interpret(_report(), provider=FakeProvider(response_text=response))


def test_ungrounded_summary_rejected() -> None:
    response = _valid_response(
        summary={"text": "invented", "evidence": [{"kind": "metric", "id": "not_real"}]}
    )
    with pytest.raises(InterpretationParseError):
        fl.interpret(_report(), provider=FakeProvider(response_text=response))


def test_ungrounded_observations_dropped() -> None:
    response = _valid_response(
        observations=[
            {"statement": "grounded", "evidence": [{"kind": "metric", "id": "failure_rate"}]},
            {"statement": "ungrounded", "evidence": [{"kind": "metric", "id": "not_real"}]},
            {"statement": "noevidence", "evidence": []},
        ]
    )
    interp = fl.interpret(_report(), provider=FakeProvider(response_text=response))
    assert [o.statement for o in interp.observations] == ["grounded"]


# --- bounds ------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_output_tokens": 0},
        {"max_evidence_items": 0},
        {"timeout": 0},
        {"max_evidence_bytes": 0},
    ],
)
def test_invalid_bounds_rejected_before_provider_call(kwargs: dict) -> None:
    provider = FakeProvider()
    with pytest.raises(ValueError):
        fl.interpret(_report(), provider=provider, **kwargs)
    assert provider.calls == 0  # never contacted the provider


def test_oversized_evidence_rejected_before_provider_call() -> None:
    provider = FakeProvider()
    with pytest.raises(ValueError):
        fl.interpret(_report(), provider=provider, max_evidence_bytes=10)
    assert provider.calls == 0


# --- provenance --------------------------------------------------------------


def test_provenance_records_hashes_not_raw_text() -> None:
    interp = fl.interpret(_report(), provider=FakeProvider())
    meta = interp.generation_metadata
    assert len(meta.prompt_sha256) == 64
    assert len(meta.response_sha256) == 64

    payload = interp.to_dict()
    meta_dict = payload["generation_metadata"]
    assert "prompt_sha256" in meta_dict and "response_sha256" in meta_dict
    assert "prompt" not in meta_dict and "response" not in meta_dict and "system" not in meta_dict
    assert "You explain a deterministic reliability analysis" not in json.dumps(payload)


def test_provenance_records_all_request_bounds() -> None:
    interp = fl.interpret(_report(), provider=FakeProvider())
    params = interp.generation_metadata.parameters
    assert params["max_output_tokens"] == 1024
    assert params["max_evidence_items"] == 20
    assert params["max_evidence_bytes"] == 65_536
    assert params["timeout"] == 30.0


def test_report_projections_serializable() -> None:
    interp = fl.interpret(_report(), provider=FakeProvider())
    json.dumps(interp.to_dict())
    assert "# FailureLab Interpretation (generated)" in interp.to_markdown()
