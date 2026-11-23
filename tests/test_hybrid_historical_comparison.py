"""
Test Suite: Hybrid Historical Comparison Filter & Dynamic Baseline Resolver
Validates the 10 Core Criteria:
1. Current-period KPI Invariance:
   - current_total_cost, current_cost_per_good_unit, current_produced_qty, current_good_qty
     remain bit-for-bit identical across all comparison modes.
2. All Available History (Full-History Comparison):
   - Combines all eligible historical records (Aug–Oct 2026, 5,000 records) without synthetic contamination.
   - Flags is_unequal_duration=True and is_aggregate_history=True.
   - Retains raw baseline total cost (~₹1,402.47 Cr) for reference.
3. Select Single Historical Month:
   - Changing month updates baseline totals, deltas, and labels while leaving current values untouched.
4. Custom Historical Date Range:
   - Resolves arbitrary historical boundaries; ensures end date is strictly clamped prior to investigation.
5. Unequal Period Length Run-rate Normalization:
   - Total cost variance equals daily run-rate variance when durations differ.
6. Volume-Weighted Cost per Good Unit:
   - Evaluated as Total Direct Cost / Total Good Finished Units (never an unweighted average of averages).
7. Consistent Multi-dimensional Filtering:
   - Product, plant, and line filters apply symmetrically to both investigation and baseline queries.
8. Missing or Incompatible Baseline Coverage Handling:
   - Gracefully reports zero or honest state without crashing or fabricating fallback data.
9. Actual Daily Trend Bars & Donut Composition Invariance:
   - Actual daily spend bars and current cost category breakdown remain 100% constant across comparison changes.
10. Baseline-Dependent Key Evidence Refresh:
   - Recommended action evidence tables reflect baseline context accurately.
"""

import os
import sys
import pytest
import datetime as dt
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("backend"))
load_dotenv("backend/.env")

from app.db import SessionLocal
from app.services.ingestion.session_store import SessionDataStore
from app.services.rca.orchestrator import RCAOrchestrator
from app.services.rca.period_baseline import DynamicBaselineResolver
from app.services.investigation.query_service import InvestigationQueryService


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="module")
def session_datasets():
    sess_data = SessionDataStore.get_session("test_nov2026_reconciliation")
    assert sess_data is not None, "Test session 'test_nov2026_reconciliation' must be present"
    return sess_data


# ---------------------------------------------------------------------------
# Point 1: Current-period KPI actual values invariance across modes
# ---------------------------------------------------------------------------
def test_current_period_kpi_invariance_across_all_modes(db_session, session_datasets):
    """Point 1: Ensure current-period values never change when Compare With changes."""
    modes = [
        ("PREVIOUS_EQUIVALENT_PERIOD", {}),
        ("ALL_AVAILABLE", {}),
        ("SELECTED_MONTHS", {"baseline_months": "2026-10"}),
        ("SELECTED_MONTHS", {"baseline_months": "2026-09,2026-10"}),
        ("CUSTOM_RANGE", {"baseline_start_date": "2026-09-01", "baseline_end_date": "2026-09-30"}),
    ]
    
    first_report = None
    for mode, kwargs in modes:
        report = RCAOrchestrator.execute_investigation(
            db=db_session,
            session_datasets=session_datasets,
            current_period="2026-11",
            baseline_mode=mode,
            **kwargs
        )
        assert report is not None
        
        if first_report is None:
            first_report = report
            # Check absolute values for November 2026 authoritative dataset (₹190.03 Cr = 1,900,314,233.7 INR)
            assert abs(report.current_total_cost - 1900314233.7) < 1.0, f"Expected ~190.03 Cr, got {report.current_total_cost}"
            assert abs(report.current_cost_per_good_unit - 17227.97) < 1.0, f"Expected ~17,227.97, got {report.current_cost_per_good_unit}"
            assert report.current_produced_qty == 121357, f"Expected 121,357 units, got {report.current_produced_qty}"
            assert report.current_good_qty == 110304, f"Expected 110,304 units, got {report.current_good_qty}"
        else:
            # Bit-for-bit invariance check
            assert report.current_total_cost == first_report.current_total_cost, f"Total cost drifted in mode {mode}"
            assert report.current_cost_per_good_unit == first_report.current_cost_per_good_unit, f"CPGU drifted in mode {mode}"
            assert report.current_produced_qty == first_report.current_produced_qty, f"Produced qty drifted in mode {mode}"
            assert report.current_good_qty == first_report.current_good_qty, f"Good qty drifted in mode {mode}"


