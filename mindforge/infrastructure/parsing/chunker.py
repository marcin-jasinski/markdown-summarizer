"""
Heading-aware chunker for document text.

Implements the chunking strategy from Architecture §10.5:

1. Split on ``##`` / ``###`` headings → each heading starts a new chunk.
2. If chunk > MAX_CHUNK_TOKENS → split further on paragraph boundaries (``\\n\\n``).
3. If sub-chunk still > MAX_CHUNK_TOKENS → split on sentence boundaries.
4. If chunk < MIN_CHUNK_TOKENS → merge with the next chunk.
5. Apply OVERLAP_TOKENS of overlap between adjacent chunks.

Chunk identity is deterministic:
    ``sha256(lesson_id|position|text)[:16]``

Each chunk carries a ``heading_context`` — the breadcrumb of heading levels
above it in the document.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Chunk output type
# ---------------------------------------------------------------------------


@dataclass
class TextChunk:
    """A single, positioned text chunk ready for Neo4j / embedding indexing."""

    chunk_id: str
    """Deterministic 16-char hex ID: ``sha256(lesson_id|position|text)[:16]``."""

    text: str
    """The chunk text (may have overlap with adjacent chunks)."""

    position: int
    """Zero-based ordinal position within the document."""

    lesson_id: str
    """The lesson this chunk belongs to."""

    heading_context: str
    """Breadcrumb of heading levels above this chunk (e.g. ``"Introduction > Basics"``)."""

    token_count: int
    """Approximate token count (character ÷ 4)."""


# ---------------------------------------------------------------------------
# Tokenization helper (character-based approximation)
# ---------------------------------------------------------------------------


def _approx_tokens(text: str) -> int:
    """Approximate token count: characters / 4 (conservative estimate)."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
# Sentence boundary: period/!/? followed by whitespace or end-of-string
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------


