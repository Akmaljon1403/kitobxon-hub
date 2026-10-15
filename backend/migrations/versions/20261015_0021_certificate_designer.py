"""certificate designer: admin-built templates with positioned elements

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-15 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0021'
down_revision: str | Sequence[str] | None = '0020'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'certificate_templates',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('background_key', sa.String(length=512), nullable=True),
        sa.Column('bg_width', sa.Integer(), server_default='1754', nullable=False),
        sa.Column('bg_height', sa.Integer(), server_default='1240', nullable=False),
        sa.Column('elements', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_certificate_templates_default',
        'certificate_templates',
        ['is_default'],
        unique=True,
        postgresql_where=sa.text('is_default AND deleted_at IS NULL'),
    )
    for table in ('certificates', 'tests', 'events'):
        column = 'template_id' if table == 'certificates' else 'certificate_template_id'
        op.add_column(table, sa.Column(column, sa.Uuid(), nullable=True))
        op.create_foreign_key(
            f'fk_{table}_{column}_certificate_templates',
            table,
            'certificate_templates',
            [column],
            ['id'],
            ondelete='SET NULL',
        )

    # A test can now give a completion certificate to every member who passed it.
    op.add_column('tests', sa.Column('certificate_on_pass', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    # Allow the new COMPLETION certificate kind (the kind column is a VARCHAR + CHECK constraint).
    op.drop_constraint(op.f('ck_certificates_certificatekind'), 'certificates', type_='check')
    op.create_check_constraint(
        op.f('ck_certificates_certificatekind'),
        'certificates',
        "kind IN ('TEST_PLACE', 'MONTHLY_TOP', 'MANUAL', 'COMPLETION')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_certificates_certificatekind'), 'certificates', type_='check')
    op.execute("DELETE FROM certificates WHERE kind = 'COMPLETION'")
    op.create_check_constraint(
        op.f('ck_certificates_certificatekind'),
        'certificates',
        "kind IN ('TEST_PLACE', 'MONTHLY_TOP', 'MANUAL')",
    )
    op.drop_column('tests', 'certificate_on_pass')
    for table in ('events', 'tests', 'certificates'):
        column = 'template_id' if table == 'certificates' else 'certificate_template_id'
        op.drop_constraint(f'fk_{table}_{column}_certificate_templates', table, type_='foreignkey')
        op.drop_column(table, column)
    op.drop_index('uq_certificate_templates_default', table_name='certificate_templates')
    op.drop_table('certificate_templates')
