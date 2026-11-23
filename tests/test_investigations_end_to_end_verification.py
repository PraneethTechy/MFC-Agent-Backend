import os
import sys
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, "backend")

from app.db import SessionLocal, engine, text
from app.services.ingestion.session_store import SessionDataStore
from app.services.investigation.query_service import (
    InvestigationQueryService,
    InvestigationQueryRequest,
    DynamicInvestigationResponse,
)
from app.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def fast_domo_fallback(monkeypatch):
    """Bypasses remote Domo AI network call during unit tests for deterministic speed."""
    orig_method = InvestigationQueryService._synthesize_with_domo
    monkeypatch.setattr(
        InvestigationQueryService,
        "_synthesize_with_domo",
        lambda *args, **kwargs: {
            "executive_summary": "Deterministic verification narrative.",
            "key_finding": "Manufacturing Cost Variance Analysis",
            "finding_explanation": "Deterministic calculation result.",
            "drilldown_dimension": "Cost Category",
        }
    )

def test_1_global_store_periods_and_provenance():
    """Verify Neon V2 records, provenance, and Global Store reporting periods."""
    with SessionLocal() as db:
        # Check actual database records by month
        rows = db.execute(text("""
            SELECT 
                TO_CHAR(posting_ts, 'YYYY-MM') as ym,
                is_synthetic,
                COUNT(*) as cnt
            FROM line_cost_batches
            GROUP BY TO_CHAR(posting_ts, 'YYYY-MM'), is_synthetic
            ORDER BY ym, is_synthetic;
        """)).fetchall()
        
        counts_by_month = {}
        for r in rows:
            m = dict(r._mapping)
            counts_by_month.setdefault(m["ym"], {})[m["is_synthetic"]] = m["cnt"]

        # August, September, October have real records (is_synthetic=False)
        assert counts_by_month.get("2026-08", {}).get(False, 0) == 1700
        assert counts_by_month.get("2026-09", {}).get(False, 0) == 1641
        assert counts_by_month.get("2026-10", {}).get(False, 0) == 1659
        
        # November has 0 real records and 900 synthetic benchmark records
        assert counts_by_month.get("2026-11", {}).get(False, 0) == 0
        assert counts_by_month.get("2026-11", {}).get(True, 0) == 900

        # Verify Global Store metadata periods dropdown only reflects committed non-synthetic data
        meta = InvestigationQueryService.get_scope_metadata(session_id="GLOBAL", db=db)
        periods = [p["id"] for p in meta["dimensions"]["periods"]]
        assert periods == ["ALL", "2026-10", "2026-09", "2026-08"], f"Unexpected periods: {periods}"
        assert "2026-11" not in periods, "November must not be in Global Store periods"

def test_2_current_dataset_mode_and_expiry():
    """Verify Current Dataset mode isolation and clear error on expired/absent session."""
    with SessionLocal() as db:
        # 1. Expired/absent session metadata
        meta_expired = InvestigationQueryService.get_scope_metadata(session_id="expired_session_123", db=db)
        assert meta_expired["has_active_session"] is False
        assert meta_expired["status"] == "NO_SESSION"
        assert "not found or has expired" in meta_expired["message"]

        # 2. Expired/absent session query execution must NOT fall back to Global Store
        req = InvestigationQueryRequest(
            title="Expired Session Test",
            problem_category="Manufacturing cost increase",
            problem_description="Testing that missing session does not silently fall back to Global Store",
            objective="Ensure strict isolation",
            mode="UPLOAD_SESSION",
            session_id="expired_session_123",
        )
        with pytest.raises(HTTPException) as exc_info:
            InvestigationQueryService.process_investigation(db=db, request=req)
        assert exc_info.value.status_code == 400
        assert "expired" in exc_info.value.detail or "not found" in exc_info.value.detail

def test_3_filter_deterministic_queries_and_insufficient_data():
    """Verify independent and combined filter SQL application and honest insufficient-data handling."""
    with SessionLocal() as db:
        def get_cost(period="ALL", prod="All Products", plant="All Plants", line="All Lines"):
            req = InvestigationQueryRequest(
                title="Filter Verification",
                problem_category="Manufacturing cost increase",
                problem_description="Verifying SQL query filters",
                objective="Test filter",
                reporting_period=period,
                product_code=prod,
                plant_code=plant,
                line_code=line,
                mode="GLOBAL",
                session_id="GLOBAL",
            )
            return InvestigationQueryService.process_investigation(db=db, request=req)

        # Baseline ALL
        r_all = get_cost()
        assert r_all.status == "COMPLETED"
        assert r_all.data_origin == "REAL_COMMITTED_STORE"
        assert r_all.is_synthetic is False

        # Independent filter: Period 2026-10 vs 2026-09
        r_oct = get_cost(period="2026-10")
        r_sep = get_cost(period="2026-09")
        assert r_oct.status == "COMPLETED"
        assert r_sep.status == "COMPLETED"
        assert r_oct.reporting_period != r_sep.reporting_period

        # Independent filter: Product SPH-PRO-256
        r_prod = get_cost(prod="SPH-PRO-256")
        assert r_prod.status == "COMPLETED"
        assert "SPH-PRO-256" in r_prod.scope_label

        # Independent filter: Plant IN-TN-01
        r_plant = get_cost(plant="IN-TN-01")
        assert r_plant.status == "COMPLETED"
        assert "IN-TN-01" in r_plant.scope_label

        # Combined filter
        r_comb = get_cost(period="2026-10", prod="SPH-PRO-256", plant="IN-TN-01", line="FAL-L1")
        assert r_comb.status == "COMPLETED"
        assert r_comb.scope_label == "SPH-PRO-256, IN-TN-01, FAL-L1"

        # Unsupported combination: Plant IN-KA-01 has lines SMT-L1, SMT-L2; Line FAL-L1 belongs to IN-TN-01!
        r_unsupp = get_cost(plant="IN-KA-01", line="FAL-L1")
        assert r_unsupp.status in ("LIMITATION_DISCLOSED", "INSUFFICIENT_DATA")
        assert "No committed manufacturing records match" in r_unsupp.executive_summary

