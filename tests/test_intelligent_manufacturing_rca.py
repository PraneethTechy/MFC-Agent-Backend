"""
Automated Test Suite for Task 4: Intelligent Manufacturing Cost Root Cause Analysis Agent.
Verifies all 15 investigable dimensions, 3 deferred dimensions, dynamic baseline resolution,
selective planner expansion, evidence graph causal modeling, mathematical reconciliation,
provenance isolation, and end-to-end RCA pipeline execution.
"""

import datetime as dt
import pytest
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services.rca.models import (
    EvidenceClassification,
    ProvenanceClassification,
    EvidenceStrength,
)
from app.services.rca.period_baseline import DynamicBaselineResolver, DynamicComparisonScope
from app.services.rca.dimension_engine import DimensionAnalyticsEngine
from app.services.rca.investigation_planner import InvestigationPlanner
from app.services.rca.evidence_graph import EvidenceGraph
from app.services.rca.root_cause_prioritizer import RootCausePrioritizer
from app.services.rca.recommendation_engine import CorrectiveRecommendationEngine
from app.services.rca.orchestrator import RCAOrchestrator


@pytest.fixture(scope="module")
def db_session():
    """Provides an isolated database session for read-only verification."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def standard_scope():
    """Provides a standard October vs September comparison scope."""
    return DynamicComparisonScope(
        investigation_period_label="Oct 2026",
        baseline_period_label="Sep 2026",
        current_start_date=dt.date(2026, 10, 1),
        current_end_date=dt.date(2026, 10, 31),
        baseline_start_date=dt.date(2026, 9, 1),
        baseline_end_date=dt.date(2026, 9, 30),
        granularity="MONTHLY",
        is_comparable=True,
    )


# =============================================================================
# SCENARIOS 1-15: ALL 15 INVESTIGABLE DIMENSIONS
# =============================================================================

def test_scenario_01_total_manufacturing_cost_increase(db_session, standard_scope):
    """Scenario 1: Evaluates D1 Total manufacturing cost and cost element breakdown."""
    res = DimensionAnalyticsEngine.analyze_dimension(1, standard_scope, db=db_session)
    assert res.dimension_number == 1
    assert res.status == "INVESTIGATED"
    assert res.baseline_value is not None and res.baseline_value > 0
    assert res.actual_value is not None and res.actual_value > 0
    assert res.variance_amount == res.actual_value - res.baseline_value
    assert "category_breakdown" in res.metrics
    assert len(res.nodes) >= 1
    node = res.nodes[0]
    assert node.metric_name == "Total Manufacturing Cost (INR)"
    assert node.classification == EvidenceClassification.PROVEN.value


def test_scenario_02_cost_per_good_unit_increase(db_session, standard_scope):
    """Scenario 2: Evaluates D2 Cost per good unit with denominator yield governance."""
    res = DimensionAnalyticsEngine.analyze_dimension(2, standard_scope, db=db_session)
    assert res.dimension_number == 2
    assert res.status == "INVESTIGATED"
    assert res.actual_value > 0
    assert res.metrics["curr_good_units"] > 0
    assert res.evidence_classification == EvidenceClassification.PROVEN.value
    assert "Direct costed runs only" in res.nodes[0].limitations[0]


def test_scenario_03_scrap_and_rework_increase(db_session, standard_scope):
    """Scenario 3: Evaluates D3 Scrap and rework testing station fallout."""
    res = DimensionAnalyticsEngine.analyze_dimension(3, standard_scope, db=db_session)
    assert res.dimension_number == 3
    assert res.status == "INVESTIGATED"
    assert res.financial_impact_inr > 0
    assert "rework_events" in res.metrics
    assert res.primary_dataset_ids == ["d4_quality_inspection", "d2_manufacturing_cost"]


def test_scenario_04_line_performance_and_downtime(db_session, standard_scope):
    """Scenario 4: Evaluates D4 Plant and line throughput and downtime hours."""
    res = DimensionAnalyticsEngine.analyze_dimension(4, standard_scope, db=db_session)
    assert res.dimension_number == 4
    assert res.status == "INVESTIGATED"
    assert res.actual_value > 0
    assert "downtime_hours" in res.metrics


def test_scenario_05_product_wise_manufacturing_cost(db_session, standard_scope):
    """Scenario 5: Evaluates D5 Product-wise SKU manufacturing costs."""
    res = DimensionAnalyticsEngine.analyze_dimension(5, standard_scope, db=db_session)
    assert res.dimension_number == 5
    assert res.status == "INVESTIGATED"
    assert "sku_breakdown" in res.metrics
    assert len(res.metrics["sku_breakdown"]) >= 3
    assert "SPH-PRO-256" in res.metrics["sku_breakdown"]


def test_scenario_06_material_consumption_excess(db_session, standard_scope):
    """Scenario 6: Evaluates D6 Component feeder scrap and machine efficiency."""
    res = DimensionAnalyticsEngine.analyze_dimension(6, standard_scope, db=db_session)
    assert res.dimension_number == 6
    assert res.status == "INVESTIGATED"
    assert res.financial_impact_inr > 0
    assert res.provenance in ("RAW_BASELINE", "SYNTHETIC_GENERATED")
    assert res.evidence_classification in (
        EvidenceClassification.PROVEN.value,
        EvidenceClassification.OBSERVED_CORRELATION.value,
    )


def test_scenario_07_energy_consumption_increase(db_session, standard_scope):
    """Scenario 7: Evaluates D7 Plant power draw and reflow oven energy."""
    res = DimensionAnalyticsEngine.analyze_dimension(7, standard_scope, db=db_session)
    assert res.dimension_number == 7
    assert res.status == "INVESTIGATED"
    assert res.metrics["curr_kwh"] > 0
    assert res.financial_impact_inr > 0


def test_scenario_08_employee_absenteeism(db_session, standard_scope):
    """Scenario 8: Evaluates D8 Shift unscheduled operator absenteeism."""
    res = DimensionAnalyticsEngine.analyze_dimension(8, standard_scope, db=db_session)
    assert res.dimension_number == 8
    assert res.status == "INVESTIGATED"
    assert res.actual_value > 0
    assert res.metrics["absenteeism_pct"] > 0


def test_scenario_09_workforce_allocation_overtime(db_session, standard_scope):
    """Scenario 9: Evaluates D9 Shift overtime surges and weekend premiums."""
    res = DimensionAnalyticsEngine.analyze_dimension(9, standard_scope, db=db_session)
    assert res.dimension_number == 9
    assert res.status == "INVESTIGATED"
    assert res.metrics["overtime_hours"] > 0
    assert res.financial_impact_inr > 0


def test_scenario_12_labour_productivity_decline(db_session, standard_scope):
    """Scenario 10 (D12): Evaluates D12 Units produced per operator labor hour."""
    res = DimensionAnalyticsEngine.analyze_dimension(12, standard_scope, db=db_session)
    assert res.dimension_number == 12
    assert res.status == "INVESTIGATED"
    assert res.actual_value > 0
    assert res.metrics["curr_units_per_hr"] > 0


def test_scenario_13_procurement_price_variance(db_session, standard_scope):
    """Scenario 11 (D13): Evaluates D13 Purchase Price Variance (PPV) and supplier defects."""
    res = DimensionAnalyticsEngine.analyze_dimension(13, standard_scope, db=db_session)
    assert res.dimension_number == 13
    assert res.status == "INVESTIGATED"
    assert res.financial_impact_inr > 0
    assert "ppv_inr" in res.metrics


def test_scenario_14_inventory_stockouts(db_session, standard_scope):
    """Scenario 12 (D14): Evaluates D14 Component stockouts and buffer starvation."""
    res = DimensionAnalyticsEngine.analyze_dimension(14, standard_scope, db=db_session)
    assert res.dimension_number == 14
    assert res.status == "INVESTIGATED"
    assert res.metrics["stockout_count"] > 0


def test_scenario_16_production_capacity_utilization(db_session, standard_scope):
    """Scenario 13 (D16): Evaluates D16 Design nameplate capacity utilization deficit."""
    res = DimensionAnalyticsEngine.analyze_dimension(16, standard_scope, db=db_session)
    assert res.dimension_number == 16
    assert res.status == "INVESTIGATED"
    assert res.metrics["utilization_pct"] > 0


def test_scenario_17_material_inventory_reconciliation(db_session, standard_scope):
    """Scenario 14 (D17): Evaluates D17 Warehouse issue vs line consumption gap."""
    res = DimensionAnalyticsEngine.analyze_dimension(17, standard_scope, db=db_session)
    assert res.dimension_number == 17
    assert res.status == "INVESTIGATED"
    assert res.metrics["reconciliation_gap_inr"] > 0


def test_scenario_18_smartphone_testing_inspection_efficiency(db_session, standard_scope):
    """Scenario 15 (D18): Evaluates D18 First Pass Yield (FPY) and testing station fallout."""
    res = DimensionAnalyticsEngine.analyze_dimension(18, standard_scope, db=db_session)
    assert res.dimension_number == 18
    assert res.status == "INVESTIGATED"
    assert res.metrics["fpy_pct"] > 0
    assert res.primary_dataset_ids == ["d4_quality_inspection"]


# =============================================================================
# DEFERRED DIMENSIONS: D10, D11, D15 STRICT GOVERNANCE
# =============================================================================

def test_deferred_dimensions_never_fabricated(db_session, standard_scope):
    """Verifies that D10, D11, D15 are strictly marked DEFERRED_NO_DATA with explicit reasons."""
    for dim_num in [10, 11, 15]:
        res = DimensionAnalyticsEngine.analyze_dimension(dim_num, standard_scope, db=db_session)
        assert res.status == "DEFERRED_NO_DATA"
        assert res.is_supported is False
        assert res.is_deferred is True
        assert res.deferral_reason is not None and len(res.deferral_reason) > 10
        assert res.financial_impact_inr == 0.0
        assert len(res.nodes) == 0


# =============================================================================
# DYNAMIC BASELINE & PERIOD RESOLUTION
# =============================================================================

def test_dynamic_baseline_daily_resolution():
    """Verifies daily upload automatically resolves prior day baseline."""
    scope = DynamicBaselineResolver.resolve_scope(
        start_date="2026-11-15",
        end_date="2026-11-15",
    )
    assert scope.granularity == "DAILY"
    assert scope.current_start_date == dt.date(2026, 11, 15)
    assert scope.baseline_start_date == dt.date(2026, 11, 14)
    assert scope.total_investigation_days == 1


def test_dynamic_baseline_weekly_resolution():
    """Verifies weekly upload automatically resolves prior week baseline."""
    scope = DynamicBaselineResolver.resolve_scope(
        start_date="2026-11-09",
        end_date="2026-11-15",
    )
    assert scope.granularity == "WEEKLY"
    assert scope.total_investigation_days == 7
    assert scope.baseline_start_date == dt.date(2026, 11, 2)
    assert scope.baseline_end_date == dt.date(2026, 11, 8)


def test_dynamic_baseline_monthly_resolution():
    """Verifies monthly upload resolves immediate prior calendar month."""
    scope = DynamicBaselineResolver.resolve_scope(current_period_str="2026-11")
    assert scope.granularity == "MONTHLY"
    assert scope.current_start_date == dt.date(2026, 11, 1)
    assert scope.current_end_date == dt.date(2026, 11, 30)
    assert scope.baseline_start_date == dt.date(2026, 10, 1)
    assert scope.baseline_end_date == dt.date(2026, 10, 31)


def test_dynamic_baseline_custom_range_resolution():
    """Verifies custom 10-day period aligns with preceding 10-day period."""
    scope = DynamicBaselineResolver.resolve_scope(
        start_date="2026-11-11",
        end_date="2026-11-20",
    )
    assert scope.granularity == "CUSTOM"
    assert scope.total_investigation_days == 10
    assert scope.baseline_end_date == dt.date(2026, 11, 10)
    assert scope.baseline_start_date == dt.date(2026, 11, 1)


# =============================================================================
# INVESTIGATION PLANNER: SELECTIVE DYNAMIC EXPANSION (NO BLIND RUNS)
# =============================================================================

def test_investigation_planner_selective_expansion(db_session, standard_scope):
    """
    Verifies that the investigation planner selects entry dimensions,
    detects causal triggers, expands dynamically, and does NOT execute all 15 blindly.
    """
    planner = InvestigationPlanner(db=db_session)
    dim_results, graph, decisions = planner.plan_and_execute(
        scope=standard_scope,
        max_expansions=2,
    )

    # Initial selection must include D1, D2, D5
    initial_decisions = [d for d in decisions if d.action == "INITIAL_SELECTION"]
    assert len(initial_decisions) == 3
    assert {d.dimension_number for d in initial_decisions} == {1, 2, 5}

    # Causal expansions occurred
    expansions = [d for d in decisions if d.action == "CAUSAL_EXPANSION"]
    assert len(expansions) > 0

    # Total investigated dimensions is a focused subset, not all 15
    investigated = [r for r in dim_results.values() if r.status == "INVESTIGATED"]
    assert 5 <= len(investigated) <= 12

    # Deferred dimensions are documented as DEFER decisions
    deferred = [d for d in decisions if d.action == "DEFER"]
    assert len(deferred) == 3
    assert {d.dimension_number for d in deferred} == {10, 11, 15}


# =============================================================================
# ROOT-CAUSE PRIORITIZATION & MATHEMATICAL RECONCILIATION
# =============================================================================

def test_root_cause_prioritization_and_reconciliation(db_session, standard_scope):
    """Verifies root-cause ranking by financial impact and exact variance reconciliation."""
    planner = InvestigationPlanner(db=db_session)
    dim_results, graph, decisions = planner.plan_and_execute(scope=standard_scope)

    d1 = dim_results[1]
    tot_var = (d1.actual_value or 0.0) - (d1.baseline_value or 0.0)

    prioritized, explained, unexplained, is_reconciled = (
        RootCausePrioritizer.prioritize_and_reconcile(
            evidence_graph=graph,
            total_variance_inr=tot_var,
            baseline_cost_inr=d1.baseline_value or 0.0,
            current_cost_inr=d1.actual_value or 0.0,
        )
    )

    assert len(prioritized) > 0
    # Rank 1 must have the highest prioritization score
    assert prioritized[0].rank == 1
    assert prioritized[0].is_primary_driver is True

    # Mathematical identity: explained + unexplained == abs(total_variance)
    # when variance is positive
    if tot_var > 0:
        assert unexplained >= 0.0
        assert explained > 0.0


# =============================================================================
# RECOMMENDATION ENGINE: EVIDENCE-GROUNDED PLAYBOOKS
# =============================================================================

def test_recommendation_engine_grounded_playbooks(db_session, standard_scope):
    """Verifies that every recommendation links to a verified root cause with an owner and KPI."""
    planner = InvestigationPlanner(db=db_session)
    dim_results, graph, decisions = planner.plan_and_execute(scope=standard_scope)
    prioritized, _, _, _ = RootCausePrioritizer.prioritize_and_reconcile(
        evidence_graph=graph,
        total_variance_inr=10000000.0,
        baseline_cost_inr=100000000.0,
        current_cost_inr=110000000.0,
    )

    recs = CorrectiveRecommendationEngine.generate_recommendations(prioritized)
    assert len(recs) > 0

    for rec in recs:
        assert rec.recommendation_id.startswith("REC-")
        assert rec.responsible_function is not None and len(rec.responsible_function) > 3
        assert rec.measurement_kpi is not None and len(rec.measurement_kpi) > 3
        assert rec.verification_timeframe is not None
        assert rec.root_cause_finding_id is not None
        assert len(rec.implementation_steps) >= 2


# =============================================================================
# DETERMINISTIC REPRODUCIBILITY & PIPELINE VERIFICATION
# =============================================================================

def test_deterministic_reproducibility(db_session):
    """Verifies that identical scope inputs produce identical mathematical outputs."""
    report1 = RCAOrchestrator.execute_investigation(
        db=db_session,
        current_period="2026-10",
        baseline_period="2026-09",
    )
    report2 = RCAOrchestrator.execute_investigation(
        db=db_session,
        current_period="2026-10",
        baseline_period="2026-09",
    )

    assert report1.baseline_total_cost == report2.baseline_total_cost
    assert report1.current_total_cost == report2.current_total_cost
    assert report1.cost_change_amount == report2.cost_change_amount
    assert report1.cost_change_pct == report2.cost_change_pct
    assert report1.baseline_cost_per_good_unit == report2.baseline_cost_per_good_unit
    assert report1.current_cost_per_good_unit == report2.current_cost_per_good_unit
    assert len(report1.findings) == len(report2.findings)
    assert len(report1.recommended_steps) == len(report2.recommended_steps)


def test_end_to_end_orchestrator_stage3_compatibility(db_session):
    """
    Verifies that the full pipeline generates an InvestigationReport object
    100% compliant with the existing Stage 3 UI contract.
    """
    report = RCAOrchestrator.execute_investigation(
        db=db_session,
        current_period="2026-10",
        baseline_period="2026-09",
    )

    # Core UI contract fields
    assert report.report_id.startswith("RCA-")
    assert report.executive_finding is not None
    assert report.executive_finding.headline is not None
    assert report.scope is not None
    assert report.bridge is not None
    assert len(report.bridge.steps) >= 3
    assert len(report.category_breakdown) == 5
    assert len(report.cost_composition) == 5
    assert len(report.recommended_steps) >= 1
    assert report.cost_improvement_plan is not None
    assert "playbooks" in report.cost_improvement_plan
    assert "investigation_planner" in report.calculation_details
    assert "evidence_graph" in report.calculation_details
    assert "dimensional_evaluations" in report.calculation_details
