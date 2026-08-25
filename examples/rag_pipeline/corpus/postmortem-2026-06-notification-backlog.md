# Postmortem: June 2026 Notification Backlog

On June 21 the notification delivery backlog grew to nine hundred thousand messages
over six hours. Delivery was delayed by up to four hours. No messages were lost and
no duplicates were sent.

The cause was a downstream provider rate limit that dropped from ten thousand to one
thousand messages per minute without notice. Retry backoff amplified the backlog
because failed deliveries were retried at the original rate.

Detection was immediate because the backlog alert fired correctly. Recovery required
pausing low priority templates and negotiating a temporary limit increase with the
provider.

Action items were to make retry backoff respond to observed provider limits, to
alert on provider limit changes, and to document the pause procedure.
