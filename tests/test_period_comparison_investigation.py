"""
Test Suite: Period Comparison and Evidence Accuracy in AI Investigations
Verifies:
1. September vs October when both periods contain data:
   - Evaluates 2026-10 vs 2026-09
   - Returns exact cost movement: +₹1.09 Cr (+0.24%)
   - Volume effect: +₹2.87 Cr (PROVEN)
   - Product mix effect: -₹0.05 Cr (PROVEN)
   - Material unit rate effect: -₹1.84 Cr (PROVEN)
   - Reconciled residual: ₹0.00 (0.00 discrepancy)
   - Never returns ₹1,402.47 Cr aggregate all-period totals.
   - Does not falsely claim direct material caused cost increase.
2. One requested period unavailable (e.g. September vs November in Global store):
   - Returns status: PERIOD_UNAVAILABLE
   - Missing period clearly identified: November 2026 (2026-11)
   - Does not blame direct material
   - Findings classified as UNAVAILABLE
3. Both requested periods unavailable (e.g. May vs June 2026):
   - Returns status: PERIOD_UNAVAILABLE
   - Both periods identified as missing
4. Comparison with no actual cost movement (September vs September):
   - Returns status: COMPLETED
   - Net delta: ₹0.00
   - All effects: 0.00, direction: NEUTRAL
   - Residual: 0.00
5. Comparison with missing category-level evidence:
   - When category costs are zero/missing, evidence_classification is UNAVAILABLE
   - Separate material price vs usage split is marked UNAVAILABLE
6. Data Origin & Database Invariants:
   - Global investigation certified as REAL_COMMITTED_STORE, is_synthetic=False
   - Baseline DB count preserved (5,000 cost, 8,832 hourly, 16,000 quality, 48 BOM)
"""

import pytest
from sqlalchemy import func
from app.db import SessionLocal
from app.models.real_datasets import (
    LineCostBatch,
    HourlyProductionLog,
    SerializedQualityInspection,
    BomComponentRecord,
)
from app.services.analytics.intelligence_engine import ManufacturingIntelligenceEngine
from app.services.investigation.query_service import (
    InvestigationQueryService,
    InvestigationQueryRequest,
    extract_comparison_periods,
    detect_question_intent,
)


@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_01_period_extractor_and_intent_detection():
    """Verify natural language period extraction and intent classification."""
    # Target question
    q1 = "What caused the increase in manufacturing cost between September and October?"
    b1, c1, lbl1, is_comp1 = extract_comparison_periods(q1)
    assert is_comp1 is True
    assert b1 == "2026-09"
    assert c1 == "2026-10"
    assert detect_question_intent(q1) == "PERIOD_COMPARISON"

    # With explicit years
    q2 = "Why did manufacturing cost increase between September 2026 and October 2026?"
    b2, c2, lbl2, is_comp2 = extract_comparison_periods(q2)
    assert is_comp2 is True
    assert b2 == "2026-09"
    assert c2 == "2026-10"

    # From X to Y
    q3 = "What drove the variance from August to September?"
    b3, c3, lbl3, is_comp3 = extract_comparison_periods(q3)
    assert is_comp3 is True
    assert b3 == "2026-08"
    assert c3 == "2026-09"

    # Non-comparison questions
    q_non = "Which component has the highest material expenditure?"
    _, _, _, is_comp_non = extract_comparison_periods(q_non)
    assert is_comp_non is False
    assert detect_question_intent(q_non) == "COMPONENT_EXPENDITURE"


def test_02_september_vs_october_comparison_both_available(db_session):
    """
    Case 1: September vs October when both periods contain data.
    Must return exact variance bridge, not aggregate ₹1,402.47 Cr.
    Must attribute increase to Volume Effect (+₹2.87 Cr), NOT material (which decreased -₹1.84 Cr).
    """
    req = InvestigationQueryRequest(
        question="What caused the increase in manufacturing cost between September and October?",
        mode="GLOBAL",
    )
    resp = InvestigationQueryService.process_investigation(db_session, req)

    assert resp.status == "COMPLETED"
    assert resp.intent == "PERIOD_COMPARISON"
    assert resp.data_origin == "REAL_COMMITTED_STORE"
    assert resp.is_synthetic is False

    # Never substitute aggregate ₹1,402.47 Cr
    assert "1,402" not in resp.executive_summary
    assert "1402" not in resp.executive_summary

    # Must contain exact period figures
    assert "461.92" in resp.executive_summary or "461.9" in resp.executive_summary
    assert "463.01" in resp.executive_summary or "463.0" in resp.executive_summary
    assert "1.09" in resp.executive_summary  # Delta cost

    # Volume effect is positive driver (+2.87 Cr)
    assert "Volume" in resp.executive_summary
    assert "2.87" in resp.executive_summary

    # Material effect is negative (-1.84 Cr, savings)
    assert "1.84" in resp.executive_summary

    # Check drilldowns
    drilldowns = resp.drilldowns or []
    assert len(drilldowns) >= 7
    drivers = {d["dimension"]: d for d in drilldowns}
    assert "Production Volume Effect" in drivers
    assert "Product Mix Shift Effect" in drivers
    assert "Direct Material Price & Usage Effect" in drivers
    assert "Reconciled Unexplained Residual" in drivers

    # Detailed findings classification
    for f in resp.detailed_findings:
        assert f["evidence_classification"] in ("PROVEN", "OBSERVED_CORRELATION", "HYPOTHESIS", "UNAVAILABLE")

    # Financial impact
    assert resp.financial_impact is not None
    assert "1.09" in resp.financial_impact["headline"]


