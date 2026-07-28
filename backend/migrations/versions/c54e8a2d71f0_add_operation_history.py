"""add operation history

Revision ID: c54e8a2d71f0
Revises: 8d4a7f2c91b6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c54e8a2d71f0"
down_revision: str | Sequence[str] | None = "8d4a7f2c91b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operation_history",
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(length=26), nullable=False),
        sa.Column("entity_label", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("restored_from_id", sa.String(length=26), nullable=True),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=26), nullable=False),
        sa.Column("is_deleted", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operation_history_created",
        "operation_history",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_operation_history_entity",
        "operation_history",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_operation_history_entity", table_name="operation_history")
    op.drop_index("ix_operation_history_created", table_name="operation_history")
    op.drop_table("operation_history")
