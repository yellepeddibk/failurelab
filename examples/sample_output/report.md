# FailureLab Analysis Report

## 1. Run overview
Deterministic analysis generated from local trace data.

## 2. Data quality
Invalid rows detected: 0

## 3. Outcomes
- **total_rows**: 4
- **known_outcome_count**: 4
- **failure_rate**: 0.5

## 4. Retrieval
- retrieval_recall_at_k: 0.75

## 5. Citations
- citation_presence_rate: 0.5

## 6. Agent/tool metrics
- tool_success_rate: unavailable (no known tool outcomes)

## 7. Latency
- latency_average_ms: 352.5
- latency_p95_ms: 486.5

## 8. Cost
- cost_total_usd: 0.1
- cost_per_successful_trace_usd: 0.02

## 9. Breakdowns
Breakdowns are available in metrics.json.

## 10. Failure slices
- No elevated failure slices found.

## 11. Root-cause hypotheses
- rag-002: retrieval_failure (high)
- rag-003: possible_reasoning_failure (low)

## 12. Draft regression tests
Generated cases: 2

## 13. Limitations
- Deterministic heuristic analysis only.
- No significance claims.

## 14. Recommended next steps
- No elevated slices to prioritize from this run.
