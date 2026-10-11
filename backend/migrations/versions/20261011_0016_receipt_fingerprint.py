"""receipt fingerprint (the same receipt sent twice)

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-11 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0016'
down_revision: str | Sequence[str] | None = '0015'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('card_payments', sa.Column('receipt_sha256', sa.String(length=64), nullable=True))
    op.create_index('ix_card_payments_receipt_sha256', 'card_payments', ['receipt_sha256'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_card_payments_receipt_sha256', table_name='card_payments')
    op.drop_column('card_payments', 'receipt_sha256')
