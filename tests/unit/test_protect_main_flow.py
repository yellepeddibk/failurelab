from __future__ import annotations

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "configure_protect_main",
    Path(__file__).resolve().parents[2] / "scripts" / "configure_protect_main.py",
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_dry_run(monkeypatch):
    monkeypatch.setattr(MODULE, "request_json", lambda method, url, token, payload=None: [])
    code = MODULE.configure_ruleset("o", "r", "t", apply=False, dry_run=True)
    assert code == 0


def test_apply_create(monkeypatch):
    calls = []

    def fake_request(method, url, token, payload=None):
        calls.append(method)
        if method == "GET":
            return [] if len(calls) == 1 else [{"name": "protect-main"}]
        return {"ok": True}

    monkeypatch.setattr(MODULE, "request_json", fake_request)
    code = MODULE.configure_ruleset("o", "r", "t", apply=True, dry_run=False)
    assert code == 0


def test_apply_update(monkeypatch):
    calls = []

    def fake_request(method, url, token, payload=None):
        calls.append(method)
        if method == "GET":
            return [{"id": 1, "name": "protect-main"}]
        return {"ok": True}

    monkeypatch.setattr(MODULE, "request_json", fake_request)
    code = MODULE.configure_ruleset("o", "r", "t", apply=True, dry_run=False)
    assert code == 0
