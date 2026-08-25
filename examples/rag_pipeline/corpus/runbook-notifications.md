# Notifications Service Runbook

The notifications service handles template rendering, delivery scheduling, and
retry backoff for all Meridian customers. It runs in the primary region with a warm
standby in the secondary region.

When an alert fires, first confirm the alert is not a duplicate of an active
incident. Check the service dashboard for error rate, saturation, and queue depth
before taking any action. Do not restart the service as a first step, because an
in-flight delivery batch can be lost and recipients may then receive duplicates.

If the delivery backlog exceeds fifty thousand messages, pause low priority
templates and open an incident at severity three. Retry backoff doubles
automatically while the backlog is draining.

Resume low priority templates only after the backlog has been below five thousand
messages for a full thirty minutes.
