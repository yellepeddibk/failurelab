# Payments Service Runbook

The payments service handles card authorization, settlement batching, and refund
processing for all Meridian customers. It runs in the primary region with a warm
standby in the secondary region.

When an alert fires, first confirm the alert is not a duplicate of an active
incident. Check the service dashboard for error rate, saturation, and queue depth
before taking any action. Do not restart the service as a first step, because an
in-flight settlement batch can be lost and must then be reconciled by hand.

If the error rate exceeds five percent for more than ten minutes, drain traffic to
the standby region and open an incident at severity two. Settlement batches pause
automatically during a drain and resume once traffic returns.

Restore normal traffic only after the error rate has been below one percent for a
full fifteen minutes.
