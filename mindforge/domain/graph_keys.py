"""
Domain-layer graph key normalization.

``dedupe_key`` is the single source of truth for transforming a concept label
into a stable, idempotent graph merge key used by both the ConceptMapper agent
and the Neo4j indexer.  Keeping the function here guarantees that both write
paths produce identical ``normalized_key`` values.

Pure Python — zero I/O, zero framework imports.
"""

from __future__ import annotations

import re
import unicodedata


def dedupe_key(text: str) -> str:
    """Normalise a concept label to a stable graph merge key.

    Transformation pipeline:

    1. Unicode NFKD normalisation (e.g. ``é`` → ``e`` + combining accent).
    2. ASCII encoding — non-ASCII chars stripped.
    3. Lowercase.
    4. Remove characters that are not ``[a-z0-9_\\s-]``.
    5. Collapse spaces and hyphens to single underscores.
    6. Strip leading/trailing underscores.
    7. Fall back to ``"unknown"`` if the result is empty.

    Examples::

        dedupe_key("Machine Learning")   == "machine_learning"
        dedupe_key("Neural-Network")     == "neural_network"
        dedupe_key("C++ programming")    == "c_programming"
        dedupe_key("Réseau de neurones") == "reseau_de_neurones"
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9_\s-]", "", text)
    text = re.sub(r"[\s\-]+", "_", text)
    text = text.strip("_")
    return text or "unknown"
