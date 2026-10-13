"""support tickets: general vs payment are separate conversations

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-13 05:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0020'
down_revision: str | Sequence[str] | None = '0019'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_kind = sa.Enum('GENERAL', 'PAYMENT', name='supportticketkind', native_enum=False, create_constraint=True, length=32)


def upgrade() -> None:
    op.add_column('support_tickets', sa.Column('kind', _kind, server_default='GENERAL', nullable=False))
    # Tickets that ever had a question in the payments chat are money conversations: mark them PAYMENT so
    # an old mixed ticket is read as payment (its answers already lived in the payments channel).
    op.execute(
        """
        UPDATE support_tickets SET kind = 'PAYMENT'
        WHERE id IN (SELECT target_id FROM payments_chat_links WHERE kind = 'ticket')
        """
    )


def downgrade() -> None:
    op.drop_column('support_tickets', 'kind')
