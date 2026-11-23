import datetime as dt
from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class CostingVersion(Base, TimestampMixin):
    """Costing revision standard (e.g. Annual Operating Plan standard cost baseline)."""
    __tablename__ = "costing_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    valid_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[dt.date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="APPROVED", nullable=False)  # DRAFT, APPROVED, SUPERSEDED

    standard_costs = relationship("StandardCostItem", back_populates="costing_version")
    boms = relationship("BillOfMaterials", back_populates="costing_version")
    routings = relationship("Routing", back_populates="costing_version")


class StandardCostItem(Base, TimestampMixin):
    """
    Approved standard unit cost broken down across all six manufacturing cost categories.
    """
    __tablename__ = "standard_cost_items"
    __table_args__ = (
        UniqueConstraint("product_id", "costing_version_id", "plant_id", name="uq_prod_costing_plant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    costing_version_id: Mapped[int] = mapped_column(ForeignKey("costing_versions.id"), nullable=False, index=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), nullable=False, index=True)

    # Six Cost Category Standards (per single unit of product)
    standard_material_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)
    standard_labour_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)
    standard_machine_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)
    standard_energy_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)
    standard_scrap_allowance_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)
    standard_overhead_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)
    standard_total_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)

    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    costing_version = relationship("CostingVersion", back_populates="standard_costs")


class BillOfMaterials(Base, TimestampMixin):
    """Product recipe header associating costing versions and plants."""
    __tablename__ = "bills_of_materials"
    __table_args__ = (
        UniqueConstraint("product_id", "costing_version_id", "plant_id", "version_num", name="uq_bom_header"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    costing_version_id: Mapped[int] = mapped_column(ForeignKey("costing_versions.id"), nullable=False)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), nullable=False)
    version_num: Mapped[str] = mapped_column(String(10), default="1.0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    items = relationship("BOMItem", back_populates="bom", cascade="all, delete-orphan")
    costing_version = relationship("CostingVersion", back_populates="boms")


class BOMItem(Base, TimestampMixin):
    """Specific line item within a Bill of Materials."""
    __tablename__ = "bom_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bom_id: Mapped[int] = mapped_column(ForeignKey("bills_of_materials.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False, index=True)
    line_num: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    uom: Mapped[str] = mapped_column(String(10), nullable=False)
    scrap_allowance_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0.0200, nullable=False)  # e.g. 2% allowance
    standard_unit_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0.0000, nullable=False)

    bom = relationship("BillOfMaterials", back_populates="items")


class Routing(Base, TimestampMixin):
    """Operational sequence header for manufacturing a product."""
    __tablename__ = "routings"
    __table_args__ = (
        UniqueConstraint("product_id", "costing_version_id", "plant_id", "version_num", name="uq_routing_header"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    costing_version_id: Mapped[int] = mapped_column(ForeignKey("costing_versions.id"), nullable=False)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), nullable=False)
    version_num: Mapped[str] = mapped_column(String(10), default="1.0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    steps = relationship("RoutingStep", back_populates="routing", cascade="all, delete-orphan")
    costing_version = relationship("CostingVersion", back_populates="routings")


class RoutingStep(Base, TimestampMixin):
    """Individual manufacturing operation or workstation process."""
    __tablename__ = "routing_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    routing_id: Mapped[int] = mapped_column(ForeignKey("routings.id", ondelete="CASCADE"), nullable=False, index=True)
    step_num: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_name: Mapped[str] = mapped_column(String(100), nullable=False)
    work_centre_id: Mapped[int] = mapped_column(ForeignKey("work_centres.id"), nullable=False)
    setup_hours: Mapped[float] = mapped_column(Numeric(8, 4), default=0.5000, nullable=False)
    run_hours_per_unit: Mapped[float] = mapped_column(Numeric(8, 4), default=0.1000, nullable=False)
    standard_labour_rate: Mapped[float] = mapped_column(Numeric(12, 4), default=0.0000, nullable=False)
    standard_machine_rate: Mapped[float] = mapped_column(Numeric(12, 4), default=0.0000, nullable=False)

    routing = relationship("Routing", back_populates="steps")

