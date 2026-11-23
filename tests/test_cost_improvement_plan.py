"""
Comprehensive Verification Tests for Truly Evidence-Driven Manufacturing Cost Improvement Plan.
Validates:
1. Dynamic, evidence-backed generation of Cost Improvement Plan on uploaded datasets.
2. Divergence of findings between November and December sessions (no identical templates).
3. December session: MAT-SOC-001 (+4.14%), SMT Line L1 (2.09%), BOM Dispense Tolerances (MUV).
4. November session: CMP-001 (+22.85%), Line LINE-02, Machine Runtime Variance (+33.95%).
5. Strict mathematical reconciliation: sum of individual savings equals total improvement opportunity.
6. Graceful handling of unquantified data when supplier purchase invoices are absent (NOT_AVAILABLE).
7. ZERO dummy data and strict mathematical integrity.
"""
import pytest
from app.db import SessionLocal
from app.services.investigation.investigation_engine import InvestigationEngineService
from app.services.investigation.schemas import RecommendedStep

DEC_SESSION_ID = "83bc61af-e690-4c01-8386-5e8313147008"
NOV_SESSION_ID = "6e9668d6-9142-4b3b-b21a-eb87f0f0f301"


def test_december_session_cost_improvement_plan():
    """Validates cost improvement plan on the 7-dataset December manufacturing session."""
    db = SessionLocal()
    try:
        report = InvestigationEngineService.generate_report(db, staged_batch_id=DEC_SESSION_ID)
        assert report is not None
        plan = report.cost_improvement_plan
        assert plan is not None, "cost_improvement_plan dictionary must be present"

        # 1. Summary Metrics Verification (Reconciled Total Opportunity)
        assert plan["recommended_actions_count"] == 3
        assert plan["total_opportunity_display"] == "₹10.40 Cr"
        assert plan["high_priority_count"] == 2
        assert plan["operational_action_count"] == 1

        # Sum of savings amounts must equal total opportunity amount
        savings_sum = sum(s.estimated_savings_amount for s in report.recommended_steps if s.estimated_savings_amount)
        assert abs(savings_sum - plan["total_opportunity_amount"]) < 1.0

        # 2. Recommendation 01 Verification (Material Cost - MAT-SOC-001)
        rec1 = report.recommended_steps[0]
        assert rec1.step_number == 1
        assert "MAT-SOC-001" in rec1.title
        assert rec1.category == "Material Cost"
        assert rec1.priority == "High Priority"
        assert rec1.estimated_savings_display == "₹3.56 Cr"
        assert rec1.unit_cost_impact_display == "↓ ~1.2%"
        assert rec1.owner == "Strategic Procurement"
        assert rec1.affected_scope is not None
        assert rec1.affected_scope.get("component_line") == "MAT-SOC-001"

        # Evidence table rows
        evidence1 = rec1.key_evidence or rec1.observed_evidence
        assert len(evidence1) >= 3
        pp_row = next(e for e in evidence1 if "Purchase Price" in e["metric"])
        assert "+4.14%" in pp_row["variance"]
        mat_row = next(e for e in evidence1 if "Total Material Cost" in e["metric"])
        assert "-17.26%" in mat_row["variance"]

        # 3. Recommendation 02 Verification (Quality - SMT Line)
        rec2 = report.recommended_steps[1]
        assert rec2.step_number == 2
        assert "SMT Line" in rec2.title
        assert rec2.category == "Quality"
        assert rec2.priority == "High Priority"
        assert rec2.estimated_savings_display == "₹0.98 Cr"
        assert rec2.owner == "Quality Engineering"
        evidence2 = rec2.key_evidence or rec2.observed_evidence
        assert len(evidence2) >= 3
        rej_row = next(e for e in evidence2 if "Line Rejection Rate" in e["metric"])
        assert "2.09%" in rej_row["current_value"]

        # 4. Recommendation 03 Verification (Operational Efficiency - BOM Dispense Tolerances)
        rec3 = report.recommended_steps[2]
        assert rec3.step_number == 3
        assert "BOM Dispense Tolerances" in rec3.title
        assert rec3.category == "Operational Efficiency"
        assert rec3.priority == "Medium Priority"
        assert rec3.estimated_savings_display == "₹5.86 Cr"
        assert rec3.owner == "Manufacturing Operations"
    finally:
        db.close()


