# Database Migration Procedure

Migrations are forward-only. A migration that cannot be rolled forward safely must
be split into steps that each leave the schema in a working state for both the old
and new application versions.

Adding a column is safe when the column is nullable or has a default. Dropping a
column requires two releases: one that stops reading and writing the column, and a
later one that drops it. Renaming a column is never done directly and is expressed
as an add, a backfill, and a drop.

Every migration is tested against a restored production snapshot before it is
applied. Migrations that take longer than five minutes run outside business hours.
