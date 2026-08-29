# Secret Rotation Procedure

Secrets rotate on a ninety-day schedule. Rotation is performed by the service owner
and verified by a second engineer before the previous secret is revoked.

The order matters. Add the new secret alongside the old one, deploy the change,
confirm every instance has picked up the new value, and only then revoke the old
secret. Revoking first causes an outage that cannot be rolled back, because the old
secret is unrecoverable once revoked.

Emergency rotation follows the same order but compresses the verification window.
An emergency rotation must be recorded in the incident log even when no incident was
declared.
