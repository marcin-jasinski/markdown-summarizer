"""
SQLAlchemy 2.0 ORM mapped classes for every table in the MindForge schema.

These are infrastructure-layer models only.  Domain objects live in
`mindforge.domain.models` and are mapped to/from these classes inside the
repository methods.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


# ---------------------------------------------------------------------------
# Identity and Access
# ---------------------------------------------------------------------------


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_admin: Mapped[bool] = mapped_column(
        Boolean, server_default="FALSE", nullable=False
    )

    external_identities: Mapped[list[ExternalIdentityModel]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    knowledge_bases: Mapped[list[KnowledgeBaseModel]] = relationship(
        back_populates="owner"
    )
    interactions: Mapped[list[InteractionModel]] = relationship(back_populates="user")


class ExternalIdentityModel(Base):
    __tablename__ = "external_identities"

    identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default="{}", nullable=False
    )
    linked_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("provider", "external_id"),)

    user: Mapped[UserModel] = relationship(back_populates="external_identities")


# ---------------------------------------------------------------------------
# Knowledge Bases
# ---------------------------------------------------------------------------


class KnowledgeBaseModel(Base):
    __tablename__ = "knowledge_bases"

    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    prompt_locale: Mapped[str] = mapped_column(
        Text, server_default="pl", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("owner_id", "name"),)

    owner: Mapped[UserModel] = relationship(back_populates="knowledge_bases")
    documents: Mapped[list[DocumentModel]] = relationship(
        back_populates="knowledge_base"
    )
    study_progress: Mapped[list[StudyProgressModel]] = relationship(
        back_populates="knowledge_base"
    )
    interactions: Mapped[list[InteractionModel]] = relationship(
        back_populates="knowledge_base"
    )
    lesson_projections: Mapped[list[LessonProjectionModel]] = relationship(
        back_populates="knowledge_base"
    )


# ---------------------------------------------------------------------------
# Documents and Artifacts
# ---------------------------------------------------------------------------


class DocumentModel(Base):
    __tablename__ = "documents"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.kb_id"), nullable=False
    )
    lesson_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="TRUE", nullable=False
    )
    content_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    source_filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    upload_source: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    current_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("kb_id", "lesson_id", "revision"),
        UniqueConstraint("kb_id", "content_sha256"),
    )

    knowledge_base: Mapped[KnowledgeBaseModel] = relationship(
        back_populates="documents"
    )
    artifacts: Mapped[list[DocumentArtifactModel]] = relationship(
        back_populates="document"
    )
    content_blocks: Mapped[list[ContentBlockModel]] = relationship(
        back_populates="document"
    )
    media_assets: Mapped[list[MediaAssetModel]] = relationship(
        back_populates="document"
    )
    pipeline_tasks: Mapped[list[PipelineTaskModel]] = relationship(
        back_populates="document"
    )
    lesson_projections: Mapped[list[LessonProjectionModel]] = relationship(
        back_populates="document"
    )


class DocumentArtifactModel(Base):
    __tablename__ = "document_artifacts"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.document_id"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    flashcards_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    concept_map_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    validation_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    fingerprints_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default="{}", nullable=False
    )
    completed_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    document: Mapped[DocumentModel] = relationship(back_populates="artifacts")


# ---------------------------------------------------------------------------
# Content Blocks (Multimodal)
# ---------------------------------------------------------------------------


class ContentBlockModel(Base):
    __tablename__ = "document_content_blocks"

    block_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    block_type: Mapped[str] = mapped_column(Text, nullable=False)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default="{}", nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    document: Mapped[DocumentModel] = relationship(back_populates="content_blocks")


class MediaAssetModel(Base):
    __tablename__ = "media_assets"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    document: Mapped[DocumentModel] = relationship(back_populates="media_assets")


# ---------------------------------------------------------------------------
# Spaced Repetition Progress
# ---------------------------------------------------------------------------


class StudyProgressModel(Base):
    __tablename__ = "study_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), primary_key=True
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.kb_id"), primary_key=True
    )
    card_id: Mapped[str] = mapped_column(CHAR(16), primary_key=True)
    ease_factor: Mapped[float] = mapped_column(
        Float, server_default="2.5", nullable=False
    )
    interval: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    repetitions: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    next_review: Mapped[date] = mapped_column(
        Date, server_default=func.current_date(), nullable=False
    )
    last_review: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped[UserModel] = relationship()
    knowledge_base: Mapped[KnowledgeBaseModel] = relationship(
        back_populates="study_progress"
    )


# ---------------------------------------------------------------------------
# Interactions and Audit Trail
# ---------------------------------------------------------------------------


class InteractionModel(Base):
    __tablename__ = "interactions"

    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    parent_interaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interactions.interaction_id"), nullable=True
    )
    interaction_type: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    kb_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.kb_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, server_default="active", nullable=False)
    context_: Mapped[dict[str, Any]] = mapped_column(
        "context", JSONB, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped[UserModel | None] = relationship(back_populates="interactions")
    knowledge_base: Mapped[KnowledgeBaseModel | None] = relationship(
        back_populates="interactions"
    )
    turns: Mapped[list[InteractionTurnModel]] = relationship(
        back_populates="interaction",
        lazy="raise",
    )
    children: Mapped[list[InteractionModel]] = relationship()


class InteractionTurnModel(Base):
    __tablename__ = "interaction_turns"

    turn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interactions.interaction_id"), nullable=False
    )
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    input_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default="{}", nullable=False
    )
    output_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default="{}", nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)

    interaction: Mapped[InteractionModel] = relationship(back_populates="turns")


# ---------------------------------------------------------------------------
# Pipeline Tasks
# ---------------------------------------------------------------------------


class PipelineTaskModel(Base):
    __tablename__ = "pipeline_tasks"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, server_default="pending", nullable=False)
    worker_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    document: Mapped[DocumentModel] = relationship(back_populates="pipeline_tasks")


# ---------------------------------------------------------------------------
# Transactional Outbox
# ---------------------------------------------------------------------------


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    sequence_num: Mapped[int] = mapped_column(
        BigInteger, Identity(always=False), unique=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    published: Mapped[bool] = mapped_column(
        Boolean, server_default="FALSE", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ConsumerCursorModel(Base):
    __tablename__ = "consumer_cursors"

    consumer_name: Mapped[str] = mapped_column(Text, primary_key=True)
    last_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Read Model Projections
# ---------------------------------------------------------------------------


class QuizSessionModel(Base):
    """Server-side quiz session storage. Contains reference_answer — never expose to API responses."""

    __tablename__ = "quiz_sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.kb_id"), nullable=False
    )
    questions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)


class LessonProjectionModel(Base):
    __tablename__ = "lesson_projections"

    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.kb_id"), primary_key=True
    )
    lesson_id: Mapped[str] = mapped_column(Text, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    flashcard_count: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    concept_count: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    summary_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    knowledge_base: Mapped[KnowledgeBaseModel] = relationship(
        back_populates="lesson_projections"
    )
    document: Mapped[DocumentModel] = relationship(back_populates="lesson_projections")
