import datetime as dt
from sqlalchemy import Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2+ models."""
    pass


class TimestampMixin:
    """Provides standard audit timestamps and synthetic flag for all models."""
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        onupdate=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True if record is synthetically generated for testing/development.",
    )

