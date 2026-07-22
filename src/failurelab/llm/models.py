"""Typed result objects for interpretation.

An ``InterpretationReport`` is generated content kept strictly separate from the
deterministic ``AnalysisReport``. It never overwrites deterministic findings,
every generated claim references supporting deterministic evidence, and its
provenance records hashes rather than raw prompt or response text.

The alias mapping that resolves pseudonymized references back to original
identifiers is held locally and is excluded from ``to_dict`` unless the caller
explicitly asks for it, so serializing a report cannot leak original trace IDs
by accident.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

EvidenceKind = Literal["metric", "slice", "hypothesis", "data_quality"]
Confidence = Literal["low", "medium", "high"]


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """A pointer from a generated statement back to a deterministic finding.

    ``id`` is an identifier from the evidence supplied to the provider: a metric
    name, or a local alias (for example ``slice-001``) that resolves through
    ``InterpretationReport.resolve_reference`` back to the deterministic report.
    """

    kind: EvidenceKind
    id: str


@dataclass(frozen=True, slots=True)
class Observation:
    statement: str
    evidence: tuple[EvidenceReference, ...]
    confidence: Confidence | None = None


@dataclass(frozen=True, slots=True)
class GenerationMetadata:
    provider: str
    model: str
    prompt_template_version: str
    prompt_sha256: str
    response_sha256: str
    parameters: Mapping[str, object]
    token_usage: Mapping[str, int] | None
    include_content: bool
    include_trace_ids: bool
    timestamp: str
    failurelab_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_template_version": self.prompt_template_version,
            "prompt_sha256": self.prompt_sha256,
            "response_sha256": self.response_sha256,
            "parameters": dict(self.parameters),
            "token_usage": dict(self.token_usage) if self.token_usage is not None else None,
            "include_content": self.include_content,
            "include_trace_ids": self.include_trace_ids,
            "timestamp": self.timestamp,
            "failurelab_version": self.failurelab_version,
        }


@dataclass(frozen=True, slots=True)
class InterpretationReport:
    summary: str
    summary_evidence: tuple[EvidenceReference, ...]
    observations: tuple[Observation, ...]
    caveats: tuple[str, ...]
    generation_metadata: GenerationMetadata
    aliases: Mapping[str, str]

    @property
    def evidence_references(self) -> tuple[EvidenceReference, ...]:
        seen: dict[tuple[str, str], EvidenceReference] = {}
        for reference in self.summary_evidence:
            seen.setdefault((reference.kind, reference.id), reference)
        for observation in self.observations:
            for reference in observation.evidence:
                seen.setdefault((reference.kind, reference.id), reference)
        return tuple(seen.values())

    def resolve_reference(self, reference: EvidenceReference) -> str:
        """Resolve a reference id back to its original deterministic identifier.

        Pseudonymized ids (``hypothesis-001``) resolve through the local alias
        map. Ids that were never pseudonymized are returned unchanged.
        """
        return self.aliases.get(reference.id, reference.id)

    def to_dict(self, *, include_aliases: bool = False) -> dict[str, Any]:
        """Serialize the report.

        The alias map is omitted by default because it can contain original
        trace IDs. Pass ``include_aliases=True`` to include it deliberately.
        """
        payload: dict[str, Any] = {
            "summary": self.summary,
            "summary_evidence": [
                {"kind": reference.kind, "id": reference.id} for reference in self.summary_evidence
            ],
            "observations": [
                {
                    "statement": observation.statement,
                    "evidence": [
                        {"kind": reference.kind, "id": reference.id}
                        for reference in observation.evidence
                    ],
                    "confidence": observation.confidence,
                }
                for observation in self.observations
            ],
            "caveats": list(self.caveats),
            "generation_metadata": self.generation_metadata.to_dict(),
        }
        if include_aliases:
            payload["aliases"] = dict(self.aliases)
        return payload

    def to_markdown(self) -> str:
        summary_refs = ", ".join(f"{r.kind}:{r.id}" for r in self.summary_evidence)
        lines = [
            "# FailureLab Interpretation (generated)",
            "",
            "Generated interpretation of a deterministic analysis report. This is not a",
            "deterministic result and makes no causal or significance claims.",
            "",
            "## Summary",
            self.summary,
            f"[evidence: {summary_refs}]",
            "",
            "## Observations",
        ]
        if self.observations:
            for observation in self.observations:
                refs = ", ".join(f"{r.kind}:{r.id}" for r in observation.evidence)
                confidence = f" ({observation.confidence})" if observation.confidence else ""
                lines.append(f"- {observation.statement}{confidence} [evidence: {refs}]")
        else:
            lines.append("- No grounded observations were produced.")
        lines.extend(["", "## Caveats"])
        lines.extend(f"- {caveat}" for caveat in self.caveats)
        return "\n".join(lines) + "\n"
