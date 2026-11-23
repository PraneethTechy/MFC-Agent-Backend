import datetime as dt
import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class ImportBatch(Base, TimestampMixin):
    """Tracks batch uploads, column mappings, validation summaries, and commit transactions."""
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    upload_timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )
    processing_status: Mapped[str] = mapped_column(
        String(30),
        default="UPLOADED",
        nullable=False,
    )  # UPLOADED, MAPPED, VALIDATED, COMMITTED, FAILED

    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    column_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_as_of: Mapped[dt.date | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    issues = relationship("DataQualityIssue", back_populates="batch", cascade="all, delete-orphan")


class DataQualityIssue(Base, TimestampMixin):
    """Individual structural, financial, manufacturing, or integrity issues flagged during ingestion."""
    __tablename__ = "data_quality_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    record_identifier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # ERROR (blocks commit) | WARNING (acceptable)
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # STRUCTURAL, FINANCIAL, MANUFACTURING, INTEGRITY
    rule_code: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    invalid_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch = relationship("ImportBatch", back_populates="issues")

