"""Typer CLI application."""

from __future__ import annotations

import os
from enum import IntEnum
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console

from failurelab import api
from failurelab._version import __version__
from failurelab.config.settings import FailureLabConfig, load_config
from failurelab.exceptions import InvalidTraceDataError
from failurelab.ingestion.jsonl import ingest_jsonl

app = typer.Typer(help="FailureLab deterministic reliability analysis")
console = Console(no_color=bool(os.getenv("NO_COLOR")))


class ExitCode(IntEnum):
    SUCCESS = 0
    CLI_CONFIG_ERROR = 2
    INVALID_TRACE_DATA = 3
    FILE_ERROR = 4
    EVALUATION_REPORT_ERROR = 5
    QUALITY_GATE_FAILED = 10


def _resolve_config(
    config_path: Path | None,
    *,
    ingestion_mode: Literal["strict", "skip_invalid"] | None = None,
    retrieval_k: int | None = None,
    fail_on_regression: bool | None = None,
) -> FailureLabConfig:
    cfg = load_config(config_path)
    if ingestion_mode is not None:
        cfg.ingestion.mode = ingestion_mode
    if retrieval_k is not None:
        cfg.evaluation.retrieval_k = retrieval_k
    if fail_on_regression is not None:
        cfg.comparison.fail_on_regression = fail_on_regression
    return cfg


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show FailureLab version and exit."),
) -> None:
    if version:
        console.print(__version__)
        raise typer.Exit(code=ExitCode.SUCCESS)
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@app.command("validate")
def validate_cmd(
    path: Path = typer.Argument(..., exists=False, dir_okay=True, file_okay=True),
    config: Path | None = typer.Option(None, "--config"),
    strict: bool = typer.Option(False, "--strict", help="Stop on first invalid row."),
    skip_invalid: bool = typer.Option(False, "--skip-invalid", help="Continue past invalid rows."),
) -> None:
    """Validate trace JSONL input."""
    if strict and skip_invalid:
        raise typer.BadParameter("--strict and --skip-invalid are mutually exclusive")
    try:
        mode_override: Literal["strict", "skip_invalid"] | None = None
        if strict:
            mode_override = "strict"
        elif skip_invalid:
            mode_override = "skip_invalid"
        cfg = _resolve_config(config, ingestion_mode=mode_override)
    except Exception as error:
        raise typer.Exit(code=ExitCode.CLI_CONFIG_ERROR) from error
    strict_mode = cfg.ingestion.mode == "strict"

    ingestion = ingest_jsonl(path, strict=strict_mode)
    console.print(
        f"valid={len(ingestion.traces)} invalid={len(ingestion.issues)} duplicates={ingestion.duplicate_ids} blanks={ingestion.blank_rows}"
    )
    if ingestion.issues and ingestion.issues[0].error_type == "file_error":
        raise typer.Exit(code=ExitCode.FILE_ERROR)
    if ingestion.issues and strict_mode:
        issue = ingestion.issues[0]
        console.print(
            f"error row={issue.row_number} field={issue.field_path} message={issue.message}"
        )
        raise typer.Exit(code=ExitCode.INVALID_TRACE_DATA)
    if ingestion.issues:
        raise typer.Exit(code=ExitCode.INVALID_TRACE_DATA)


@app.command("analyze")
def analyze_cmd(
    path: Path = typer.Argument(..., exists=False, dir_okay=True, file_okay=True),
    output: Path = typer.Option(Path("reports"), "--output"),
    config: Path | None = typer.Option(None, "--config"),
    strict: bool = typer.Option(False, "--strict", help="Stop on first invalid row."),
    skip_invalid: bool = typer.Option(False, "--skip-invalid", help="Continue past invalid rows."),
    retrieval_k: int | None = typer.Option(None, "--retrieval-k", min=1),
    overwrite: bool = typer.Option(False, "--overwrite"),
    include_content: bool = typer.Option(False, "--include-content"),
    quiet: bool = typer.Option(False, "--quiet"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    """Analyze traces and produce deterministic reports."""
    _ = include_content
    _ = debug
    if strict and skip_invalid:
        raise typer.BadParameter("--strict and --skip-invalid are mutually exclusive")
    try:
        mode_override: Literal["strict", "skip_invalid"] | None = None
        if strict:
            mode_override = "strict"
        elif skip_invalid:
            mode_override = "skip_invalid"
        cfg = _resolve_config(config, ingestion_mode=mode_override, retrieval_k=retrieval_k)
    except Exception as error:
        raise typer.Exit(code=ExitCode.CLI_CONFIG_ERROR) from error
    strict_mode = cfg.ingestion.mode == "strict"

    try:
        report = api.analyze(path, config=cfg, strict=strict_mode)
    except InvalidTraceDataError as error:
        issue = error.issues[0]
        console.print(
            f"strict validation error row={issue.row_number} field={issue.field_path} message={issue.message}"
        )
        raise typer.Exit(code=ExitCode.INVALID_TRACE_DATA) from error
    except Exception as error:
        if debug:
            raise
        console.print(f"analysis failed: {error}")
        raise typer.Exit(code=ExitCode.EVALUATION_REPORT_ERROR) from error

    try:
        written = report.write(output, overwrite=overwrite)
    except FileExistsError as error:
        console.print(str(error))
        raise typer.Exit(code=ExitCode.FILE_ERROR) from error
    except OSError as error:
        console.print(str(error))
        raise typer.Exit(code=ExitCode.FILE_ERROR) from error

    if not quiet:
        console.print(
            f"valid={report.data_quality.valid_count} invalid={report.data_quality.invalid_count}"
        )
        for file_path in written:
            console.print(str(file_path))


@app.command("compare")
def compare_cmd(
    baseline_path: Path = typer.Argument(..., exists=False, dir_okay=True, file_okay=True),
    candidate_path: Path = typer.Argument(..., exists=False, dir_okay=True, file_okay=True),
    output: Path = typer.Option(Path("reports"), "--output"),
    config: Path | None = typer.Option(None, "--config"),
    retrieval_k: int | None = typer.Option(None, "--retrieval-k", min=1),
    fail_on_regression: bool = typer.Option(False, "--fail-on-regression"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Compare baseline and candidate traces."""
    try:
        cfg = _resolve_config(
            config,
            retrieval_k=retrieval_k,
            fail_on_regression=True if fail_on_regression else None,
        )
    except Exception as error:
        raise typer.Exit(code=ExitCode.CLI_CONFIG_ERROR) from error

    try:
        report = api.compare(baseline_path, candidate_path, config=cfg)
    except InvalidTraceDataError as error:
        issue = error.issues[0]
        console.print(f"error row={issue.row_number} message={issue.message}")
        raise typer.Exit(code=ExitCode.INVALID_TRACE_DATA) from error

    written = report.write(output, overwrite=overwrite)
    console.print(f"gate_status={report.gate_status}")
    console.print(f"gate_passed={report.gate_passed}")
    for output_path in written:
        console.print(str(output_path))
    if cfg.comparison.fail_on_regression and report.gate_passed is False:
        raise typer.Exit(code=ExitCode.QUALITY_GATE_FAILED)


def main() -> int:
    app()
    return ExitCode.SUCCESS
