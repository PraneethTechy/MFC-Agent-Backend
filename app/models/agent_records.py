import datetime as dt
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class AnalysisRun(Base, TimestampMixin):
    """Execution trace of cost variance investigations for future AI analysis runs."""
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(30), default="SCHEDULED", nullable=False)  # SCHEDULED, USER_PROMPT, ALERT
    period_id: Mapped[int | None] = mapped_column(ForeignKey("calendar_periods.id"), nullable=True)
    plant_id: Mapped[int | None] = mapped_column(ForeignKey("plants.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETED", nullable=False)
    findings_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ScenarioRun(Base, TimestampMixin):
    """What-if simulation configurations and calculated projections."""
    __tablename__ = "scenario_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    costing_version_id: Mapped[int | None] = mapped_column(ForeignKey("costing_versions.id"), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)  # e.g. {"material_price_pct": 0.05, "scrap_pct": -0.15}
    projected_savings: Mapped[float] = mapped_column(Numeric(14, 2), default=0.00, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)


class Recommendation(Base, TimestampMixin):
    """Evidence-backed operational cost saving recommendations."""
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    cost_category: Mapped[str] = mapped_column(String(30), nullable=False)  # MATERIAL, LABOUR, MACHINE, ENERGY, SCRAP, OVERHEAD
    plant_id: Mapped[int | None] = mapped_column(ForeignKey("plants.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_savings: Mapped[float] = mapped_column(Numeric(14, 2), default=0.00, nullable=False)
    realised_savings: Mapped[float] = mapped_column(Numeric(14, 2), default=0.00, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(4, 2), default=0.85, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="IDENTIFIED", nullable=False)  # IDENTIFIED, IN_REVIEW, APPROVED, IMPLEMENTED, REJECTED
    owner_role: Mapped[str] = mapped_column(String(50), default="Plant Controller", nullable=False)


class AuditEvent(Base, TimestampMixin):
    """Security and compliance audit log for financial records and imports."""
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_identifier: Mapped[str] = mapped_column(String(100), default="system", nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)  # CREATE, UPDATE, DELETE, IMPORT
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class InvestigationReportRecord(Base, TimestampMixin):
    """
    Permanent storage for deterministic AI agent root-cause investigations in Neon PostgreSQL.
    Survives backend restarts and ensures historical traceability with strict source isolation.
    """
    __tablename__ = "investigation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    inspection_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="COMPLETED", nullable=False)  # COMPLETED, FAILED, RUNNING

    data_origin: Mapped[str] = mapped_column(String(30), default="REAL", nullable=False)  # REAL, SYNTHETIC_TEST
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uploaded_files: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    dataset_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    data_scope: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


