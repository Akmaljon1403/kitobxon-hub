"""Faculty order and the international faculty (owner's Q14)

The club owner set the canonical faculty order:
  1. Davolash ishi
  2. Pediatriya
  3. Xalqaro fakultet   (added here if missing)
  4. Tibbiy profilaktika va jamoat salomatligi

Administrators can still rename, reorder or deactivate faculties in the Admin Panel
(Sozlamalar → Fakultetlar); this migration only sets the default order and inserts the
international faculty if it is not there yet. A renamed faculty is left untouched.

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (name, sort_order) in the owner's order.
ORDER = (
    ("Davolash ishi", 1),
    ("Pediatriya", 2),
    ("Xalqaro fakultet", 3),
    ("Tibbiy profilaktika va jamoat salomatligi", 4),
)


def upgrade() -> None:
    # Add the international faculty if it is missing (admins may rename it later).
    op.execute(
        sa.text(
            "INSERT INTO faculties (name, sort_order) VALUES (:name, :sort_order) ON CONFLICT (name) DO NOTHING"
        ).bindparams(name="Xalqaro fakultet", sort_order=3)
    )
    # Set the canonical order by exact name; a faculty an admin already renamed is left as is.
    for name, sort_order in ORDER:
        op.execute(
            sa.text("UPDATE faculties SET sort_order = :sort_order WHERE name = :name").bindparams(
                name=name, sort_order=sort_order
            )
        )


def downgrade() -> None:
    # Only remove the international faculty, and only when no member is attached to it.
    op.execute(
        sa.text(
            "DELETE FROM faculties f WHERE f.name = :name "
            "AND NOT EXISTS (SELECT 1 FROM users u WHERE u.faculty_id = f.id)"
        ).bindparams(name="Xalqaro fakultet")
    )
