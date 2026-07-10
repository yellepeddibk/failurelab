"""Typer CLI application."""

from __future__ import annotations

import os
from enum import IntEnum
from pathlib import Path

import typer
from rich.console import Console

from failurelab import __version__
from failurelab.config.settings import load_config
from failurelab.services.pipeline import analyze, compare, validate

app = typer.Typer(help="FailureLab deterministic reliability analysis")
console = Console(no_color=bool(os.getenv("NO_COLOR")))


class ExitCode(IntEnum):
    SUCCESS = 0
    CLI_CONFIG_ERROR = 2
    INVALID_TRACE_DATA = 3
    FILE_ERROR = 4
    EVALUATION_REPORT_ERROR = 5
    QUALITY_GATE_FAILED = 10


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
    strict: bool = typer.Option(True, "--strict/--skip-invalid"),
) -> None:
    """Validate trace JSONL input."""
    ingestion = validate(path, strict=strict)
    console.print(
        f"valid={len(ingestion.traces)} invalid={len(ingestion.issues)} duplicates={ingestion.duplicate_ids} blanks={ingestion.blank_rows}"
    )
    if ingestion.issues and ingestion.issues[0].error_type == "file_error":
        raise typer.Exit(code=ExitCode.FILE_ERROR)
    if ingestion.issues and strict:
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
        cfg = load_config(config)
    except Exception as error:
        raise typer.Exit(code=ExitCode.CLI_CONFIG_ERROR) from error
    if retrieval_k is not None:
        cfg.evaluation.retrieval_k = retrieval_k
    strict_mode = strict or cfg.ingestion.mode == "strict"
    if skip_invalid:
        strict_mode = False

    try:
        result = analyze(path, output, cfg, strict=strict_mode, overwrite=overwrite)
    except FileExistsError as error:
        console.print(str(error))
        raise typer.Exit(code=ExitCode.FILE_ERROR) from error
    except OSError as error:
        console.print(str(error))
        raise typer.Exit(code=ExitCode.FILE_ERROR) from error
    except Exception as error:
        if debug:
            raise
        console.print(f"analysis failed: {error}")
        raise typer.Exit(code=ExitCode.EVALUATION_REPORT_ERROR) from error

    if result.ingestion.issues and strict_mode:
        issue = result.ingestion.issues[0]
        console.print(
            f"strict validation error row={issue.row_number} field={issue.field_path} message={issue.message}"
        )
        raise typer.Exit(code=ExitCode.INVALID_TRACE_DATA)

    if not quiet:
        console.print(
            f"valid={len(result.ingestion.traces)} invalid={len(result.ingestion.issues)}"
        )
        for file_path in result.output_files:
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
    cfg = load_config(config)
    if retrieval_k is not None:
        cfg.evaluation.retrieval_k = retrieval_k
    if fail_on_regression:
        cfg.comparison.fail_on_regression = True

    result = compare(baseline_path, candidate_path, output, cfg, overwrite)
    if result.ingestion.issues:
        issue = result.ingestion.issues[0]
        console.print(f"error row={issue.row_number} message={issue.message}")
        raise typer.Exit(code=ExitCode.INVALID_TRACE_DATA)

    if result.comparison is None:
        raise typer.Exit(code=ExitCode.EVALUATION_REPORT_ERROR)

    console.print(f"gate_passed={result.comparison.gate_passed}")
    for output_path in result.output_files:
        console.print(str(output_path))
    if cfg.comparison.fail_on_regression and not result.comparison.gate_passed:
        raise typer.Exit(code=ExitCode.QUALITY_GATE_FAILED)


def main() -> int:
    app()
    return ExitCode.SUCCESS