def test_november_session_cost_improvement_plan():
    """Validates cost improvement plan on the 7-dataset November manufacturing session."""
    db = SessionLocal()
    try:
        report = InvestigationEngineService.generate_report(db, staged_batch_id=NOV_SESSION_ID)
        assert report is not None
        plan = report.cost_improvement_plan
        assert plan is not None, "cost_improvement_plan dictionary must be present"

        # 1. Summary Metrics Verification (Reconciled Total Opportunity for November)
        assert plan["recommended_actions_count"] == 3
        assert plan["total_opportunity_display"] == "₹18.31 Cr"
        assert plan["high_priority_count"] == 2
        assert plan["operational_action_count"] == 1

        # Sum of savings amounts must equal total opportunity amount
        savings_sum = sum(s.estimated_savings_amount for s in report.recommended_steps if s.estimated_savings_amount)
        assert abs(savings_sum - plan["total_opportunity_amount"]) < 1.0

        # 2. Recommendation 01 Verification (Material Cost - CMP-001)
        rec1 = report.recommended_steps[0]
        assert rec1.step_number == 1
        assert "CMP-001" in rec1.title
        assert rec1.category == "Material Cost"
        assert rec1.priority == "High Priority"
        assert rec1.estimated_savings_display == "₹15.74 Cr"
        assert rec1.unit_cost_impact_display == "↓ ~5.0%"
        assert rec1.owner == "Strategic Procurement"
        assert rec1.affected_scope is not None
        assert rec1.affected_scope.get("component_line") == "CMP-001"
        assert "PLT-01" in rec1.affected_scope.get("plants", [])

        # Evidence table rows
        evidence1 = rec1.key_evidence or rec1.observed_evidence
        assert len(evidence1) >= 3
        pp_row = next(e for e in evidence1 if "Purchase Price" in e["metric"])
        assert "+22.85%" in pp_row["variance"]
        mat_row = next(e for e in evidence1 if "Total Material Cost" in e["metric"])
        assert "-32.62%" in mat_row["variance"]

        # 3. Recommendation 02 Verification (Quality - Line LINE-02)
        rec2 = report.recommended_steps[1]
        assert rec2.step_number == 2
        assert "LINE-02" in rec2.title
        assert rec2.category == "Quality"
        assert rec2.priority == "High Priority"
        assert rec2.estimated_savings_display == "₹0.17 Cr"
        assert rec2.owner == "Quality Engineering"
        evidence2 = rec2.key_evidence or rec2.observed_evidence
        assert len(evidence2) >= 3

        # 4. Recommendation 03 Verification (Operational Efficiency - Machine Runtime Variance)
        rec3 = report.recommended_steps[2]
        assert rec3.step_number == 3
        assert "Machine Runtime Variance" in rec3.title
        assert rec3.category == "Operational Efficiency"
        assert rec3.priority == "Medium Priority"
        assert rec3.estimated_savings_display == "₹2.40 Cr"
        assert rec3.owner == "Manufacturing Operations"
        evidence3 = rec3.key_evidence or rec3.observed_evidence
        assert len(evidence3) >= 3
        mac_row = next(e for e in evidence3 if "Machine Operating Cost" in e["metric"])
        assert "+33.95%" in mac_row["variance"]
    finally:
        db.close()


def test_cross_session_differentiation():
    """Verifies that November and December sessions produce distinct, evidence-grounded recommendations."""
    db = SessionLocal()
    try:
        rep_nov = InvestigationEngineService.generate_report(db, staged_batch_id=NOV_SESSION_ID)
        rep_dec = InvestigationEngineService.generate_report(db, staged_batch_id=DEC_SESSION_ID)

        # Total opportunity must differ
        assert rep_nov.cost_improvement_plan["total_opportunity_display"] != rep_dec.cost_improvement_plan["total_opportunity_display"]
        assert rep_nov.cost_improvement_plan["total_opportunity_display"] == "₹18.31 Cr"
        assert rep_dec.cost_improvement_plan["total_opportunity_display"] == "₹10.40 Cr"

        # Step 1 component and savings must differ
        rec1_nov = rep_nov.recommended_steps[0]
        rec1_dec = rep_dec.recommended_steps[0]
        assert "CMP-001" in rec1_nov.title
        assert "MAT-SOC-001" in rec1_dec.title
        assert rec1_nov.estimated_savings_display == "₹15.74 Cr"
        assert rec1_dec.estimated_savings_display == "₹3.56 Cr"

        # Step 2 line must differ
        rec2_nov = rep_nov.recommended_steps[1]
        rec2_dec = rep_dec.recommended_steps[1]
        assert "LINE-02" in rec2_nov.title
        assert "SMT Line" in rec2_dec.title

        # Step 3 must reflect distinct operational drivers (Machine vs BOM MUV)
        rec3_nov = rep_nov.recommended_steps[2]
        rec3_dec = rep_dec.recommended_steps[2]
        assert "Machine Runtime Variance" in rec3_nov.title
        assert "BOM Dispense Tolerances" in rec3_dec.title
    finally:
        db.close()


def test_missing_purchase_invoices_unquantified_handling():
    """Validates that missing purchase invoices yield explicit NOT_AVAILABLE data limitation disclosures."""
    steps, plan = InvestigationEngineService._build_cost_improvement_plan(
        has_purch=False,
        has_cons=True,
        has_bom=True,
        has_rework=True,
        price_movement_table=[],
        ppv_amount=0.0,
        muv_amount=0.0,
        mat_change=0.0,
        rework_exp=0.0,
        prod_rows=[],
        cost_rows=[],
        rework_rows=[],
        distinct_skus={"SPH-A15-128", "SPH-A15-256"},
        distinct_plants={"Plant 01"},
        distinct_lines={"SMT-L1"},
        b_label="Oct 2026",
        c_label="Nov 2026",
        b_period="2026-10",
        c_period="2026-11",
        curr_good_units=10000.0,
        curr_unit_cost=10000.0,
        curr_mat=100000000.0,
        base_mat=100000000.0,
    )

    rec1 = steps[0]
    assert rec1.estimated_savings_display == "NOT_AVAILABLE"
    assert rec1.unit_cost_impact_display == "NOT_AVAILABLE"
