"""add device

Revision ID: b6f4a1c2098e
Revises: 64e0e278de2e
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6f4a1c2098e"
down_revision: str | Sequence[str] | None = "64e0e278de2e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("device_type", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("last_sync_at", sa.String(), nullable=True),
        sa.Column("last_pull_rev", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=26), nullable=False),
        sa.Column("is_deleted", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )


def downgrade() -> None:
    op.drop_table("device")
