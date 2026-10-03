"""passport: the member's own photo and the premium card design

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-04 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("passport_photo_key", sa.String(length=512), nullable=True))
    op.add_column("users", sa.Column("passport_theme", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "passport_theme")
    op.drop_column("users", "passport_photo_key")
