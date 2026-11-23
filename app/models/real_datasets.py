"""
Manufacturing Cost Agent - Real Dataset & Ingestion Models
Defines file registry, staging tables, and operational target tables
for the four real manufacturing datasets:
1. fact_manufacturing_cost.csv (5,000 records)
2. fact_hourly_production.csv (8,832 records)
3. fact_quality_inspection.csv (16,000 records)
4. fact_bom_component.csv (48 records)
"""

import datetime as dt
import uuid
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Index,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class IngestionFileRegistry(Base, TimestampMixin):
    """
    Authoritative registry of all ingested manufacturing CSV/XLSX source files.
    Enforces SHA-256 idempotency and duplicate detection.
    """
    __tablename__ = "ingestion_file_registry"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_checksum_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    total_rows_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True,
    )  # PENDING, STAGED, VALIDATED, PROMOTED, FAILED
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    promoted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# =============================================================================
# Staging Tables (Raw bulk import targets before validation and promotion)
# =============================================================================

class StgManufacturingCost(Base):
    """Staging table for fact_manufacturing_cost.csv."""
    __tablename__ = "stg_manufacturing_cost"

    staging_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    cost_record_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    posting_ts: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    line_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    production_order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    produced_qty: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    material_cost_inr: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    labour_cost_inr: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    machine_cost_inr: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    energy_cost_inr: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    scrap_rework_cost_inr: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    source_standard_cost_per_unit: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    costing_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    validation_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )


class StgHourlyProduction(Base):
    """Staging table for fact_hourly_production.csv."""
    __tablename__ = "stg_hourly_production"

    staging_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    event_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_ts: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    line_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shift_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    production_order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_qty: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    actual_qty: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    good_qty: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    reject_qty: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    rework_qty: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    downtime_min: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    downtime_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operator_team: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_system: Mapped[str | None] = mapped_column(String(50), nullable=True)
    data_quality: Mapped[str | None] = mapped_column(String(50), nullable=True)

    validation_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )


class StgQualityInspection(Base):
    """Staging table for fact_quality_inspection.csv."""
    __tablename__ = "stg_quality_inspection"

    staging_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    inspection_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inspection_ts: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    line_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    station_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    production_order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inspection_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    defect_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    measurement_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    spec_min: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    spec_max: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    inspector_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    spec_revision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_system: Mapped[str | None] = mapped_column(String(50), nullable=True)

    validation_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )


class StgBomComponent(Base):
    """Staging table for fact_bom_component.csv."""
    __tablename__ = "stg_bom_component"

    staging_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    bom_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    material_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    component_qty: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    scrap_factor: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    revision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    effective_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    validation_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )


# =============================================================================
# Operational Target Tables (Final promoted business facts)
# =============================================================================

class LineCostBatch(Base, TimestampMixin):
    """
    Direct hourly manufacturing cost facts from fact_manufacturing_cost.csv.
    Reconciles exactly to INR 14,024,712,024.30 across 5,000 records.
    """
    __tablename__ = "line_cost_batches"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    cost_record_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    posting_ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    plant_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    line_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    production_order_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    produced_qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    material_cost_inr: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    labour_cost_inr: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    machine_cost_inr: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    energy_cost_inr: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    scrap_rework_cost_inr: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    total_direct_cost_inr: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)

    source_standard_cost_per_unit: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    standard_cost_status: Mapped[str] = mapped_column(
        String(50),
        default="UNVERIFIED_STANDARD",
        nullable=False,
    )
    costing_version: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id"),
        nullable=False,
        index=True,
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version_num: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("idx_line_cost_lookup", "plant_code", "line_code", "posting_ts"),
    )


