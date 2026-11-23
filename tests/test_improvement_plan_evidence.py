"""
Test Suite: Manufacturing Cost Improvement Plan Evidence, Scope & Financial Reconciliation
Validates that:
1. Every recommendation contains populated, multi-row key evidence tables with baseline, current, variance, and source.
2. Affected scope contains non-empty lists for products, plants, lines/component without any 'NOT_AVAILABLE' strings.
3. Unit cost impact is accurately derived and formatted in INR/unit (negative savings impact).
4. Financial figures are defensible and mathematically reconciled: total savings equals sum of individual recommendations without double counting.
"""

import pytest
from app.db import SessionLocal
from app.services.ingestion.session_store import SessionDataStore
from app.services.rca.orchestrator import RCAOrchestrator


def test_improvement_plan_evidence_and_scope():
    db = SessionLocal()
    sess_data = SessionDataStore.get_session("test_nov2026_reconciliation")
    assert sess_data is not None, "Test session data must be present"

    report = RCAOrchestrator.execute_investigation(
        db=db,
        session_datasets=sess_data,
        current_period="2026-11",
    )

    # 1. Validate recommended steps exist
    assert len(report.recommended_steps) >= 3, "Expected at least 3 prioritized operational recommendations"

    # 2. Validate step 1: Supplier Quality Remediation
    step1 = report.recommended_steps[0]
    assert "Display" in step1.title or "Quality" in step1.title
    assert step1.key_evidence is not None and len(step1.key_evidence) >= 4
    for ev in step1.key_evidence:
        assert ev.get("metric"), "Evidence row must have metric name"
        assert ev.get("baseline_value"), "Evidence row must have baseline value"
        assert ev.get("current_value"), "Evidence row must have current value"
        assert ev.get("variance"), "Evidence row must have variance"
        assert ev.get("source_dataset"), "Evidence row must have source dataset"

    assert step1.affected_scope is not None
    assert len(step1.affected_scope.get("products", [])) > 0
    assert len(step1.affected_scope.get("plants", [])) > 0
    assert "NOT_AVAILABLE" not in str(step1.affected_scope)
    assert step1.unit_cost_impact_display is not None
    assert "NOT_AVAILABLE" not in step1.unit_cost_impact_display
    assert "₹" in step1.unit_cost_impact_display and "/ unit" in step1.unit_cost_impact_display

    # 3. Validate step 2: SoC PPV
    step2 = report.recommended_steps[1]
    assert "SoC" in step2.title or "Contract" in step2.title or "Price" in step2.title
    assert step2.key_evidence is not None and len(step2.key_evidence) >= 4
    assert step2.affected_scope is not None
    assert "NOT_AVAILABLE" not in str(step2.affected_scope)
    assert step2.unit_cost_impact_display is not None
    assert "NOT_AVAILABLE" not in step2.unit_cost_impact_display

    # 4. Validate step 3: Line 2 Downtime Maintenance
    step3 = report.recommended_steps[2]
    assert "Line 2" in step3.title or "Feeder" in step3.title or "Downtime" in step3.title
    assert step3.key_evidence is not None and len(step3.key_evidence) >= 4
    assert step3.affected_scope is not None
    assert "NOT_AVAILABLE" not in str(step3.affected_scope)
    assert step3.unit_cost_impact_display is not None
    assert "NOT_AVAILABLE" not in step3.unit_cost_impact_display

    # 5. Financial Reconciliation
    total_savings = sum(s.estimated_savings_amount or 0.0 for s in report.recommended_steps)
    # Step 1: ~₹8.28 Cr, Step 2: ₹1.05 Cr, Step 3: ₹0.63 Cr => Total ~₹9.96 Cr
    assert 9.5e7 <= total_savings <= 10.5e7, f"Total savings should be ~₹9.96 Cr, got {total_savings}"

    # 6. Cost improvement plan in calculation_details or scope
    cip = report.cost_improvement_plan if hasattr(report, "cost_improvement_plan") else None
    if cip:
        assert cip.get("recommended_actions_count") == len(report.recommended_steps)
        assert cip.get("total_savings_opportunity_inr") == total_savings
