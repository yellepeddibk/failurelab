"""Optional narrative interpretation of a deterministic analysis report.

``interpret`` makes exactly one provider call, never overwrites deterministic
findings, requires every generated claim (including the summary) to reference
supplied evidence, and records prompt and response hashes rather than raw text.
It performs no agent loop, no follow-up calls, and no paid retries. Execution
bounds are validated before the provider is contacted.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import cast

from failurelab._version import __version__
from failurelab.llm.errors import (
    InterpretationParseError,
    ProviderError,
    SanitizedProviderError,
)
from failurelab.llm.evidence import PROMPT_TEMPLATE_VERSION, pack_evidence
from failurelab.llm.models import (
    Confidence,
    EvidenceKind,
    EvidenceReference,
    GenerationMetadata,
    InterpretationReport,
    Observation,
)
from failurelab.llm.protocol import InterpretationProvider, InterpretationRequest
from failurelab.reports.models import AnalysisReport
from failurelab.utilities.serialization import stable_dumps

DEFAULT_MAX_EVIDENCE_BYTES = 65_536

_SYSTEM_PROMPT = (
    "You explain a deterministic reliability analysis of RAG and agent traces. "
    "You are given structured evidence (metrics, failure slices, root-cause "
    "hypotheses, data quality). Return ONLY a JSON object with keys: "
    '"summary" (object with "text" string and "evidence" array), "observations" '
    '(array of objects with "statement" string, "evidence" array, and optional '
    '"confidence" of "low"|"medium"|"high"), and "caveats" (array of strings). '
    'Every "evidence" array holds {"kind","id"} objects. Reference evidence only '
    "by the exact kind and id present in the supplied evidence, including for the "
    "summary. Do not invent metrics, values, or findings. Do not make causal or "
    "statistical-significance claims. State uncertainty plainly."
)

_STANDARD_CAVEATS: tuple[str, ...] = (
    "Generated interpretation, not a deterministic result.",
    "No causal or statistical-significance claims.",
    "Verify observations against the deterministic report before acting.",
)


def interpret(
    report: AnalysisReport,
    *,
    provider: InterpretationProvider,
    include_content: bool = False,
    include_trace_ids: bool = False,
    max_output_tokens: int = 1024,
    max_evidence_items: int = 20,
    timeout: float = 30.0,
    max_evidence_bytes: int = DEFAULT_MAX_EVIDENCE_BYTES,
) -> InterpretationReport:
    """Generate an interpretation of ``report`` using ``provider`` (one call).

    Sends only structured, privacy-filtered evidence. ``include_content`` and
    ``include_trace_ids`` default to false; nothing about the caller's
    environment activates a provider on its own. Invalid bounds and oversized
    evidence are rejected before the provider is contacted.
    """
    _validate_bounds(
        max_output_tokens=max_output_tokens,
        max_evidence_items=max_evidence_items,
        timeout=timeout,
        max_evidence_bytes=max_evidence_bytes,
    )
    packaged = pack_evidence(
        report,
        include_content=include_content,
        include_trace_ids=include_trace_ids,
        max_items=max_evidence_items,
    )
    serialized_evidence = stable_dumps(packaged.evidence)
    evidence_bytes = len(serialized_evidence.encode("utf-8"))
    if evidence_bytes > max_evidence_bytes:
        raise ValueError(
            f"serialized evidence is {evidence_bytes} bytes, "
            f"which exceeds max_evidence_bytes ({max_evidence_bytes})"
        )

    parameters: dict[str, object] = {
        "max_output_tokens": max_output_tokens,
        "max_evidence_items": max_evidence_items,
        "max_evidence_bytes": max_evidence_bytes,
        "timeout": timeout,
    }
    request = InterpretationRequest(
        system=_SYSTEM_PROMPT, evidence=packaged.evidence, parameters=parameters
    )

    try:
        response = provider.generate(request)
    except SanitizedProviderError:
        # Only errors an adapter explicitly marked as safe pass through unchanged.
        raise
    except Exception as error:
        # Suppress the provider exception chain: its message may carry credentials.
        raise ProviderError(
            f"provider {provider.name!r} failed to generate a response ({type(error).__name__})"
        ) from None

    payload = _parse_response(response.text)
    summary, summary_evidence = _build_summary(payload, packaged.allowed_references)
    observations = _build_observations(payload, packaged.allowed_references)
    caveats = _STANDARD_CAVEATS + _model_caveats(payload)

    prompt_digest = hashlib.sha256(
        stable_dumps(
            {"system": request.system, "evidence": request.evidence, "parameters": parameters}
        ).encode("utf-8")
    ).hexdigest()
    response_digest = hashlib.sha256(response.text.encode("utf-8")).hexdigest()

    metadata = GenerationMetadata(
        provider=provider.name,
        model=response.model,
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        prompt_sha256=prompt_digest,
        response_sha256=response_digest,
        parameters=parameters,
        token_usage=dict(response.token_usage) if response.token_usage is not None else None,
        include_content=include_content,
        include_trace_ids=include_trace_ids,
        timestamp=datetime.now(timezone.utc).isoformat(),
        failurelab_version=__version__,
    )
    return InterpretationReport(
        summary=summary,
        summary_evidence=summary_evidence,
        observations=tuple(observations),
        caveats=caveats,
        generation_metadata=metadata,
        aliases=packaged.aliases,
    )


def _validate_bounds(
    *,
    max_output_tokens: int,
    max_evidence_items: int,
    timeout: float,
    max_evidence_bytes: int,
) -> None:
    if max_output_tokens <= 0:
        raise ValueError("max_output_tokens must be greater than 0")
    if max_evidence_items <= 0:
        raise ValueError("max_evidence_items must be greater than 0")
    if timeout <= 0:
        raise ValueError("timeout must be greater than 0")
    if max_evidence_bytes <= 0:
        raise ValueError("max_evidence_bytes must be greater than 0")


def _parse_response(text: str) -> dict[str, object]:
    payload = _load_object(text)
    _require_schema(payload)
    return payload


def _load_object(text: str) -> dict[str, object]:
    candidates = [text.strip()]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return cast(dict[str, object], parsed)
    raise InterpretationParseError("provider response was not a valid JSON object")


def _require_schema(payload: dict[str, object]) -> None:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise InterpretationParseError("summary must be an object with text and evidence")
    text = summary.get("text")
    if not isinstance(text, str) or not text.strip():
        raise InterpretationParseError("summary.text must be a non-empty string")
    if not isinstance(summary.get("evidence"), list):
        raise InterpretationParseError("summary.evidence must be a list")

    observations = payload.get("observations")
    if not isinstance(observations, list):
        raise InterpretationParseError("observations must be a list")
    for item in observations:
        if not isinstance(item, dict):
            raise InterpretationParseError("each observation must be an object")
        statement = item.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            raise InterpretationParseError("each observation must have a non-empty statement")
        if not isinstance(item.get("evidence"), list):
            raise InterpretationParseError("each observation must have an evidence list")

    caveats = payload.get("caveats")
    if not isinstance(caveats, list) or any(not isinstance(item, str) for item in caveats):
        raise InterpretationParseError("caveats must be a list of strings")


def _build_summary(
    payload: dict[str, object], allowed: frozenset[tuple[str, str]]
) -> tuple[str, tuple[EvidenceReference, ...]]:
    summary = cast(dict[str, object], payload["summary"])
    references = _grounded_references(summary.get("evidence"), allowed)
    if not references:
        raise InterpretationParseError("summary must reference at least one supplied evidence item")
    return cast(str, summary["text"]).strip(), tuple(references)


def _build_observations(
    payload: dict[str, object], allowed: frozenset[tuple[str, str]]
) -> list[Observation]:
    observations: list[Observation] = []
    for item in cast(list[object], payload["observations"]):
        entry = cast(dict[str, object], item)
        references = _grounded_references(entry.get("evidence"), allowed)
        if not references:
            continue  # structurally valid but ungrounded: dropped
        observations.append(
            Observation(
                statement=cast(str, entry["statement"]).strip(),
                evidence=tuple(references),
                confidence=_confidence(entry.get("confidence")),
            )
        )
    return observations


def _grounded_references(
    raw: object, allowed: frozenset[tuple[str, str]]
) -> list[EvidenceReference]:
    if not isinstance(raw, list):
        return []
    references: list[EvidenceReference] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        identifier = entry.get("id")
        if not isinstance(kind, str) or not isinstance(identifier, str):
            continue
        if (kind, identifier) in allowed:
            references.append(EvidenceReference(kind=cast(EvidenceKind, kind), id=identifier))
    return references


def _confidence(value: object) -> Confidence | None:
    if value in ("low", "medium", "high"):
        return value
    return None


def _model_caveats(payload: dict[str, object]) -> tuple[str, ...]:
    raw = cast(list[object], payload["caveats"])
    return tuple(item.strip() for item in raw if isinstance(item, str) and item.strip())
