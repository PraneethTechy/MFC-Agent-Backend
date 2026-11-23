"""
Comprehensive Regression Test Suite for Manufacturing Cost Agent Final Corrections.
Verifies:
1. Centralized INR to Crore and Lakh deterministic formatting.
2. Exact November financial benchmarks (Total: ₹314.41 Cr, Material: ₹300.43 Cr, etc.).
3. Report numerical consistency (no LLM unit conversion hallucinations).
4. Strict session isolation: invalid session returns HTTP 404.
5. Missing session without active upload returns HTTP 404.
6. Analytical terminology: distinction between produced unit cost, good unit cost, and uplift.
7. All 5 manufacturing investigation questions.
8. Controlled +50% SoC price mutation test.
"""

import copy
import pytest
from fastapi import HTTPException
from app.db import SessionLocal
from app.services.ingestion.session_store import SessionDataStore
from app.services.investigation.formatters import (
    format_inr,
    format_crores,
    format_lakhs,
    format_currency_auto,
    format_pct,
    format_units,
)
from app.services.investigation.analytics import ManufacturingAnalytics
from app.services.investigation.query_service import (
    InvestigationQueryService,
    InvestigationQueryRequest,
)
from app.models.agent_records import InvestigationReportRecord


@pytest.fixture(scope="module")
def session_id():
    sid = SessionDataStore.get_or_create_default_benchmark_session()
    assert sid is not None, "Benchmark session should be initialized"
    return sid


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


# =============================================================================
# 1. TEST FORMATTERS
# =============================================================================
def test_inr_formatters():
    """Verifies deterministic currency and unit conversions."""
    # Crores
    assert format_crores(3144056862.26) == "₹314.41 Cr"
    assert format_crores(3004312504.55) == "₹300.43 Cr"
    assert format_crores(76838563.02) == "₹7.68 Cr"
    assert format_crores(44059348.13) == "₹4.41 Cr"
    assert format_crores(13714933.06) == "₹1.37 Cr"
    assert format_crores(5131513.50) == "₹0.51 Cr"

    # Lakhs
    assert format_lakhs(5131513.50) == "₹51.32 Lakhs"
    assert format_lakhs(100000) == "₹1.00 Lakhs"

    # Standard INR
    assert format_inr(11025.74) == "₹11,025.74"
    assert format_inr(11264.46) == "₹11,264.46"
    assert format_inr(238.72) == "₹238.72"

    # Auto formatting
    assert format_currency_auto(3144056862.26) == "₹314.41 Cr"
    assert format_currency_auto(5131513.50) == "₹51.32 Lakhs"
    assert format_currency_auto(11264.46) == "₹11,264.46"

    # Units
    assert format_units(285156) == "285,156 units"
    assert format_units(279113) == "279,113 units"


