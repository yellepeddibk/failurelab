# Quickstart

```bash
python -m pip install "failurelab>=0.2.0"
```

## Analyze traces in memory

Pass a list of trace dictionaries (or `TraceRecord` objects). Nothing is written to disk unless you call `write`.

```python
import failurelab as fl

traces = [
    {"schema_version": "0.1", "trace_id": "t1",
     "timestamp": "2026-01-01T00:00:00+00:00", "success": True},
    {"schema_version": "0.1", "trace_id": "t2",
     "timestamp": "2026-01-01T00:01:00+00:00", "success": False,
     "query": "Who owns this incident?", "failure_type": "retrieval_failure"},
]

report = fl.analyze(traces)

failure_rate = report.metric("failure_rate")
print(failure_rate.value if failure_rate else None)
print(report.data_quality.analyzable)

report.write("reports", overwrite=True)  # persistence is explicit and opt-in
```

`fl.analyze` also accepts a path to a JSONL file:

```python
report = fl.analyze("traces.jsonl")
```

Inspect the report:

```python
report.failure_slices          # segments with elevated failure
report.root_cause_hypotheses   # per-failed-trace hypotheses
report.to_markdown()           # the human-readable report as a string
report.to_dict()               # a JSON-serializable view of everything
```

## Validate input

`validate` inspects the complete input and reports every issue. It never raises for invalid data.

```python
result = fl.validate("traces.jsonl")   # or an iterable of dicts / TraceRecord
print(result.is_valid, result.data_quality.invalid_count)
```

`analyze` and `compare` instead raise `InvalidTraceDataError` in strict mode (the default), carrying the full issue list.

## Compare two runs

```python
comparison = fl.compare("baseline.jsonl", "candidate.jsonl")
print(comparison.gate_status, comparison.gate_passed, comparison.is_comparable)
comparison.write("reports", overwrite=True)
```

## Runnable examples

Complete, runnable versions live in the repository:

- [examples/analyze_in_memory.py](https://github.com/yellepeddibk/failurelab/blob/main/examples/analyze_in_memory.py)
- [examples/analyze_from_jsonl.py](https://github.com/yellepeddibk/failurelab/blob/main/examples/analyze_from_jsonl.py)
