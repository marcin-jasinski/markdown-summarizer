"""
Parser registry and shared types for all document format parsers.

:class:`ParsedDocument` is the canonical output type for all parsers and lives
in ``mindforge.domain.models``.  Import it directly from there — not from this
module.
"""

from __future__ import annotations

from mindforge.domain.models import ParsedDocument as ParsedDocument  # noqa: F401
from mindforge.domain.ports import DocumentParser


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UnsupportedFormatError(ValueError):
    """Raised when no registered parser handles the requested MIME type."""

    def __init__(self, mime_type: str) -> None:
        super().__init__(
            f"No parser registered for MIME type {mime_type!r}. "
            "Register a DocumentParser via ParserRegistry.register()."
        )
        self.mime_type = mime_type


# ---------------------------------------------------------------------------
# ParseError
# ---------------------------------------------------------------------------


class ParseError(RuntimeError):
    """Raised when a parser cannot extract content from the supplied bytes."""


# ---------------------------------------------------------------------------
# ParserRegistry
# ---------------------------------------------------------------------------


class ParserRegistry:
    """
    Registry mapping MIME types to :class:`~mindforge.domain.ports.DocumentParser`
    implementations.

    Adding a new format: call ``registry.register(mime_type, MyParser())``
    at the composition root — no modification to this class required.
    """

    def __init__(self) -> None:
        self._parsers: dict[str, DocumentParser] = {}

    def register(self, mime_type: str, parser: DocumentParser) -> None:
        """Register *parser* as the handler for *mime_type*."""
        self._parsers[mime_type] = parser

    def get(self, mime_type: str) -> DocumentParser:
        """
        Return the parser for *mime_type*.

        Raises :class:`UnsupportedFormatError` if none is registered.
        """
        parser = self._parsers.get(mime_type)
        if parser is None:
            raise UnsupportedFormatError(mime_type)
        return parser

    def supported_mime_types(self) -> list[str]:
        """Return the list of registered MIME types."""
        return list(self._parsers)
