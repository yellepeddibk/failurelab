# Data Retention Policy

Customer records are retained for seven years after account closure to satisfy
financial reporting obligations. Application logs are retained for ninety days.
Debug traces are retained for fourteen days and are never included in backups.

Deletion requests from customers are honored within thirty days. The request
removes customer records from primary storage immediately and from backups at the
next backup rotation, which completes within thirty days.

Retention periods are set by the legal team. Engineering may shorten a retention
period for a specific data class only with written approval.
