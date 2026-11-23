import pytest
from app.db import SessionLocal
from app.models.agent_records import InvestigationReportRecord
from app.services.investigation.query_service import (
    InvestigationQueryService,
    InvestigationQueryRequest,
    DynamicInvestigationResponse,
)
from app.services.reports_service import (
    classify_investigation_record,
    TYPE_AI_INVESTIGATION,
    TYPE_DATA_UPLOAD,
)


def test_structured_investigation_request_and_persistence():
    """
    Verifies that structured manufacturer problem context:
    - Section A (Title, Category, Description, Objective)
    - Section B (Scope: Period, Product, Plant, Line, Mode)
    - Section C (Observed Impact: KPI, Observed, Target, Financial Impact, Component, Ref, Date)
    - Section D (Additional Context: Suspected Cause - unverified hypothesis, Actions Taken, Comments)
    are processed, returned in DynamicInvestigationResponse, and persisted durably in Neon DB.
    """
    db = SessionLocal()
    try:
        req = InvestigationQueryRequest(
            title="OLED Display Panel Scrap Spike on Line 2",
            problem_category="Scrap / rework increase",
            problem_description="OLED display module inspection fallout spiked to 10.40% across 153 runs in Nov 2026, causing scrap spend variance.",
            objective="Identify root cause of display defects, establish supplier warranty liability, and recommend corrective actions.",
            reporting_period="ALL",
            product_code="PHX-PRO",
            plant_code="PLT-01",
            line_code="Line 2",
            mode="GLOBAL_ONLY",
            observed_kpi="Display Defect Rate",
            observed_value="10.40%",
            target_value="< 0.80%",
            financial_impact_inr=51700000.0,
            affected_component="OLED Display Panel 6.7\" (DSP-61)",
            operational_reference="SUP-104 (OptoTech Display), PO-9812",
            shift_or_date="Shift 1 & 2, Nov 13-25, 2026",
            suspected_cause="Suspected cleanroom bonding parameter drift at vendor OptoTech",
            actions_already_taken="Quarantined incoming lot SUP-104-B8, issued initial SCAR warning",
            additional_comments="Requires metallurgical joint audit",
        )

        resp = InvestigationQueryService.process_investigation(db=db, request=req)

        assert isinstance(resp, DynamicInvestigationResponse)
        assert resp.title == "OLED Display Panel Scrap Spike on Line 2"
        assert resp.problem_category == "Scrap / rework increase"
        assert resp.problem_description == req.problem_description
        assert resp.objective == req.objective
        assert resp.observed_impact is not None
        assert resp.observed_impact["kpi"] == "Display Defect Rate"
        assert resp.observed_impact["financial_impact_inr"] == 51700000.0
        assert resp.observed_impact["affected_component"] == "OLED Display Panel 6.7\" (DSP-61)"
        assert resp.user_context is not None
        assert resp.user_context["suspected_cause"] == "Suspected cleanroom bonding parameter drift at vendor OptoTech"
        assert resp.user_context["hypothesis_status"] == "USER_HYPOTHESIS_UNVERIFIED"

        # Verify durable persistence in Neon DB
        persisted = db.query(InvestigationReportRecord).filter(
            InvestigationReportRecord.report_id == resp.report_id
        ).first()

        assert persisted is not None
        assert persisted.title == "OLED Display Panel Scrap Spike on Line 2"
        assert persisted.report_json is not None
        assert persisted.report_json["problem_category"] == "Scrap / rework increase"
        assert persisted.report_json["observed_impact"]["kpi"] == "Display Defect Rate"
        assert persisted.report_json["user_context"]["hypothesis_status"] == "USER_HYPOTHESIS_UNVERIFIED"

        # Verify reports service classification as AI Investigation
        rec_type, rec_label = classify_investigation_record(persisted)
        assert rec_type == TYPE_AI_INVESTIGATION
        assert rec_label == "AI Investigation"

    finally:
        db.close()
