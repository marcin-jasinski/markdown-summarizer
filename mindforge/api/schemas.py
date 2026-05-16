"""
API Pydantic request/response schemas.

These models define the contract between the FastAPI backend and the Angular
frontend.  They must stay in sync with
``frontend/src/app/core/models/api.models.ts``.

Security note: no ``reference_answer``, ``grounding_context``, ``raw_prompt``
or ``raw_completion`` fields appear in *any* user-facing schema — those are
redacted at the store level and excluded here as defence-in-depth.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    user_id: UUID
    display_name: str
    email: str | None = None
    avatar_url: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Knowledge base schemas
# ---------------------------------------------------------------------------


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    prompt_locale: str = Field(default="pl", pattern="^(pl|en)$")


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    prompt_locale: str | None = Field(default=None, pattern="^(pl|en)$")


class KnowledgeBaseResponse(BaseModel):
    kb_id: UUID
    owner_id: UUID
    name: str
    description: str
    created_at: datetime
    document_count: int
    prompt_locale: str = "pl"


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------


class DocumentResponse(BaseModel):
    document_id: UUID
    knowledge_base_id: UUID
    lesson_id: str
    title: str
    source_filename: str
    mime_type: str
    status: str
    upload_source: str
    revision: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UploadResponse(BaseModel):
    """Returned immediately on document upload (HTTP 202)."""

    document_id: UUID
    task_id: UUID
    lesson_id: str
    revision: int
    message: str = "Dokument przyjęty do przetworzenia."


class ReprocessRequest(BaseModel):
    force: bool = False


# ---------------------------------------------------------------------------
# Pipeline task schemas
# ---------------------------------------------------------------------------


class TaskStatusResponse(BaseModel):
    task_id: UUID
    document_id: UUID
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    attempt_count: int = 0


# ---------------------------------------------------------------------------
# Concept / graph schemas
# ---------------------------------------------------------------------------


class ConceptNodeResponse(BaseModel):
    key: str
    label: str
    description: str
    related: list[str] = Field(default_factory=list)


class ConceptEdgeResponse(BaseModel):
    source: str
    target: str
    relation: str


class ConceptGraphResponse(BaseModel):
    """Graph data shaped for Cytoscape.js."""

    concepts: list[ConceptNodeResponse]
    edges: list[ConceptEdgeResponse]


# ---------------------------------------------------------------------------
# Quiz schemas
# ---------------------------------------------------------------------------


class StartQuizRequest(BaseModel):
    topic: str | None = None


class QuizQuestionResponse(BaseModel):
    """Returned to client — reference_answer and grounding_context are NOT included."""

    session_id: UUID
    question_id: str
    question_text: str
    question_type: str
    lesson_id: str


class SubmitAnswerRequest(BaseModel):
    question_id: str
    user_answer: str = Field(min_length=1, max_length=4000)


class AnswerEvaluationResponse(BaseModel):
    """Evaluation result returned to client — reference_answer NOT included."""

    question_id: str
    score: int
    feedback: str
    is_correct: bool


# ---------------------------------------------------------------------------
# Flashcard schemas
# ---------------------------------------------------------------------------


class FlashcardResponse(BaseModel):
    card_id: str
    lesson_id: str
    card_type: str
    front: str
    back: str
    tags: list[str] = Field(default_factory=list)
    next_review: str | None = None
    ease_factor: float | None = None
    interval: int | None = None


class ReviewRequest(BaseModel):
    card_id: str
    rating: int = Field(ge=0, le=5)

    @field_validator("rating")
    @classmethod
    def _rating_range(cls, v: int) -> int:
        if not (0 <= v <= 5):
            raise ValueError("Rating must be between 0 and 5")
        return v


class DueCountResponse(BaseModel):
    due_count: int
    kb_id: UUID


# ---------------------------------------------------------------------------
# Search schemas
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    content: str
    source_lesson_id: str
    source_document_id: UUID
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    query: str


# ---------------------------------------------------------------------------
# Chat schemas
# ---------------------------------------------------------------------------


class StartChatRequest(BaseModel):
    knowledge_base_id: UUID


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatTurnResponse(BaseModel):
    role: str
    content: str
    created_at: datetime


class ChatSessionResponse(BaseModel):
    session_id: UUID
    knowledge_base_id: UUID
    created_at: datetime
    turns: list[ChatTurnResponse] = Field(default_factory=list)


class ChatMessageResponse(BaseModel):
    """Response for a single chat message.

    Deliberately excludes grounding context, raw prompts, and raw completions.
    """

    session_id: UUID
    answer: str
    source_concept_keys: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# SSE / events schemas
# ---------------------------------------------------------------------------


class SSEEvent(BaseModel):
    event_type: str
    payload: dict[str, Any]
    created_at: str


# ---------------------------------------------------------------------------
# Interaction history schemas (redacted)
# ---------------------------------------------------------------------------


class InteractionTurnResponse(BaseModel):
    turn_id: UUID
    interaction_id: UUID
    turn_number: int
    role: str
    content: str
    created_at: datetime
    tokens_used: int = 0


class InteractionResponse(BaseModel):
    interaction_id: UUID
    interaction_type: str
    created_at: datetime
    knowledge_base_id: UUID | None = None
    completed_at: datetime | None = None
    turns: list[InteractionTurnResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Health check schema
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    database: str
    neo4j: str | None = None
    redis: str | None = None


# ---------------------------------------------------------------------------
# Admin schemas
# ---------------------------------------------------------------------------


class SystemMetricsResponse(BaseModel):
    total_users: int
    total_documents: int
    total_knowledge_bases: int
    pending_pipeline_tasks: int
    outbox_unpublished: int


# ---------------------------------------------------------------------------
# Lesson schemas
# ---------------------------------------------------------------------------


class LessonResponse(BaseModel):
    lesson_id: str
    title: str
    document_count: int
    flashcard_count: int
    concept_count: int
    last_processed_at: datetime | None = None


# ---------------------------------------------------------------------------
# User stats schemas
# ---------------------------------------------------------------------------


class UserStatsResponse(BaseModel):
    streak_days: int = 0
    due_today: int = 0
