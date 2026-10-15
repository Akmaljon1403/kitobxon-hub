"""reading contests: per-campaign participants, isolated from one another

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-15 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KINDS = ("EVENT", "EVENT_REMINDER", "BOOK", "READING_NUDGE", "QUOTE", "RESULTS", "INVITE", "MANUAL", "REPORT")


def _kind_in(*values: str) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"kind IN ({joined})"


def upgrade() -> None:
    op.create_table(
        "campaign_participants",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("points_awarded", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "user_id", name="uq_campaign_participant"),
    )
    op.create_index("ix_campaign_participants_campaign_id", "campaign_participants", ["campaign_id"], unique=False)

    # Allow the new CAMPAIGN channel-post kind.
    op.drop_constraint(op.f("ck_channel_posts_channelpostkind"), "channel_posts", type_="check")
    op.create_check_constraint(op.f("ck_channel_posts_channelpostkind"), "channel_posts", _kind_in(*_KINDS, "CAMPAIGN"))


def downgrade() -> None:
    op.drop_constraint(op.f("ck_channel_posts_channelpostkind"), "channel_posts", type_="check")
    op.execute("DELETE FROM channel_posts WHERE kind = 'CAMPAIGN'")
    op.create_check_constraint(op.f("ck_channel_posts_channelpostkind"), "channel_posts", _kind_in(*_KINDS))
    op.drop_index("ix_campaign_participants_campaign_id", table_name="campaign_participants")
    op.drop_table("campaign_participants")
