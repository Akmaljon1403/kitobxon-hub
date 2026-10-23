"""Test kind: «Tadbir» (event) vs «Doimiy» (permanent) — owner's Q13

Every existing test is an event test (EVENT); permanent tests are a new, always-open kind
with unlimited attempts that award points only for the first perfect result.

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | Sequence[str] | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tests", sa.Column("kind", sa.String(length=32), nullable=False, server_default="EVENT"))
    op.create_check_constraint("tests_kind_valid", "tests", "kind IN ('EVENT', 'PERMANENT')")


def downgrade() -> None:
    op.drop_constraint("tests_kind_valid", "tests", type_="check")
    op.drop_column("tests", "kind")
