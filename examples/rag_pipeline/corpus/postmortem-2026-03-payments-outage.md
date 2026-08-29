# Postmortem: March 2026 Payments Outage

On March 14 the payments service returned errors for forty-one minutes. Card
authorization failed for approximately eighteen thousand requests. No settlement
data was lost.

The trigger was a configuration change that reduced the connection pool size from
two hundred to twenty. The change was intended for a staging environment and was
applied to production because the environment selector defaulted to production when
the flag was omitted.

Detection took nine minutes because the error rate alert was configured against a
five-minute window with a three-window threshold. Recovery took a further thirty
two minutes, most of which was spent identifying which change had been applied.

Action items were to make the environment selector required with no default, to
shorten the alert window, and to add the configuration diff to the deploy
notification.
