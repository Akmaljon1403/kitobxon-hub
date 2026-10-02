"""member messages to admins, membership numbers, new message types, 10-second attendance codes

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_TYPES = (
    "EVENT_CREATED",
    "EVENT_REMINDER",
    "EVENT_STARTED",
    "ATTENDANCE_OPEN",
    "TEST_STARTED",
    "TEST_ENDING",
    "TEST_RESULT",
    "NEW_BOOK",
    "READING_REMINDER",
    "QUOTE_OF_DAY",
    "RANKING_UPDATE",
    "ACHIEVEMENT_UNLOCKED",
    "REWARD",
    "ADMIN_MESSAGE",
    "SYSTEM",
)
NEW_TYPES = (*OLD_TYPES, "SUPPORT", "CERTIFICATE", "PREMIUM", "ANNOUNCEMENT", "FEEDBACK_REQUEST", "DIGEST")
TABLES = ("notifications", "notification_templates")


def _type_check(types: tuple[str, ...]) -> str:
    return "type IN (" + ", ".join(f"'{value}'" for value in types) + ")"


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT ck_{table}_notificationtype")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT ck_{table}_notificationtype CHECK ({_type_check(NEW_TYPES)})")

    # Membership numbers, in order of registration.
    op.execute("CREATE SEQUENCE users_member_number_seq")
    op.add_column("users", sa.Column("member_number", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE users SET member_number = numbered.n
        FROM (
            SELECT id, nextval('users_member_number_seq') AS n
            FROM (SELECT id FROM users ORDER BY coalesce(registered_at, created_at), created_at, id) AS ordered
        ) AS numbered
        WHERE users.id = numbered.id
        """
    )
    op.alter_column(
        "users", "member_number", nullable=False, server_default=sa.text("nextval('users_member_number_seq')")
    )
    op.execute("ALTER SEQUENCE users_member_number_seq OWNED BY users.member_number")
    op.create_unique_constraint(op.f("uq_users_member_number"), "users", ["member_number"])

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("OPEN", "ANSWERED", "CLOSED", name="supportticketstatus", native_enum=False, create_constraint=True, length=32),
            server_default="OPEN",
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("unread_for_admin", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_support_tickets_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_tickets")),
    )
    op.create_index(
        "ix_support_tickets_status_last_message_at", "support_tickets", ["status", "last_message_at"], unique=False
    )
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"], unique=False)
    op.create_table(
        "support_messages",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("from_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("photo_file_id", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_id"], ["users.id"], name=op.f("fk_support_messages_admin_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["support_tickets.id"],
            name=op.f("fk_support_messages_ticket_id_support_tickets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_messages")),
    )
    op.create_index(
        "ix_support_messages_ticket_id_created_at", "support_messages", ["ticket_id", "created_at"], unique=False
    )

    # Attendance codes now change every 10 seconds and stay valid for 30 seconds, so a member can
    # still type the code that just changed. Only untouched defaults are updated.
    op.execute(
        "UPDATE system_settings SET value = '10'::jsonb "
        "WHERE key = 'attendance.rotation_seconds' AND value = '30'::jsonb"
    )
    op.execute(
        "UPDATE system_settings SET value = '30'::jsonb "
        "WHERE key = 'attendance.token_ttl_seconds' AND value = '60'::jsonb"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE system_settings SET value = '60'::jsonb "
        "WHERE key = 'attendance.token_ttl_seconds' AND value = '30'::jsonb"
    )
    op.execute(
        "UPDATE system_settings SET value = '30'::jsonb "
        "WHERE key = 'attendance.rotation_seconds' AND value = '10'::jsonb"
    )
    op.drop_index("ix_support_messages_ticket_id_created_at", table_name="support_messages")
    op.drop_table("support_messages")
    op.drop_index("ix_support_tickets_user_id", table_name="support_tickets")
    op.drop_index("ix_support_tickets_status_last_message_at", table_name="support_tickets")
    op.drop_table("support_tickets")
    op.drop_constraint(op.f("uq_users_member_number"), "users", type_="unique")
    op.drop_column("users", "member_number")  # drops the owned sequence too
    for table in TABLES:
        op.execute(f"DELETE FROM {table} WHERE NOT ({_type_check(OLD_TYPES)})")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT ck_{table}_notificationtype")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT ck_{table}_notificationtype CHECK ({_type_check(OLD_TYPES)})")