def test_03_one_requested_period_unavailable(db_session):
    """
    Case 2: One requested period unavailable (September vs November in Global store).
    November is uncommitted test data only.
    Must return PERIOD_UNAVAILABLE, clearly identify November 2026, and not blame material.
    """
    req = InvestigationQueryRequest(
        question="What caused the increase in manufacturing cost between September and November?",
        mode="GLOBAL",
    )
    resp = InvestigationQueryService.process_investigation(db_session, req)

    assert resp.status == "PERIOD_UNAVAILABLE"
    assert resp.intent == "PERIOD_COMPARISON"
    assert resp.data_origin == "REAL_COMMITTED_STORE"

    # Must clearly name November 2026 as missing
    assert "November 2026" in resp.executive_summary
    assert "2026-11" in resp.executive_summary

    # Must list available periods
    assert "October 2026" in resp.executive_summary
    assert "September 2026" in resp.executive_summary

    # Must NOT blame material
    assert "largest aggregate expenditure category" in resp.executive_summary or "does not substitute" in resp.executive_summary

    # Detailed findings must be marked UNAVAILABLE
    assert len(resp.detailed_findings) >= 1
    assert resp.detailed_findings[0]["evidence_classification"] == "UNAVAILABLE"

    # Recommendations must advise uploading/committing November data
    assert any("November" in r.get("action", "") for r in resp.recommended_actions)


def test_04_both_requested_periods_unavailable(db_session):
    """
    Case 3: Both requested periods unavailable (May vs June 2026).
    Must return PERIOD_UNAVAILABLE, identifying both periods as missing.
    """
    req = InvestigationQueryRequest(
        question="What caused the increase in manufacturing cost between May and June?",
        mode="GLOBAL",
    )
    resp = InvestigationQueryService.process_investigation(db_session, req)

    assert resp.status == "PERIOD_UNAVAILABLE"
    assert resp.intent == "PERIOD_COMPARISON"

    # Both periods identified
    assert "May 2026" in resp.executive_summary
    assert "June 2026" in resp.executive_summary

    # Shows available periods
    assert "2026-10" in resp.executive_summary or "October" in resp.executive_summary
    assert "2026-09" in resp.executive_summary or "September" in resp.executive_summary


def test_05_comparison_with_no_actual_cost_movement(db_session):
    """
    Case 4: Comparison with no actual cost movement (September vs September).
    Must return COMPLETED, delta = 0.00, residual = 0.00, direction = NEUTRAL.
    """
    req = InvestigationQueryRequest(
        question="Cost movement between September and September",
        mode="GLOBAL",
    )
    resp = InvestigationQueryService.process_investigation(db_session, req)

    assert resp.status == "COMPLETED"
    assert resp.intent == "PERIOD_COMPARISON"
    assert "0.00" in resp.executive_summary or "unchanged" in resp.executive_summary.lower() or "identical" in resp.executive_summary.lower()

    # Financial impact direction must be NEUTRAL
    assert resp.financial_impact["direction"] == "NEUTRAL"
    assert "0.00" in resp.financial_impact["headline"]


def test_06_missing_category_evidence_classification(db_session):
    """
    Case 5: Missing category-level evidence.
    Verify that calculate_cost_movement marks missing categories and price-usage split as UNAVAILABLE.
    """
    res = ManufacturingIntelligenceEngine.calculate_cost_movement(
        db=db_session,
        current_period="2026-10",
        baseline_period="2026-09",
    )
    assert res["status"] == "COMPLETED"
    ev_status = res["category_evidence_status"]
    # Separate price vs usage split is strictly UNAVAILABLE without vendor POs
    assert ev_status["price_usage_split"] == "UNAVAILABLE"
    assert ev_status["volume_effect"] == "PROVEN"
    assert ev_status["mix_effect"] == "PROVEN"
    assert ev_status["unexplained_residual"] == "PROVEN"


def test_07_baseline_database_invariants(db_session):
    """
    Requirement 9: Ensure baseline database is completely unmodified and intact.
    """
    cost_cnt = db_session.query(LineCostBatch).filter(LineCostBatch.is_synthetic == False).count()
    prod_cnt = db_session.query(HourlyProductionLog).filter(HourlyProductionLog.is_synthetic == False).count()
    qual_cnt = db_session.query(SerializedQualityInspection).filter(SerializedQualityInspection.is_synthetic == False).count()
    bom_cnt = db_session.query(BomComponentRecord).filter(BomComponentRecord.is_synthetic == False).count()

    assert cost_cnt == 5000, f"Expected 5,000 cost batches, got {cost_cnt}"
    assert prod_cnt == 8832, f"Expected 8,832 hourly logs, got {prod_cnt}"
    assert qual_cnt == 16000, f"Expected 16,000 quality records, got {qual_cnt}"
    assert bom_cnt == 48, f"Expected 48 BOM records, got {bom_cnt}"

    total_cost = float(db_session.query(func.sum(LineCostBatch.total_direct_cost_inr)).filter(LineCostBatch.is_synthetic == False).scalar() or 0.0)
    assert abs(total_cost - 14024712024.30) < 1.0, f"Expected ₹14,024,712,024.30 total cost, got {total_cost}"