# =============================================================================
# 2. TEST NOVEMBER BENCHMARKS
# =============================================================================
def test_exact_november_benchmarks(session_id):
    """Calculates and verifies exact November financial benchmarks from raw session records."""
    datasets = SessionDataStore.get_session(session_id)
    assert datasets is not None
    analytics = ManufacturingAnalytics.analyze_manufacturing_cost(datasets)

    # 1. Total Direct Cost: ₹314.405686226 Cr
    assert analytics["total_cost"] == pytest.approx(3144056862.26, rel=1e-5)
    assert analytics["formatted_total_cost"] == "₹314.41 Cr"

    # 2. Material: ₹300.431250455 Cr (95.56%)
    mat_amt = analytics["categories"]["Material"]["amount"]
    assert mat_amt == pytest.approx(3004312504.55, rel=1e-5)
    assert analytics["categories"]["Material"]["formatted"] == "₹300.43 Cr"
    assert analytics["categories"]["Material"]["share_pct"] == pytest.approx(95.56, rel=1e-3)

    # 3. Labour: ₹7.683856302 Cr
    lab_amt = analytics["categories"]["Labour"]["amount"]
    assert lab_amt == pytest.approx(76838563.02, rel=1e-5)
    assert analytics["categories"]["Labour"]["formatted"] == "₹7.68 Cr"

    # 4. Machine: ₹4.405934813 Cr
    mac_amt = analytics["categories"]["Machine Operating"]["amount"]
    assert mac_amt == pytest.approx(44059348.13, rel=1e-5)
    assert analytics["categories"]["Machine Operating"]["formatted"] == "₹4.41 Cr"

    # 5. Energy: ₹1.371493306 Cr
    nrg_amt = analytics["categories"]["Factory Energy"]["amount"]
    assert nrg_amt == pytest.approx(13714933.06, rel=1e-5)
    assert analytics["categories"]["Factory Energy"]["formatted"] == "₹1.37 Cr"

    # 6. Scrap & Rework: ₹0.513151350 Cr (₹51.32 Lakhs)
    scr_amt = analytics["categories"]["Scrap & Rework"]["amount"]
    assert scr_amt == pytest.approx(5131513.50, rel=1e-5)
    assert analytics["categories"]["Scrap & Rework"]["formatted"] == "₹0.51 Cr"
    assert analytics["categories"]["Scrap & Rework"]["formatted_lakhs"] == "₹51.32 Lakhs"

    # 7. Produced Units & Cost per Produced Unit
    assert analytics["produced_units"] == 285156.0
    assert analytics["cost_per_produced_unit"] == pytest.approx(11025.74, rel=1e-4)
    assert analytics["formatted_cost_per_produced_unit"] == "₹11,025.74"

    # 8. Good Units & Cost per Good Unit
    assert analytics["good_units"] == 279113.0
    assert analytics["cost_per_good_unit"] == pytest.approx(11264.46, rel=1e-4)
    assert analytics["formatted_cost_per_good_unit"] == "₹11,264.46"

    # 9. Cost per Good Unit Uplift
    assert analytics["cost_per_good_unit_uplift"] == pytest.approx(238.72, rel=1e-4)
    assert analytics["formatted_cost_per_good_unit_uplift"] == "₹238.72"


# =============================================================================
# 3. TEST SESSION ISOLATION & FAILURE MODES
# =============================================================================
def test_session_isolation_invalid_session_returns_404(db):
    """Verifies that an explicitly requested non-existent session returns HTTP 404, never silent fallback."""
    req = InvestigationQueryRequest(
        question="What was the total manufacturing cost in November 2026?",
        session_id="invalid_session_that_does_not_exist_xyz",
    )
    with pytest.raises(HTTPException) as exc_info:
        InvestigationQueryService.process_investigation(db=db, request=req)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_session_isolation_missing_session_without_active_upload(db):
    """Verifies that omitted session_id fails with HTTP 404 if no active upload session exists."""
    # Temporarily clear active session pointer
    orig_active = SessionDataStore._active_session_id
    SessionDataStore._active_session_id = None
    try:
        req = InvestigationQueryRequest(
            question="What was the total manufacturing cost in November 2026?",
            session_id=None,
        )
        # If latest_session.json exists, delete/bypass or check that it handles clean missing state
        import os
        latest_fp = os.path.join(SessionDataStore._ensure_dir(), "latest_session.json")
        backup_fp = latest_fp + ".bak"
        if os.path.exists(latest_fp):
            os.rename(latest_fp, backup_fp)
        try:
            with pytest.raises(HTTPException) as exc_info:
                InvestigationQueryService.process_investigation(db=db, request=req)
            assert exc_info.value.status_code == 404
        finally:
            if os.path.exists(backup_fp):
                os.rename(backup_fp, latest_fp)
    finally:
        SessionDataStore._active_session_id = orig_active


