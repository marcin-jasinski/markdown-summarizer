"""
Upload sanitizer — filename validation and file size / format enforcement.

All filenames and binary payloads arriving from untrusted surfaces (API,
Discord, Slack) MUST pass through this module before any further processing.
"""

from __future__ import annotations

import os
import re

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UploadViolation(ValueError):
    """Raised when an uploaded file or filename fails a security check."""


# ---------------------------------------------------------------------------
# Allowed MIME types per format (extension → MIME)
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES: dict[str, str] = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Maximum byte-size per format (defaults — overridable via settings)
DEFAULT_MAX_BYTES_PER_FORMAT: dict[str, int] = {
    "text/markdown": 10 * 1024 * 1024,
    "text/plain": 10 * 1024 * 1024,
    "application/pdf": 50 * 1024 * 1024,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": 20
    * 1024
    * 1024,
}

# Sequences that indicate path traversal attempts
_TRAVERSAL_PATTERNS = re.compile(r"\.\.")
# Characters disallowed in safe filenames
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class UploadSanitizer:
    """
    Validates uploaded files before ingestion.

    Responsibilities:
    - Strip path components from filenames (retain basename only).
    - Reject absolute paths, drive-qualified paths, and traversal sequences.
    - Validate extension against the allowed set.
    - Enforce per-format byte-size limits.
    """

    def __init__(
        self,
        max_bytes_per_format: dict[str, int] | None = None,
        global_max_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        self._max_bytes = max_bytes_per_format or DEFAULT_MAX_BYTES_PER_FORMAT
        self._global_max = global_max_bytes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sanitize_filename(self, filename: str) -> str:
        """
        Return a safe basename for *filename*.

        Raises :class:`UploadViolation` if the filename contains path
        traversal sequences, is absolute, or has no valid extension.
        """
        if not filename or not filename.strip():
            raise UploadViolation("Filename must not be empty.")

        # Reject path traversal sequences before any normalization
        if _TRAVERSAL_PATTERNS.search(filename):
            raise UploadViolation(
                f"Filename contains path traversal sequence: {filename!r}"
            )

        # Strip path components — keep only the basename
        # Use both os.sep and forward-slash to handle cross-platform payloads
        basename = os.path.basename(filename.replace("\\", "/").replace("/", os.sep))
        basename = basename.strip()

        if not basename:
            raise UploadViolation(
                f"Filename resolves to an empty basename after stripping path components: {filename!r}"
            )

        # Reject absolute paths (Windows drive letters e.g. "C:")
        if os.path.isabs(filename) or re.match(r"^[A-Za-z]:", filename):
            raise UploadViolation(
                f"Filename must not be an absolute path: {filename!r}"
            )

        # Reject files with no extension or unknown extension
        self._validate_extension(basename)

        return basename

    def validate(self, raw_bytes: bytes, filename: str) -> str:
        """
        Full validation: sanitize filename + validate size.

        Returns the resolved MIME type for the file.
        Raises :class:`UploadViolation` on any policy breach.
        """
        safe_name = self.sanitize_filename(filename)
        mime_type = self._mime_for(safe_name)

        # Global cap
        if len(raw_bytes) > self._global_max:
            raise UploadViolation(
                f"File exceeds global maximum size of {self._global_max} bytes "
                f"({len(raw_bytes)} bytes received)."
            )

        # Per-format cap
        format_max = self._max_bytes.get(mime_type, self._global_max)
        if len(raw_bytes) > format_max:
            raise UploadViolation(
                f"File exceeds maximum size for format {mime_type!r} "
                f"({format_max} bytes). Received {len(raw_bytes)} bytes."
            )

        return mime_type

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_extension(self, basename: str) -> None:
        _, ext = os.path.splitext(basename)
        ext = ext.lower()
        if ext not in ALLOWED_MIME_TYPES:
            allowed = ", ".join(sorted(ALLOWED_MIME_TYPES))
            raise UploadViolation(
                f"File extension {ext!r} is not allowed. "
                f"Allowed extensions: {allowed}."
            )

    def _mime_for(self, basename: str) -> str:
        _, ext = os.path.splitext(basename)
        return ALLOWED_MIME_TYPES[ext.lower()]
