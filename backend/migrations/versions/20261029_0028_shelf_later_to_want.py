"""Move «Keyinroq» (LATER) shelf items into «O'qimoqchiman» (WANT)

«Javonim» now has three sections only: O'qimoqchiman (WANT), O'qiyapman (READING)
and O'qib bo'ldim (FINISHED). The old «Keyinroq» (LATER) section is removed from
every interface. Its books are not deleted — they are moved to «O'qimoqchiman»,
the closest meaning («plan to read»), so no reader loses a book.

This is a data-only migration. The ``LATER`` value stays in the status CHECK
constraint (the column is VARCHAR + CHECK, so leaving the value costs nothing and
keeps any row written during a rolling deploy valid); it is simply never produced
by any interface again. A later migration may drop it from the constraint once the
owner confirms no row uses it.

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | Sequence[str] | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent: moves every «Keyinroq» book to «O'qimoqchiman». Re-running is a no-op.
    op.execute(sa.text("UPDATE shelf_items SET status = 'WANT' WHERE status = 'LATER'"))


def downgrade() -> None:
    # «Keyinroq» and «O'qimoqchiman» are indistinguishable once merged, so this cannot be
    # reversed without data loss. Left as a no-op on purpose.
    pass
