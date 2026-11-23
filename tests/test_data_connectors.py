"""Unit and Integration Tests for Data Connectors Module."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models.connectors import DataConnector
from app.services.connectors.crypto import encrypt_password, decrypt_password


@pytest.fixture
def client():
    return TestClient(app)


def test_crypto_roundtrip():
    """Verify HMAC-SHA256 authenticated symmetric cipher encrypts and decrypts correctly."""
    plain = "SuperSecret_P@ssw0rd!_12345"
    token = encrypt_password(plain)
    assert len(token) > 30
    assert plain not in token

    decrypted = decrypt_password(token)
    assert decrypted == plain


def test_crypto_empty_and_corrupt_handling():
    """Verify empty handling and tamper resistance in crypto."""
    assert encrypt_password("") == ""
    assert decrypt_password("") == ""
    with pytest.raises(ValueError, match="Failed to decrypt"):
        decrypt_password("invalid_token")


def test_get_catalog(client):
    """GET /api/connectors/catalog returns 4 adapters."""
    res = client.get("/api/connectors/catalog")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 4
    types = [d["id"] for d in data]
    assert "postgresql" in types
    assert "sqlserver" in types
    assert "mysql" in types
    assert "snowflake" in types

    pg = next(d for d in data if d["id"] == "postgresql")
    assert pg["status"] == "AVAILABLE"

    ms = next(d for d in data if d["id"] == "sqlserver")
    assert ms["status"] == "PLANNED"


def test_list_connectors_primary_neon(client):
    """GET /api/connectors surfaces the primary Neon database with masked credentials."""
    res = client.get("/api/connectors")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1

    primary = next((c for c in data if c["is_primary"]), None)
    assert primary is not None
    assert primary["connector_type"].upper() == "POSTGRESQL"
    assert primary["status"] == "CONNECTED"
    # Verify masking
    assert "•" in primary["host_masked"] or "***" in primary["host_masked"]
    assert "•" in primary["username_masked"] or "***" in primary["username_masked"]
    # Verify password is NOT present
    assert "password" not in primary
    assert "encrypted_password" not in primary


def test_primary_schemas_discovery(client):
    """GET /api/connectors/{id}/schemas returns at least public schema."""
    res = client.get("/api/connectors")
    primary = next(c for c in res.json() if c["is_primary"])

    res_schemas = client.get(f"/api/connectors/{primary['id']}/schemas")
    assert res_schemas.status_code == 200
    schemas = res_schemas.json()
    schema_names = [s["schema_name"] if isinstance(s, dict) else s for s in schemas]
    assert "public" in schema_names


def test_primary_tables_discovery(client):
    """GET /api/connectors/{id}/tables discovers tables and suggests families."""
    res = client.get("/api/connectors")
    primary = next(c for c in res.json() if c["is_primary"])

    res_tables = client.get(f"/api/connectors/{primary['id']}/tables?schema=public")
    assert res_tables.status_code == 200
    tables = res_tables.json()
    assert len(tables) > 0

    table_names = [t["table_name"] for t in tables]
    assert "line_cost_batches" in table_names

    batch_tbl = next(t for t in tables if t["table_name"] == "line_cost_batches")
    assert batch_tbl["suggested_family"] == "MANUFACTURING_COST"


def test_columns_discovery(client):
    """GET /api/connectors/{id}/tables/{table}/columns returns column definitions."""
    res = client.get("/api/connectors")
    primary = next(c for c in res.json() if c["is_primary"])

    res_cols = client.get(f"/api/connectors/{primary['id']}/tables/line_cost_batches/columns?schema=public")
    assert res_cols.status_code == 200
    cols = res_cols.json()
    assert len(cols) > 0
    col_names = [c["column_name"] for c in cols]
    assert "id" in col_names
    assert "total_direct_cost_inr" in col_names


def test_test_connection_invalid_params(client):
    """POST /api/connectors/test reports clean connection error for invalid credentials."""
    payload = {
        "connector_type": "postgresql",
        "host": "invalid-host-that-does-not-exist.local",
        "port": 5432,
        "database_name": "fake_db",
        "username": "fake_user",
        "password": "fake_password",
        "ssl_mode": "require",
    }
    res = client.post("/api/connectors/test", json=payload)
    assert res.status_code == 200
    result = res.json()
    assert result["success"] is False
    assert result["status"] == "CONNECTION_FAILED"
    assert "Connection error" in result["message"]
