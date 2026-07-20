# Command-line interface

The CLI wraps the same deterministic engine as the [Python API](api.md) and writes the same report files.

```bash
failurelab --version
failurelab validate traces.jsonl
failurelab analyze traces.jsonl --output reports --overwrite
failurelab compare baseline.jsonl candidate.jsonl --output reports --overwrite
```

## Commands

### `validate`

Validate trace JSONL input and report counts of valid, invalid, duplicate, and blank rows.

### `analyze`

Analyze traces and write reports. Common options:

- `--output` output directory (default `reports`)
- `--config` path to a YAML config file
- `--strict` / `--skip-invalid` ingestion mode (mutually exclusive)
- `--retrieval-k` retrieval cut-off for recall metrics
- `--overwrite` replace existing output files
- `--quiet` suppress the summary line

### `compare`

Compare a baseline run against a candidate run. Common options:

- `--output`, `--config`, `--overwrite`
- `--fail-on-regression` exit non-zero when a configured gate fails

## Configuration precedence

Configuration resolves deterministically: built-in defaults, then a config file (`--config`), then explicit CLI overrides. `run_manifest.json` records the effective resolved configuration.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 2 | CLI or configuration error |
| 3 | Invalid trace data |
| 4 | File error |
| 5 | Evaluation or report error |
| 10 | Quality gate failed |
