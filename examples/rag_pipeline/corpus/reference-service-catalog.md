# Service Catalog

Meridian operates four customer-facing services and three internal services.

The customer-facing services are payments, search, notifications, and the account
API. Each has a named service owner, a runbook, and a dedicated alert route.

The internal services are the deploy controller, the configuration store, and the
audit log collector. Internal services have runbooks but route alerts to the
platform team rather than to a per-service escalation owner.

Every service records its dependencies in the catalog entry. A service may not take
a hard dependency on another service without the other owner agreeing.
