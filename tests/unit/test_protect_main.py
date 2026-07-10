from __future__ import annotations

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "configure_protect_main",
    Path(__file__).resolve().parents[2] / "scripts" / "configure_protect_main.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_parse_repo() -> None:
    owner, repo = MODULE.parse_repo("org/repo")
    assert owner == "org"
    assert repo == "repo"


def test_payload_has_required_rules() -> None:
    payload = MODULE.build_ruleset_payload()
    assert payload["name"] == "protect-main"
    rule_types = {rule["type"] for rule in payload["rules"]}
    assert {
        "deletion",
        "non_fast_forward",
        "pull_request",
        "required_linear_history",
        "required_status_checks",
    }.issubset(rule_types)
