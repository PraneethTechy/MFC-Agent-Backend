"""add_seven_dataset_architecture_tables

Revision ID: c4b1a89f30e2
Revises: 89f2a7b8c0e1
Create Date: 2026-11-14 22:30:00.000000+00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4b1a89f30e2'
down_revision: Union[str, None] = '89f2a7b8c0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. Staging table for material purchases
    if 'stg_material_purchases' not in existing_tables:
        op.create_table(
            'stg_material_purchases',
            sa.Column('staging_id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('ingestion_batch_id', sa.String(length=36), nullable=False),
            sa.Column('file_checksum_sha256', sa.String(length=64), nullable=False),
            sa.Column('source_row_number', sa.Integer(), nullable=False),
            sa.Column('purchase_record_id', sa.String(length=50), nullable=True),
            sa.Column('purchase_order_id', sa.String(length=50), nullable=True),
            sa.Column('goods_receipt_id', sa.String(length=50), nullable=True),
            sa.Column('receipt_date', sa.Date(), nullable=True),
            sa.Column('supplier_id', sa.String(length=50), nullable=True),
            sa.Column('supplier_name', sa.String(length=255), nullable=True),
            sa.Column('component_id', sa.String(length=50), nullable=True),
            sa.Column('material_lot_id', sa.String(length=50), nullable=True),
            sa.Column('received_quantity', sa.Numeric(precision=14, scale=4), nullable=True),
            sa.Column('rejected_quantity', sa.Numeric(precision=14, scale=4), nullable=True),
            sa.Column('accepted_quantity', sa.Numeric(precision=14, scale=4), nullable=True),
            sa.Column('reference_unit_price', sa.Numeric(precision=16, scale=4), nullable=True),
            sa.Column('purchase_unit_price', sa.Numeric(precision=16, scale=4), nullable=True),
            sa.Column('duty_cost', sa.Numeric(precision=16, scale=4), nullable=True),
            sa.Column('freight_cost', sa.Numeric(precision=16, scale=4), nullable=True),
            sa.Column('landed_unit_cost', sa.Numeric(precision=16, scale=4), nullable=True),
            sa.Column('currency', sa.String(length=10), server_default='INR', nullable=True),
            sa.Column('data_origin', sa.String(length=30), server_default='REAL', nullable=True),
            sa.Column('validation_status', sa.String(length=50), server_default='PENDING', nullable=False),
            sa.Column('validation_error', sa.Text(), nullable=True),
            sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['ingestion_batch_id'], ['import_batches.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('staging_id')
        )
        op.create_index(op.f('ix_stg_material_purchases_ingestion_batch_id'), 'stg_material_purchases', ['ingestion_batch_id'], unique=False)

    # 2. Staging table for material consumption
    if 'stg_material_consumption' not in existing_tables:
        op.create_table(
            'stg_material_consumption',
            sa.Column('staging_id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('ingestion_batch_id', sa.String(length=36), nullable=False),
            sa.Column('file_checksum_sha256', sa.String(length=64), nullable=False),
            sa.Column('source_row_number', sa.Integer(), nullable=False),
            sa.Column('consumption_record_id', sa.String(length=50), nullable=True),
            sa.Column('production_order_id', sa.String(length=50), nullable=True),
            sa.Column('cost_record_id', sa.String(length=50), nullable=True),
            sa.Column('production_date', sa.Date(), nullable=True),
            sa.Column('plant_id', sa.String(length=50), nullable=True),
            sa.Column('line_id', sa.String(length=50), nullable=True),
            sa.Column('product_id', sa.String(length=50), nullable=True),
            sa.Column('component_id', sa.String(length=50), nullable=True),
            sa.Column('bom_record_id', sa.String(length=50), nullable=True),
            sa.Column('material_lot_id', sa.String(length=50), nullable=True),
            sa.Column('goods_receipt_id', sa.String(length=50), nullable=True),
            sa.Column('issued_quantity', sa.Numeric(precision=14, scale=4), nullable=True),
            sa.Column('returned_quantity', sa.Numeric(precision=14, scale=4), server_default='0.0000', nullable=True),
            sa.Column('net_consumed_quantity', sa.Numeric(precision=14, scale=4), nullable=True),
            sa.Column('bom_allowed_quantity', sa.Numeric(precision=14, scale=4), nullable=True),
            sa.Column('scrap_quantity', sa.Numeric(precision=14, scale=4), server_default='0.0000', nullable=True),
            sa.Column('unit_of_measure', sa.String(length=20), server_default='PCS', nullable=True),
            sa.Column('landed_unit_cost', sa.Numeric(precision=16, scale=4), nullable=True),
            sa.Column('consumed_value_inr', sa.Numeric(precision=18, scale=4), nullable=True),
            sa.Column('data_origin', sa.String(length=30), server_default='REAL', nullable=True),
            sa.Column('validation_status', sa.String(length=50), server_default='PENDING', nullable=False),
            sa.Column('validation_error', sa.Text(), nullable=True),
            sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['ingestion_batch_id'], ['import_batches.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('staging_id')
        )
        op.create_index(op.f('ix_stg_material_consumption_ingestion_batch_id'), 'stg_material_consumption', ['ingestion_batch_id'], unique=False)

    # 3. Staging table for quality rework events
    if 'stg_quality_rework_events' not in existing_tables:
        op.create_table(
            'stg_quality_rework_events',
            sa.Column('staging_id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('ingestion_batch_id', sa.String(length=36), nullable=False),
            sa.Column('file_checksum_sha256', sa.String(length=64), nullable=False),
            sa.Column('source_row_number', sa.Integer(), nullable=False),
            sa.Column('rework_event_id', sa.String(length=50), nullable=True),
            sa.Column('inspection_id', sa.String(length=50), nullable=True),
            sa.Column('production_order_id', sa.String(length=50), nullable=True),
            sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=True),
            sa.Column('event_date', sa.Date(), nullable=True),
            sa.Column('plant_id', sa.String(length=50), nullable=True),
            sa.Column('line_id', sa.String(length=50), nullable=True),
            sa.Column('product_id', sa.String(length=50), nullable=True),
            sa.Column('defect_code', sa.String(length=50), nullable=True),
            sa.Column('rework_type', sa.String(length=50), nullable=True),
            sa.Column('rework_quantity', sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column('scrap_quantity', sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column('rework_hours', sa.Numeric(precision=10, scale=2), nullable=True),
            sa.Column('labour_cost', sa.Numeric(precision=16, scale=4), nullable=True),
            sa.Column('material_cost', sa.Numeric(precision=16, scale=4), nullable=True),
            sa.Column('scrap_cost', sa.Numeric(precision=16, scale=4), nullable=True),
            sa.Column('total_rework_cost', sa.Numeric(precision=18, scale=4), nullable=True),
            sa.Column('disposition', sa.String(length=50), nullable=True),
            sa.Column('data_origin', sa.String(length=30), server_default='REAL', nullable=True),
            sa.Column('validation_status', sa.String(length=50), server_default='PENDING', nullable=False),
            sa.Column('validation_error', sa.Text(), nullable=True),
            sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['ingestion_batch_id'], ['import_batches.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('staging_id')
        )
        op.create_index(op.f('ix_stg_quality_rework_events_ingestion_batch_id'), 'stg_quality_rework_events', ['ingestion_batch_id'], unique=False)

    # 4. Operational table: material_purchase_records
    if 'material_purchase_records' not in existing_tables:
        op.create_table(
            'material_purchase_records',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('purchase_record_id', sa.String(length=50), nullable=False),
            sa.Column('purchase_order_id', sa.String(length=50), nullable=False),
            sa.Column('goods_receipt_id', sa.String(length=50), nullable=False),
            sa.Column('receipt_date', sa.Date(), nullable=False),
            sa.Column('supplier_code', sa.String(length=50), nullable=False),
            sa.Column('supplier_name', sa.String(length=255), nullable=False),
            sa.Column('material_code', sa.String(length=50), nullable=False),
            sa.Column('material_lot_id', sa.String(length=50), nullable=True),
            sa.Column('received_quantity', sa.Numeric(precision=14, scale=4), nullable=False),
            sa.Column('rejected_quantity', sa.Numeric(precision=14, scale=4), server_default='0.0000', nullable=False),
            sa.Column('accepted_quantity', sa.Numeric(precision=14, scale=4), nullable=False),
            sa.Column('reference_unit_price', sa.Numeric(precision=16, scale=4), nullable=False),
            sa.Column('purchase_unit_price', sa.Numeric(precision=16, scale=4), nullable=False),
            sa.Column('duty_cost', sa.Numeric(precision=16, scale=4), server_default='0.0000', nullable=False),
            sa.Column('freight_cost', sa.Numeric(precision=16, scale=4), server_default='0.0000', nullable=False),
            sa.Column('landed_unit_cost', sa.Numeric(precision=16, scale=4), nullable=False),
            sa.Column('currency', sa.String(length=10), server_default='INR', nullable=False),
            sa.Column('ingestion_batch_id', sa.String(length=36), nullable=False),
            sa.Column('data_origin', sa.String(length=30), server_default='REAL', nullable=False),
            sa.Column('is_synthetic', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('is_current', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('version_num', sa.Integer(), server_default='1', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['ingestion_batch_id'], ['import_batches.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('purchase_record_id')
        )
        op.create_index(op.f('ix_material_purchase_records_purchase_record_id'), 'material_purchase_records', ['purchase_record_id'], unique=True)
        op.create_index(op.f('ix_material_purchase_records_purchase_order_id'), 'material_purchase_records', ['purchase_order_id'], unique=False)
        op.create_index(op.f('ix_material_purchase_records_goods_receipt_id'), 'material_purchase_records', ['goods_receipt_id'], unique=False)
        op.create_index(op.f('ix_material_purchase_records_receipt_date'), 'material_purchase_records', ['receipt_date'], unique=False)
        op.create_index(op.f('ix_material_purchase_records_supplier_code'), 'material_purchase_records', ['supplier_code'], unique=False)
        op.create_index(op.f('ix_material_purchase_records_material_code'), 'material_purchase_records', ['material_code'], unique=False)
        op.create_index(op.f('ix_material_purchase_records_is_synthetic'), 'material_purchase_records', ['is_synthetic'], unique=False)
        op.create_index(op.f('ix_material_purchase_records_is_current'), 'material_purchase_records', ['is_current'], unique=False)
        op.create_index('idx_mat_purch_lookup', 'material_purchase_records', ['material_code', 'receipt_date'], unique=False)
        op.create_index('idx_mat_purch_supplier', 'material_purchase_records', ['supplier_code', 'receipt_date'], unique=False)

    # 5. Operational table: material_consumption_records
    if 'material_consumption_records' not in existing_tables:
        op.create_table(
            'material_consumption_records',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('consumption_record_id', sa.String(length=50), nullable=False),
            sa.Column('production_order_id', sa.String(length=50), nullable=False),
            sa.Column('cost_record_id', sa.String(length=50), nullable=False),
            sa.Column('production_date', sa.Date(), nullable=False),
            sa.Column('plant_code', sa.String(length=50), nullable=False),
            sa.Column('line_code', sa.String(length=50), nullable=False),
            sa.Column('product_code', sa.String(length=50), nullable=False),
            sa.Column('material_code', sa.String(length=50), nullable=False),
            sa.Column('bom_id', sa.String(length=50), nullable=False),
            sa.Column('material_lot_id', sa.String(length=50), nullable=True),
            sa.Column('goods_receipt_id', sa.String(length=50), nullable=True),
            sa.Column('issued_quantity', sa.Numeric(precision=14, scale=4), nullable=False),
            sa.Column('returned_quantity', sa.Numeric(precision=14, scale=4), server_default='0.0000', nullable=False),
            sa.Column('net_consumed_quantity', sa.Numeric(precision=14, scale=4), nullable=False),
            sa.Column('bom_allowed_quantity', sa.Numeric(precision=14, scale=4), nullable=False),
            sa.Column('scrap_quantity', sa.Numeric(precision=14, scale=4), server_default='0.0000', nullable=False),
            sa.Column('unit_of_measure', sa.String(length=20), server_default='PCS', nullable=False),
            sa.Column('landed_unit_cost', sa.Numeric(precision=16, scale=4), nullable=False),
            sa.Column('consumed_value_inr', sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column('currency', sa.String(length=10), server_default='INR', nullable=False),
            sa.Column('ingestion_batch_id', sa.String(length=36), nullable=False),
            sa.Column('data_origin', sa.String(length=30), server_default='REAL', nullable=False),
            sa.Column('is_synthetic', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('is_current', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('version_num', sa.Integer(), server_default='1', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['ingestion_batch_id'], ['import_batches.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('consumption_record_id')
        )
        op.create_index(op.f('ix_material_consumption_records_consumption_record_id'), 'material_consumption_records', ['consumption_record_id'], unique=True)
        op.create_index(op.f('ix_material_consumption_records_production_order_id'), 'material_consumption_records', ['production_order_id'], unique=False)
        op.create_index(op.f('ix_material_consumption_records_cost_record_id'), 'material_consumption_records', ['cost_record_id'], unique=False)
        op.create_index(op.f('ix_material_consumption_records_production_date'), 'material_consumption_records', ['production_date'], unique=False)
        op.create_index(op.f('ix_material_consumption_records_plant_code'), 'material_consumption_records', ['plant_code'], unique=False)
        op.create_index(op.f('ix_material_consumption_records_line_code'), 'material_consumption_records', ['line_code'], unique=False)
        op.create_index(op.f('ix_material_consumption_records_product_code'), 'material_consumption_records', ['product_code'], unique=False)
        op.create_index(op.f('ix_material_consumption_records_material_code'), 'material_consumption_records', ['material_code'], unique=False)
        op.create_index(op.f('ix_material_consumption_records_bom_id'), 'material_consumption_records', ['bom_id'], unique=False)
        op.create_index(op.f('ix_material_consumption_records_is_synthetic'), 'material_consumption_records', ['is_synthetic'], unique=False)
        op.create_index(op.f('ix_material_consumption_records_is_current'), 'material_consumption_records', ['is_current'], unique=False)
        op.create_index('idx_mat_cons_cost_batch', 'material_consumption_records', ['cost_record_id'], unique=False)
        op.create_index('idx_mat_cons_material', 'material_consumption_records', ['material_code', 'production_date'], unique=False)

    # 6. Operational table: quality_rework_event_records
    if 'quality_rework_event_records' not in existing_tables:
        op.create_table(
            'quality_rework_event_records',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('rework_event_id', sa.String(length=50), nullable=False),
            sa.Column('inspection_id', sa.String(length=50), nullable=True),
            sa.Column('production_order_id', sa.String(length=50), nullable=False),
            sa.Column('event_timestamp', sa.DateTime(timezone=True), nullable=False),
            sa.Column('event_date', sa.Date(), nullable=False),
            sa.Column('plant_code', sa.String(length=50), nullable=False),
            sa.Column('line_code', sa.String(length=50), nullable=False),
            sa.Column('product_code', sa.String(length=50), nullable=False),
            sa.Column('defect_code', sa.String(length=50), nullable=False),
            sa.Column('rework_type', sa.String(length=50), nullable=False),
            sa.Column('rework_quantity', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('scrap_quantity', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
            sa.Column('rework_hours', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('labour_cost', sa.Numeric(precision=16, scale=4), nullable=False),
            sa.Column('material_cost', sa.Numeric(precision=16, scale=4), nullable=False),
            sa.Column('scrap_cost', sa.Numeric(precision=16, scale=4), nullable=False),
            sa.Column('total_rework_cost', sa.Numeric(precision=18, scale=4), nullable=False),
            sa.Column('disposition', sa.String(length=50), nullable=False),
            sa.Column('currency', sa.String(length=10), server_default='INR', nullable=False),
            sa.Column('ingestion_batch_id', sa.String(length=36), nullable=False),
            sa.Column('data_origin', sa.String(length=30), server_default='REAL', nullable=False),
            sa.Column('is_synthetic', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('is_current', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('version_num', sa.Integer(), server_default='1', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['ingestion_batch_id'], ['import_batches.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('rework_event_id')
        )
        op.create_index(op.f('ix_quality_rework_event_records_rework_event_id'), 'quality_rework_event_records', ['rework_event_id'], unique=True)
        op.create_index(op.f('ix_quality_rework_event_records_inspection_id'), 'quality_rework_event_records', ['inspection_id'], unique=False)
        op.create_index(op.f('ix_quality_rework_event_records_production_order_id'), 'quality_rework_event_records', ['production_order_id'], unique=False)
        op.create_index(op.f('ix_quality_rework_event_records_event_timestamp'), 'quality_rework_event_records', ['event_timestamp'], unique=False)
        op.create_index(op.f('ix_quality_rework_event_records_event_date'), 'quality_rework_event_records', ['event_date'], unique=False)
        op.create_index(op.f('ix_quality_rework_event_records_plant_code'), 'quality_rework_event_records', ['plant_code'], unique=False)
        op.create_index(op.f('ix_quality_rework_event_records_line_code'), 'quality_rework_event_records', ['line_code'], unique=False)
        op.create_index(op.f('ix_quality_rework_event_records_product_code'), 'quality_rework_event_records', ['product_code'], unique=False)
        op.create_index(op.f('ix_quality_rework_event_records_defect_code'), 'quality_rework_event_records', ['defect_code'], unique=False)
        op.create_index(op.f('ix_quality_rework_event_records_is_synthetic'), 'quality_rework_event_records', ['is_synthetic'], unique=False)
        op.create_index(op.f('ix_quality_rework_event_records_is_current'), 'quality_rework_event_records', ['is_current'], unique=False)
        op.create_index('idx_rework_order', 'quality_rework_event_records', ['production_order_id'], unique=False)
        op.create_index('idx_rework_defect', 'quality_rework_event_records', ['defect_code', 'event_date'], unique=False)

    # 7. Immutable audit history table: fact_record_history (Strategy C)
    if 'fact_record_history' not in existing_tables:
        op.create_table(
            'fact_record_history',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('entity_type', sa.String(length=50), nullable=False),
            sa.Column('record_identifier', sa.String(length=100), nullable=False),
            sa.Column('superseded_batch_id', sa.String(length=36), nullable=False),
            sa.Column('superseding_batch_id', sa.String(length=36), nullable=False),
            sa.Column('version_num', sa.Integer(), nullable=False),
            sa.Column('approved_by', sa.String(length=255), nullable=False),
            sa.Column('correction_reason', sa.Text(), nullable=False),
            sa.Column('prior_record_state', sa.JSON(), nullable=False),
            sa.Column('superseded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_fact_record_history_entity_type'), 'fact_record_history', ['entity_type'], unique=False)
        op.create_index(op.f('ix_fact_record_history_record_identifier'), 'fact_record_history', ['record_identifier'], unique=False)
        op.create_index(op.f('ix_fact_record_history_superseded_batch_id'), 'fact_record_history', ['superseded_batch_id'], unique=False)
        op.create_index(op.f('ix_fact_record_history_superseding_batch_id'), 'fact_record_history', ['superseding_batch_id'], unique=False)
        op.create_index(op.f('ix_fact_record_history_superseded_at'), 'fact_record_history', ['superseded_at'], unique=False)
        op.create_index('idx_history_lookup', 'fact_record_history', ['entity_type', 'record_identifier'], unique=False)

    # 8. Add is_current and version_num to existing 4 operational fact tables if missing
    for table_name in ['line_cost_batches', 'hourly_production_logs', 'serialized_quality_inspections', 'bom_component_records']:
        if table_name in existing_tables:
            cols = {c['name'] for c in insp.get_columns(table_name)}
            if 'is_current' not in cols:
                op.add_column(table_name, sa.Column('is_current', sa.Boolean(), server_default='true', nullable=False))
                op.create_index(f'ix_{table_name}_is_current', table_name, ['is_current'], unique=False)
            if 'version_num' not in cols:
                op.add_column(table_name, sa.Column('version_num', sa.Integer(), server_default='1', nullable=False))


def downgrade() -> None:
    pass
