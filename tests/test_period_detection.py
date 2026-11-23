"""
Unit tests for Period Detector and /api/import/detect-period API endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.ingestion.period_detector import detect_dataset_period, detect_file_dates

client = TestClient(app)


def test_detect_dataset_period_default_files():
    """Validates period detection across staged manufacturing datasets."""
    res = detect_dataset_period()
    assert res["status"] == "SUCCESS"
    assert res["detected_period"] == "Oct 01, 2026 – Nov 25, 2026"
    assert res["earliest_date"] == "2026-10-01"
    assert res["latest_date"] == "2026-11-25"
    assert res["total_days"] == 56
    assert res["coverage_status"] == "CONSISTENT"
    assert res["alignment_pct"] == 100.0
    assert len(res["datasets"]) >= 6


def test_detect_file_dates_with_custom_csv():
    """Validates detection on custom CSV payload."""
    csv_bytes = b"posting_ts,cost,product_id\n2026-11-01,150.00,SPH-PRO-256\n2026-11-28,210.00,SPH-PRO-256\n"
    res = detect_file_dates("custom_fact_cost.csv", csv_bytes)
    assert res["status"] == "VALID"
    assert res["is_transactional"] is True
    assert res["earliest_date"] == "2026-11-01"
    assert res["latest_date"] == "2026-11-28"
    assert res["dated_rows"] == 2


def test_api_detect_period_endpoint_get():
    """Validates GET /api/import/detect-period."""
    resp = client.get("/api/import/detect-period")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "Oct 01, 2026" in data["detected_period"]
    assert data["earliest_date"] == "2026-10-01"
    assert data["latest_date"] == "2026-11-25"


def test_api_detect_period_endpoint_post_upload():
    """Validates POST /api/import/detect-period with uploaded file."""
    files = {
        "files": ("fact_cost.csv", b"posting_ts,amount\n2026-10-05,500\n2026-10-25,900\n", "text/csv")
    }
    resp = client.post("/api/import/detect-period", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["earliest_date"] == "2026-10-05"
    assert data["latest_date"] == "2026-10-25"
    assert data["total_days"] == 21

