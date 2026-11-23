"""
End-to-end integration tests for Reports Page & Investigation History Retrieval Centre.
Verifies genuine counts, dual investigation types (upload and ai), snapshot preservation,
and search/filter capabilities.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models.agent_records import InvestigationReportRecord
from app.services.reports_service import ReportsService

client = TestClient(app)


def test_reports_summary_genuine_counts():
    """Verify summary KPI numbers are strictly derived from actual database records."""
    res = client.get("/api/reports/summary")
    assert res.status_code == 200
    data = res.json()

    assert "total_upload_investigations" in data
    assert "total_ai_investigations" in data
    assert "total_saved_reports" in data
    assert "latest_activity" in data
    assert "available_periods" in data

    # Check database counts match
    db = SessionLocal()
    records = db.query(InvestigationReportRecord).all()
    db.close()

    total_records = len(records)
    assert data["total_saved_reports"] == total_records
    assert data["total_upload_investigations"] + data["total_ai_investigations"] == total_records
    assert data["total_upload_investigations"] > 0
    assert data["total_ai_investigations"] > 0


def test_reports_list_filtering():
    """Verify list filtering by type (upload, ai, all), search, and periods."""
    # 1. Fetch All
    res_all = client.get("/api/reports/list?type=all&limit=200")
    assert res_all.status_code == 200
    items_all = res_all.json()
    assert len(items_all) > 0

    # Every item must have authoritative record_type and typeLabel
    for item in items_all:
        assert item["record_type"] in ("DATA_UPLOAD_INVESTIGATION", "AI_INVESTIGATION")
        assert item["type"] in ("DATA_UPLOAD_INVESTIGATION", "AI_INVESTIGATION", "upload", "ai")
        assert item["typeLabel"] in ("Data Upload Investigation", "Dataset Upload Investigation", "AI Investigation")
        assert "provenance" in item
        # Internal flags should not be in presentation provenance
        assert "SYNTHETIC_TEST" not in item["provenance"]

    # 2. Filter type=DATA_UPLOAD_INVESTIGATION (and backward compatible type=upload)
    res_upload = client.get("/api/reports/list?type=DATA_UPLOAD_INVESTIGATION&limit=50")
    assert res_upload.status_code == 200
    items_upload = res_upload.json()
    assert all(i["record_type"] == "DATA_UPLOAD_INVESTIGATION" for i in items_upload)

    res_upload_legacy = client.get("/api/reports/list?type=upload&limit=50")
    assert res_upload_legacy.status_code == 200
    assert len(res_upload_legacy.json()) == len(items_upload)

    # 3. Filter type=AI_INVESTIGATION (and backward compatible type=ai)
    res_ai = client.get("/api/reports/list?type=AI_INVESTIGATION&limit=50")
    assert res_ai.status_code == 200
    items_ai = res_ai.json()
    assert all(i["record_type"] == "AI_INVESTIGATION" for i in items_ai)

    res_ai_legacy = client.get("/api/reports/list?type=ai&limit=50")
    assert res_ai_legacy.status_code == 200
    assert len(res_ai_legacy.json()) == len(items_ai)

    # 4. Search query
    if items_all:
        first_title = items_all[0]["title"]
        token = first_title.split()[0]
        res_search = client.get(f"/api/reports/list?search={token}&limit=20")
        assert res_search.status_code == 200
        search_items = res_search.json()
        assert len(search_items) > 0


def test_get_report_details_and_reopen():
    """Verify individual report lookup returns complete structured snapshot for reopening."""
    res_list = client.get("/api/reports/list?limit=10")
    assert res_list.status_code == 200
    items = res_list.json()

    # Find one upload report and one AI report
    upload_item = next(
        (i for i in items if i.get("record_type") == "DATA_UPLOAD_INVESTIGATION" or i["type"] in ("DATA_UPLOAD_INVESTIGATION", "upload")),
        None
    )
    ai_item = next(
        (i for i in items if i.get("record_type") == "AI_INVESTIGATION" or i["type"] in ("AI_INVESTIGATION", "ai")),
        None
    )

    if upload_item:
        res_up = client.get(f"/api/reports/{upload_item['id']}")
        assert res_up.status_code == 200
        data_up = res_up.json()
        assert data_up["id"] == upload_item["id"]
        assert data_up.get("record_type") == "DATA_UPLOAD_INVESTIGATION"
        assert data_up["report_json"] is not None

        # Also check /api/investigation/report/{report_id}
        res_inv = client.get(f"/api/investigation/report/{upload_item['id']}")
        assert res_inv.status_code == 200
        inv_data = res_inv.json()
        assert inv_data["report_id"] == upload_item["id"]
        assert "executive_finding" in inv_data or "bridge" in inv_data

    if ai_item:
        res_ai = client.get(f"/api/reports/{ai_item['id']}")
        assert res_ai.status_code == 200
        data_ai = res_ai.json()
        assert data_ai["id"] == ai_item["id"]
        assert data_ai.get("record_type") == "AI_INVESTIGATION"
        assert data_ai["report_json"] is not None
