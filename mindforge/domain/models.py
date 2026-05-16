"""
Domain layer — core entities, value objects, and domain structures.

Pure Python only.  Zero I/O, zero framework imports.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DocumentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class UploadSource(str, Enum):
    API = "API"
    DISCORD = "DISCORD"
    SLACK = "SLACK"
    FILE_WATCHER = "FILE_WATCHER"


class BlockType(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    CODE = "CODE"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"


class CardType(str, Enum):
    BASIC = "BASIC"
    CLOZE = "CLOZE"
    REVERSE = "REVERSE"


class ModelTier(str, Enum):
    SMALL = "SMALL"
    LARGE = "LARGE"
    VISION = "VISION"


class CostTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DeadlineProfile(str, Enum):
    INTERACTIVE = "INTERACTIVE"
    BATCH = "BATCH"
    BACKGROUND = "BACKGROUND"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LessonIdentityError(ValueError):
    """Raised when a valid lesson_id cannot be derived from document metadata."""


class DeadlineExceeded(Exception):
    """Raised when an AI gateway call exceeds its deadline profile budget.

    Callers decide how to handle:
    - INTERACTIVE: return a degraded response
    - BATCH / BACKGROUND: retry
    """

    def __init__(
        self, deadline_profile: str, elapsed_ms: float, budget_ms: float
    ) -> None:
        self.deadline_profile = deadline_profile
        self.elapsed_ms = elapsed_ms
        self.budget_ms = budget_ms
        super().__init__(
            f"Deadline exceeded for profile {deadline_profile!r}: "
            f"{elapsed_ms:.0f}ms > {budget_ms:.0f}ms budget"
        )


# ---------------------------------------------------------------------------
# Helper function
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Convert arbitrary text to a valid lesson_id slug."""
    # Normalize unicode (e.g., ę → e) and encode to ASCII
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    # Replace any invalid characters with hyphens
    text = re.sub(r"[^a-z0-9\-_]+", "-", text)
    # Collapse multiple hyphens
    text = re.sub(r"-{2,}", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    return text


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContentHash:
    sha256: str

    @staticmethod
    def compute(raw_bytes: bytes) -> ContentHash:
        digest = hashlib.sha256(raw_bytes).hexdigest()
        return ContentHash(sha256=digest)


@dataclass(frozen=True)
class LessonIdentity:
    lesson_id: str
    title: str

    # Class-level constants (not dataclass fields — no type annotation)
    _RESERVED = frozenset({"__init__", "index", "default"})
    _VALID_PATTERN = re.compile(r"^[a-z0-9\-_]+$")
    _MAX_LEN = 80

    @classmethod
    def resolve(cls, metadata: dict[str, Any], filename: str) -> LessonIdentity:
        """Deterministically resolve a LessonIdentity from parser-supplied metadata.

        Steps (first match wins):
            1. Frontmatter ``lesson_id:``  — used verbatim after validation
            2. Frontmatter ``title:``      — slugified
            3. PDF metadata ``pdf_title:`` — slugified
            4. Filename stem              — sanitized
            5. Raise ``LessonIdentityError``
        """
        lesson_id: str | None = None

        # Step 1: frontmatter lesson_id (verbatim)
        if metadata.get("lesson_id"):
            lesson_id = cls._validate(str(metadata["lesson_id"]).strip())

        # Step 2: frontmatter title (slugified)
        if lesson_id is None and metadata.get("title"):
            lesson_id = cls._validate(slugify(str(metadata["title"])))

        # Step 3: PDF metadata title (slugified)
        if lesson_id is None and metadata.get("pdf_title"):
            lesson_id = cls._validate(slugify(str(metadata["pdf_title"])))

        # Step 4: filename stem (sanitized)
        if lesson_id is None:
            stem = filename.rsplit(".", 1)[0] if "." in filename else filename
            lesson_id = cls._validate(slugify(stem))

        # Step 5: reject
        if lesson_id is None:
            raise LessonIdentityError(
                f"Cannot derive a valid lesson_id. "
                f"metadata={metadata!r}, filename={filename!r}"
            )

        # Resolve display title (independent of lesson_id)
        raw_title = (
            metadata.get("title")
            or metadata.get("first_heading")
            or metadata.get("pdf_title")
            or (filename.rsplit(".", 1)[0] if "." in filename else filename)
        )
        return cls(lesson_id=lesson_id, title=str(raw_title))

    @classmethod
    def _validate(cls, candidate: str) -> str | None:
        """Return ``candidate`` if it passes all validation rules, else ``None``."""
        if not candidate:
            return None
        if len(candidate) > cls._MAX_LEN:
            return None
        if not cls._VALID_PATTERN.match(candidate):
            return None
        if candidate in cls._RESERVED:
            return None
        return candidate


# ---------------------------------------------------------------------------
# Content Block
# ---------------------------------------------------------------------------


@dataclass
class ContentBlock:
    block_type: BlockType
    content: str
    position: int
    media_ref: str | None = None
    media_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parsed Document (output of document format parsers)
# ---------------------------------------------------------------------------


@dataclass
class ParsedDocument:
    """Structured output returned by a document format parser.

    ``embedded_images`` carries raw image bytes extracted from the document
    for later vision-model analysis by the ImageAnalyzer agent.
    """

    text_content: str
    metadata: dict[str, Any]
    content_blocks: list[ContentBlock] = field(default_factory=list)
    embedded_images: list[bytes] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core Entities
# ---------------------------------------------------------------------------


@dataclass
class Document:
    document_id: UUID
    knowledge_base_id: UUID
    lesson_identity: LessonIdentity
    content_hash: ContentHash
    source_filename: str
    mime_type: str
    original_content: str
    upload_source: UploadSource
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    content_blocks: list[ContentBlock] = field(default_factory=list)
    uploaded_by: UUID | None = None
    tags: list[str] = field(default_factory=list)
    is_active: bool = True
    revision: int = 1

    @property
    def lesson_id(self) -> str:
        return self.lesson_identity.lesson_id

    @property
    def title(self) -> str:
        return self.lesson_identity.title


@dataclass
class KnowledgeBase:
    kb_id: UUID
    owner_id: UUID
    name: str
    description: str
    created_at: datetime
    document_count: int = 0
    prompt_locale: str = "pl"


@dataclass
class User:
    user_id: UUID
    display_name: str
    created_at: datetime
    email: str | None = None
    password_hash: str | None = None
    avatar_url: str | None = None
    last_login_at: datetime | None = None
    is_admin: bool = False


# ---------------------------------------------------------------------------
# Pipeline checkpoint structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepFingerprint:
    input_hash: str
    prompt_version: str
    model_id: str
    agent_version: str

    def compute(self) -> str:
        """Return a 16-char hex digest uniquely identifying this processing step."""
        raw = f"{self.input_hash}|{self.prompt_version}|{self.model_id}|{self.agent_version}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class StepCheckpoint:
    output_key: str
    fingerprint: str
    completed_at: datetime


# ---------------------------------------------------------------------------
# Artifact sub-structures
# ---------------------------------------------------------------------------


@dataclass
class SummaryData:
    summary: str
    key_points: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)


