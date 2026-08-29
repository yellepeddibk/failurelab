# Access Control Policy

Production access is granted by role, never to an individual account directly.
Every role grant expires after ninety days and must be renewed through the access
review process.

Break-glass access exists for incidents. It requires a second approver, is limited
to four hours, and every command issued under break-glass is recorded in the audit
log. Using break-glass access outside a declared incident is a policy violation.

Contractors receive read-only access by default. Write access requires written
approval from the service owner and the security lead, and it is revoked
automatically when the contract end date passes.
