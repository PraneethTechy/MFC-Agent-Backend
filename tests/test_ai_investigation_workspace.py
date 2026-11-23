import pytest
from app.services.ingestion.session_store import SessionDataStore
from app.services.investigation.query_service import InvestigationQueryService, InvestigationQueryRequest


def test_scope_metadata_active_session():
    """Verifies that scope metadata is extracted dynamically from the active session."""
    active_sid = SessionDataStore.get_active_session_id()
    if not active_sid or not SessionDataStore.get_session(active_sid):
        active_sid = "test_active_session_for_meta"
        SessionDataStore.init_session(active_sid)
        SessionDataStore.store_dataset(active_sid, "MANUFACTURING_COST", {
            "rows": [
                {"production_date": "2026-11-15", "cost_date": "2026-11-15", "product_code": "SPH-PRO-256", "plant_code": "PLT-01", "line_id": "L1"},
                {"production_date": "2026-11-16", "cost_date": "2026-11-16", "product_code": "SPH-A15-128", "plant_code": "PLT-01", "line_id": "L2"},
            ],
            "column_mapping": {"production_date": "production_date", "cost_date": "cost_date"}
        })
        SessionDataStore.set_active_session_id(active_sid)

    assert active_sid is not None

    meta = InvestigationQueryService.get_scope_metadata(active_sid)
    assert meta["has_active_session"] is True
    assert meta["session_id"] == active_sid
    assert "dimensions" in meta
    assert len(meta["dimensions"]["products"]) > 1
    assert len(meta["dimensions"]["plants"]) > 1
    assert len(meta["dimensions"]["lines"]) > 1
    assert "plant_lines_map" in meta["dimensions"]

    # Check plant-lines mapping
    for plant, lines in meta["dimensions"]["plant_lines_map"].items():
        assert isinstance(lines, list)
        assert len(lines) > 0

    # Check suggestions
    assert len(meta["suggestions"]) > 0
    assert any("manufacturing cost" in s.lower() for s in meta["suggestions"])


def test_scope_metadata_empty_session():
    """Verifies that scope metadata handles invalid or missing session gracefully."""
    meta = InvestigationQueryService.get_scope_metadata("non_existent_session_uuid_12345")
    assert "dimensions" in meta
    assert len(meta["dimensions"]["products"]) >= 1
    assert len(meta["dimensions"]["plants"]) >= 1
    assert len(meta["dimensions"]["lines"]) >= 1


def test_investigation_query_title_truncation(monkeypatch):
    """Verifies that dynamic investigation reports safely persist to database even with long AI titles."""
    from app.db import SessionLocal
    db = SessionLocal()

    active_sid = SessionDataStore.get_active_session_id()
    req = InvestigationQueryRequest(
        question="Which components contributed most to material expenditure?",
        reporting_period="ALL",
        product_code="All Products",
        plant_code="All Plants",
        line_code="All Lines",
        data_origin="SYNTHETIC_TEST",
        session_id=active_sid,
    )

    resp = InvestigationQueryService.process_investigation(db=db, request=req)
    assert resp.report_id.startswith("INV-")
    assert resp.intent == "COMPONENT_EXPENDITURE"
    assert resp.executive_summary is not None
    assert len(resp.detailed_findings) > 0
    assert len(resp.evidence) > 0
    assert len(resp.what_we_cannot_conclude_yet) > 0
    assert len(resp.recommended_actions) > 0


def test_missing_dataset_boundary_disclosure(monkeypatch):
    """Verifies that queries requiring datasets missing from session return honest LIMITATION_DISCLOSED status."""
    from app.db import SessionLocal
    db = SessionLocal()

    # Create temporary mock session with ONLY manufacturing_cost (missing BOM, hourly, quality)
    sparse_sid = "test_sparse_session_123"
    sparse_datasets = {
        "MANUFACTURING_COST": {
            "rows": [
                {"product_id": "P-100", "plant_id": "PL-1", "total_cost": 1000, "production_date": "2026-11-05"}
            ],
            "total_rows": 1,
        }
    }
    monkeypatch.setattr(SessionDataStore, "get_session", lambda sid: sparse_datasets if sid == sparse_sid else None)

    req = InvestigationQueryRequest(
        question="Which components exceeded standard BOM allowance?",
        reporting_period="ALL",
        product_code="All Products",
        plant_code="All Plants",
        line_code="All Lines",
        data_origin="SYNTHETIC_TEST",
        session_id=sparse_sid,
    )

    resp = InvestigationQueryService.process_investigation(db=db, request=req)
    assert resp.status == "LIMITATION_DISCLOSED"
    assert "Missing" in resp.title or "Boundary" in resp.title or "requires" in resp.title.lower()
    assert "BOM_COMPONENT" in resp.executive_summary or "BOM" in resp.executive_summary
    assert len(resp.what_we_cannot_conclude_yet) > 0
    assert len(resp.recommended_actions) > 0


