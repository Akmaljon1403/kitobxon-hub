"""a reading contest can be tied to an event; an event can pin a standard certificate design

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-21 07:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # One reading contest may be attached to one event (created inside the event window).
    op.add_column("campaigns", sa.Column("event_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_campaigns_event_id_events"),
        "campaigns",
        "events",
        ["event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # At most one live contest per event: one tadbir → one tanlov.
    op.create_index(
        "uq_campaigns_event_id",
        "campaigns",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("event_id IS NOT NULL AND deleted_at IS NULL"),
    )
    # A pinned standard certificate design for the event's winners; NULL keeps the "next in turn" behaviour.
    op.add_column("events", sa.Column("certificate_design", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "certificate_design")
    op.drop_index("uq_campaigns_event_id", table_name="campaigns")
    op.drop_constraint(op.f("fk_campaigns_event_id_events"), "campaigns", type_="foreignkey")
    op.drop_column("campaigns", "event_id")
