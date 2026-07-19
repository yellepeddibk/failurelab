# Agent Architecture

FailureLab exposes its deterministic analysis as typed skills (metrics, slice discovery, root-cause classification, comparison, regression drafting, and so on).

The `DeterministicInvestigationAgent` executes a caller-provided, ordered sequence of those skill invocations and aggregates their structured evidence into a single result. It performs no planning, routing, or autonomous decision-making: the caller supplies the exact sequence of skills to run, and the output is a deterministic function of the inputs. It is an orchestration helper over the deterministic skills, not an autonomous agent.
