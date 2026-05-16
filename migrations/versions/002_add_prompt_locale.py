"""Add prompt_locale to knowledge_bases.

Revision ID: 002_add_prompt_locale
Revises: 001_initial_schema
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa

revision = "002_add_prompt_locale"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_bases",
        sa.Column("prompt_locale", sa.Text(), server_default="pl", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("knowledge_bases", "prompt_locale")
