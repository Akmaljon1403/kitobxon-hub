"""Faculties of Farg'ona jamoat salomatligi tibbiyot instituti

Initial faculty list provided by the club owner. Administrators can rename, reorder or
deactivate faculties later in the Admin Panel; this migration only inserts missing rows.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FACULTIES = (
    ("Davolash ishi", 1),
    ("Pediatriya", 2),
    ("Tibbiy profilaktika va jamoat salomatligi", 3),
)


def upgrade() -> None:
    for name, sort_order in FACULTIES:
        op.execute(
            sa.text(
                "INSERT INTO faculties (name, sort_order) VALUES (:name, :sort_order) ON CONFLICT (name) DO NOTHING"
            ).bindparams(name=name, sort_order=sort_order)
        )


def downgrade() -> None:
    for name, _ in FACULTIES:
        op.execute(
            sa.text(
                "DELETE FROM faculties f WHERE f.name = :name "
                "AND NOT EXISTS (SELECT 1 FROM users u WHERE u.faculty_id = f.id)"
            ).bindparams(name=name)
        )
