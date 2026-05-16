"""
001 — Initial schema

Creates the full MindForge 2.0 PostgreSQL schema as defined in
architecture.md Section 7.1, including all tables, constraints, and indexes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Identity and Access
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "external_identities",
        sa.Column(
            "identity_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "linked_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("identity_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "external_id"),
    )

    # ------------------------------------------------------------------
    # Knowledge Bases
    # ------------------------------------------------------------------
    op.create_table(
        "knowledge_bases",
        sa.Column(
            "kb_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("kb_id"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.user_id"]),
        sa.UniqueConstraint("owner_id", "name"),
    )

    # ------------------------------------------------------------------
    # Documents and Artifacts
    # ------------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column(
            "document_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("kb_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="TRUE", nullable=False),
        sa.Column("content_sha256", sa.CHAR(64), nullable=False),
        sa.Column("source_filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("original_content", sa.Text(), nullable=False),
        sa.Column("upload_source", sa.Text(), nullable=False),
        sa.Column("uploaded_by", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("current_task_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("document_id"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.user_id"]),
        sa.UniqueConstraint("kb_id", "lesson_id", "revision"),
        sa.UniqueConstraint("kb_id", "content_sha256"),
    )
    # Partial unique index: only one active revision per logical lesson per KB
    op.create_index(
        "uq_active_lesson",
        "documents",
        ["kb_id", "lesson_id"],
        unique=True,
        postgresql_where=sa.text("is_active = TRUE"),
    )

    op.create_table(
        "document_artifacts",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("artifact_json", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("summary_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("flashcards_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("concept_map_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("validation_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "fingerprints_json",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("completed_step", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("document_id", "version"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
    )

    # ------------------------------------------------------------------
    # Content Blocks (Multimodal)
    # ------------------------------------------------------------------
    op.create_table(
        "document_content_blocks",
        sa.Column(
            "block_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("block_type", sa.Text(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("media_ref", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("block_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
    )

    op.create_table(
        "media_assets",
        sa.Column(
            "asset_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("asset_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
    )

    # ------------------------------------------------------------------
    # Spaced Repetition Progress
    # ------------------------------------------------------------------
    op.create_table(
        "study_progress",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kb_id", sa.UUID(), nullable=False),
        sa.Column("card_id", sa.CHAR(16), nullable=False),
        sa.Column("ease_factor", sa.Float(), server_default="2.5", nullable=False),
        sa.Column("interval", sa.Integer(), server_default="0", nullable=False),
        sa.Column("repetitions", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_review",
            sa.Date(),
            server_default=sa.text("CURRENT_DATE"),
            nullable=False,
        ),
        sa.Column("last_review", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "kb_id", "card_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"]),
    )

    # ------------------------------------------------------------------
    # Interactions and Audit Trail
    # ------------------------------------------------------------------
    op.create_table(
        "interactions",
        sa.Column(
            "interaction_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("parent_interaction_id", sa.UUID(), nullable=True),
        sa.Column("interaction_type", sa.Text(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("kb_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column(
            "context",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("interaction_id"),
        sa.ForeignKeyConstraint(
            ["parent_interaction_id"], ["interactions.interaction_id"]
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"]),
    )

    op.create_table(
        "interaction_turns",
        sa.Column(
            "turn_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("interaction_id", sa.UUID(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column(
            "input_data",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "output_data",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Numeric(10, 6), nullable=True),
        sa.PrimaryKeyConstraint("turn_id"),
        sa.ForeignKeyConstraint(["interaction_id"], ["interactions.interaction_id"]),
    )

    # ------------------------------------------------------------------
    # Pipeline Tasks
    # ------------------------------------------------------------------
    op.create_table(
        "pipeline_tasks",
        sa.Column(
            "task_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("task_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
    )

    # ------------------------------------------------------------------
    # Transactional Outbox
    # ------------------------------------------------------------------
    op.create_table(
        "outbox_events",
        sa.Column(
            "event_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "sequence_num", sa.BigInteger(), sa.Identity(always=False), nullable=False
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("published", sa.Boolean(), server_default="FALSE", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("sequence_num"),
    )
    op.create_index(
        "ix_outbox_unpublished",
        "outbox_events",
        ["created_at"],
        postgresql_where=sa.text("NOT published"),
    )

    op.create_table(
        "consumer_cursors",
        sa.Column("consumer_name", sa.Text(), nullable=False),
        sa.Column("last_sequence", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("consumer_name"),
    )

    # ------------------------------------------------------------------
    # Quiz Sessions (server-side; contains reference_answer — never exposed)
    # ------------------------------------------------------------------
    op.create_table(
        "quiz_sessions",
        sa.Column(
            "session_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kb_id", sa.UUID(), nullable=False),
        sa.Column(
            "questions",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["kb_id"], ["knowledge_bases.kb_id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_quiz_sessions_user_id",
        "quiz_sessions",
        ["user_id"],
    )
    op.create_index(
        "ix_quiz_sessions_expires_at",
        "quiz_sessions",
        ["expires_at"],
    )

    # ------------------------------------------------------------------
    # Read Model Projections
    # ------------------------------------------------------------------
    op.create_table(
        "lesson_projections",
        sa.Column("kb_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.Text(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("flashcard_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("concept_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("summary_excerpt", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("kb_id", "lesson_id"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
    )


def downgrade() -> None:
    op.drop_table("lesson_projections")
    op.drop_index("ix_quiz_sessions_expires_at", table_name="quiz_sessions")
    op.drop_index("ix_quiz_sessions_user_id", table_name="quiz_sessions")
    op.drop_table("quiz_sessions")
    op.drop_table("consumer_cursors")
    op.drop_index("ix_outbox_unpublished", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_table("pipeline_tasks")
    op.drop_table("interaction_turns")
    op.drop_table("interactions")
    op.drop_table("study_progress")
    op.drop_table("media_assets")
    op.drop_table("document_content_blocks")
    op.drop_table("document_artifacts")
    op.drop_index("uq_active_lesson", table_name="documents")
    op.drop_table("documents")
    op.drop_table("knowledge_bases")
    op.drop_table("external_identities")
    op.drop_table("users")
