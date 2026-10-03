"""premium extras (trial, Stars by card, discounts, lifetime), leaving the club, referrals, channel review

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-05 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum columns are VARCHAR + CHECK: new values need the CHECK constraint replaced.
ENUM_CHECKS = (
    ("users", "ck_users_userstatus", "status", ("PENDING", "ACTIVE", "BLOCKED", "INACTIVE"), ("LEFT",)),
    (
        "premium_subscriptions",
        "ck_premium_subscriptions_premiumsource",
        "source",
        ("STARS", "MANUAL", "CARD"),
        ("TRIAL", "GIVEAWAY", "REFERRAL"),
    ),
    ("payments", "ck_payments_paymentkind", "kind", ("PREMIUM", "DONATION"), ("STARS",)),
    ("card_payments", "ck_card_payments_paymentkind", "kind", ("PREMIUM", "DONATION"), ("STARS",)),
    (
        "giveaways",
        "ck_giveaways_giveawayrule",
        "rule",
        ("RANDOM", "TEST_TOP", "EVENT_PLACES", "RANKING_TOP"),
        ("NEW_MEMBERS",),
    ),
)
# Student-friendly prices (only where the plan still has the first default price).
PRICES = (("month", 100, 50, 9000), ("quarter", 250, 120, 22000), ("year", 900, 400, 75000))


def _check(table: str, name: str, column: str, values: tuple[str, ...]) -> None:
    listed = ", ".join(f"'{value}'" for value in values)
    op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
    op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({column} IN ({listed}))")


def upgrade() -> None:
    op.create_table('premium_discounts',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('percent', sa.SmallInteger(), nullable=False),
    sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
    sa.Column('note', sa.String(length=255), nullable=True),
    sa.Column('giveaway_id', sa.Uuid(), nullable=True),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('used_for', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('percent BETWEEN 1 AND 100', name=op.f('ck_premium_discounts_percent_range')),
    sa.ForeignKeyConstraint(['giveaway_id'], ['giveaways.id'], name=op.f('fk_premium_discounts_giveaway_id_giveaways'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_premium_discounts_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_premium_discounts'))
    )
    op.create_index('ix_premium_discounts_user_id', 'premium_discounts', ['user_id'], unique=False)
    op.add_column('card_payments', sa.Column('stars', sa.Integer(), nullable=True))
    op.add_column('card_payments', sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('card_payments', sa.Column('delivered_by', sa.Uuid(), nullable=True))
    op.add_column('card_payments', sa.Column('discount_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(op.f('fk_card_payments_discount_id_premium_discounts'), 'card_payments', 'premium_discounts', ['discount_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_card_payments_delivered_by_users'), 'card_payments', 'users', ['delivered_by'], ['id'], ondelete='SET NULL')
    op.add_column('channel_posts', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('channel_posts', sa.Column('reviewed_by', sa.Uuid(), nullable=True))
    op.create_foreign_key(op.f('fk_channel_posts_reviewed_by_users'), 'channel_posts', 'users', ['reviewed_by'], ['id'], ondelete='SET NULL')
    op.add_column('channel_stickers', sa.Column('mood', sa.Enum('CELEBRATE', 'READING', 'WELCOME', 'ANY', name='stickermood', native_enum=False, create_constraint=True, length=32), server_default='ANY', nullable=False))
    op.add_column('giveaways', sa.Column('prize', sa.Enum('CODES', 'PREMIUM_DAYS', 'PREMIUM_DISCOUNT', name='giveawayprize', native_enum=False, create_constraint=True, length=32), server_default='CODES', nullable=False))
    op.add_column('giveaways', sa.Column('prize_value', sa.Integer(), nullable=True))
    op.alter_column('giveaways', 'reward_id',
               existing_type=sa.UUID(),
               nullable=True)
    op.add_column('users', sa.Column('left_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('left_reason', sa.String(length=16), nullable=True))
    op.add_column('users', sa.Column('restore_requested_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('erased_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('referred_by', sa.Uuid(), nullable=True))
    op.add_column('users', sa.Column('referral_rewarded_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(op.f('fk_users_referred_by_users'), 'users', 'users', ['referred_by'], ['id'], ondelete='SET NULL')
    op.create_check_constraint(
        "prize_complete",
        "giveaways",
        "(prize = 'CODES' AND reward_id IS NOT NULL) OR (prize <> 'CODES' AND prize_value IS NOT NULL)",
    )
    for table, name, column, old, new in ENUM_CHECKS:
        _check(table, name, column, old + new)
    for code, old_stars, stars, uzs in PRICES:
        op.execute(f"UPDATE premium_plans SET stars = {stars} WHERE code = '{code}' AND stars = {old_stars}")
        op.execute(f"UPDATE premium_plans SET price_uzs = {uzs} WHERE code = '{code}' AND price_uzs IS NULL")


def downgrade() -> None:
    op.execute("DELETE FROM premium_subscriptions WHERE source IN ('TRIAL', 'GIVEAWAY', 'REFERRAL')")
    op.execute("DELETE FROM card_payments WHERE kind = 'STARS'")
    op.execute("DELETE FROM giveaways WHERE rule = 'NEW_MEMBERS' OR prize <> 'CODES'")
    op.execute("UPDATE users SET status = 'INACTIVE' WHERE status = 'LEFT'")
    for table, name, column, old, _ in ENUM_CHECKS:
        _check(table, name, column, old)
    op.drop_constraint(op.f("ck_giveaways_prize_complete"), "giveaways", type_="check")
    op.drop_constraint(op.f('fk_users_referred_by_users'), 'users', type_='foreignkey')
    op.drop_column('users', 'referral_rewarded_at')
    op.drop_column('users', 'referred_by')
    op.drop_column('users', 'erased_at')
    op.drop_column('users', 'restore_requested_at')
    op.drop_column('users', 'left_reason')
    op.drop_column('users', 'left_at')
    op.alter_column('giveaways', 'reward_id',
               existing_type=sa.UUID(),
               nullable=False)
    op.drop_column('giveaways', 'prize_value')
    op.drop_column('giveaways', 'prize')
    op.drop_column('channel_stickers', 'mood')
    op.drop_constraint(op.f('fk_channel_posts_reviewed_by_users'), 'channel_posts', type_='foreignkey')
    op.drop_column('channel_posts', 'reviewed_by')
    op.drop_column('channel_posts', 'reviewed_at')
    op.drop_constraint(op.f('fk_card_payments_delivered_by_users'), 'card_payments', type_='foreignkey')
    op.drop_constraint(op.f('fk_card_payments_discount_id_premium_discounts'), 'card_payments', type_='foreignkey')
    op.drop_column('card_payments', 'discount_id')
    op.drop_column('card_payments', 'delivered_by')
    op.drop_column('card_payments', 'delivered_at')
    op.drop_column('card_payments', 'stars')
    op.drop_index('ix_premium_discounts_user_id', table_name='premium_discounts')
    op.drop_table('premium_discounts')
