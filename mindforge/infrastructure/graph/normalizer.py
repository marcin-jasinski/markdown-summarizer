"""Graph normalization utilities for the Neo4j indexer.

``dedupe_key`` is the authoritative implementation, now living in
``mindforge.domain.graph_keys``.  Re-exported here for backward compatibility
with any infrastructure code that imports from this module directly.
"""

from __future__ import annotations

from mindforge.domain.graph_keys import dedupe_key  # noqa: F401 (re-export)
