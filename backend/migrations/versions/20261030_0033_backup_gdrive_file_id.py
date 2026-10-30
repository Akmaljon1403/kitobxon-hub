"""Record the Google Drive copy of a backup

Adds backups.gdrive_file_id: the Drive file id of the off-site copy, when one was made.

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | Sequence[str] | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("backups", sa.Column("gdrive_file_id", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("backups", "gdrive_file_id")