def test_4_all_form_fields_intake_and_hypothesis_separation():
    """Verify that all structured intake fields reach backend and manufacturer hypothesis is kept unverified."""
    with SessionLocal() as db:
        req = InvestigationQueryRequest(
            title="Line 2 Thermal Sensor Overconsumption Analysis",
            problem_category="Scrap / rework increase",
            problem_description="Line 2 exhibits frequent optical sensor drift causing automated test rejection.",
            objective="Isolate sensor failure correlation and determine tooling replacement window.",
            reporting_period="2026-10",
            product_code="SPH-PRO-256",
            plant_code="IN-TN-01",
            line_code="FAL-L2",
            mode="GLOBAL",
            session_id="GLOBAL",
            observed_kpi="First Pass Yield (FPY)",
            observed_value="85.9%",
            target_value="95.8%",
            financial_impact_inr=51700000.0,
            affected_component="OLED Display Panel 6.7 (DSP-61)",
            operational_reference="SUP-104 / BATCH-NOV-4491",
            shift_or_date="Shift 2",
            suspected_cause="Supplier SUP-104 defective glass bonding lot",
            actions_already_taken="Issued containment quarantine for incoming lot",
            additional_comments="Requires review with Quality Engineering",
        )
        resp = InvestigationQueryService.process_investigation(db=db, request=req)
        
        # Verify response attributes
        assert resp.title == "Line 2 Thermal Sensor Overconsumption Analysis"
        assert resp.problem_category == "Scrap / rework increase"
        assert resp.problem_description == "Line 2 exhibits frequent optical sensor drift causing automated test rejection."
        assert resp.objective == "Isolate sensor failure correlation and determine tooling replacement window."
        
        # Verify observed impact values
        assert resp.observed_impact is not None
        assert resp.observed_impact["observed_kpi"] == "First Pass Yield (FPY)"
        assert resp.observed_impact["observed_value"] == "85.9%"
        assert resp.observed_impact["target_value"] == "95.8%"
        assert resp.observed_impact["financial_impact_inr"] == 51700000.0
        assert resp.observed_impact["affected_component"] == "OLED Display Panel 6.7 (DSP-61)"
        assert resp.observed_impact["operational_reference"] == "SUP-104 / BATCH-NOV-4491"
        assert resp.observed_impact["shift_or_date"] == "Shift 2"

        # Verify user context and hypothesis separation
        assert resp.user_context is not None
        assert resp.user_context["suspected_cause"] == "Supplier SUP-104 defective glass bonding lot"
        assert resp.user_context["actions_already_taken"] == "Issued containment quarantine for incoming lot"
        assert resp.user_context["hypothesis_status"] == "USER_HYPOTHESIS_UNVERIFIED"

def test_5_report_persistence_and_replay_without_recalc():
    """Verify report persistence in Neon DB and replay without recalculation, preserving Global Store."""
    with SessionLocal() as db:
        # Record initial row count in Global Store
        initial_cost_count = db.execute(text("SELECT COUNT(*) FROM line_cost_batches;")).scalar()

        # Submit realistic investigation
        req = InvestigationQueryRequest(
            title="E2E Persistence Verification",
            problem_category="Manufacturing cost increase",
            problem_description="Testing report persistence and replay",
            objective="Ensure replay without recalculation",
            reporting_period="2026-10",
            product_code="All Products",
            plant_code="All Plants",
            line_code="All Lines",
            mode="GLOBAL",
            session_id="GLOBAL",
            observed_kpi="Total Manufacturing Cost",
            observed_value="₹472.10 Cr",
            suspected_cause="Unscheduled maintenance surge",
        )
        res = InvestigationQueryService.process_investigation(db=db, request=req)
        report_id = res.report_id

        # Verify replay via GET /api/investigation/query/{report_id}
        client_res = client.get(f"/api/investigation/query/{report_id}")
        assert client_res.status_code == 200
        saved_data = client_res.json()
        assert saved_data["report_id"] == report_id
        assert saved_data["title"] == "E2E Persistence Verification"
        assert saved_data["user_context"]["suspected_cause"] == "Unscheduled maintenance surge"
        assert saved_data["user_context"]["hypothesis_status"] == "USER_HYPOTHESIS_UNVERIFIED"

        # Verify that Global Store records were NOT modified or promoted
        final_cost_count = db.execute(text("SELECT COUNT(*) FROM line_cost_batches;")).scalar()
        assert initial_cost_count == final_cost_count, "Global Store count must remain untouched!"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