@dataclass
class FlashcardData:
    kb_id: UUID
    lesson_id: str
    card_type: CardType
    front: str
    back: str
    tags: list[str] = field(default_factory=list)
    card_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        raw = f"{self.kb_id}|{self.lesson_id}|{self.card_type.value}|{self.front}|{self.back}"
        self.card_id = hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class ConceptEdge:
    source: str
    target: str
    relation: str


@dataclass
class ConceptNode:
    key: str
    label: str
    description: str
    related: list[str] = field(default_factory=list)


@dataclass
class ConceptMapData:
    concepts: list[ConceptNode] = field(default_factory=list)
    edges: list[ConceptEdge] = field(default_factory=list)


@dataclass
class ImageDescription:
    media_ref: str
    description: str
    alt_text: str = ""


@dataclass
class FetchedArticle:
    url: str
    title: str
    content: str
    fetched_at: datetime


@dataclass
class ValidationResult:
    is_relevant: bool
    confidence: float
    reason: str


# ---------------------------------------------------------------------------
# Document Artifact (canonical pipeline output)
# ---------------------------------------------------------------------------


@dataclass
class DocumentArtifact:
    document_id: UUID
    knowledge_base_id: UUID
    lesson_id: str
    version: int
    created_at: datetime
    summary: SummaryData | None = None
    flashcards: list[FlashcardData] = field(default_factory=list)
    concept_map: ConceptMapData | None = None
    image_descriptions: list[ImageDescription] = field(default_factory=list)
    fetched_articles: list[FetchedArticle] = field(default_factory=list)
    validation_result: ValidationResult | None = None
    step_fingerprints: dict[str, StepCheckpoint] = field(default_factory=dict)
    completed_step: str | None = None

    def is_step_cached(self, step_name: str, fingerprint: StepFingerprint) -> bool:
        """Return True if ``step_name`` has a stored checkpoint matching ``fingerprint``."""
        checkpoint = self.step_fingerprints.get(step_name)
        if checkpoint is None:
            return False
        return checkpoint.fingerprint == fingerprint.compute()


