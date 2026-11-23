"""
Pydantic Schemas for Data Connectors module.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class ConnectorCatalogItem(BaseModel):
    id: str
    name: str
    connector_type: str
    status: str = Field(..., description="AVAILABLE or PLANNED")
    description: str
    is_available: bool


class DataConnectorSummary(BaseModel):
    id: str
    name: str
    connector_type: str
    host_masked: str
    port: int
    database_name: str
    username_masked: str
    ssl_mode: str
    is_primary: bool = False
    status: str  # CONNECTED, CONNECTION_FAILED, AUTHENTICATION_FAILED, NOT_TESTED, PLANNED
    last_error: Optional[str] = None
    last_tested_at: Optional[str] = None
    last_synced_at: Optional[str] = None
    mapped_tables_count: int = 0
    table_mappings: dict[str, str] = Field(default_factory=dict)


class ConnectionTestRequest(BaseModel):
    name: Optional[str] = "Test Connection"
    connector_type: str = "POSTGRESQL"
    host: str = Field(..., min_length=1)
    port: int = Field(5432, ge=1, le=65535)
    database_name: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    ssl_mode: str = "require"


class ConnectionTestResponse(BaseModel):
    success: bool
    status: str
    message: str
    latency_ms: int = 0
    server_version: Optional[str] = None


class CreateConnectorRequest(BaseModel):
    name: str = Field(..., min_length=1)
    connector_type: str = "POSTGRESQL"
    host: str = Field(..., min_length=1)
    port: int = Field(5432, ge=1, le=65535)
    database_name: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    ssl_mode: str = "require"


class DiscoveredSchema(BaseModel):
    schema_name: str
    table_count: int = 0


class DiscoveredTable(BaseModel):
    table_name: str
    table_schema: str = "public"
    approx_rows: int = 0
    columns_count: int = 0
    suggested_family: Optional[str] = None
    mapping_status: str = "Not Mapped"  # Mapped, Not Mapped, Validation Required


class DiscoveredColumn(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool = True


class UpdateMappingsRequest(BaseModel):
    mappings: dict[str, str] = Field(default_factory=dict)

