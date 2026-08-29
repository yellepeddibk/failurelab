# Search Service Runbook

The search service handles query parsing, index lookup, and result ranking for all
Meridian customers. It runs in the primary region with a warm standby in the
secondary region.

When an alert fires, first confirm the alert is not a duplicate of an active
incident. Check the service dashboard for error rate, saturation, and queue depth
before taking any action. Do not restart the service as a first step, because an
in-flight index merge can be lost and must then be rebuilt from the source of
truth.

If query latency at the ninety-ninth percentile exceeds two seconds for more than
ten minutes, shed optional ranking features and open an incident at severity three.
Index merges pause automatically while features are shed.

Restore ranking features only after latency has been below eight hundred
milliseconds for a full fifteen minutes.