# =============================================================================
# 4. TEST QUESTION 1: Total Manufacturing Cost & Number Integrity
# =============================================================================
def test_question_1_total_cost_integrity(session_id, db):
    req = InvestigationQueryRequest(
        question="What was the total manufacturing cost in November 2026?",
        reporting_period="Nov 2026 vs Oct 2026",
        session_id=session_id,
        data_origin="SYNTHETIC_TEST",
    )
    resp = InvestigationQueryService.process_investigation(db=db, request=req)

    # Assert report contains exact verified deterministic figures
    assert resp.financial_impact["headline"] == "₹314.41 Cr Total Direct Cost"
    assert "+₹22.93 Cr (+7.87%)" in resp.financial_impact["variance"]
    assert "₹11,264.46" in resp.financial_impact["description"]
    assert "₹238.72" in resp.financial_impact["description"]

    # Assert executive summary DOES NOT hallucinate ₹3,004.31 Cr
    assert "3,004.31 Cr" not in resp.executive_summary
    assert "3004.31 Cr" not in resp.executive_summary
    assert "₹300.43 Cr" in resp.executive_summary or "₹314.41 Cr" in resp.executive_summary

    # Assert drilldowns are strictly deterministic
    drill_map = {d["dimension"]: d["value"] for d in resp.drilldowns}
    assert drill_map["Material"] == "₹300.43 Cr"
    assert drill_map["Labour"] == "₹7.68 Cr"
    assert drill_map["Machine Operating"] == "₹4.41 Cr"
    assert drill_map["Factory Energy"] == "₹1.37 Cr"
    assert drill_map["Scrap & Rework"] == "₹0.51 Cr"


# =============================================================================
# 5. TEST QUESTION 2: Component Expenditure
# =============================================================================
def test_question_2_component_expenditure(session_id, db):
    req = InvestigationQueryRequest(
        question="Which components contributed most to material expenditure?",
        reporting_period="Nov 2026 vs Oct 2026",
        session_id=session_id,
        data_origin="SYNTHETIC_TEST",
    )
    resp = InvestigationQueryService.process_investigation(db=db, request=req)

    assert resp.intent == "COMPONENT_EXPENDITURE"
    assert "MAT-SOC-001" in resp.financial_impact["variance"]
    assert "₹90.42 Cr" in resp.financial_impact["description"]
    assert resp.drilldowns[0]["value"] == "₹90.42 Cr"
    assert resp.drilldowns[1]["value"] == "₹38.98 Cr"
    assert resp.drilldowns[2]["value"] == "₹34.30 Cr"


# =============================================================================
# 6. TEST QUESTION 3: BOM Consumption
# =============================================================================
def test_question_3_bom_consumption(session_id, db):
    req = InvestigationQueryRequest(
        question="Is material consumption exceeding BOM allowance?",
        reporting_period="Nov 2026 vs Oct 2026",
        session_id=session_id,
        data_origin="SYNTHETIC_TEST",
    )
    resp = InvestigationQueryService.process_investigation(db=db, request=req)

    assert resp.intent == "BOM_CONSUMPTION"
    assert resp.financial_impact is not None
    assert len(resp.drilldowns) > 0


# =============================================================================
# 7. TEST QUESTION 4: Line with Highest Rejection Rate
# =============================================================================
def test_question_4_highest_rejection_line(session_id, db):
    req = InvestigationQueryRequest(
        question="Which production line has the highest rejection rate?",
        reporting_period="Nov 2026 vs Oct 2026",
        session_id=session_id,
        data_origin="SYNTHETIC_TEST",
    )
    resp = InvestigationQueryService.process_investigation(db=db, request=req)

    assert resp.intent == "PRODUCTION_QUALITY"
    assert "Line SMT-L1: 2.55%" in resp.financial_impact["variance"]
    assert resp.drilldowns[0]["dimension"] == "Line SMT-L1"
    assert resp.drilldowns[0]["value"] == "2.55% Rejection"


