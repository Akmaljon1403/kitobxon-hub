"""Database backup records

One row per pg_dump created (automatic nightly/monthly or a super admin's manual
«Hozir zaxira olish»). The dump file itself lives in the configured file storage;
this table only records what was taken, when, how big and its checksum.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | Sequence[str] | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backups",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("db_name", sa.String(length=128), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('DAILY', 'MONTHLY', 'MANUAL')", name="ck_backups_backupkind"),
        sa.CheckConstraint("status IN ('SUCCESS', 'FAILED')", name="ck_backups_backupstatus"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_backups_created_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_backups"),
    )
    op.create_index("ix_backups_created_at", "backups", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_backups_created_at", table_name="backups")
    op.drop_table("backups")