class Chunker:
    """
    Heading-aware text chunker with configurable token limits.

    Parameters
    ----------
    max_tokens:
        Hard upper bound per chunk.  Chunks above this are split further.
    min_tokens:
        Soft lower bound.  Chunks below this are merged with the next one.
    overlap_tokens:
        Token overlap between adjacent final chunks.
    """

    def __init__(
        self,
        max_tokens: int = 512,
        min_tokens: int = 64,
        overlap_tokens: int = 64,
    ) -> None:
        self._max = max_tokens
        self._min = min_tokens
        self._overlap = overlap_tokens

    def chunk(self, text: str, lesson_id: str) -> list[TextChunk]:
        """
        Split *text* into heading-aware chunks with overlap.

        :param text:      The document's plain text (frontmatter stripped).
        :param lesson_id: Used in deterministic chunk ID computation.
        :returns:         Ordered list of :class:`TextChunk`.
        """
        if not text.strip():
            return []

        raw_chunks = self._split_by_headings(text)
        final_texts = self._apply_size_constraints(raw_chunks)
        final_texts = self._apply_overlap(final_texts)
        return self._build_chunks(final_texts, lesson_id)

    # ------------------------------------------------------------------
    # Step 1: Split on heading boundaries
    # ------------------------------------------------------------------

    def _split_by_headings(self, text: str) -> list[dict]:
        """
        Return a list of raw segment dicts with keys:
        ``{"text": str, "heading_context": str}``.
        """
        segments: list[dict] = []
        heading_stack: list[tuple[int, str]] = []  # (level, heading_text)

        lines = text.splitlines(keepends=True)
        current_lines: list[str] = []

        def flush(ctx: str) -> None:
            block = "".join(current_lines)
            if block.strip():
                segments.append({"text": block, "heading_context": ctx})
            current_lines.clear()

        current_context = ""

        for line in lines:
            m = re.match(r"^(#{1,6})\s+(.+)$", line.rstrip())
            if m:
                flush(current_context)
                level = len(m.group(1))
                heading_text = m.group(2).strip()
                # Pop stack items at same/lower level
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, heading_text))
                current_context = " > ".join(h for _, h in heading_stack)
                current_lines.append(line)  # include heading line in block
            else:
                current_lines.append(line)

        flush(current_context)
        return segments

    # ------------------------------------------------------------------
    # Step 2: Apply size constraints (split large, merge small)
    # ------------------------------------------------------------------

    def _apply_size_constraints(self, segments: list[dict]) -> list[dict]:
        """
        Expand oversized segments and merge undersized ones.

        Returns refined segment list with same dict structure.
        """
        expanded: list[dict] = []
        for seg in segments:
            ctx = seg["heading_context"]
            if _approx_tokens(seg["text"]) > self._max:
                sub_segs = self._split_large(seg["text"], ctx)
                expanded.extend(sub_segs)
            else:
                expanded.append(seg)

        # Merge undersized chunks with adjacents
        merged: list[dict] = []
        for seg in expanded:
            if merged and _approx_tokens(merged[-1]["text"]) < self._min:
                merged[-1]["text"] = merged[-1]["text"].rstrip() + "\n\n" + seg["text"]
            else:
                merged.append(
                    {"text": seg["text"], "heading_context": seg["heading_context"]}
                )

        return merged

    def _split_large(self, text: str, heading_context: str) -> list[dict]:
        """Split text exceeding max_tokens on paragraph, then sentence boundaries."""
        # Try paragraph splits first
        paragraphs = re.split(r"\n\n+", text)
        result: list[dict] = []
        buf: list[str] = []
        buf_tokens = 0

        for para in paragraphs:
            tok = _approx_tokens(para)
            if buf and buf_tokens + tok > self._max:
                result.append(
                    {"text": "\n\n".join(buf), "heading_context": heading_context}
                )
                buf = []
                buf_tokens = 0
            if tok > self._max:
                # Fall back to sentence splitting
                for sent_chunk in self._split_on_sentences(para, heading_context):
                    result.append(sent_chunk)
            else:
                buf.append(para)
                buf_tokens += tok

        if buf:
            result.append(
                {"text": "\n\n".join(buf), "heading_context": heading_context}
            )

        return (
            result if result else [{"text": text, "heading_context": heading_context}]
        )

    def _split_on_sentences(self, text: str, heading_context: str) -> list[dict]:
        """Last-resort split on sentence boundaries."""
        sentences = _SENTENCE_END_RE.split(text)
        result: list[dict] = []
        buf: list[str] = []
        buf_tokens = 0

        for sentence in sentences:
            tok = _approx_tokens(sentence)
            if buf and buf_tokens + tok > self._max:
                result.append(
                    {"text": " ".join(buf), "heading_context": heading_context}
                )
                buf = []
                buf_tokens = 0
            buf.append(sentence)
            buf_tokens += tok

        if buf:
            result.append({"text": " ".join(buf), "heading_context": heading_context})

        return (
            result if result else [{"text": text, "heading_context": heading_context}]
        )

    # ------------------------------------------------------------------
    # Step 3: Apply overlap
    # ------------------------------------------------------------------

    def _apply_overlap(self, segments: list[dict]) -> list[dict]:
        """Prepend trailing tokens of the previous segment to each segment."""
        if self._overlap <= 0 or len(segments) <= 1:
            return segments

        result: list[dict] = [segments[0]]
        for i in range(1, len(segments)):
            prev_text = segments[i - 1]["text"]
            overlap_text = self._tail_tokens(prev_text, self._overlap)
            new_text = (
                overlap_text + "\n" + segments[i]["text"]
                if overlap_text
                else segments[i]["text"]
            )
            result.append(
                {
                    "text": new_text,
                    "heading_context": segments[i]["heading_context"],
                }
            )

        return result

    def _tail_tokens(self, text: str, n_tokens: int) -> str:
        """Return the last ~n_tokens characters (approx) from *text*."""
        char_count = n_tokens * 4  # reverse of _approx_tokens
        return text[-char_count:].lstrip() if len(text) > char_count else text

    # ------------------------------------------------------------------
    # Step 4: Build TextChunk objects
    # ------------------------------------------------------------------

    def _build_chunks(self, segments: list[dict], lesson_id: str) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for position, seg in enumerate(segments):
            text = seg["text"]
            chunk_id = _compute_chunk_id(lesson_id, position, text)
            chunks.append(
                TextChunk(
                    chunk_id=chunk_id,
                    text=text,
                    position=position,
                    lesson_id=lesson_id,
                    heading_context=seg["heading_context"],
                    token_count=_approx_tokens(text),
                )
            )
        return chunks


# ---------------------------------------------------------------------------
# Deterministic chunk ID
# ---------------------------------------------------------------------------


def _compute_chunk_id(lesson_id: str, position: int, text: str) -> str:
    """Return ``sha256(lesson_id|position|text)[:16]``."""
    raw = f"{lesson_id}|{position}|{text}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
