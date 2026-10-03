"""general and period reports, feature switches, premium membership with Telegram Stars, event feedback

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-03 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_DIGEST = "{message}"
NEW_DIGEST = "📊 <b>Haftalik xulosangiz</b>\n\n{message}\n\nYangi haftada omad! 📚"
OLD_ANNOUNCEMENT = "🎉 {message}"
NEW_ANNOUNCEMENT = "🎉 <b>Tabriklaymiz, bot yangilandi!</b>\n\nEndi sizda yangi imkoniyat bor:\n{title} — {description}."


def upgrade() -> None:
    op.create_table('premium_plans',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('stars', sa.Integer(), nullable=False),
    sa.Column('days', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('days > 0', name=op.f('ck_premium_plans_days_positive')),
    sa.CheckConstraint('stars > 0', name=op.f('ck_premium_plans_stars_positive')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_premium_plans')),
    sa.UniqueConstraint('code', name=op.f('uq_premium_plans_code'))
    )
    op.create_table('feature_flags',
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('mode', sa.Enum('OFF', 'ALL', 'PREMIUM', name='featuremode', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name=op.f('fk_feature_flags_updated_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('code', name=op.f('pk_feature_flags'))
    )
    op.create_table('payments',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.Enum('PREMIUM', 'DONATION', name='paymentkind', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('status', sa.Enum('PAID', 'REFUNDED', name='paymentstatus', native_enum=False, create_constraint=True, length=32), server_default='PAID', nullable=False),
    sa.Column('currency', sa.String(length=8), server_default='XTR', nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('plan_id', sa.Uuid(), nullable=True),
    sa.Column('invoice_payload', sa.String(length=128), nullable=False),
    sa.Column('telegram_charge_id', sa.String(length=255), nullable=False),
    sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('refunded_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('amount > 0', name=op.f('ck_payments_amount_positive')),
    sa.ForeignKeyConstraint(['plan_id'], ['premium_plans.id'], name=op.f('fk_payments_plan_id_premium_plans'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['refunded_by'], ['users.id'], name=op.f('fk_payments_refunded_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_payments_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payments')),
    sa.UniqueConstraint('telegram_charge_id', name=op.f('uq_payments_telegram_charge_id'))
    )
    op.create_index('ix_payments_created_at', 'payments', ['created_at'], unique=False)
    op.create_index('ix_payments_user_id', 'payments', ['user_id'], unique=False)
    op.create_table('premium_subscriptions',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('source', sa.Enum('STARS', 'MANUAL', name='premiumsource', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('plan_id', sa.Uuid(), nullable=True),
    sa.Column('payment_id', sa.Uuid(), nullable=True),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('granted_by', sa.Uuid(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('ends_at > starts_at', name=op.f('ck_premium_subscriptions_period_order')),
    sa.ForeignKeyConstraint(['granted_by'], ['users.id'], name=op.f('fk_premium_subscriptions_granted_by_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], name=op.f('fk_premium_subscriptions_payment_id_payments'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['plan_id'], ['premium_plans.id'], name=op.f('fk_premium_subscriptions_plan_id_premium_plans'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_premium_subscriptions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_premium_subscriptions'))
    )
    op.create_index('ix_premium_subscriptions_user_id_ends_at', 'premium_subscriptions', ['user_id', 'ends_at'], unique=False)
    op.create_table('event_feedback',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('rating', sa.SmallInteger(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('rating BETWEEN 1 AND 5', name=op.f('ck_event_feedback_rating_range')),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], name=op.f('fk_event_feedback_event_id_events'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_event_feedback_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_event_feedback')),
    sa.UniqueConstraint('event_id', 'user_id', name=op.f('uq_event_feedback_event_id_user_id'))
    )
    op.add_column('reports', sa.Column('kind', sa.Enum('EVENT', 'PERIOD', 'GENERAL', name='reportkind', native_enum=False, create_constraint=True, length=32), server_default='EVENT', nullable=False))
    op.add_column('reports', sa.Column('period_start', sa.Date(), nullable=True))
    op.add_column('reports', sa.Column('period_end', sa.Date(), nullable=True))
    op.alter_column('reports', 'event_id',
               existing_type=sa.UUID(),
               nullable=True)
    op.create_check_constraint("event_required", "reports", "kind <> 'EVENT' OR event_id IS NOT NULL")
    op.create_check_constraint(
        "period_required",
        "reports",
        "kind <> 'PERIOD' OR (period_start IS NOT NULL AND period_end IS NOT NULL AND period_end >= period_start)",
    )

    # The announcement template now names the feature; keep it if an administrator edited it.
    templates = sa.table("notification_templates", sa.column("type", sa.String), sa.column("body", sa.Text))
    op.execute(
        templates.update()
        .where(templates.c.type == "ANNOUNCEMENT", templates.c.body == OLD_ANNOUNCEMENT)
        .values(body=NEW_ANNOUNCEMENT)
    )
    op.execute(
        templates.update()
        .where(templates.c.type == "DIGEST", templates.c.body == OLD_DIGEST)
        .values(body=NEW_DIGEST)
    )
    # Default premium plans are created by the reference-data sync on start-up (app.services.bootstrap).


def downgrade() -> None:
    templates = sa.table("notification_templates", sa.column("type", sa.String), sa.column("body", sa.Text))
    op.execute(
        templates.update()
        .where(templates.c.type == "ANNOUNCEMENT", templates.c.body == NEW_ANNOUNCEMENT)
        .values(body=OLD_ANNOUNCEMENT)
    )
    op.execute(
        templates.update().where(templates.c.type == "DIGEST", templates.c.body == NEW_DIGEST).values(body=OLD_DIGEST)
    )
    op.execute("DELETE FROM reports WHERE kind <> 'EVENT'")
    op.drop_constraint("period_required", "reports", type_="check")
    op.drop_constraint("event_required", "reports", type_="check")
    op.alter_column('reports', 'event_id',
               existing_type=sa.UUID(),
               nullable=False)
    op.drop_column('reports', 'period_end')
    op.drop_column('reports', 'period_start')
    op.drop_column('reports', 'kind')
    op.drop_table('event_feedback')
    op.drop_index('ix_premium_subscriptions_user_id_ends_at', table_name='premium_subscriptions')
    op.drop_table('premium_subscriptions')
    op.drop_index('ix_payments_user_id', table_name='payments')
    op.drop_index('ix_payments_created_at', table_name='payments')
    op.drop_table('payments')
    op.drop_table('feature_flags')
    op.drop_table('premium_plans')
