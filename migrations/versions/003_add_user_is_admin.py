"""Add is_admin column to users.

Revision ID: 003_add_user_is_admin
Revises: 002_add_prompt_locale
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa

revision = "003_add_user_is_admin"
down_revision = "002_add_prompt_locale"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            server_default="FALSE",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")