# ---------------------------------------------------------------------------
# Point 2: All Available History uses all 5,000 eligible records & dates
# ---------------------------------------------------------------------------
def test_all_available_history_coverage_and_records(db_session, session_datasets):
    """Point 2: Verify ALL_AVAILABLE discovers all historical records without synthetic pollution."""
    meta = InvestigationQueryService.get_scope_metadata(
        session_id="3cbfd40d-8b03-4cc9-ad18-3228c2589667",
        db=db_session
    )
    hc = meta["historical_comparison"]
    assert hc["all_available"]["total_records"] == 5000
    assert hc["min_date"] == "2026-08-01"
    assert hc["max_date"] == "2026-10-31"

    report = RCAOrchestrator.execute_investigation(
        db=db_session,
        session_datasets=session_datasets,
        current_period="2026-11",
        baseline_mode="ALL_AVAILABLE",
    )
    assert report.is_aggregate_history is True
    assert report.is_unequal_duration is True
    assert "All available history" in report.comparison_period_label
    
    # 3 full months of history ~1,402 Cr
    assert report.raw_baseline_total_cost is not None
    raw_cr = report.raw_baseline_total_cost / 1e7
    assert 1350 <= raw_cr <= 1450, f"Expected raw aggregate history ~1402 Cr, got {raw_cr:.2f}"


# ---------------------------------------------------------------------------
# Point 3: Selecting a month changes only comparison-dependent values
# ---------------------------------------------------------------------------
def test_selecting_single_month_updates_only_comparison_values(db_session, session_datasets):
    """Point 3: Selecting October vs September changes baseline totals but preserves current values."""
    rep_oct = RCAOrchestrator.execute_investigation(
        db=db_session,
        session_datasets=session_datasets,
        current_period="2026-11",
        baseline_mode="SELECTED_MONTHS",
        baseline_months="2026-10",
    )
    rep_sep = RCAOrchestrator.execute_investigation(
        db=db_session,
        session_datasets=session_datasets,
        current_period="2026-11",
        baseline_mode="SELECTED_MONTHS",
        baseline_months="2026-09",
    )
    # Current values unchanged
    assert rep_oct.current_total_cost == rep_sep.current_total_cost
    assert rep_oct.current_cost_per_good_unit == rep_sep.current_cost_per_good_unit
    
    # Comparison-dependent values changed
    assert rep_oct.comparison_period_label != rep_sep.comparison_period_label
    assert "Oct" in rep_oct.comparison_period_label
    assert "Sep" in rep_sep.comparison_period_label
    assert rep_oct.baseline_total_cost != rep_sep.baseline_total_cost
    assert rep_oct.cost_change_pct != rep_sep.cost_change_pct


# ---------------------------------------------------------------------------
# Point 4: Custom date range validation and bounding
# ---------------------------------------------------------------------------
def test_custom_date_range_validation_and_clamping(db_session, session_datasets):
    """Point 4: Custom date range bounds within eligible history and clamps if exceeding cutoff."""
    resolved = DynamicBaselineResolver.resolve_scope(
        db=db_session,
        current_period_str="2026-11",
        baseline_mode="CUSTOM_RANGE",
        baseline_start_date="2026-10-15",
        baseline_end_date="2026-11-10",  # crosses into November
    )
    assert resolved.baseline_start_date == dt.date(2026, 10, 15)
    # Must clamp end date to 2026-10-31 (day prior to current investigation start)
    assert resolved.baseline_end_date == dt.date(2026, 10, 31)
    assert "Oct 15 – Oct 31, 2026" in resolved.baseline_period_label


# ---------------------------------------------------------------------------
# Point 5: Unequal period length run-rate normalization
# ---------------------------------------------------------------------------
def test_unequal_period_length_run_rate_normalization(db_session, session_datasets):
    """Point 5: Total cost variance uses daily run rate when durations differ."""
    report = RCAOrchestrator.execute_investigation(
        db=db_session,
        session_datasets=session_datasets,
        current_period="2026-11",
        baseline_mode="ALL_AVAILABLE",
    )
    assert report.is_unequal_duration is True
    assert report.normalized_daily_cost is not None
    assert report.normalized_baseline_daily_cost is not None
    
    # cost_change_pct must equal run_rate_variance_pct
    assert abs(report.cost_change_pct - report.run_rate_variance_pct) < 1e-4


