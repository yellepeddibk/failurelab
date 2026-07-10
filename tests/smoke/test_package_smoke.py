from __future__ import annotations

from failurelab import __version__


def test_version_present() -> None:
    assert __version__ == "0.1.0"
