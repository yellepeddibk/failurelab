#!/usr/bin/env python3
"""Create or update the protect-main ruleset through GitHub REST API."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import TypeAlias

API_VERSION = "2022-11-28"
JsonValue: TypeAlias = dict[str, object] | list[dict[str, object]]


def build_ruleset_payload() -> dict[str, object]:
    return {
        "name": "protect-main",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "bypass_actors": [],
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 1,
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": False,
                    "require_last_push_approval": True,
                    "required_review_thread_resolution": True,
                },
            },
            {"type": "required_linear_history"},
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "required_status_checks": [{"context": "quality-gate", "integration_id": None}],
                },
            },
        ],
    }


def parse_repo(value: str) -> tuple[str, str]:
    if "/" not in value:
        raise ValueError("repository must be in OWNER/REPO format")
    owner, repo = value.split("/", 1)
    return owner.strip(), repo.strip()


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "failurelab-protect-main-script",
    }


def request_json(
    method: str, url: str, token: str, payload: dict[str, object] | None = None
) -> JsonValue:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "api.github.com":
        raise ValueError("request_json only allows https://api.github.com URLs")
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url=url, method=method, data=body, headers=_headers(token))
    with urllib.request.urlopen(req, timeout=20) as response:  # nosec B310
        return json.loads(response.read().decode("utf-8"))


def configure_ruleset(owner: str, repo: str, token: str, apply: bool, dry_run: bool) -> int:
    payload = build_ruleset_payload()
    base_url = f"https://api.github.com/repos/{owner}/{repo}/rulesets"
    existing = request_json("GET", base_url, token)
    current = next((item for item in existing if item.get("name") == "protect-main"), None)

    if dry_run:
        print("Dry run: no mutation performed")
        print(
            json.dumps(
                {
                    "owner": owner,
                    "repo": repo,
                    "action": "update" if current else "create",
                    "ruleset": payload,
                },
                indent=2,
            )
        )
        return 0

    if not apply:
        print("Use --apply to make changes. --dry-run shows payload without changes.")
        return 2

    try:
        if current:
            ruleset_id = current["id"]
            request_json("PUT", f"{base_url}/{ruleset_id}", token, payload)
            action = "updated"
        else:
            request_json("POST", base_url, token, payload)
            action = "created"
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        if error.code in {401, 403}:
            print("Permission error: token lacks admin/ruleset permissions.")
        else:
            print(f"GitHub API error {error.code}: {body}")
        return 1

    verify = request_json("GET", base_url, token)
    if not any(item.get("name") == "protect-main" for item in verify):
        print("verification failed: protect-main ruleset not found after apply")
        return 1

    print(f"protect-main ruleset {action} and verified")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        help="Repository as OWNER/REPO. Auto-detected from GITHUB_REPOSITORY when omitted.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply create/update mutation.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payload and planned action without mutation.",
    )
    args = parser.parse_args()

    repo_value = args.repo or os.getenv("GITHUB_REPOSITORY")
    if not repo_value:
        print("repository not provided; set --repo OWNER/REPO or GITHUB_REPOSITORY")
        return 2

    try:
        owner, repo = parse_repo(repo_value)
    except ValueError as error:
        print(str(error))
        return 2

    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        print("missing GH_TOKEN or GITHUB_TOKEN")
        return 2

    return configure_ruleset(owner, repo, token, apply=args.apply, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
