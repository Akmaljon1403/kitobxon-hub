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

# Livelier, book-flavoured texts: replaced only where an admin has not edited the old default.
TEMPLATES = (
    (
        'EVENT_CREATED',
        "📅 Yangi tadbir: «{event_title}»\n🕒 {starts_at}\n📍 {location}\n\nQatnashmoqchi bo'lsangiz, ilovada ro'yxatdan o'ting.",
        "📅 <b>Yangi uchrashuv: «{event_title}»</b>\n🕒 {starts_at}\n📍 {location}\n\nKitob haqidagi suhbat — kitobning davomi. Qatnashmoqchi bo'lsangiz, ilovada joyingizni band qiling 👇",
    ),
    (
        'EVENT_REMINDER',
        '⏰ Eslatma: «{event_title}» tadbiri {starts_at} da boshlanadi.\n📍 {location}',
        "⏰ <b>Eslatma:</b> «{event_title}» {starts_at} da boshlanadi.\n📍 {location}\n\nKitobingiz va savollaringizni olib keling — eng qiziq fikrlar suhbatda tug'iladi 📚",
    ),
    (
        'EVENT_STARTED',
        '▶️ «{event_title}» tadbiri boshlandi!',
        '▶️ «{event_title}» boshlandi! Birinchi sahifa ochildi — kechikmang 📖',
    ),
    (
        'ATTENDANCE_OPEN',
        '✅ «{event_title}» tadbirida davomat ochildi. Ekrandagi QR kodni ilova orqali skanerlang yoki kodni kiriting.',
        '✅ «{event_title}» tadbirida davomat ochildi. Ekrandagi QR kodni ilova orqali skanerlang yoki kodni kiriting — bugungi sahifa kitobxonlik kundaligingizga yozilsin ✍️',
    ),
    (
        'TEST_STARTED',
        '📝 Yangi test: «{test_title}»\nTest {ends_at} gacha ochiq. Ishlash vaqti: {duration} daqiqa.',
        "📝 <b>Yangi test: «{test_title}»</b>\nTest {ends_at} gacha ochiq, ishlash vaqti — {duration} daqiqa.\n\nO'qiganlaringizni sinab ko'ring: har bir to'g'ri javob — ball 🎯",
    ),
    (
        'TEST_ENDING',
        "⌛ «{test_title}» testi {ends_at} da yopiladi. Hali ishlamagan bo'lsangiz, ulguring!",
        '⌛ «{test_title}» testi {ends_at} da yopiladi. Oxirgi bob qolgandek — ulguring! 🏃',
    ),
    (
        'NEW_BOOK',
        "📚 Yangi kitob: «{book_title}» — {book_author}\n🗓 O'qish muddati: {deadline}",
        "📚 <b>Yangi kitob: «{book_title}»</b> — {book_author}\n🗓 O'qish muddati: {deadline}\n\nHar bir kitob — yangi dunyo. Birinchi sahifani bugun oching! 📖",
    ),
    (
        'READING_REMINDER',
        "📖 «{book_title}» kitobini o'qish muddati {deadline} da tugaydi.",
        "📖 «{book_title}» sizni kutyapti: o'qish muddati {deadline} da tugaydi.\nKuniga bir necha bet — va marra sizniki! 💪",
    ),
    (
        'QUOTE_OF_DAY',
        '💬 Kun iqtibosi\n\n«{quote_text}»\n\n— {quote_author}',
        '💬 <b>Kun iqtibosi</b>\n\n<i>«{quote_text}»</i>\n\n— {quote_author}',
    ),
    (
        'ACHIEVEMENT_UNLOCKED',
        "🏅 Tabriklaymiz! Siz «{achievement_title}» yutug'ini qo'lga kiritdingiz.",
        "🏅 Tabriklaymiz! Siz «{achievement_title}» yutug'ini qo'lga kiritdingiz.\nKitobxonlik tarixingizga yangi sahifa yozildi ✨",
    ),
    (
        'REWARD',
        "🎁 Sizga sovg'a berildi: «{reward_title}». Batafsil ma'lumot ilovada.",
        "🎁 Sizga sovg'a berildi: «{reward_title}»! Batafsil ma'lumot ilovada — «Sovg'alarim» bo'limida.\nMutolaangiz yanada maroqli bo'lsin 📚",
    ),
    (
        'CERTIFICATE',
        '🎓 <b>Tabriklaymiz! Sizga sertifikat berildi.</b>\n\n🏅 {title}\n\nSertifikat PDF fayl sifatida ilova qilingan — uni yuklab olib, chop etishingiz mumkin.\n{details}',
        "🎓 <b>Tabriklaymiz! Sizga sertifikat berildi.</b>\n\n🏅 {title}\n\nMehnatingiz muhrlandi — bu kitobxonlik yo'lingizdagi yangi bekat.\n{details}",
    ),
    (
        'FEEDBACK_REQUEST',
        '💬 «{event_title}» tadbiri sizga yoqdimi? Bir bosishda baho bering — bu keyingi tadbirlarni yaxshilashga yordam beradi.',
        "💬 «{event_title}» sizga yoqdimi? Kitobga taqriz yozilgandek, tadbirga ham bir bosishda baho bering — keyingilari yanada qiziq bo'ladi.",
    ),
    (
        'DIGEST',
        '📊 <b>Haftalik xulosangiz</b>\n\n{message}\n\nYangi haftada omad! 📚',
        '📊 <b>Haftalik xulosangiz</b>\n\n{message}\n\nYangi hafta — yangi bob. Omad! 📚',
    ),
)
# Moods of the stickers saved before (the bot now picks a fitting one: 🎉 under wins, 📚 under books).
STICKER_MOODS = (
    ("CELEBRATE", "🎉🥳🏆🥇🥈🥉👏🎊💪🔥🤩😍❤⭐🌟🎁💎✨😎🙌👍🏅🎖💯🚀"),
    ("READING", "📚📖📕📗📘📙📓📔📒🤓🧐✍📝🔖🧠☕🤔💡🖋"),
    ("WELCOME", "👋🤗😊🙂☺🌸🌷💐🤝😉🙋🌹🌼☀"),
)


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
    op.add_column('channel_posts', sa.Column('review_sent_at', sa.DateTime(timezone=True), nullable=True))
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
    templates = sa.table("notification_templates", sa.column("type", sa.String), sa.column("body", sa.Text))
    for type_, old_body, new_body in TEMPLATES:
        op.execute(
            templates.update()
            .where(templates.c.type == type_, templates.c.body == old_body)
            .values(body=new_body)
        )
    stickers = sa.table(
        "channel_stickers", sa.column("id", sa.Uuid), sa.column("emoji", sa.String), sa.column("mood", sa.String)
    )
    connection = op.get_bind()
    for sticker_id, emoji in connection.execute(sa.select(stickers.c.id, stickers.c.emoji)).all():
        base = (emoji or "").replace("\ufe0f", "")
        mood = next((name for name, symbols in STICKER_MOODS if base and any(s in base for s in symbols)), "ANY")
        if mood != "ANY":
            connection.execute(stickers.update().where(stickers.c.id == sticker_id).values(mood=mood))


def downgrade() -> None:
    templates = sa.table("notification_templates", sa.column("type", sa.String), sa.column("body", sa.Text))
    for type_, old_body, new_body in TEMPLATES:
        op.execute(
            templates.update()
            .where(templates.c.type == type_, templates.c.body == new_body)
            .values(body=old_body)
        )
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
    op.drop_column('channel_posts', 'review_sent_at')
    op.drop_constraint(op.f('fk_card_payments_delivered_by_users'), 'card_payments', type_='foreignkey')
    op.drop_constraint(op.f('fk_card_payments_discount_id_premium_discounts'), 'card_payments', type_='foreignkey')
    op.drop_column('card_payments', 'discount_id')
    op.drop_column('card_payments', 'delivered_by')
    op.drop_column('card_payments', 'delivered_at')
    op.drop_column('card_payments', 'stars')
    op.drop_index('ix_premium_discounts_user_id', table_name='premium_discounts')
    op.drop_table('premium_discounts')
