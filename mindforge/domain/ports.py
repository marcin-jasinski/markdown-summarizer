"""
Domain layer — port (abstract interface) definitions.

Each Protocol here is the «port» side of a hexagonal adapter pair.
Concrete implementations live in ``mindforge/infrastructure/``.

Pure Python only.  Zero I/O, zero framework imports.
The ``connection`` parameters are typed as ``Any`` to avoid importing
SQLAlchemy at the domain level.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from mindforge.domain.events import DomainEvent


# ---------------------------------------------------------------------------
# Egress exceptions
# ---------------------------------------------------------------------------


class EgressViolation(ValueError):
    """Raised when an outbound request violates the configured egress policy.

    Defined in the domain so that agents can catch it without importing
    infrastructure modules.
    """


from mindforge.domain.models import (
    CardState,
    CompletionResult,
    ContentHash,
    ConceptNeighborhood,
    ConceptNode,
    ConceptEdge,
    DeadlineProfile,
    Document,
    DocumentArtifact,
    DocumentStatus,
    FlashcardData,
    Interaction,
    KnowledgeBase,
    ParsedDocument,
    QuizSession,
    RetrievalResult,
    ReviewResult,
    TokenBudget,
    User,
    WeakConcept,
)


# ---------------------------------------------------------------------------
# Document parsing ports (used by IngestionService)
# ---------------------------------------------------------------------------


@runtime_checkable
class DocumentParser(Protocol):
    """Synchronous, pure parser for a single document format."""

    def parse(self, raw_bytes: bytes, filename: str) -> ParsedDocument: ...


@runtime_checkable
class DocumentParserRegistry(Protocol):
    """Format-dispatch registry for document parsers."""

    def get(self, mime_type: str) -> DocumentParser:
        """Return the parser for ``mime_type``; raise if unavailable."""
        ...


@runtime_checkable
class DocumentSanitizer(Protocol):
    """Validates and sanitizes document uploads before any processing."""

    def sanitize_filename(self, filename: str) -> str:
        """Return the sanitized (basename-only) filename; raise on traversal."""
        ...

    def validate(self, raw_bytes: bytes, filename: str) -> str:
        """Validate size and format; return the resolved MIME type."""
        ...


# ---------------------------------------------------------------------------
# Document Repository
# ---------------------------------------------------------------------------


@runtime_checkable
class DocumentRepository(Protocol):
    async def save(self, document: Document) -> None:
        """Persist a new document within the caller's session/unit-of-work."""
        ...

    async def get_by_id(self, document_id: UUID) -> Document | None: ...

    async def get_by_content_hash(
        self, kb_id: UUID, content_hash: ContentHash
    ) -> Document | None:
        """Return the active document matching the given content hash, or None."""
        ...

    async def get_active_by_lesson(
        self, kb_id: UUID, lesson_id: str
    ) -> Document | None:
        """Return the currently active revision for a lesson in a KB, or None."""
        ...

    async def deactivate_lesson(self, kb_id: UUID, lesson_id: str) -> int:
        """Mark the active revision for a lesson as inactive.

        Returns the ``revision`` number of the document that was deactivated,
        or 0 if no active document was found.
        """
        ...

    async def update_status(
        self, document_id: UUID, status: DocumentStatus
    ) -> None: ...

    async def list_by_knowledge_base(
        self,
        kb_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]: ...


# ---------------------------------------------------------------------------
# Artifact Repository
# ---------------------------------------------------------------------------


@runtime_checkable
class ArtifactRepository(Protocol):
    async def save_checkpoint(self, artifact: DocumentArtifact) -> None:
        """UPSERT artifact JSON and step fingerprints within the caller's session."""
        ...

    async def load_latest(self, document_id: UUID) -> DocumentArtifact | None:
        """Load the highest-version artifact for a document."""
        ...

    async def count_flashcards(self, kb_id: UUID, lesson_id: str) -> int: ...

    async def list_flashcards_for_kb(
        self,
        kb_id: UUID,
        lesson_id: str | None = None,
    ) -> list[FlashcardData]:
        """Return all flashcards across all active documents in a knowledge base.

        When *lesson_id* is provided, restrict results to that lesson only.
        Used by ``FlashcardService`` to join card content with study-progress state.
        """
        ...


# ---------------------------------------------------------------------------
# Retrieval Port
# ---------------------------------------------------------------------------


@runtime_checkable
class RetrievalPort(Protocol):
    async def retrieve(
        self,
        query: str,
        kb_id: UUID,
        *,
        top_k: int = 5,
        budget: TokenBudget | None = None,
    ) -> list[RetrievalResult]:
        """Graph-first, lexical fallback, embedding last."""
        ...

    async def retrieve_concept_neighborhood(
        self,
        kb_id: UUID,
        concept_key: str,
        *,
        depth: int = 2,
    ) -> ConceptNeighborhood | None: ...

    async def find_weak_concepts(
        self,
        user_id: UUID,
        kb_id: UUID,
        today: date,
        *,
        limit: int = 10,
    ) -> list[WeakConcept]: ...

    async def get_concepts(self, kb_id: UUID) -> list[ConceptNode]: ...

    async def get_concept_edges(self, kb_id: UUID) -> list[ConceptEdge]: ...

    async def get_lesson_concepts(
        self, kb_id: UUID, lesson_id: str
    ) -> list[ConceptNode]: ...


# ---------------------------------------------------------------------------
# AI Gateway
# ---------------------------------------------------------------------------


