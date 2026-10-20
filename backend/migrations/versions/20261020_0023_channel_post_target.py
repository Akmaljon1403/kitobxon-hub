"""channel posts can target an extra channel, not only the primary one

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-20 20:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL for every existing post: they all go to the primary club channel, as before.
    op.add_column("channel_posts", sa.Column("target_chat_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("channel_posts", "target_chat_id")
