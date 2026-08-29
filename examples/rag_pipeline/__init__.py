"""A runnable RAG pipeline that emits FailureLab-compatible traces.

This package is an example, not part of the ``failurelab`` distribution. It is
deliberately dependency-free: retrieval is implemented with the standard library
so that running the example adds nothing to the install footprint.

The stages are documents, chunking, retrieval, generation, evaluation, and trace
emission. Each stage is deterministic except answer generation, which depends on
the configured generator.
"""

from __future__ import annotations

__all__ = ["__doc__"]
