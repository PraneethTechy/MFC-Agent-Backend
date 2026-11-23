import datetime as dt
from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class Plant(Base, TimestampMixin):
    """Manufacturing facility location."""
    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(50), default="India", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    capacity_hours_month: Mapped[float] = mapped_column(Numeric(10, 2), default=4000.00, nullable=False)

    production_lines = relationship("ProductionLine", back_populates="plant", cascade="all, delete-orphan")
    work_centres = relationship("WorkCentre", back_populates="plant")


class ProductionLine(Base, TimestampMixin):
    """Specific manufacturing or assembly line within a plant."""
    __tablename__ = "production_lines"
    __table_args__ = (UniqueConstraint("plant_id", "code", name="uq_plant_line_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    line_type: Mapped[str] = mapped_column(String(50), default="Fabrication & Assembly", nullable=False)

    plant = relationship("Plant", back_populates="production_lines")
    work_centres = relationship("WorkCentre", back_populates="production_line")


class WorkCentre(Base, TimestampMixin):
    """Individual machine group, cell, or operational work area."""
    __tablename__ = "work_centres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), nullable=False, index=True)
    production_line_id: Mapped[int | None] = mapped_column(ForeignKey("production_lines.id"), nullable=True)
    cost_centre_code: Mapped[str] = mapped_column(String(30), nullable=False)
    hourly_machine_rate: Mapped[float] = mapped_column(Numeric(12, 4), default=0.0000, nullable=False)
    hourly_labour_rate: Mapped[float] = mapped_column(Numeric(12, 4), default=0.0000, nullable=False)
    efficiency_factor: Mapped[float] = mapped_column(Numeric(5, 4), default=1.0000, nullable=False)

    plant = relationship("Plant", back_populates="work_centres")
    production_line = relationship("ProductionLine", back_populates="work_centres")


class Product(Base, TimestampMixin):
    """Finished goods or sellable sub-assemblies."""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    product_group: Mapped[str] = mapped_column(String(50), nullable=False)
    uom: Mapped[str] = mapped_column(String(10), default="EA", nullable=False)
    standard_batch_size: Mapped[float] = mapped_column(Numeric(12, 2), default=100.00, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Material(Base, TimestampMixin):
    """Raw materials, purchased components, and sub-assemblies."""
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    material_type: Mapped[str] = mapped_column(String(30), default="RAW", nullable=False)  # RAW, COMPONENT, PACKAGING
    base_uom: Mapped[str] = mapped_column(String(10), default="KG", nullable=False)
    standard_unit_price: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)


class Supplier(Base, TimestampMixin):
    """External vendors supplying raw materials and parts."""
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    country: Mapped[str] = mapped_column(String(50), default="India", nullable=False)
    payment_terms: Mapped[str] = mapped_column(String(50), default="Net 30", nullable=False)
    reliability_rating: Mapped[float] = mapped_column(Numeric(3, 2), default=4.50, nullable=False)


class UnitOfMeasure(Base, TimestampMixin):
    """Units of measure catalog."""
    __tablename__ = "units_of_measure"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # WEIGHT, COUNT, TIME, ENERGY, LENGTH


class UnitConversion(Base, TimestampMixin):
    """Conversion factors between units of measure."""
    __tablename__ = "unit_conversions"
    __table_args__ = (UniqueConstraint("from_uom", "to_uom", name="uq_uom_conversion"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_uom: Mapped[str] = mapped_column(ForeignKey("units_of_measure.code"), nullable=False)
    to_uom: Mapped[str] = mapped_column(ForeignKey("units_of_measure.code"), nullable=False)
    factor: Mapped[float] = mapped_column(Numeric(16, 8), nullable=False)


class CalendarPeriod(Base, TimestampMixin):
    """Fiscal and calendar manufacturing periods."""
    __tablename__ = "calendar_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)  # e.g. "2026-M01"
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    working_days: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    standard_capacity_hours: Mapped[float] = mapped_column(Numeric(10, 2), default=200.00, nullable=False)


class ExchangeRate(Base, TimestampMixin):
    """Foreign exchange rates per period."""
    __tablename__ = "exchange_rates"
    __table_args__ = (UniqueConstraint("from_currency", "to_currency", "period_id", name="uq_fx_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    period_id: Mapped[int] = mapped_column(ForeignKey("calendar_periods.id"), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(14, 6), default=1.000000, nullable=False)

