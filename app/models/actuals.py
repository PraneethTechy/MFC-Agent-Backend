import datetime as dt
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class ProductionOrder(Base, TimestampMixin):
    """Manufacturing work order tracking batch completion against plan."""
    __tablename__ = "production_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("calendar_periods.id"), nullable=False, index=True)

    planned_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    actual_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    scrap_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    rework_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="RELEASED", nullable=False)  # RELEASED, IN_PROGRESS, COMPLETED, CLOSED
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    completion_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    outputs = relationship("ProductionOutput", back_populates="production_order", cascade="all, delete-orphan")
    material_postings = relationship("MaterialPosting", back_populates="production_order")
    labour_postings = relationship("LabourPosting", back_populates="production_order")
    quality_events = relationship("QualityEvent", back_populates="production_order")


class ProductionOutput(Base, TimestampMixin):
    """Daily or shift output declaration against an order."""
    __tablename__ = "production_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    production_order_id: Mapped[int] = mapped_column(ForeignKey("production_orders.id"), nullable=False, index=True)
    posting_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    shift: Mapped[str] = mapped_column(String(10), default="1", nullable=False)
    good_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    scrap_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    rework_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)

    production_order = relationship("ProductionOrder", back_populates="outputs")


class MaterialPosting(Base, TimestampMixin):
    """Actual consumption and landed costs of raw materials against an order."""
    __tablename__ = "material_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    production_order_id: Mapped[int] = mapped_column(ForeignKey("production_orders.id"), nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), nullable=False, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("calendar_periods.id"), nullable=False, index=True)

    posting_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    lot_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    actual_quantity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    uom: Mapped[str] = mapped_column(String(10), nullable=False)

    unit_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    freight_component: Mapped[float] = mapped_column(Numeric(12, 4), default=0.0000, nullable=False)
    duty_component: Mapped[float] = mapped_column(Numeric(12, 4), default=0.0000, nullable=False)
    landed_unit_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    total_actual_cost: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    production_order = relationship("ProductionOrder", back_populates="material_postings")


class LabourPosting(Base, TimestampMixin):
    """Aggregated labour time and hourly cost posted to order or work centre."""
    __tablename__ = "labour_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    production_order_id: Mapped[int | None] = mapped_column(ForeignKey("production_orders.id"), nullable=True, index=True)
    work_centre_id: Mapped[int] = mapped_column(ForeignKey("work_centres.id"), nullable=False, index=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), nullable=False, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("calendar_periods.id"), nullable=False, index=True)

    posting_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    operation_name: Mapped[str] = mapped_column(String(100), nullable=False)
    shift: Mapped[str] = mapped_column(String(10), default="1", nullable=False)
    regular_hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    overtime_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0.00, nullable=False)
    hourly_rate: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    overtime_premium_rate: Mapped[float] = mapped_column(Numeric(12, 4), default=0.0000, nullable=False)
    total_labour_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    is_overtime: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    production_order = relationship("ProductionOrder", back_populates="labour_postings")


class MachineEvent(Base, TimestampMixin):
    """Machine running, setup, and downtime operating hours and machine cost."""
    __tablename__ = "machine_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_centre_id: Mapped[int] = mapped_column(ForeignKey("work_centres.id"), nullable=False, index=True)
    production_order_id: Mapped[int | None] = mapped_column(ForeignKey("production_orders.id"), nullable=True, index=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), nullable=False, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("calendar_periods.id"), nullable=False, index=True)

    event_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    run_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0.00, nullable=False)
    setup_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0.00, nullable=False)
    downtime_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0.00, nullable=False)
    downtime_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)  # TOOL_BREAKAGE, CHANGEOVER, MAINTENANCE
    hourly_rate: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    total_machine_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)


class EnergyReading(Base, TimestampMixin):
    """Energy sub-meter and plant consumption logs."""
    __tablename__ = "energy_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), nullable=False, index=True)
    work_centre_id: Mapped[int | None] = mapped_column(ForeignKey("work_centres.id"), nullable=True, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("calendar_periods.id"), nullable=False, index=True)

    meter_reference: Mapped[str] = mapped_column(String(40), nullable=False)
    reading_timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    kwh_consumed: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    tariff_band: Mapped[str] = mapped_column(String(20), default="PEAK", nullable=False)  # PEAK, OFF_PEAK, SHOULDER
    tariff_rate: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    total_energy_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    is_idle_load: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class QualityEvent(Base, TimestampMixin):
    """Quality rejects, scrap categorization, and rework hours."""
    __tablename__ = "quality_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    production_order_id: Mapped[int] = mapped_column(ForeignKey("production_orders.id"), nullable=False, index=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), nullable=False, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("calendar_periods.id"), nullable=False, index=True)

    event_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    defect_code: Mapped[str] = mapped_column(String(30), nullable=False)  # e.g. DEF-DIMENSION, DEF-POROSITY
    defect_description: Mapped[str] = mapped_column(String(200), nullable=False)
    lot_reference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scrap_quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)
    rework_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0.00, nullable=False)
    rework_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)

    production_order = relationship("ProductionOrder", back_populates="quality_events")


class OverheadPool(Base, TimestampMixin):
    """Periodic factory indirect expenses and absorption tracking."""
    __tablename__ = "overhead_pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), nullable=False, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("calendar_periods.id"), nullable=False, index=True)
    cost_centre_code: Mapped[str] = mapped_column(String(30), nullable=False)
    pool_name: Mapped[str] = mapped_column(String(100), nullable=False)  # Maintenance, Factory Lease, Supervisory

    actual_amount: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    absorption_driver: Mapped[str] = mapped_column(String(30), default="MACHINE_HOURS", nullable=False)
    planned_driver_capacity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    actual_driver_usage: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    standard_absorption_rate: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    absorbed_amount: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)
    under_over_absorption: Mapped[float] = mapped_column(Numeric(16, 4), nullable=False)


class SupplierPriceHistory(Base, TimestampMixin):
    """Historical supplier material quotations and negotiated contract prices."""
    __tablename__ = "supplier_price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    effective_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)

