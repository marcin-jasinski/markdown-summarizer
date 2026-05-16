"""
ArticleFetcher agent — extracts Markdown links, classifies them with an LLM,
and fetches article/api_docs URLs via EgressPolicy.

All outbound HTTP requests go through EgressPolicy — direct use of httpx or
similar is prohibited per architecture security requirements.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from mindforge.domain.agents import AgentCapability, AgentContext, AgentResult
from mindforge.domain.models import (
    CostTier,
    DeadlineProfile,
    FetchedArticle,
    ModelTier,
)
from mindforge.domain.ports import EgressViolation

if TYPE_CHECKING:
    from mindforge.infrastructure.security.egress_policy import EgressPolicy

__version__ = "1.0.0"

log = logging.getLogger(__name__)

_CAPABILITY = AgentCapability(
    name="article_fetcher",
    description="Extracts and fetches linked articles from document content.",
    input_types=("cleaned_content",),
    output_types=("fetched_articles",),
    required_model_tier=ModelTier.SMALL,
    estimated_cost_tier=CostTier.LOW,
)

# Matches Markdown links: [text](url) — excludes image links (![...)
_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\((https?://[^)]+)\)")

# Categories the LLM can return; only these are fetched
_FETCH_CATEGORIES = frozenset({"article", "api_docs"})


def _extract_links(content: str) -> list[tuple[str, str]]:
    """Return list of (anchor_text, url) from Markdown content.

    Code blocks are stripped first to avoid picking up example URLs.
    """
    # Strip fenced code blocks
    stripped = re.sub(r"```[\s\S]*?```", "", content)
    # Strip inline code
    stripped = re.sub(r"`[^`]+`", "", stripped)
    return _LINK_RE.findall(stripped)


def _url_cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


class ArticleFetcherAgent:
    """Produces ``fetched_articles`` in the pipeline artifact."""

    __version__ = __version__

    def __init__(self, egress_policy: EgressPolicy, *, prompts=None) -> None:
        if prompts is None:
            from mindforge.infrastructure.ai.agents import (
                article_fetcher as prompts,
            )  # noqa: PLC0415
        self._egress = egress_policy
        self._prompts = prompts

    @property
    def name(self) -> str:
        return "article_fetcher"

    @property
    def capabilities(self) -> tuple[AgentCapability, ...]:
        return (_CAPABILITY,)

    async def execute(self, context: AgentContext) -> AgentResult:
        start = time.monotonic()

        if not context.settings.enable_article_fetch:
            context.artifact.fetched_articles = []
            return AgentResult(
                success=True,
                output_key="fetched_articles",
            )

        content: str = context.metadata.get(
            "cleaned_content",
            context.metadata.get("original_content", ""),
        )
        if not content:
            context.artifact.fetched_articles = []
            return AgentResult(
                success=True,
                output_key="fetched_articles",
            )

        links = _extract_links(content)
        if not links:
            context.artifact.fetched_articles = []
            return AgentResult(
                success=True,
                output_key="fetched_articles",
            )

        # Deduplicate URLs, preserve order
        seen: set[str] = set()
        unique_urls: list[str] = []
        for _, url in links:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        # Classify URLs
        model = context.settings.model_for_tier(ModelTier.SMALL)
        url_list_json = json.dumps(unique_urls)
        classify_messages = [
            {
                "role": "system",
                "content": self._prompts.system_prompt(context.settings.prompt_locale),
            },
            {"role": "user", "content": url_list_json},
        ]

        total_tokens = 0
        total_cost = 0.0

        try:
            classify_result = await context.gateway.complete(
                model=model,
                messages=classify_messages,
                deadline=DeadlineProfile.BATCH,
                temperature=0.0,
            )
            total_tokens += classify_result.input_tokens + classify_result.output_tokens
            total_cost += classify_result.cost_usd
            classifications = json.loads(classify_result.content)
        except Exception as exc:
            log.warning("ArticleFetcher URL classification failed: %s", exc)
            context.artifact.fetched_articles = []
            return AgentResult(
                success=True,
                output_key="fetched_articles",
                error=f"URL classification failed: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        # Fetch URLs categorised as article or api_docs
        articles: list[FetchedArticle] = []
        for entry in classifications:
            url = entry.get("url", "")
            category = entry.get("category", "irrelevant")
            if category not in _FETCH_CATEGORIES:
                continue

            try:
                raw_bytes = await self._egress.fetch(url)
                body = raw_bytes.decode("utf-8", errors="replace")
                # Extract a simple title from the first <title> tag or first line
                title = _extract_title(body, url)
                articles.append(
                    FetchedArticle(
                        url=url,
                        title=title,
                        content=body[:10_000],  # cap at 10k chars
                        fetched_at=datetime.now(timezone.utc),
                    )
                )
            except EgressViolation as exc:
                log.warning("ArticleFetcher egress violation for %r: %s", url, exc)
            except Exception as exc:
                log.warning("ArticleFetcher fetch failed for %r: %s", url, exc)

        context.artifact.fetched_articles = articles

        duration_ms = (time.monotonic() - start) * 1000
        return AgentResult(
            success=True,
            output_key="fetched_articles",
            tokens_used=total_tokens,
            cost_usd=total_cost,
            duration_ms=duration_ms,
        )


def _extract_title(html_or_text: str, fallback_url: str) -> str:
    """Extract a page title from HTML or return the URL as fallback."""
    match = re.search(r"<title[^>]*>([^<]+)</title>", html_or_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Try first non-empty line
    for line in html_or_text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return fallback_url
