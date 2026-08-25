"""Make the bundled examples importable from the test suite.

``examples/`` is not part of the installed distribution, so the RAG example is
imported by path rather than as a package dependency.
"""

from __future__ import annotations

import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))
