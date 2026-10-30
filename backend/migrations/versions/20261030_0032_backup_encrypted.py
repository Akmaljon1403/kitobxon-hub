"""Mark whether a backup dump is encrypted at rest

Adds backups.encrypted. Existing rows are plaintext (false). New backups are
AES-256-GCM encrypted when BACKUP_ENCRYPTION_KEY is set.

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | Sequence[str] | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backups",
        sa.Column("encrypted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("backups", "encrypted")
