"""Add the «Bu safar bora olmayman» (DECLINED) RSVP answer

Members can now answer a published event in two ways — «✅ Qatnashaman» (REGISTERED)
or «✖️ Bu safar bora olmayman» (DECLINED) — and switch between them until the event
ends; only the last answer counts. DECLINED is a recorded answer, distinct from never
answering (no row) and from CANCELLED (withdrew after registering, kept for history).

The ``event_registrations.status`` column is VARCHAR + CHECK, so this only widens the
CHECK constraint to allow the new value. No existing row changes.

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Raw SQL with the real constraint name: op.drop_constraint would re-apply the
# metadata naming convention and mangle this already-conventional name.
_CONSTRAINT = "ck_event_registrations_registrationstatus"


def upgrade() -> None:
    op.execute(f"ALTER TABLE event_registrations DROP CONSTRAINT {_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE event_registrations ADD CONSTRAINT {_CONSTRAINT} "
        "CHECK (status IN ('REGISTERED', 'DECLINED', 'CANCELLED'))"
    )


def downgrade() -> None:
    # A DECLINED row would violate the narrower constraint, so fold it into CANCELLED first.
    op.execute("UPDATE event_registrations SET status = 'CANCELLED' WHERE status = 'DECLINED'")
    op.execute(f"ALTER TABLE event_registrations DROP CONSTRAINT {_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE event_registrations ADD CONSTRAINT {_CONSTRAINT} "
        "CHECK (status IN ('REGISTERED', 'CANCELLED'))"
    )
