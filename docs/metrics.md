# Metrics

FailureLab metrics expose value, numerator, denominator, eligibility, exclusions, and unavailable reasons.

- Counts may legitimately be `0`.
- Observation-dependent metrics (rates, averages, percentiles, extrema) are emitted as unavailable when no eligible observations exist:
  - `value: null`
  - `unavailable_reason`: deterministic reason text
- Unavailable values are not treated as numeric zero in comparison deltas.
