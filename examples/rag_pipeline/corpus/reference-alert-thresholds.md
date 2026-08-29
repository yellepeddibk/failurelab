# Alert Thresholds

Payments alerts on an error rate above one percent measured over a two-minute
window. Search alerts on ninety-ninth percentile latency above one and a half
seconds over a five-minute window. Notifications alerts on a delivery backlog above
twenty-five thousand messages.

Every alert names the service, the measured value, the threshold, and a link to the
runbook. An alert that cannot name its runbook is considered misconfigured and is
fixed rather than silenced.

Threshold changes require the service owner to approve and are recorded in the
change log.
