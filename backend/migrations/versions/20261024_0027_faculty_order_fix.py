"""Correct the faculty order (owner's fix to Q14)

The club owner corrected the canonical faculty order. It is now, everywhere a
faculty list appears (registration, rankings, analytics, reports):

  1. Tibbiy profilaktika va jamoat salomatligi
  2. Davolash ishi
  3. Pediatriya
  4. Xalqaro fakultet

Any other faculty an administrator adds comes after these four. This supersedes
migration 0025, which had a different order. As before, admins may rename, reorder
or deactivate faculties in the Admin Panel; a faculty already renamed is left as is.

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | Sequence[str] | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (name, sort_order) in the owner's corrected order.
ORDER = (
    ("Tibbiy profilaktika va jamoat salomatligi", 1),
    ("Davolash ishi", 2),
    ("Pediatriya", 3),
    ("Xalqaro fakultet", 4),
)
CANONICAL_NAMES = tuple(name for name, _ in ORDER)


def upgrade() -> None:
    # Set the canonical order by exact name; a faculty an admin already renamed is left as is.
    for name, sort_order in ORDER:
        op.execute(
            sa.text("UPDATE faculties SET sort_order = :sort_order WHERE name = :name").bindparams(
                name=name, sort_order=sort_order
            )
        )
    # Any other faculty that still sits in the canonical range (e.g. a fresh install's default 0)
    # is pushed after the four, so "others come after" holds. A faculty an admin deliberately placed
    # at 5 or later keeps its place.
    op.execute(
        sa.text(
            "UPDATE faculties SET sort_order = 100 WHERE name NOT IN :names AND sort_order < 5"
        ).bindparams(sa.bindparam("names", value=CANONICAL_NAMES, expanding=True))
    )


def downgrade() -> None:
    # Restore migration 0025's order.
    previous = (
        ("Davolash ishi", 1),
        ("Pediatriya", 2),
        ("Xalqaro fakultet", 3),
        ("Tibbiy profilaktika va jamoat salomatligi", 4),
    )
    for name, sort_order in previous:
        op.execute(
            sa.text("UPDATE faculties SET sort_order = :sort_order WHERE name = :name").bindparams(
                name=name, sort_order=sort_order
            )
        )
