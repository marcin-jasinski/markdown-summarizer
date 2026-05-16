"""
Markdown document parser.

Extracts frontmatter (via ``python-frontmatter``), plain text, first heading,
and embedded image references from Markdown source.
"""

from __future__ import annotations

import re
from typing import Any

try:
    import frontmatter as fm
except ImportError as exc:
    raise ImportError(
        "python-frontmatter is required for MarkdownParser. "
        "Install it via: pip install python-frontmatter"
    ) from exc

from mindforge.domain.models import BlockType, ContentBlock, ParsedDocument
from mindforge.infrastructure.parsing.registry import ParseError


class MarkdownParser:
    """
    Parse Markdown documents.

    Extracts:
    - YAML frontmatter (``lesson_id``, ``title``, any other fields)
    - Full text content (frontmatter stripped)
    - First ``# Heading`` as ``first_heading`` in metadata
    - Embedded image references (``![alt](url)``, ``![alt](./path)``)
    """

    # Matches ![alt text](image_url_or_path)
    _IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    # Matches the first ATX heading (# … through ###### …)
    _HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)

    def parse(self, raw_bytes: bytes, filename: str) -> ParsedDocument:
        try:
            text = raw_bytes.decode("utf-8", errors="replace")
        except Exception as exc:
            raise ParseError(f"Failed to decode Markdown bytes: {exc}") from exc

        try:
            post = fm.loads(text)
        except Exception as exc:
            raise ParseError(f"Failed to parse Markdown frontmatter: {exc}") from exc

        metadata: dict[str, Any] = dict(post.metadata) if post.metadata else {}
        content_text: str = post.content or ""

        # Capture first heading for title resolution
        heading_match = self._HEADING_RE.search(content_text)
        if heading_match:
            metadata.setdefault("first_heading", heading_match.group(1).strip())

        # Build content blocks
        content_blocks: list[ContentBlock] = []
        image_refs: list[str] = []
        position = 0

        # Split on image tags to produce alternating text/image blocks
        parts = self._IMAGE_RE.split(content_text)
        # _IMAGE_RE.split returns: [text, alt, url, text, alt, url, ...]
        i = 0
        while i < len(parts):
            chunk = parts[i]
            if chunk.strip():
                content_blocks.append(
                    ContentBlock(
                        block_type=BlockType.TEXT,
                        content=chunk,
                        position=position,
                    )
                )
                position += 1
            i += 1
            if i < len(parts):
                alt_text = parts[i]
                i += 1
                img_url = parts[i] if i < len(parts) else ""
                i += 1
                content_blocks.append(
                    ContentBlock(
                        block_type=BlockType.IMAGE,
                        content=alt_text,
                        media_ref=img_url,
                        media_type="image/*",
                        position=position,
                        metadata={"alt": alt_text, "src": img_url},
                    )
                )
                image_refs.append(img_url)
                position += 1

        # If no content blocks were created from split, add the full text
        if not content_blocks and content_text.strip():
            content_blocks.append(
                ContentBlock(
                    block_type=BlockType.TEXT,
                    content=content_text,
                    position=0,
                )
            )

        if image_refs:
            metadata["image_refs"] = image_refs

        return ParsedDocument(
            text_content=content_text,
            metadata=metadata,
            content_blocks=content_blocks,
            embedded_images=[],  # Markdown references images by URL, not embedding bytes
        )
