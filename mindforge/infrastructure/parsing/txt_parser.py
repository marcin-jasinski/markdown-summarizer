"""
Plain text document parser.

Minimal parser for ``.txt`` files — extracts raw text, no metadata,
no images.
"""

from __future__ import annotations

from mindforge.domain.models import BlockType, ContentBlock, ParsedDocument
from mindforge.infrastructure.parsing.registry import ParseError


class TxtParser:
    """
    Parse plain text documents.

    Produces a single TEXT content block. No metadata or images are
    extracted; lesson identity falls back to filename-based resolution.
    """

    def parse(self, raw_bytes: bytes, filename: str) -> ParsedDocument:
        try:
            text = raw_bytes.decode("utf-8", errors="replace")
        except Exception as exc:
            raise ParseError(f"Failed to decode text file: {exc}") from exc

        content_blocks: list[ContentBlock] = []
        if text.strip():
            content_blocks.append(
                ContentBlock(
                    block_type=BlockType.TEXT,
                    content=text,
                    position=0,
                )
            )

        return ParsedDocument(
            text_content=text,
            metadata={},
            content_blocks=content_blocks,
            embedded_images=[],
        )
