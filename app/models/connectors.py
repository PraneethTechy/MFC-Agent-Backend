"""
Data Connectors Models
Stores configured manufacturing database connections, connection health, and table-to-family mappings.
"""

import datetime as dt
from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class DataConnector(Base, TimestampMixin):
    """
    Configured external database connector connection records.
    Stores host, port, database, user, encrypted password, and discovered dataset mappings.
    """
    __tablename__ = "data_connectors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(40), default="POSTGRESQL", nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=5432, nullable=False)
    database_name: Mapped[str] = mapped_column(String(120), nullable=False)
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)
    ssl_mode: Mapped[str] = mapped_column(String(30), default="require", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="NOT_TESTED", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    table_mappings: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)

