from __future__ import annotations

from pathlib import Path

import pytest

from failurelab.config.settings import load_config
from failurelab.utilities.serialization import ensure_json_serializable, stable_dumps


def test_config_load_and_validation(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "schema_version: '0.1'\nevaluation:\n  retrieval_k: 2\n", encoding="utf-8"
    )
    config = load_config(config_file)
    assert config.evaluation.retrieval_k == 2

    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("evaluation:\n  retrieval_k: 0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(bad_config)


def test_serialization_helpers() -> None:
    payload = {"b": 1, "a": [1, {"k": "v"}]}
    assert ensure_json_serializable(payload)
    rendered = stable_dumps(payload)
    assert rendered.startswith('{"a"')

    with pytest.raises(ValueError):
        ensure_json_serializable(float("inf"))