# =============================================================================
# 8. TEST QUESTION 5: Scrap and Rework Expenditure
# =============================================================================
def test_question_5_scrap_rework(session_id, db):
    req = InvestigationQueryRequest(
        question="How much did scrap and rework cost, and which defects contributed most?",
        reporting_period="Nov 2026 vs Oct 2026",
        session_id=session_id,
        data_origin="SYNTHETIC_TEST",
    )
    resp = InvestigationQueryService.process_investigation(db=db, request=req)

    assert resp.intent == "SCRAP_REWORK"
    assert "₹51.32 Lakhs" in resp.financial_impact["headline"]
    assert "D004" in resp.drilldowns[0]["dimension"]


# =============================================================================
# 9. TEST GOOD-UNIT AND UNIT-COST SOURCE RECONCILIATION
# =============================================================================
def test_good_unit_and_unit_cost_source_reconciliation(session_id):
    """
    Rigorously verifies the authoritative definitions and reconciliation across datasets:
    1. test_fact_manufacturing_cost.csv:
       - Total Direct Cost: ₹3,144,056,862.26
       - Produced Quantity: 285,156 units
    2. test_fact_hourly_production.csv:
       - Actual Produced Quantity: 285,156 units
       - Authoritative Good Units: 279,113 units
       - Rejected Units: 6,043 units
       - Balance: 279,113 (good) + 6,043 (reject) == 285,156 (produced)
    3. Derived Unit Metrics:
       - Cost per Produced Unit = ₹3,144,056,862.26 / 285,156 = ₹11,025.74
       - Cost per Good Unit = ₹3,144,056,862.26 / 279,113 = ₹11,264.46
       - Uplift = ₹11,264.4578... - ₹11,025.7419... = ₹238.72
    4. Discrepancy Reconciliation:
       - A prior summary report contained a typographical slip listing 279,112.
       - ₹3,144,056,862.26 / 279,112 = ₹11,264.50.
       - The true, authoritative, data-backed value in the hourly production dataset
         is strictly 279,113, confirming ₹11,264.46 and uplift ₹238.72.
    """
    datasets = SessionDataStore.get_session(session_id)
    assert datasets is not None

    mfg_rows = datasets["MANUFACTURING_COST"]["rows"]
    nov_mfg = [r for r in mfg_rows if str(r.get("posting_ts", "")).startswith("2026-11")]

    tot_direct_cost = sum(
        float(r.get("material_cost_inr", 0))
        + float(r.get("labour_cost_inr", 0))
        + float(r.get("machine_cost_inr", 0))
        + float(r.get("energy_cost_inr", 0))
        + float(r.get("scrap_rework_cost_inr", 0))
        for r in nov_mfg
    )
    mfg_produced = sum(int(r.get("produced_qty", 0)) for r in nov_mfg)

    hourly_rows = datasets["HOURLY_PRODUCTION"]["rows"]
    nov_hourly = [r for r in hourly_rows if str(r.get("event_ts", "")).startswith("2026-11")]

    h_actual = sum(int(r.get("actual_qty", 0)) for r in nov_hourly)
    h_good = sum(int(r.get("good_qty", 0)) for r in nov_hourly)
    h_reject = sum(int(r.get("reject_qty", 0)) for r in nov_hourly)

    assert mfg_produced == 285156
    assert h_actual == 285156
    assert h_good == 279113
    assert h_reject == 6043
    assert h_good + h_reject == h_actual

    # Unrounded unit calculations
    unrounded_cost_per_produced = tot_direct_cost / mfg_produced
    unrounded_cost_per_good = tot_direct_cost / h_good
    unrounded_uplift = unrounded_cost_per_good - unrounded_cost_per_produced

    assert round(unrounded_cost_per_produced, 2) == 11025.74
    assert round(unrounded_cost_per_good, 2) == 11264.46
    assert round(unrounded_uplift, 2) == 238.72


