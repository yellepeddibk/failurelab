# Escalation Contacts

Alerts route to the escalation owner for the owning service. The rotation calendar
is the authoritative source for who currently holds that role.

If the escalation owner does not acknowledge within the policy window, the alert
escalates to the engineering manager for that team, and then to the director on
duty after a further twenty minutes.

Security incidents bypass the service rotation and route directly to the security
on-call. Legal escalation is handled by the incident commander and never by the
responding engineer.
