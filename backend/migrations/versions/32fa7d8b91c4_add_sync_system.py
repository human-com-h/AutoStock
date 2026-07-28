"""add sync system

Revision ID: 32fa7d8b91c4
Revises: b6f4a1c2098e
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "32fa7d8b91c4"
down_revision: str | Sequence[str] | None = "b6f4a1c2098e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def _business_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=26), nullable=False),
        sa.Column("is_deleted", sa.Integer(), nullable=False),
    )


def upgrade() -> None:
    naming_convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    with op.batch_alter_table(
        "part",
        naming_convention=naming_convention,
        recreate="always",
    ) as batch_op:
        batch_op.add_column(sa.Column("merged_into", sa.String(length=26), nullable=True))
        batch_op.drop_constraint("uq_part_part_number", type_="unique")
    op.create_index(
        "uq_part_number_master",
        "part",
        ["part_number"],
        unique=True,
        sqlite_where=sa.text("merged_into IS NULL AND is_deleted = 0"),
    )

    op.create_table(
        "sync_log",
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("client_batch_id", sa.String(length=26), nullable=True),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("finished_at", sa.String(), nullable=True),
        sa.Column("pushed_count", sa.Integer(), nullable=False),
        sa.Column("pulled_count", sa.Integer(), nullable=False),
        sa.Column("conflict_count", sa.Integer(), nullable=False),
        sa.Column("from_rev", sa.Integer(), nullable=False),
        sa.Column("to_rev", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=True),
        *_business_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id",
            "direction",
            "client_batch_id",
            name="uq_sync_log_device_direction_batch",
        ),
    )
    op.create_index("ix_sync_log_started_at", "sync_log", ["started_at"], unique=False)

    op.create_table(
        "sync_conflict",
        sa.Column("table_name", sa.String(), nullable=False),
        sa.Column("row_id", sa.String(length=26), nullable=False),
        sa.Column("local_value", sa.Text(), nullable=False),
        sa.Column("remote_value", sa.Text(), nullable=False),
        sa.Column("resolution", sa.String(), nullable=False),
        sa.Column("conflict_type", sa.String(), nullable=False),
        sa.Column("clock_skew", sa.Integer(), nullable=False),
        sa.Column("resolved_by", sa.String(), nullable=True),
        sa.Column("resolved_at", sa.String(), nullable=True),
        *_business_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sync_conflict_unresolved",
        "sync_conflict",
        ["resolved_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_sync_conflict_row",
        "sync_conflict",
        ["table_name", "row_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sync_conflict_row", table_name="sync_conflict")
    op.drop_index("ix_sync_conflict_unresolved", table_name="sync_conflict")
    op.drop_table("sync_conflict")
    op.drop_index("ix_sync_log_started_at", table_name="sync_log")
    op.drop_table("sync_log")
    op.drop_index("uq_part_number_master", table_name="part")
    with op.batch_alter_table("part", recreate="always") as batch_op:
        batch_op.drop_column("merged_into")
        batch_op.create_unique_constraint("uq_part_part_number", ["part_number"])
