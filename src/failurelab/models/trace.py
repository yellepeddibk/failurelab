"""Typed trace models."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from failurelab.utilities.serialization import ensure_json_serializable, stable_dumps

SCHEMA_VERSION = "0.1"


class ErrorDetail(BaseModel):
    """Structured error details."""

    category: str
    code: str
    message: str
    retryable: bool = False
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("category", "code", "message")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must be non-empty")
        return trimmed

    @field_validator("metadata")
    @classmethod
    def _metadata_json(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return cast(dict[str, Any], ensure_json_serializable(value))


class AgentStep(BaseModel):
    """Single agent step."""

    step_id: str
    sequence: int
    step_type: str
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_result: dict[str, Any] | None = None
    success: bool | None = None
    error: ErrorDetail | None = None
    latency_ms: float | None = None
    model: str | None = None
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("step_id", "step_type")
    @classmethod
    def _trimmed_nonempty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must be non-empty")
        return trimmed

    @field_validator("sequence")
    @classmethod
    def _sequence_nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("sequence must be non-negative")
        return value

    @field_validator("latency_ms")
    @classmethod
    def _latency_nonnegative(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not math.isfinite(value) or value < 0:
            raise ValueError("latency_ms must be finite and non-negative")
        return value

    @field_validator("tool_arguments", "tool_result", "metadata")
    @classmethod
    def _json_fields(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return cast(dict[str, Any], ensure_json_serializable(value))


class TraceRecord(BaseModel):
    """Primary RAG/agent trace contract."""

    schema_version: str = Field(default=SCHEMA_VERSION)
    trace_id: str
    project: str | None = None
    run_id: str | None = None
    version: str | None = None
    timestamp: datetime | None = None
    query: str | None = None
    answer: str | None = None
    success: bool | None = None
    failure_type: str | None = None
    error: ErrorDetail | None = None
    model: str | None = None
    prompt_version: str | None = None
    retriever_version: str | None = None
    retrieved_context: list[str] | None = None
    retrieved_sources: list[str] | None = None
    expected_sources: list[str] | None = None
    citations: list[str] | None = None
    latency_ms: float | None = None
    cost_usd: float | None = None
    metadata: dict[str, Any] | None = None
    agent_steps: list[AgentStep] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("trace_id")
    @classmethod
    def _trace_id_nonempty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("trace_id must be non-empty")
        return trimmed

    @field_validator("timestamp")
    @classmethod
    def _timestamp_tzaware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

    @field_validator("latency_ms", "cost_usd")
    @classmethod
    def _finite_nonnegative(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not math.isfinite(value) or value < 0:
            raise ValueError("must be finite and non-negative")
        return value

    @field_validator("retrieved_sources", "expected_sources", "citations")
    @classmethod
    def _source_values_nonempty(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        output: list[str] = []
        for item in value:
            trimmed = item.strip()
            if not trimmed:
                raise ValueError("source identifiers must be non-empty")
            output.append(trimmed)
        return output

    @field_validator("metadata")
    @classmethod
    def _metadata_json(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return cast(dict[str, Any], ensure_json_serializable(value))

    @model_validator(mode="after")
    def _sorted_steps(self) -> TraceRecord:
        if self.agent_steps is not None:
            self.agent_steps = sorted(
                self.agent_steps, key=lambda step: (step.sequence, step.step_id)
            )
        return self

    def to_stable_json(self) -> str:
        return stable_dumps(self.model_dump(mode="json", exclude_none=True))


class ValidationIssue(BaseModel):
    """Validation issue for bad rows."""

    row_number: int
    trace_id: str | None = None
    error_type: Literal["file_error", "json_error", "schema_error", "duplicate_id"]
    field_path: str | None = None
    message: str
    safe_excerpt: str | None = None
    input_file: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("row_number")
    @classmethod
    def _row_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("row_number must be >= 1")
        return value
