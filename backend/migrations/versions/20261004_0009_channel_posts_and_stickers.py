"""channel posts of the bot (club channel) and stickers saved for them

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-04 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('channel_posts',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('kind', sa.Enum('EVENT', 'EVENT_REMINDER', 'BOOK', 'READING_NUDGE', 'QUOTE', 'RESULTS', 'INVITE', 'MANUAL', name='channelpostkind', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('photo_key', sa.String(length=512), nullable=True),
    sa.Column('photo_url', sa.Text(), nullable=True),
    sa.Column('sticker_file_id', sa.String(length=255), nullable=True),
    sa.Column('buttons', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('dedup_key', sa.String(length=160), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'SENT', 'FAILED', 'CANCELLED', name='channelpoststatus', native_enum=False, create_constraint=True, length=32), server_default='PENDING', nullable=False),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('attempts', sa.SmallInteger(), server_default='0', nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('message_id', sa.BigInteger(), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_channel_posts_created_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_channel_posts')),
    sa.UniqueConstraint('dedup_key', name=op.f('uq_channel_posts_dedup_key'))
    )
    op.create_index('ix_channel_posts_status_scheduled_at', 'channel_posts', ['status', 'scheduled_at'], unique=False)
    op.create_table('channel_stickers',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('file_id', sa.String(length=255), nullable=False),
    sa.Column('file_unique_id', sa.String(length=64), nullable=False),
    sa.Column('emoji', sa.String(length=16), nullable=True),
    sa.Column('set_name', sa.String(length=64), nullable=True),
    sa.Column('is_animated', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_channel_stickers_created_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_channel_stickers')),
    sa.UniqueConstraint('file_unique_id', name=op.f('uq_channel_stickers_file_unique_id'))
    )


def downgrade() -> None:
    op.drop_table('channel_stickers')
    op.drop_index('ix_channel_posts_status_scheduled_at', table_name='channel_posts')
    op.drop_table('channel_posts')