class HourlyProductionLog(Base, TimestampMixin):
    """
    Complete hourly production logs from fact_hourly_production.csv (8,832 records).
    Preserves all operational runs with explicit costing status.
    """
    __tablename__ = "hourly_production_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    event_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    event_ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    plant_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    line_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    shift_id: Mapped[str] = mapped_column(String(50), nullable=False)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    production_order_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    target_qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    actual_qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    good_qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    reject_qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    rework_qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    downtime_min: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)
    downtime_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operator_team: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_system: Mapped[str] = mapped_column(String(50), default="MES", nullable=False)
    data_quality: Mapped[str] = mapped_column(String(50), default="VALID", nullable=False)

    costing_status: Mapped[str] = mapped_column(
        String(50),
        default="UNCOSTED_OPERATIONAL_RUN",
        nullable=False,
        index=True,
    )  # DIRECT_COSTED (5,000 rows) or UNCOSTED_OPERATIONAL_RUN (3,832 rows)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id"),
        nullable=False,
        index=True,
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version_num: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("idx_hourly_prod_lookup", "plant_code", "line_code", "event_ts"),
    )


class SerializedQualityInspection(Base, TimestampMixin):
    """
    Granular serialized quality inspection records from fact_quality_inspection.csv (16,000 records).
    Preserves defect codes, serial numbers, and dispositions without unsafe cost joins.
    """
    __tablename__ = "serialized_quality_inspections"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    inspection_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    inspection_ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    plant_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    line_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    station_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    production_order_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    inspection_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    defect_code: Mapped[str] = mapped_column(String(50), default="NONE", nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)  # PASS or FAIL
    severity: Mapped[str] = mapped_column(String(50), default="NONE", nullable=False)
    measurement_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    spec_min: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    spec_max: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    inspector_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    disposition: Mapped[str] = mapped_column(String(50), nullable=False)  # RELEASE, REWORK, HOLD, SCRAP
    spec_revision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_system: Mapped[str] = mapped_column(String(50), default="QMS", nullable=False)

    lineage_status: Mapped[str] = mapped_column(
        String(50),
        default="UNRESOLVED_LINEAGE",
        nullable=False,
    )
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id"),
        nullable=False,
        index=True,
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version_num: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class BomComponentRecord(Base, TimestampMixin):
    """
    Standard Bill of Materials component lines from fact_bom_component.csv (48 records).
    """
    __tablename__ = "bom_component_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    bom_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    material_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    component_qty: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    scrap_factor: Mapped[float] = mapped_column(Numeric(8, 4), default=0.0000, nullable=False)
    revision: Mapped[str] = mapped_column(String(50), default="REV-C", nullable=False)
    effective_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id"),
        nullable=False,
        index=True,
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version_num: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("uq_bom_component_line", "bom_id", "material_code", unique=True),
    )


class ProductStandardCost(Base, TimestampMixin):
    """
    Authoritative, versioned standard cost card table requiring explicit finance approval.
    """
    __tablename__ = "product_standard_costs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    product_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    costing_version_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    plant_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    standard_unit_cost: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    effective_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default="UNVERIFIED",
        nullable=False,
    )  # UNVERIFIED, APPROVED, SUPERSEDED
    approval_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# =============================================================================
# Additional Staging Tables for 7-Dataset Architecture
# =============================================================================

class StgMaterialPurchase(Base):
    """Staging table for raw material purchase and goods receipt records."""
    __tablename__ = "stg_material_purchases"

    staging_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    purchase_record_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    purchase_order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    goods_receipt_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    receipt_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    supplier_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    component_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    material_lot_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    received_quantity: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    rejected_quantity: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    accepted_quantity: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    reference_unit_price: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    purchase_unit_price: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    duty_cost: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    freight_cost: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    landed_unit_cost: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), default="INR", nullable=True)
    data_origin: Mapped[str | None] = mapped_column(String(30), default="REAL", nullable=True)

    validation_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )


class StgMaterialConsumption(Base):
    """Staging table for raw material consumption / issue / return records."""
    __tablename__ = "stg_material_consumption"

    staging_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    consumption_record_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    production_order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost_record_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    production_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    line_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    component_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bom_record_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    material_lot_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    goods_receipt_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    issued_quantity: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    returned_quantity: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    net_consumed_quantity: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    bom_allowed_quantity: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    scrap_quantity: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(20), default="PCS", nullable=True)
    landed_unit_cost: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    consumed_value_inr: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    data_origin: Mapped[str | None] = mapped_column(String(30), default="REAL", nullable=True)

    validation_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )


