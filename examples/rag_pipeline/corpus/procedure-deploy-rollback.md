# Deploy and Rollback Procedure

Every deploy proceeds through staging, canary, and full rollout. A deploy may not
skip canary unless the incident commander approves it during an active incident.

The canary stage routes five percent of traffic to the new version for a minimum of
fifteen minutes. During canary the deployer watches error rate, tail latency, and
saturation against the previous version. Any regression beyond the agreed threshold
stops the rollout automatically and the deployer must decide whether to proceed or
roll back.

A rollback must be initiated within thirty minutes of the regression being detected,
because the previous container image is evicted from the regional cache after that
window and a rollback then requires a full rebuild from source. A rebuild adds
roughly twenty-five minutes to recovery and is the single largest contributor to
extended incidents in this organization.

Rollbacks do not require approval. Any engineer may roll back a deploy at any time,
and no post-hoc justification is required.
