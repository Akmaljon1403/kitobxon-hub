"""card payments with receipts, promo-code giveaways

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-04 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('giveaways',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('reward_id', sa.Uuid(), nullable=False),
    sa.Column('rule', sa.Enum('RANDOM', 'TEST_TOP', 'EVENT_PLACES', 'RANKING_TOP', name='giveawayrule', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('audience', sa.Enum('ALL', 'ATTENDED', 'PREMIUM', name='giveawayaudience', native_enum=False, create_constraint=True, length=32), server_default='ALL', nullable=False),
    sa.Column('winners_count', sa.SmallInteger(), nullable=False),
    sa.Column('premium_bonus', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('status', sa.Enum('DRAFT', 'SCHEDULED', 'DONE', 'CANCELLED', name='giveawaystatus', native_enum=False, create_constraint=True, length=32), server_default='DRAFT', nullable=False),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('announce', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('repeat_monthly', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('drawn_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('seed', sa.String(length=64), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('period_end >= period_start', name=op.f('ck_giveaways_period_order')),
    sa.CheckConstraint('winners_count BETWEEN 1 AND 100', name=op.f('ck_giveaways_winners_count_range')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_giveaways_created_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['reward_id'], ['rewards.id'], name=op.f('fk_giveaways_reward_id_rewards'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_giveaways'))
    )
    op.create_index('ix_giveaways_status_scheduled_at', 'giveaways', ['status', 'scheduled_at'], unique=False)
    op.create_table('card_payments',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.Enum('PREMIUM', 'DONATION', name='paymentkind', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('plan_id', sa.Uuid(), nullable=True),
    sa.Column('amount_uzs', sa.Integer(), nullable=False),
    sa.Column('receipt_key', sa.String(length=512), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='cardpaymentstatus', native_enum=False, create_constraint=True, length=32), server_default='PENDING', nullable=False),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decided_by', sa.Uuid(), nullable=True),
    sa.Column('reject_reason', sa.Text(), nullable=True),
    sa.Column('subscription_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('amount_uzs > 0', name=op.f('ck_card_payments_amount_positive')),
    sa.ForeignKeyConstraint(['decided_by'], ['users.id'], name=op.f('fk_card_payments_decided_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['plan_id'], ['premium_plans.id'], name=op.f('fk_card_payments_plan_id_premium_plans'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['subscription_id'], ['premium_subscriptions.id'], name=op.f('fk_card_payments_subscription_id_premium_subscriptions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_card_payments_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_card_payments'))
    )
    op.create_index('ix_card_payments_status_created_at', 'card_payments', ['status', 'created_at'], unique=False)
    op.create_index('ix_card_payments_user_id', 'card_payments', ['user_id'], unique=False)
    op.add_column('premium_plans', sa.Column('price_uzs', sa.Integer(), nullable=True))
    op.create_check_constraint("price_uzs_positive", "premium_plans", "price_uzs IS NULL OR price_uzs > 0")
    # Premium periods can now come from a confirmed card payment.
    op.execute("ALTER TABLE premium_subscriptions DROP CONSTRAINT ck_premium_subscriptions_premiumsource")
    op.execute(
        "ALTER TABLE premium_subscriptions ADD CONSTRAINT ck_premium_subscriptions_premiumsource "
        "CHECK (source IN ('STARS', 'MANUAL', 'CARD'))"
    )


def downgrade() -> None:
    op.execute("DELETE FROM premium_subscriptions WHERE source = 'CARD'")
    op.execute("ALTER TABLE premium_subscriptions DROP CONSTRAINT ck_premium_subscriptions_premiumsource")
    op.execute(
        "ALTER TABLE premium_subscriptions ADD CONSTRAINT ck_premium_subscriptions_premiumsource "
        "CHECK (source IN ('STARS', 'MANUAL'))"
    )
    op.drop_constraint("price_uzs_positive", "premium_plans", type_="check")
    op.drop_column('premium_plans', 'price_uzs')
    op.drop_index('ix_card_payments_user_id', table_name='card_payments')
    op.drop_index('ix_card_payments_status_created_at', table_name='card_payments')
    op.drop_table('card_payments')
    op.drop_index('ix_giveaways_status_scheduled_at', table_name='giveaways')
    op.drop_table('giveaways')