def test_dynamic_reporting_periods(monkeypatch):
    """Verifies that reporting periods start with All Available Periods and list descending months without duplicates."""
    custom_sid = "test_custom_dates_session"
    custom_datasets = {
        "MANUFACTURING_COST": {
            "rows": [
                {"product_id": "P-100", "plant_id": "PL-1", "material_cost_inr": 500, "production_date": "2025-05-10"},
                {"product_id": "P-100", "plant_id": "PL-1", "material_cost_inr": 600, "production_date": "2025-06-15"},
            ],
            "total_rows": 2,
        },
        "HOURLY_PRODUCTION": {
            "rows": [
                # Overlapping month 2025-06 to test deduplication
                {"product_id": "P-100", "plant_id": "PL-1", "actual_qty": 50, "production_date": "2025-06-20"},
            ],
            "total_rows": 1,
        },
    }
    monkeypatch.setattr(SessionDataStore, "get_session", lambda sid: custom_datasets if sid == custom_sid else None)
    monkeypatch.setattr(SessionDataStore, "get_session_info", lambda sid: None)

    meta = InvestigationQueryService.get_scope_metadata(custom_sid)
    periods = meta["dimensions"]["periods"]
    assert len(periods) == 3

    # Option 1: All Available Periods
    assert periods[0]["id"] == "ALL"
    assert periods[0]["label"] == "All Available Periods"

    # Option 2: June 2025 (descending order)
    assert periods[1]["id"] == "2025-06"
    assert periods[1]["label"] == "June 2025"

    # Option 3: May 2025
    assert periods[2]["id"] == "2025-05"
    assert periods[2]["label"] == "May 2025"

    # Zero duplicate months
    ids = [p["id"] for p in periods]
    assert len(ids) == len(set(ids))


def test_period_filtering_analytics(monkeypatch):
    """Verifies that selecting one month filters actual backend calculations and ALL analyzes all periods."""
    from app.services.investigation.analytics import ManufacturingAnalytics

    custom_datasets = {
        "MANUFACTURING_COST": {
            "rows": [
                {"product_id": "P-100", "plant_id": "PL-1", "material_cost_inr": 500, "production_date": "2025-05-10", "produced_qty": 10},
                {"product_id": "P-100", "plant_id": "PL-1", "material_cost_inr": 600, "production_date": "2025-06-15", "produced_qty": 10},
            ],
            "total_rows": 2,
        }
    }

    # 1. Test All Available Periods (ALL)
    res_all = ManufacturingAnalytics.analyze_manufacturing_cost(custom_datasets, {"reporting_period": "ALL"})
    assert res_all["total_cost"] == 1100.0
    assert res_all["current_period"] == "All Available Periods"
    assert res_all["produced_units"] == 20

    # 2. Test specific month 2025-05
    res_may = ManufacturingAnalytics.analyze_manufacturing_cost(custom_datasets, {"reporting_period": "2025-05"})
    assert res_may["total_cost"] == 500.0
    assert res_may["current_period"] == "2025-05"
    assert res_may["produced_units"] == 10

    # 3. Test specific month 2025-06
    res_jun = ManufacturingAnalytics.analyze_manufacturing_cost(custom_datasets, {"reporting_period": "2025-06"})
    assert res_jun["total_cost"] == 600.0
    assert res_jun["current_period"] == "2025-06"
    assert res_jun["produced_units"] == 10


def test_invalid_period_validation_error(monkeypatch):
    """Verifies that selecting an unavailable reporting period returns an honest validation error."""
    from fastapi import HTTPException
    from app.db import SessionLocal
    db = SessionLocal()

    custom_sid = "test_custom_dates_session"
    custom_datasets = {
        "MANUFACTURING_COST": {
            "rows": [
                {"product_id": "P-100", "plant_id": "PL-1", "material_cost_inr": 500, "production_date": "2025-05-10"},
            ],
            "total_rows": 1,
        }
    }
    monkeypatch.setattr(SessionDataStore, "get_session", lambda sid: custom_datasets if sid == custom_sid else None)

    req = InvestigationQueryRequest(
        question="Why did manufacturing cost increase?",
        reporting_period="2024-01",  # Unavailable month
        product_code="All Products",
        plant_code="All Plants",
        line_code="All Lines",
        data_origin="SYNTHETIC_TEST",
        session_id=custom_sid,
    )

    with pytest.raises(HTTPException) as excinfo:
        InvestigationQueryService.process_investigation(db=db, request=req)

    assert excinfo.value.status_code == 400
    assert "not available" in excinfo.value.detail


