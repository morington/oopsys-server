"""
container hidden flag

Revision ID: a1b2c3d4e5f6
Revises: dbbc70bac54f
Create Date: 2026-06-01 20:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "dbbc70bac54f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "container_states",
        sa.Column("hidden", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("container_states", "hidden")
