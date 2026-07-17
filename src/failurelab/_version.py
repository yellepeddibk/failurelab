"""Single source of the package version.

Kept separate from ``failurelab.__init__`` so modules can read the version
without importing the package root, which avoids a partial-initialization
import cycle once the root re-exports the public API.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("failurelab")
except PackageNotFoundError:
    __version__ = "0.2.0"