# =============================================================================
# 10. TEST SESSION SURVIVES BACKEND REINITIALIZATION
# =============================================================================
def test_session_survives_backend_reinitialization(session_id):
    """
    Verifies that sessions persisted to disk survive complete backend reinitialization:
    1. Creates and persists an isolated session with 7 datasets.
    2. Simulates backend restart by resetting in-memory cache and active pointers.
    3. Reloads session from disk.
    4. Confirms row counts and deterministic analytics match 100%.
    """
    import os, shutil

    orig_datasets = SessionDataStore.get_session(session_id)
    assert orig_datasets is not None

    test_restart_sid = "session_test_restart_durability"
    SessionDataStore.save_session(
        session_id=test_restart_sid,
        datasets=orig_datasets,
        data_origin="SYNTHETIC_TEST",
        metadata={"test": "persistence_durability_check"},
        set_as_active=False,
    )

    # Verify session is initially in memory cache
    assert test_restart_sid in SessionDataStore._cache

    # Simulate server shutdown / restart
    SessionDataStore.reset_in_memory_state()

    # Verify memory is completely clean
    assert len(SessionDataStore._cache) == 0
    assert SessionDataStore._active_session_id is None

    # Retrieve session (triggers disk hydration)
    rehydrated = SessionDataStore.get_session(test_restart_sid)
    assert rehydrated is not None
    assert test_restart_sid in SessionDataStore._cache

    # Verify row counts match exactly
    for dk in orig_datasets.keys():
        assert dk in rehydrated
        assert len(rehydrated[dk]["rows"]) == len(orig_datasets[dk]["rows"])

    # Verify analytical results on rehydrated session are identical
    orig_analytics = ManufacturingAnalytics.analyze_manufacturing_cost(orig_datasets)
    rehydrated_analytics = ManufacturingAnalytics.analyze_manufacturing_cost(rehydrated)

    assert orig_analytics["total_cost"] == rehydrated_analytics["total_cost"]
    assert orig_analytics["good_units"] == rehydrated_analytics["good_units"]
    assert orig_analytics["cost_per_good_unit"] == rehydrated_analytics["cost_per_good_unit"]
    assert orig_analytics["cost_per_good_unit_uplift"] == rehydrated_analytics["cost_per_good_unit_uplift"]

    # Cleanup disk test session
    session_dir = os.path.join(SessionDataStore._ensure_dir(), test_restart_sid)
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir, ignore_errors=True)
    SessionDataStore._cache.pop(test_restart_sid, None)


# =============================================================================
# 11. TEST CONTROLLED MUTATION (+50% SoC price)
# =============================================================================
def test_controlled_mutation_changes_analytical_results(session_id, db):
    """
    Rigorously verifies dynamic data-responsiveness via controlled mutation:
    - Dataset: MATERIAL_CONSUMPTION
    - Column: consumed_value_inr
    - Target Material: MAT-SOC-001 (Snapdragon 8 Gen 3 SoC)
    - Target Period: 2026-11 (880 records)
    - Mutation Formula: consumed_value_inr * 1.5 (+50% price/expenditure surge)
    - Baseline Result: ₹90.42 Cr (from ₹904,188,290.40 raw consumption)
    - Mutated Result: ₹135.63 Cr (from ₹1,356,282,435.60 mutated consumption)
    - Preserves baseline session and does not overwrite active pointer.
    """
    baseline_datasets = SessionDataStore.get_session(session_id)
    assert baseline_datasets is not None

    mutated_datasets = copy.deepcopy(baseline_datasets)
    cons_rows = mutated_datasets["MATERIAL_CONSUMPTION"]["rows"]

    mutated_count = 0
    for r in cons_rows:
        if r.get("material_id") == "MAT-SOC-001" and str(r.get("consumption_ts", "")).startswith("2026-11"):
            curr_val = float(r.get("consumed_value_inr", 0))
            r["consumed_value_inr"] = str(round(curr_val * 1.5, 2))
            mutated_count += 1

    assert mutated_count == 880, "Should have mutated exactly 880 November SoC consumption records"

    mutated_sid = "session_mutation_test_controlled"
    SessionDataStore.save_session(
        session_id=mutated_sid,
        datasets=mutated_datasets,
        data_origin="SYNTHETIC_TEST",
        set_as_active=False,  # Do not clobber latest active session pointer
    )

    req_base = InvestigationQueryRequest(
        question="Which components contributed most to material expenditure?",
        session_id=session_id,
    )
    resp_base = InvestigationQueryService.process_investigation(db=db, request=req_base)

    req_mut = InvestigationQueryRequest(
        question="Which components contributed most to material expenditure?",
        session_id=mutated_sid,
    )
    resp_mut = InvestigationQueryService.process_investigation(db=db, request=req_mut)

    assert resp_base.drilldowns[0]["value"] == "₹90.42 Cr"
    assert resp_mut.drilldowns[0]["value"] == "₹135.63 Cr"
    assert resp_base.drilldowns[0]["value"] != resp_mut.drilldowns[0]["value"]


