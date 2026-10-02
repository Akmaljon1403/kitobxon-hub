"""certificates for winners (tests, monthly ranking, issued by hand)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-03 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_CERTIFICATE_TEXT = "🎓 Tabriklaymiz! Sizga «{title}» sertifikati berildi.\n{details}"
NEW_CERTIFICATE_TEXT = (
    "🎓 <b>Tabriklaymiz! Sizga sertifikat berildi.</b>\n\n🏅 {title}\n\n"
    "Sertifikat PDF fayl sifatida ilova qilingan — uni yuklab olib, chop etishingiz mumkin.\n{details}"
)


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "TEST_PLACE",
                "MONTHLY_TOP",
                "MANUAL",
                name="certificatekind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("place", sa.SmallInteger(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("test_id", sa.Uuid(), nullable=True),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("period", sa.String(length=7), nullable=True),
        sa.Column("dedup_key", sa.String(length=128), nullable=False),
        sa.Column("verify_code", sa.String(length=16), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("issued_by", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("file_key", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("place IS NULL OR place BETWEEN 1 AND 3", name=op.f("ck_certificates_place_range")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_certificates_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["issued_by"], ["users.id"], name=op.f("fk_certificates_issued_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["test_id"], ["tests.id"], name=op.f("fk_certificates_test_id_tests"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], name=op.f("fk_certificates_event_id_events"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_certificates")),
        sa.UniqueConstraint("dedup_key", name=op.f("uq_certificates_dedup_key")),
        sa.UniqueConstraint("verify_code", name=op.f("uq_certificates_verify_code")),
    )
    op.create_index("ix_certificates_user_id_issued_at", "certificates", ["user_id", "issued_at"], unique=False)

    # The message template got clearer wording; keep it if an administrator already edited it.
    templates = sa.table("notification_templates", sa.column("type", sa.String), sa.column("body", sa.Text))
    op.execute(
        templates.update()
        .where(templates.c.type == "CERTIFICATE", templates.c.body == OLD_CERTIFICATE_TEXT)
        .values(body=NEW_CERTIFICATE_TEXT)
    )


def downgrade() -> None:
    templates = sa.table("notification_templates", sa.column("type", sa.String), sa.column("body", sa.Text))
    op.execute(
        templates.update()
        .where(templates.c.type == "CERTIFICATE", templates.c.body == NEW_CERTIFICATE_TEXT)
        .values(body=OLD_CERTIFICATE_TEXT)
    )
    op.drop_index("ix_certificates_user_id_issued_at", table_name="certificates")
    op.drop_table("certificates")