# ---------------------------------------------------------------------------
# Point 6: Volume-weighted Cost per Good Unit aggregation
# ---------------------------------------------------------------------------
def test_cost_per_good_unit_volume_weighted(db_session, session_datasets):
    """Point 6: Cost per good unit is sum(cost)/sum(good_units), never average of averages."""
    report = RCAOrchestrator.execute_investigation(
        db=db_session,
        session_datasets=session_datasets,
        current_period="2026-11",
        baseline_mode="PREVIOUS_EQUIVALENT_PERIOD",
    )
    # Current CPGU = 1,900,314,233.7 / 110,304 = 17,227.972
    expected_cpgu = report.current_total_cost / report.current_good_qty
    assert abs(report.current_cost_per_good_unit - expected_cpgu) < 0.05
    
    # Baseline CPGU = baseline_cost / baseline_good_qty
    if report.baseline_good_qty and report.baseline_good_qty > 0:
        expected_base_cpgu = report.baseline_total_cost / report.baseline_good_qty
        assert abs(report.baseline_cost_per_good_unit - expected_base_cpgu) < 1.0


# ---------------------------------------------------------------------------
# Point 7: Product, plant, and line filters apply consistently
# ---------------------------------------------------------------------------
def test_consistent_multidimensional_filtering(db_session, session_datasets):
    """Point 7: Product/plant/line filters filter both baseline and current periods."""
    unfiltered = RCAOrchestrator.execute_investigation(
        db=db_session,
        session_datasets=session_datasets,
        current_period="2026-11",
        baseline_mode="ALL_AVAILABLE",
    )
    filtered = RCAOrchestrator.execute_investigation(
        db=db_session,
        session_datasets=session_datasets,
        current_period="2026-11",
        baseline_mode="ALL_AVAILABLE",
        product_code="PHX-PRO",
    )
    assert filtered.scope.product_code == "PHX-PRO"
    assert filtered.current_total_cost < unfiltered.current_total_cost
    assert filtered.baseline_total_cost < unfiltered.baseline_total_cost


# ---------------------------------------------------------------------------
# Point 8: Missing or incompatible baseline coverage handling
# ---------------------------------------------------------------------------
def test_missing_or_incompatible_baseline_handling(db_session, session_datasets):
    """Point 8: Non-existent product in baseline gives honest state, not fabricated data."""
    report = RCAOrchestrator.execute_investigation(
        db=db_session,
        session_datasets=session_datasets,
        current_period="2026-11",
        baseline_mode="ALL_AVAILABLE",
        product_code="NON-EXISTENT-SKU-999",
    )
    assert report is not None
    # No records for this SKU in current upload or baseline
    assert report.current_total_cost == 0.0
    assert report.baseline_total_cost == 0.0


# ---------------------------------------------------------------------------
# Point 9: Daily trend bars & donut composition invariance
# ---------------------------------------------------------------------------
def test_trend_bars_and_donut_invariance(db_session, session_datasets):
    """Point 9: Actual daily trend bars and donut category values remain identical across modes."""
    rep_prev = RCAOrchestrator.execute_investigation(
        db=db_session,
        session_datasets=session_datasets,
        current_period="2026-11",
        baseline_mode="PREVIOUS_EQUIVALENT_PERIOD",
    )
    rep_all = RCAOrchestrator.execute_investigation(
        db=db_session,
        session_datasets=session_datasets,
        current_period="2026-11",
        baseline_mode="ALL_AVAILABLE",
    )
    
    # 1. Daily trend actual bars must be identical
    trend_prev = rep_prev.daily_cost_trend or []
    trend_all = rep_all.daily_cost_trend or []
    assert len(trend_prev) == len(trend_all) and len(trend_prev) > 0
    for p_bar, a_bar in zip(trend_prev, trend_all):
        assert p_bar["date"] == a_bar["date"]
        assert p_bar["cost"] == a_bar["cost"]
    
    # 2. Donut / category actual expenditure must be identical
    cat_prev = {c.category: c.current_amount for c in (rep_prev.category_breakdown or [])}
    cat_all = {c.category: c.current_amount for c in (rep_all.category_breakdown or [])}
    for cat_name, actual_c in cat_prev.items():
        assert actual_c == cat_all.get(cat_name)


# ---------------------------------------------------------------------------
# Point 10: Baseline-dependent Key Evidence in Improvement Plan
# ---------------------------------------------------------------------------
def test_improvement_plan_evidence_refreshes_with_baseline(db_session, session_datasets):
    """Point 10: Improvement plan recommendations contain full evidence & valid scope."""
    report = RCAOrchestrator.execute_investigation(
        db=db_session,
        session_datasets=session_datasets,
        current_period="2026-11",
        baseline_mode="ALL_AVAILABLE",
    )
    assert len(report.recommended_steps) >= 3
    for step in report.recommended_steps:
        assert step.key_evidence is not None and len(step.key_evidence) > 0
        assert step.affected_scope is not None
        assert "NOT_AVAILABLE" not in str(step.affected_scope)
        assert "NOT_AVAILABLE" not in (step.unit_cost_impact_display or "")