# =============================================================================
# 12. TEST /api/investigation/report ENDPOINT DATA INTEGRITY (UI Acceptance)
# =============================================================================
def test_investigation_report_endpoint_data_integrity(session_id):
    """
    Verifies that GET /api/investigation/report endpoint returns the exact
    reconciled benchmarks for the Investigation Result page:
    - current_total_cost: ₹3,144,056,862.26 (₹314.41 Cr)
    - current_good_qty: 279,113
    - current_produced_qty: 285,156
    - current_cost_per_good_unit: ₹11,264.46
    - 4 products whose good units sum to 279,113 and total costs sum to ₹314.41 Cr
    - daily trend: 25 points
    - weekly trend: 4 points
    - reasons breakdown: variance sums to exactly +₹22.93 Cr (+7.87%)
    """
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get(f"/api/investigation/report?session_id={session_id}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()

    # Financial & Quantitative Integrity
    assert round(data["current_total_cost"], 2) == 3144056862.26
    assert data["current_produced_qty"] == 285156.0
    assert data["current_good_qty"] == 279113.0
    assert round(data["current_cost_per_good_unit"], 2) == 11264.46
    assert round(data["baseline_cost_per_good_unit"], 2) == 10774.27
    assert round(data["unit_cost_change_pct"], 2) == 4.55
    assert round(data["cost_change_pct"], 2) == 7.87

    # Product Cost Comparison Integrity
    products = data.get("product_comparison", [])
    assert len(products) == 4, f"Expected 4 active products, got {len(products)}"
    total_good_units = sum(p["good_units_produced"] for p in products if p.get("good_units_produced"))
    total_product_cost = sum(p["current_total_cost"] for p in products if p.get("current_total_cost"))
    assert total_good_units == 279113.0, f"Good units sum {total_good_units} != 279,113"
    assert round(total_product_cost / 1e7, 2) == 314.41, f"Product cost sum {total_product_cost} != ₹314.41 Cr"

    # Multi-Granularity Trends
    calc_details = data.get("calculation_details", {})
    daily_trend = calc_details.get("daily_trend", [])
    weekly_trend = calc_details.get("weekly_trend", [])
    assert len(daily_trend) == 25, f"Expected 25 daily posting points, got {len(daily_trend)}"
    assert len(weekly_trend) == 4, f"Expected 4 weekly points, got {len(weekly_trend)}"

    # Reasons Breakdown
    reasons = calc_details.get("reasons_breakdown", [])
    assert len(reasons) >= 5
    mat_reason = next(r for r in reasons if "Material" in r["name"])
    assert mat_reason.get("formatted_amount") in ("₹22.39 Cr", "+₹22.39 Cr") or mat_reason.get("val") in ("₹22.39 Cr", "+₹22.39 Cr")
    assert mat_reason.get("pct_of_variance") == 97.7 or mat_reason.get("pct") == "97.7%"

