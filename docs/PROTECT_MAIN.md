# Main Branch Protection

## Purpose

The `main` branch is protected so that every change remains reviewable, tested, and traceable. Changes reach `main` only through pull requests that pass CI.

## Operational source of truth

The active, enforced ruleset is managed in the GitHub UI:

Repository Settings > Rules > Rulesets > protect-main

GitHub's active UI configuration is the operational source of truth. Repository files do not enforce anything by themselves.

## Version-controlled snapshot

[.github/rulesets/protect-main.json](../.github/rulesets/protect-main.json) is a version-controlled export of the active ruleset. It exists for backup, review, audit history, manual import, and reuse. It is not automatically applied or synchronized with GitHub.

After changing the live ruleset in the GitHub UI, a maintainer should export the updated ruleset and update the tracked snapshot through a pull request.

## Expected active policy

- Enforcement: active
- Target: default branch
- Restrict branch deletion
- Block force pushes
- Require linear history
- Require changes through pull requests
- Require 1 approving review
- Dismiss stale approvals after new pushes
- Require approval of the most recent reviewable push
- Require review conversation resolution
- Squash is the only allowed merge method
- Require the `quality-gate` status check to pass
- Require the `CodeQL` status check to pass
- Require branches to be up to date before merging
- Repository administrators may bypass only for pull requests
- Direct pushes to `main` remain blocked

## Contributor workflow

1. Create a focused branch (`feat/`, `fix/`, `docs/`, `chore/`, etc.).
2. Open a pull request against `main`.
3. Resolve all review conversations.
4. Keep the branch up to date with `main`.
5. Wait for the `quality-gate` check to pass.
6. Merge with squash.

## Administrative caution

Grant Admin access sparingly. Repository administrators receive the configured pull-request-only bypass, so anyone with Admin access can merge a pull request without a separate approval.

## Importing the snapshot elsewhere

When importing the JSON into another repository, review every value before activation:

- confirm the target branch
- confirm required status-check names and integration IDs
- confirm approval requirements
- confirm allowed merge methods
- confirm bypass actors and bypass modes

Do not assume repository-specific IDs or integrations have the same meaning in another repository.

## Verifying the active ruleset

Open Repository Settings > Rules > Rulesets, select `protect-main`, and compare the configured rules against the policy above and the tracked snapshot. The snapshot reflects the ruleset at export time and is not guaranteed to match the live configuration until it is re-exported.
