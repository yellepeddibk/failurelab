# Environment Matrix

There are three environments: development, staging, and production.

Development uses synthetic data only and is reset weekly. Staging uses a scrubbed
copy of production data refreshed monthly and is the only environment where
migrations are rehearsed. Production is the live environment.

The environment selector is a required argument for every deploy and configuration
command. There is no default value, and a command without it fails rather than
guessing.

Staging and production run identical infrastructure at different scale. Development
runs a reduced footprint and does not represent production performance.
