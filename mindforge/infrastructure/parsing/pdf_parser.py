"""
PDF document parser.

Extracts text, metadata (Title, Author, Subject), and embedded images
from PDF files using PyMuPDF (``fitz``).
"""

from __future__ import annotations

from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError as exc:
    raise ImportError(
        "PyMuPDF is required for PdfParser. " "Install it via: pip install pymupdf"
    ) from exc

from mindforge.domain.models import BlockType, ContentBlock, ParsedDocument
from mindforge.infrastructure.parsing.registry import ParseError

# Default limits — overridden at construction time
DEFAULT_MAX_PAGES = 500
DEFAULT_MAX_IMAGE_BYTES = 10 * 1024 * 1024   # 10 MB per image
DEFAULT_MAX_TOTAL_IMAGE_BYTES = 50 * 1024 * 1024  # 50 MB across all images


class PdfParser:
    """
    Parse PDF documents using PyMuPDF.

    Extracts:
    - Full text (page-concatenated)
    - PDF metadata: ``pdf_title``, ``pdf_author``, ``pdf_subject``
    - Embedded images as raw bytes (for vision-model analysis)
    """

    def __init__(
        self,
        max_pages: int = DEFAULT_MAX_PAGES,
        max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
        max_total_image_bytes: int = DEFAULT_MAX_TOTAL_IMAGE_BYTES,
    ) -> None:
        self._max_pages = max_pages
        self._max_image_bytes = max_image_bytes
        self._max_total_image_bytes = max_total_image_bytes

    def parse(self, raw_bytes: bytes, filename: str) -> ParsedDocument:
        try:
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
        except Exception as exc:
            raise ParseError(f"Failed to open PDF: {exc}") from exc

        try:
            return self._extract(doc, filename)
        finally:
            doc.close()

    def _extract(self, doc: fitz.Document, filename: str) -> ParsedDocument:
        page_count = doc.page_count

        if page_count > self._max_pages:
            raise ParseError(
                f"PDF has {page_count} pages which exceeds the maximum "
                f"of {self._max_pages}."
            )

        # -- Metadata -------------------------------------------------------
        raw_meta: dict[str, str] = doc.metadata or {}
        metadata: dict[str, Any] = {}
        if raw_meta.get("title"):
            metadata["pdf_title"] = raw_meta["title"]
        if raw_meta.get("author"):
            metadata["pdf_author"] = raw_meta["author"]
        if raw_meta.get("subject"):
            metadata["pdf_subject"] = raw_meta["subject"]

        # -- Text and image extraction per page ----------------------1-------
        pages_text: list[str] = []
        content_blocks: list[ContentBlock] = []
        embedded_images: list[bytes] = []
        total_image_bytes = 0
        position = 0

        for page_num in range(page_count):
            page: fitz.Page = doc.load_page(page_num)

            page_text = page.get_text("text")  # type: ignore[attr-defined]
            if page_text.strip():
                pages_text.append(page_text)
                content_blocks.append(
                    ContentBlock(
                        block_type=BlockType.TEXT,
                        content=page_text,
                        position=position,
                        metadata={"page": page_num + 1},
                    )
                )
                position += 1

            # Extract embedded images
            image_list = page.get_images(full=True)
            for img_info in image_list:
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes: bytes = base_image.get("image", b"")
                    mime_type: str = base_image.get("ext", "png")
                    if not image_bytes:
                        continue
                    if len(image_bytes) > self._max_image_bytes:
                        # Skip individual oversized images (non-fatal)
                        continue
                    if total_image_bytes + len(image_bytes) > self._max_total_image_bytes:
                        # Cumulative cap reached; stop collecting images
                        break
                    total_image_bytes += len(image_bytes)
                    embedded_images.append(image_bytes)
                    content_blocks.append(
                        ContentBlock(
                            block_type=BlockType.IMAGE,
                            content="",
                            media_ref=f"page_{page_num + 1}_img_{xref}",
                            media_type=f"image/{mime_type}",
                            position=position,
                            metadata={"page": page_num + 1, "xref": xref},
                        )
                    )
                    position += 1
                except Exception:
                    # Non-fatal: skip individual images that fail to extract
                    pass

        full_text = "\n".join(pages_text)

        return ParsedDocument(
            text_content=full_text,
            metadata=metadata,
            content_blocks=content_blocks,
            embedded_images=embedded_images,
        )
