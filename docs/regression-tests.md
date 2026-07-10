# Regression Tests

Regression tests are deterministic draft YAML cases generated from explicit failed traces with replayable non-empty input.

- No draft case is generated for successful or unknown-outcome traces.
- Empty placeholder inputs are never synthesized.
- Each case includes source trace provenance (`source_trace_id`) and is marked as `draft`.
