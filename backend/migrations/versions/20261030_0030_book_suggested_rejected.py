"""Members can suggest books — add the SUGGESTED and REJECTED statuses

A member proposes a book from the Mini App; it is stored as a ``books`` row with
status ``SUGGESTED`` (created_by = the member). An admin then publishes it (→ ACTIVE)
or rejects it (→ REJECTED). SUGGESTED and REJECTED books are never shown in the member
catalogue. The ``books.status`` column is VARCHAR + CHECK, so this only widens the
CHECK constraint to allow the two new values. No existing row changes.

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0030"
down_revision: str | Sequence[str] | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Raw SQL with the real constraint name: op.drop_constraint would re-apply the
# metadata naming convention and mangle this already-conventional name.
_CONSTRAINT = "ck_books_bookstatus"
_ALL = "'SUGGESTED', 'DRAFT', 'ACTIVE', 'COMPLETED', 'ARCHIVED', 'REJECTED'"
_OLD = "'DRAFT', 'ACTIVE', 'COMPLETED', 'ARCHIVED'"


def upgrade() -> None:
    op.execute(f"ALTER TABLE books DROP CONSTRAINT {_CONSTRAINT}")
    op.execute(f"ALTER TABLE books ADD CONSTRAINT {_CONSTRAINT} CHECK (status IN ({_ALL}))")


def downgrade() -> None:
    # A SUGGESTED/REJECTED book would violate the narrower constraint; fold them into DRAFT first.
    op.execute("UPDATE books SET status = 'DRAFT' WHERE status IN ('SUGGESTED', 'REJECTED')")
    op.execute(f"ALTER TABLE books DROP CONSTRAINT {_CONSTRAINT}")
    op.execute(f"ALTER TABLE books ADD CONSTRAINT {_CONSTRAINT} CHECK (status IN ({_OLD}))")