# ---------------------------------------------------------------------------
# AI completion result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompletionResult:
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str
    latency_ms: float
    cost_usd: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------


@dataclass
class TokenBudget:
    total_tokens: int
    system_tokens: int
    query_tokens: int

    @property
    def available_for_context(self) -> int:
        return max(0, self.total_tokens - self.system_tokens - self.query_tokens)


# ---------------------------------------------------------------------------
# Interaction audit trail
# ---------------------------------------------------------------------------


@dataclass
class InteractionTurn:
    turn_id: UUID
    interaction_id: UUID
    turn_number: int
    role: str
    content: str
    created_at: datetime
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    tokens_used: int = 0
    cost: float | None = None


@dataclass
class Interaction:
    interaction_id: UUID
    user_id: UUID
    interaction_type: str
    created_at: datetime
    knowledge_base_id: UUID | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    turns: list[InteractionTurn] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Chat session
# ---------------------------------------------------------------------------


@dataclass
class ChatTurn:
    role: str
    content: str
    created_at: datetime


@dataclass
class ChatSession:
    session_id: UUID
    user_id: UUID
    knowledge_base_id: UUID
    created_at: datetime
    turns: list[ChatTurn] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Quiz session
# ---------------------------------------------------------------------------


@dataclass
class QuizQuestion:
    question_id: str
    question_text: str
    question_type: str
    reference_answer: str
    grounding_context: str
    lesson_id: str


@dataclass
class QuizSession:
    session_id: UUID
    user_id: UUID
    kb_id: UUID
    questions: list[QuizQuestion]
    created_at: datetime
    expires_at: datetime
    current_index: int = 0
    score: float = 0.0


# ---------------------------------------------------------------------------
# Spaced-repetition card state
# ---------------------------------------------------------------------------


@dataclass
class CardState:
    card_id: str
    kb_id: UUID
    lesson_id: str
    card_type: CardType
    front: str
    back: str
    next_review: date
    interval: int
    ease_factor: float
    repetitions: int


@dataclass
class ReviewResult:
    rating: int  # SM-2 rating 0–5
    quality_flag: str | None = None


def sm2_update(
    rating: int,
    ease_factor: float,
    interval: int,
    repetitions: int,
) -> tuple[float, int, int]:
    """Standard SM-2 spaced-repetition algorithm update.  ``rating`` is 0–5.

    Returns ``(new_ease_factor, new_interval, new_repetitions)``.
    """
    if rating < 3:
        # Failed recall — reset schedule
        repetitions = 0
        interval = 1
    else:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * ease_factor)
        repetitions += 1

    ease_factor = max(
        1.3,
        ease_factor + 0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02),
    )
    return ease_factor, interval, repetitions


# ---------------------------------------------------------------------------
# Retrieval results
# ---------------------------------------------------------------------------


@dataclass
class RelatedConceptSummary:
    key: str
    label: str
    relation: str
    description: str = ""


@dataclass
class ConceptNeighborhood:
    center: ConceptNode
    neighbors: list[RelatedConceptSummary]
    depth: int
    facts: list[str] = field(default_factory=list)


@dataclass
class WeakConcept:
    key: str
    label: str
    due_count: int
    last_reviewed: date | None = None


@dataclass
class RetrievalResult:
    content: str
    source_lesson_id: str
    source_document_id: UUID
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
