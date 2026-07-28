"""add customer location

Revision ID: 8d4a7f2c91b6
Revises: 32fa7d8b91c4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8d4a7f2c91b6"
down_revision: str | Sequence[str] | None = "32fa7d8b91c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("customer") as batch_op:
        batch_op.add_column(sa.Column("location", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("customer") as batch_op:
        batch_op.drop_column("location")
