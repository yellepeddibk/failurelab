# Postmortem: May 2026 Search Latency Regression

Between May 2 and May 9 search latency at the ninety-ninth percentile rose from six
hundred milliseconds to three seconds. No errors were returned and no alert fired,
because the latency alert measured the median rather than a tail percentile.

The cause was a ranking model update that added a feature requiring a second index
lookup per result. The additional lookup was cheap in isolation but was executed
once per result rather than once per query.

The regression was found by a customer report, not by monitoring. Recovery was a
rollback of the ranking model, which took eleven minutes once the cause was known.

Action items were to alert on tail latency, to add a per-query lookup budget, and to
require load testing for ranking changes.