class StgQualityReworkEvent(Base):
    """Staging table for defect rework and remediation records."""
    __tablename__ = "stg_quality_rework_events"

    staging_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    rework_event_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inspection_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    production_order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_timestamp: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    line_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    defect_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rework_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rework_quantity: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    scrap_quantity: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    rework_hours: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    labour_cost: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    material_cost: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    scrap_cost: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    total_rework_cost: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    data_origin: Mapped[str | None] = mapped_column(String(30), default="REAL", nullable=True)

    validation_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )


# =============================================================================
# Additional Operational Target Tables (Final promoted business facts)
# =============================================================================

class MaterialPurchaseRecord(Base, TimestampMixin):
    """
    Authoritative raw material procurement and goods receipt facts.
    """
    __tablename__ = "material_purchase_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    purchase_record_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    purchase_order_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    goods_receipt_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    receipt_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    supplier_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    material_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    material_lot_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    received_quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    rejected_quantity: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)
    accepted_quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    reference_unit_price: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    purchase_unit_price: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    duty_cost: Mapped[float] = mapped_column(Numeric(16, 4), default=0.0000, nullable=False)
    freight_cost: Mapped[float] = mapped_column(Numeric(16, 4), default=0.0000, nullable=False)
    landed_unit_cost: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)

    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id"),
        nullable=False,
        index=True,
    )
    data_origin: Mapped[str] = mapped_column(String(30), default="REAL", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version_num: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("idx_mat_purch_lookup", "material_code", "receipt_date"),
        Index("idx_mat_purch_supplier", "supplier_code", "receipt_date"),
    )


class MaterialConsumptionRecord(Base, TimestampMixin):
    """
    Authoritative raw material consumption and variance facts per production order.
    """
    __tablename__ = "material_consumption_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    consumption_record_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    production_order_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    cost_record_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    production_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    plant_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    line_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    material_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    bom_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    material_lot_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    goods_receipt_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    issued_quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    returned_quantity: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)
    net_consumed_quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    bom_allowed_quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    scrap_quantity: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(20), default="PCS", nullable=False)
    landed_unit_cost: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    consumed_value_inr: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)

    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id"),
        nullable=False,
        index=True,
    )
    data_origin: Mapped[str] = mapped_column(String(30), default="REAL", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version_num: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("idx_mat_cons_cost_batch", "cost_record_id"),
        Index("idx_mat_cons_material", "material_code", "production_date"),
    )


class QualityReworkEventRecord(Base, TimestampMixin):
    """
    Authoritative defect remediation, rework labor, and scrap expenditure facts.
    """
    __tablename__ = "quality_rework_event_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    rework_event_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    inspection_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    production_order_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    plant_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    line_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    defect_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rework_type: Mapped[str] = mapped_column(String(50), nullable=False)

    rework_quantity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    scrap_quantity: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    rework_hours: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    labour_cost: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    material_cost: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    scrap_cost: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    total_rework_cost: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    disposition: Mapped[str] = mapped_column(String(50), nullable=False)

    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    ingestion_batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("import_batches.id"),
        nullable=False,
        index=True,
    )
    data_origin: Mapped[str] = mapped_column(String(30), default="REAL", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version_num: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("idx_rework_order", "production_order_id"),
        Index("idx_rework_defect", "defect_code", "event_date"),
    )


# =============================================================================
# Historical Fact Versioning & Immutable Ledger (Strategy C)
# =============================================================================

class FactRecordHistory(Base, TimestampMixin):
    """
    Immutable audit history table capturing pre-correction snapshots of operational facts.
    Provides complete time-travel auditability without degrading operational fact table join performance.
    """
    __tablename__ = "fact_record_history"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    record_identifier: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    superseded_batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    superseding_batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_num: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(255), nullable=False)
    correction_reason: Mapped[str] = mapped_column(Text, nullable=False)
    prior_record_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    superseded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("idx_history_lookup", "entity_type", "record_identifier"),
    )