@runtime_checkable
class AIGateway(Protocol):
    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        deadline: DeadlineProfile = DeadlineProfile.INTERACTIVE,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> CompletionResult: ...

    async def embed(
        self,
        *,
        model: str,
        texts: list[str],
    ) -> list[list[float]]: ...


# ---------------------------------------------------------------------------
# Study Progress Store
# ---------------------------------------------------------------------------


@runtime_checkable
class StudyProgressStore(Protocol):
    async def get_due_cards(
        self, user_id: UUID, kb_id: UUID, today: date
    ) -> list[CardState]: ...

    async def save_review(
        self,
        user_id: UUID,
        kb_id: UUID,
        card_id: str,
        result: ReviewResult,
    ) -> None: ...

    async def due_count(self, user_id: UUID, kb_id: UUID, today: date) -> int: ...


# ---------------------------------------------------------------------------
# Event Publisher (outbox pattern)
# ---------------------------------------------------------------------------


@runtime_checkable
class EventPublisher(Protocol):
    async def publish_in_tx(self, event: DomainEvent, connection: Any) -> None:
        """Write event to the outbox table within the caller's transaction."""
        ...


# ---------------------------------------------------------------------------
# Pipeline Task Store
# ---------------------------------------------------------------------------


@runtime_checkable
class PipelineTaskStore(Protocol):
    async def create_task(self, document_id: UUID) -> UUID:
        """Insert a new pipeline_task row with status='pending'.

        Returns the generated ``task_id``.
        Must be called within the caller's active session/unit-of-work.
        """
        ...

    async def count_pending_for_user(self, user_id: UUID) -> int:
        """Return the number of pending or running tasks owned by ``user_id``."""
        ...


# ---------------------------------------------------------------------------
# Interaction Store
# ---------------------------------------------------------------------------


@runtime_checkable
class InteractionStore(Protocol):
    async def create_interaction(
        self,
        *,
        interaction_type: str,
        user_id: UUID | None = None,
        kb_id: UUID | None = None,
        context: dict[str, Any] | None = None,
        parent_interaction_id: UUID | None = None,
    ) -> UUID: ...

    async def add_turn(
        self,
        interaction_id: UUID,
        *,
        actor_type: str,
        actor_id: str,
        action: str,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        duration_ms: int | None = None,
        cost: float | None = None,
    ) -> UUID: ...

    async def get_interaction(self, interaction_id: UUID) -> Interaction | None: ...

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Interaction]:
        """Return interactions for the user with redaction applied.

        Strips ``reference_answer``, ``grounding_context``, ``raw_prompt``,
        ``raw_completion`` from ``output_data``, and hides ``cost``.
        Redaction is enforced here, not in the router (defense in depth).
        """
        ...

    async def list_unredacted(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Interaction]:
        """Admin-only: return full unredacted interaction data."""
        ...


# ---------------------------------------------------------------------------
# External Identity Repository
# ---------------------------------------------------------------------------


@runtime_checkable
class ExternalIdentityRepository(Protocol):
    async def find_user_id(self, provider: str, external_id: str) -> UUID | None: ...

    async def link(
        self,
        user_id: UUID,
        provider: str,
        external_id: str,
        email: str | None,
        metadata: dict[str, Any],
    ) -> None: ...

    async def create_user_and_link(
        self,
        provider: str,
        external_id: str,
        display_name: str,
        email: str | None = None,
        avatar_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        """Atomically create a user row and link the external identity."""
        ...


# ---------------------------------------------------------------------------
# Quiz Session Store
# ---------------------------------------------------------------------------


@runtime_checkable
class QuizSessionStore(Protocol):
    async def create_session(self, session: QuizSession) -> None: ...

    async def get_session(self, session_id: UUID) -> QuizSession | None: ...

    async def update_session(self, session: QuizSession) -> None: ...

    async def delete_session(self, session_id: UUID) -> None: ...


# ---------------------------------------------------------------------------
# Graph Indexer
# ---------------------------------------------------------------------------


@runtime_checkable
class GraphIndexer(Protocol):
    async def index_artifact(self, artifact: DocumentArtifact, connection: Any) -> None:
        """Write/update graph nodes and edges from a processed artifact."""
        ...

    async def rebuild_knowledge_base(self, kb_id: UUID) -> None:
        """Rebuild the full graph projection for a knowledge base from PostgreSQL."""
        ...

    async def remove_lesson(self, kb_id: UUID, lesson_id: str) -> None:
        """Remove all graph nodes and edges for a deactivated lesson."""
        ...


# ---------------------------------------------------------------------------
# Knowledge Base Repository
# ---------------------------------------------------------------------------


@runtime_checkable
class KnowledgeBaseRepository(Protocol):
    async def create(
        self, owner_id: UUID, name: str, description: str
    ) -> KnowledgeBase: ...

    async def get_by_id(
        self, kb_id: UUID, owner_id: UUID | None = None
    ) -> KnowledgeBase | None: ...

    async def list_by_owner(self, owner_id: UUID) -> list[KnowledgeBase]: ...

    async def update(
        self,
        kb_id: UUID,
        owner_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> KnowledgeBase | None: ...

    async def delete(self, kb_id: UUID, owner_id: UUID) -> bool: ...


# ---------------------------------------------------------------------------
# User Repository
# ---------------------------------------------------------------------------


@runtime_checkable
class UserRepository(Protocol):
    async def save(self, user: User, connection: Any) -> None: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...
