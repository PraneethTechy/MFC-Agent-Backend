"""create_investigation_reports_table

Revision ID: 89f2a7b8c0e1
Revises: 54a1be1972dd
Create Date: 2026-11-12 14:55:00.000000+00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89f2a7b8c0e1'
down_revision: Union[str, None] = '54a1be1972dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'investigation_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('report_id', sa.String(length=64), nullable=False),
        sa.Column('inspection_id', sa.String(length=64), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='COMPLETED', nullable=False),
        sa.Column('data_origin', sa.String(length=30), server_default='REAL', nullable=False),
        sa.Column('uploaded_files', sa.JSON(), nullable=False),
        sa.Column('dataset_types', sa.JSON(), nullable=False),
        sa.Column('source_batch_id', sa.String(length=64), nullable=True),
        sa.Column('data_scope', sa.JSON(), nullable=False),
        sa.Column('executive_summary', sa.Text(), nullable=True),
        sa.Column('findings', sa.JSON(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('report_json', sa.JSON(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('report_id')
    )
    op.create_index(op.f('ix_investigation_reports_report_id'), 'investigation_reports', ['report_id'], unique=True)
    op.create_index(op.f('ix_investigation_reports_inspection_id'), 'investigation_reports', ['inspection_id'], unique=False)
    op.create_index(op.f('ix_investigation_reports_source_batch_id'), 'investigation_reports', ['source_batch_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_investigation_reports_source_batch_id'), table_name='investigation_reports')
    op.drop_index(op.f('ix_investigation_reports_inspection_id'), table_name='investigation_reports')
    op.drop_index(op.f('ix_investigation_reports_report_id'), table_name='investigation_reports')
    op.drop_table('investigation_reports')

