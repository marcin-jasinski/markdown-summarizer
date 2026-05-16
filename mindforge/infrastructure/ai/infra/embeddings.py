"""
Embedding helper for the LiteLLM-backed AI Gateway.

Handles provider batch-size limits by splitting large text lists and
reassembling the results in order.

Used internally by ``LiteLLMGateway.embed()``.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from litellm import aembedding

    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False

log = logging.getLogger(__name__)

# Most embedding providers cap at 2048 texts per request.
# We use a conservative default that works for all major providers.
_DEFAULT_BATCH_SIZE = 512


async def embed_batched(
    model: str,
    texts: list[str],
    *,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    timeout_s: float = 30.0,
) -> list[list[float]]:
    """Embed ``texts`` using LiteLLM, splitting into batches as needed.

    Args:
        model: LiteLLM model string (e.g. ``"openai/text-embedding-3-small"``).
        texts: Texts to embed.
        batch_size: Maximum number of texts per provider request.
        timeout_s: Per-batch request timeout in seconds.

    Returns:
        A list of embedding vectors in the same order as ``texts``.

    Raises:
        ImportError: If ``litellm`` is not installed.
    """
    if not _LITELLM_AVAILABLE:
        raise ImportError(
            "litellm is not installed. Install it with: pip install litellm"
        )

    if not texts:
        return []

    results: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        log.debug(
            "Embedding batch %d–%d of %d via %r", i, i + len(batch), len(texts), model
        )

        kwargs: dict[str, Any] = {
            "model": model,
            "input": batch,
            "timeout": timeout_s,
        }
        response = await aembedding(**kwargs)

        # LiteLLM returns response.data as a list of EmbeddingObject
        batch_vectors: list[list[float]] = [
            item.embedding for item in sorted(response.data, key=lambda x: x.index)
        ]
        results.extend(batch_vectors)

    return results
