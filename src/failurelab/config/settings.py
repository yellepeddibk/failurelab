"""Versioned configuration models and loading."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from failurelab.models.trace import SCHEMA_VERSION


class IngestionConfig(BaseModel):
    mode: str = Field(default="strict", pattern="^(strict|skip-invalid)$")


class EvaluationConfig(BaseModel):
    retrieval_k: int = Field(default=3, gt=0)
    excessive_steps_threshold: int = Field(default=8, ge=1)


class SliceConfig(BaseModel):
    minimum_support: int = Field(default=2, ge=1)
    maximum_findings: int = Field(default=10, ge=1)


class RootCauseConfig(BaseModel):
    repeated_tool_threshold: int = Field(default=2, ge=2)


class RegressionConfig(BaseModel):
    include_thresholds: bool = False


class ComparisonGateConfig(BaseModel):
    max_failure_rate_increase: float | None = Field(default=None, ge=0)
    max_latency_p95_increase_ms: float | None = Field(default=None, ge=0)


class ComparisonConfig(BaseModel):
    fail_on_regression: bool = False


class ReportingConfig(BaseModel):
    include_content: bool = False


class FailureLabConfig(BaseModel):
    schema_version: str = SCHEMA_VERSION
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    slices: SliceConfig = Field(default_factory=SliceConfig)
    root_cause: RootCauseConfig = Field(default_factory=RootCauseConfig)
    regression_tests: RegressionConfig = Field(default_factory=RegressionConfig)
    comparison: ComparisonConfig = Field(default_factory=ComparisonConfig)
    gate: ComparisonGateConfig = Field(default_factory=ComparisonGateConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)

    model_config = ConfigDict(extra="forbid")


def load_config(path: Path | None = None) -> FailureLabConfig:
    if path is None:
        return FailureLabConfig()
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise ValueError("configuration file root must be a mapping")
    try:
        return FailureLabConfig.model_validate(loaded)
    except ValidationError as error:
        detail = "; ".join(
            f"{'.'.join(map(str, issue['loc']))}: {issue['msg']}" for issue in error.errors()
        )
        raise ValueError(f"invalid configuration: {detail}") from error
