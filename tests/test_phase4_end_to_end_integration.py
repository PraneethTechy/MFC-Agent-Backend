"""
Phase 4 End-to-End Integration & Verification Test Suite.
Verifies all 9 application modules, baseline protection, dual investigation modes,
authoritative global store queries, and synthetic isolation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from app.main import app
from app.db import SessionLocal
from app.models.real_datasets import (
    LineCostBatch,
    HourlyProductionLog,
    SerializedQualityInspection,
    BomComponentRecord,
    MaterialPurchaseRecord,
    MaterialConsumptionRecord,
    QualityReworkEventRecord,
    FactRecordHistory,
)
from app.tools import validate_cost_data, get_cost_summary, inspect_bom_components
from app.services.investigation.query_service import InvestigationQueryService, InvestigationQueryRequest


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


# =============================================================================
# 1. BASELINE PROTECTION VERIFICATION
# =============================================================================
def test_01_baseline_records_preserved(db):
    """Verifies that baseline records in Neon DB are intact and total cost is exactly preserved."""
    cost_count = db.query(LineCostBatch).filter(LineCostBatch.is_synthetic == False).count()
    prod_count = db.query(HourlyProductionLog).filter(HourlyProductionLog.is_synthetic == False).count()
    qual_count = db.query(SerializedQualityInspection).filter(SerializedQualityInspection.is_synthetic == False).count()
    bom_count = db.query(BomComponentRecord).filter(BomComponentRecord.is_synthetic == False).count()

    total_cost = db.query(func.sum(LineCostBatch.total_direct_cost_inr)).filter(LineCostBatch.is_synthetic == False).scalar()

    assert cost_count == 5000, f"Expected 5000 cost records, got {cost_count}"
    assert prod_count == 8832, f"Expected 8832 hourly production records, got {prod_count}"
    assert qual_count == 16000, f"Expected 16000 quality records, got {qual_count}"
    assert bom_count == 48, f"Expected 48 BOM records, got {bom_count}"
    assert abs(float(total_cost) - 14024712024.30) < 0.01, f"Total cost mismatch: {total_cost}"


def test_02_synthetic_isolation_in_database(db):
    """Verifies that uncommitted synthetic records have NOT leaked into production Neon DB."""
    syn_cost = db.query(LineCostBatch).filter(LineCostBatch.is_synthetic == True).count()
    syn_prod = db.query(HourlyProductionLog).filter(HourlyProductionLog.is_synthetic == True).count()
    syn_qual = db.query(SerializedQualityInspection).filter(SerializedQualityInspection.is_synthetic == True).count()
    syn_bom = db.query(BomComponentRecord).filter(BomComponentRecord.is_synthetic == True).count()
    mat_pur = db.query(MaterialPurchaseRecord).count()
    mat_con = db.query(MaterialConsumptionRecord).count()
    rew_ev = db.query(QualityReworkEventRecord).count()

    assert syn_cost == 0, f"Found {syn_cost} synthetic cost records in production database!"
    assert syn_prod == 0, f"Found {syn_prod} synthetic production records in production database!"
    assert syn_qual == 0, f"Found {syn_qual} synthetic quality records in production database!"
    assert syn_bom == 0, f"Found {syn_bom} synthetic BOM records in production database!"
    assert mat_pur == 0, f"Found uncommitted material purchases in DB: {mat_pur}"
    assert mat_con == 0, f"Found uncommitted material consumptions in DB: {mat_con}"
    assert rew_ev == 0, f"Found uncommitted rework events in DB: {rew_ev}"


# =============================================================================
# 2. OVERVIEW API INTEGRATION
# =============================================================================
def test_03_overview_api_reads_committed_data_exclusively(client):
    """Verifies /api/dashboard/overview returns live committed baseline data without synthetic leakage."""
    res = client.get("/api/dashboard/overview")
    assert res.status_code == 200
    data = res.json()

    # Must contain cost actuals
    assert "kpis" in data
    kpis = data["kpis"]
    assert abs(kpis["total_direct_cost_inr"] - 14024712024.30) < 1.0

    # Production metrics
    prod = data["production"]
    assert prod["total_produced"] == 2424184.0
    assert prod["good_output"] == 2378960.0
    assert prod["rejected_output"] == 45224.0
    assert prod["data_origin"] == "REAL_COMMITTED_STORE"
    assert prod["is_synthetic"] is False

    # Monthly trends must reflect baseline months (Aug, Sep, Oct 2026)
    assert len(data["monthly_trend"]) == 3
    months = [m["month_name"] for m in data["monthly_trend"]]
    assert months == ["Aug", "Sep", "Oct"]

    # Available filters must include distinct periods
    assert "available_filters" in data
    assert "periods" in data["available_filters"]
    assert "2026-08" in data["available_filters"]["periods"]
    assert "2026-09" in data["available_filters"]["periods"]
    assert "2026-10" in data["available_filters"]["periods"]


# =============================================================================
# 3. CHATBOT TOOLS COMMITTED GLOBAL DATA QUERYING
# =============================================================================
def test_04_chatbot_tools_query_authoritative_data():
    """Verifies that chatbot tools enforce is_synthetic == False and return accurate baseline figures."""
    # 1. Cost summary across all baseline records
    summary = get_cost_summary.func()
    assert summary["status"] == "SUCCESS"
    assert summary["batches_analyzed"] == 5000
    assert abs(summary["total_direct_actual_cost_inr"] - 14024712024.30) < 1.0

    # 2. Validate cost data
    val = validate_cost_data.func()
    assert val["status"] == "VALIDATED"
    assert val["datasets_summary"]["line_cost_batches"] == 5000
    assert val["datasets_summary"]["hourly_production_logs"] == 8832

    # 3. Inspect BOM components
    bom = inspect_bom_components.func(product_code="SPH-PRO-256")
    assert bom["status"] == "SUCCESS"
    assert bom["components_count"] == 16


# =============================================================================
# 4. AI INVESTIGATIONS DUAL MODES (GLOBAL vs UPLOAD_SESSION)
# =============================================================================
def test_05_ai_investigations_global_mode(client, db):
    """Verifies that an investigation query with mode=GLOBAL evaluates against committed PostgreSQL baseline."""
    # 1. Scope metadata for GLOBAL
    meta_res = client.get("/api/investigation/scope-metadata?session_id=GLOBAL")
    assert meta_res.status_code == 200
    meta = meta_res.json()
    assert meta["data_origin"] == "REAL_COMMITTED_STORE"
    assert meta["origin_label"] == "Global Store (Authoritative PostgreSQL)"
    assert meta["status"] == "COMMITTED"
    assert meta["total_rows"] == 29880
    assert meta["dataset_count"] == 4

    # 2. Execute an investigation in GLOBAL mode
    req = InvestigationQueryRequest(
        question="Why did manufacturing cost increase in October 2026?",
        reporting_period="2026-10",
        product_code="All Products",
        plant_code="All Plants",
        line_code="All Lines",
        session_id="GLOBAL",
        mode="GLOBAL",
    )
    resp = InvestigationQueryService.process_investigation(db=db, request=req)
    assert resp.status == "COMPLETED"
    assert resp.data_origin == "REAL_COMMITTED_STORE"
    assert resp.is_synthetic is False
    assert resp.session_id == "GLOBAL"
    assert any("Authoritative Global Manufacturing Store" in ev for ev in resp.evidence)


def test_06_ai_investigations_upload_session_mode(client, db):
    """Verifies that an investigation query targeting an upload session maintains SYNTHETIC_TEST origin."""
    from app.services.ingestion.session_store import SessionDataStore
    sessions = SessionDataStore.list_sessions()
    if sessions:
        sid = sessions[0]["session_id"]
        meta_res = client.get(f"/api/investigation/scope-metadata?session_id={sid}")
        assert meta_res.status_code == 200
        meta = meta_res.json()
        assert meta["data_origin"] == "SYNTHETIC_TEST"
        assert meta["origin_label"] == "Synthetic Test"

        # Ask question against synthetic session
        req = InvestigationQueryRequest(
            question="Why did manufacturing cost increase?",
            reporting_period="ALL",
            session_id=sid,
            mode="UPLOAD_SESSION",
        )
        resp = InvestigationQueryService.process_investigation(db=db, request=req)
        assert resp.data_origin == "SYNTHETIC_TEST"
        assert resp.is_synthetic is True
        assert resp.session_id == sid


# =============================================================================
# 5. GLOBAL ANALYTICS ENDPOINTS VERIFICATION
# =============================================================================
def test_07_global_analytics_endpoints_enforce_committed_store(client):
    """Verifies /api/analytics/* endpoints return 200 with REAL_COMMITTED_STORE."""
    for ep in ["/api/analytics/cost", "/api/analytics/products", "/api/analytics/components", "/api/analytics/production-quality"]:
        res = client.get(ep)
        assert res.status_code == 200, f"Endpoint {ep} failed: {res.text}"
        data = res.json()
        assert data.get("data_origin") == "REAL_COMMITTED_STORE", f"Endpoint {ep} origin mismatch: {data.get('data_origin')}"


# =============================================================================
# 6. DATA UPLOAD WORKFLOW & PROMOTION AUDIT
# =============================================================================
def test_08_import_history_and_promotion_safety(client):
    """Verifies import history cleanly separates staged batches and protects against false promotion."""
    res = client.get("/api/import/history")
    assert res.status_code == 200
    batches = res.json()
    assert isinstance(batches, list)
    # Committed / promoted baseline batches must have committed_at or promoted_at timestamp
    for b in batches:
        if b.get("status") in ("PROMOTED", "COMMITTED"):
            assert b.get("committed_at") is not None or b.get("promoted_at") is not None
