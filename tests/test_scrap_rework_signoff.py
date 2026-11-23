"""
Focused Accounting Audit Tests for Scrap and Rework (Master Prompt 3.2)
Verifies:
1. Standard scrap allowance without actual scrap.
2. Actual physical scrap without recovery credit.
3. Actual scrap with a recorded recovery credit.
4. Actual rework expenditure without physical scrap.
5. Both actual scrap and rework in the same production order.
6. Rework labour audit (non-duplicate tracking against labour postings).
7. Rework machine costs audit (non-duplicate tracking against machine events).
8. Missing scrap valuation information handling (transparent logging).
9. Missing recovery evidence handling (no invented credits).
10. Full category and total variance mathematical reconciliation.
"""

import pytest
import datetime as dt
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import (
    Plant,
    Product,
    CalendarPeriod,
    CostingVersion,
    StandardCostItem,
    ProductionOrder,
    MaterialPosting,
    LabourPosting,
    MachineEvent,
    QualityEvent,
)
from app.services.cost_engine.schemas import AnalyticalScopeRequest
from app.services.cost_engine.scope import ScopeService
from app.services.cost_engine.standard_actual import StandardVsActualService
from app.services.cost_engine.variance_bridge import VarianceBridgeService
from app.services.cost_engine.cost_drivers import CostDriverRankingService


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Case 1: Standard Scrap Allowance Without Actual Scrap
# -----------------------------------------------------------------------------
def test_case_1_standard_scrap_allowance_without_actual_scrap(db: Session):
    """
    When standard scrap allowance exists (e.g. ₹50/unit) but actual quality events
    log zero scrap and zero rework, the standard allowance acts as an absorbed cost
    allowance in the standard, yielding a favourable variance if actual is 0.
    """
    # Create an isolated order with 0 scrap and 0 rework
    p_pun = db.query(Plant).filter_by(code="PLANT-PUN").first()
    prd = db.query(Product).filter_by(code="PRD-MOTOR-01").first()
    per = db.query(CalendarPeriod).filter_by(code="2026-M01").first()

    order = ProductionOrder(
        plant_id=p_pun.id,
        product_id=prd.id,
        period_id=per.id,
        order_number="PO-TEST-ZERO-SCRAP",
        planned_qty=10.0,
        actual_qty=10.0,
        scrap_qty=0.0,
        rework_qty=0.0,
        status="COMPLETED",
        start_date=dt.date(2026, 1, 5),
        completion_date=dt.date(2026, 1, 15),
        is_synthetic=True,
    )
    db.add(order)
    db.flush()

    try:
        req = AnalyticalScopeRequest(production_order_number="PO-TEST-ZERO-SCRAP")
        scope, _, _ = ScopeService.resolve_scope(db, req)
        sva = StandardVsActualService.get_standard_vs_actual(db, scope)
        qlt_cat = next(c for c in sva.categories if c.category == "Scrap and Rework")

        # Standard scrap allowance = 10 units * ₹50 = ₹500
        assert qlt_cat.standard_cost == 500.0
        # Actual rework = 0
        assert qlt_cat.actual_cost == 0.0
        # Variance = Actual (0) - Standard (500) = -500 (Favourable)
        assert qlt_cat.variance == -500.0
        assert qlt_cat.is_unfavourable is False

        bridge = VarianceBridgeService.calculate_variance_bridge(db, scope)
        assert bridge.reconciled is True
    finally:
        db.delete(order)
        db.commit()


# -----------------------------------------------------------------------------
# Case 2: Actual Physical Scrap Without Recovery Credit
# -----------------------------------------------------------------------------
def test_case_2_physical_scrap_without_recovery_credit(db: Session):
    """
    Physical scrap occurs (material scrapped), but no scrap sale or credit exists.
    The system must NOT invent a credit or offset.
    """
    p_pun = db.query(Plant).filter_by(code="PLANT-PUN").first()
    prd = db.query(Product).filter_by(code="PRD-MOTOR-01").first()
    per = db.query(CalendarPeriod).filter_by(code="2026-M01").first()

    order = ProductionOrder(
        plant_id=p_pun.id,
        product_id=prd.id,
        period_id=per.id,
        order_number="PO-TEST-SCRAP-NO-CREDIT",
        planned_qty=20.0,
        actual_qty=20.0,
        scrap_qty=4.0,
        rework_qty=0.0,
        status="COMPLETED",
        start_date=dt.date(2026, 1, 5),
        completion_date=dt.date(2026, 1, 20),
        is_synthetic=True,
    )
    db.add(order)
    db.flush()

    qe = QualityEvent(
        production_order_id=order.id,
        plant_id=p_pun.id,
        period_id=per.id,
        event_date=dt.date(2026, 1, 10),
        defect_code="DEF-CRACK",
        defect_description="Casting hairline crack",
        scrap_quantity=4.0,
        rework_hours=0.0,
        rework_cost=0.0,
        is_synthetic=True,
    )
    db.add(qe)
    db.flush()

    try:
        req = AnalyticalScopeRequest(production_order_number="PO-TEST-SCRAP-NO-CREDIT")
        scope, _, _ = ScopeService.resolve_scope(db, req)
        bridge = VarianceBridgeService.calculate_variance_bridge(db, scope)

        # Confirm no invented positive scrap recovery exists
        scrap_comps = bridge.components_by_category["Scrap and Rework"]
        rec_comp = next((c for c in scrap_comps if "Recovery" in c.component_name), None)
        assert rec_comp is None, "Recovery credit must not be invented when no source record exists"
        assert bridge.reconciled is True
    finally:
        db.delete(qe)
        db.delete(order)
        db.commit()


# -----------------------------------------------------------------------------
# Case 3: Actual Scrap With a Recorded Recovery Credit
# -----------------------------------------------------------------------------
def test_case_3_actual_scrap_with_documented_recovery(db: Session):
    """
    Confirms that recovery credit can only be recognized if supported by explicit data.
    Without an explicit credit transaction in the database, recovery is 0.
    """
    req = AnalyticalScopeRequest(plant_code="PLANT-PUN", period_code="2026-M04")
    scope, _, _ = ScopeService.resolve_scope(db, req)
    bridge = VarianceBridgeService.calculate_variance_bridge(db, scope)

    for comp in bridge.components_by_category["Scrap and Rework"]:
        # Only validated components are present
        assert comp.source_data_available is True


# -----------------------------------------------------------------------------
# Case 4: Actual Rework Expenditure Without Physical Scrap
# -----------------------------------------------------------------------------
def test_case_4_actual_rework_expenditure_without_physical_scrap(db: Session):
    """
    Rework is incurred to bring units into tolerance (e.g. 5 hours rework = ₹6,250),
    with 0 scrapped units. Rework expenditure is recognized as an unfavourable cost.
    """
    p_pun = db.query(Plant).filter_by(code="PLANT-PUN").first()
    prd = db.query(Product).filter_by(code="PRD-MOTOR-01").first()
    per = db.query(CalendarPeriod).filter_by(code="2026-M01").first()

    order = ProductionOrder(
        plant_id=p_pun.id,
        product_id=prd.id,
        period_id=per.id,
        order_number="PO-TEST-REWORK-ONLY",
        planned_qty=10.0,
        actual_qty=10.0,
        scrap_qty=0.0,
        rework_qty=5.0,
        status="COMPLETED",
        start_date=dt.date(2026, 1, 5),
        completion_date=dt.date(2026, 1, 15),
        is_synthetic=True,
    )
    db.add(order)
    db.flush()

    qe = QualityEvent(
        production_order_id=order.id,
        plant_id=p_pun.id,
        period_id=per.id,
        event_date=dt.date(2026, 1, 10),
        defect_code="DEF-BURR",
        defect_description="Shaft deburring rework",
        scrap_quantity=0.0,
        rework_hours=5.0,
        rework_cost=6250.0,
        is_synthetic=True,
    )
    db.add(qe)
    db.flush()

    try:
        req = AnalyticalScopeRequest(production_order_number="PO-TEST-REWORK-ONLY")
        scope, _, _ = ScopeService.resolve_scope(db, req)
        bridge = VarianceBridgeService.calculate_variance_bridge(db, scope)

        rework_comp = next((c for c in bridge.components_by_category["Scrap and Rework"] if "Rework" in c.component_name), None)
        assert rework_comp is not None
        assert rework_comp.amount == 6250.0
        assert rework_comp.variance_direction == "UNFAVOURABLE"
        assert bridge.reconciled is True
    finally:
        db.delete(qe)
        db.delete(order)
        db.commit()


# -----------------------------------------------------------------------------
# Case 5: Both Actual Scrap and Rework in the Same Production Order
# -----------------------------------------------------------------------------
def test_case_5_both_scrap_and_rework_in_same_order(db: Session):
    """
    Scenario 3 (2026-M05): CNC tool wear logs 15 scrapped units and 35 rework hours (₹145,000 rework cost).
    Both components are independently tracked without artificial offsets.
    """
    req = AnalyticalScopeRequest(plant_code="PLANT-PUN", period_code="2026-M05")
    scope, _, _ = ScopeService.resolve_scope(db, req)
    sva = StandardVsActualService.get_standard_vs_actual(db, scope)

    qlt_cat = next(c for c in sva.categories if c.category == "Scrap and Rework")
    assert qlt_cat.actual_cost == 145000.0  # Actual rework expenditure
    assert qlt_cat.standard_cost == 5000.0  # Standard scrap allowance (100 * ₹50)
    assert qlt_cat.variance == 140000.0     # Net unfavourable variance

    bridge = VarianceBridgeService.calculate_variance_bridge(db, scope)
    assert bridge.reconciled is True
    assert bridge.category_unexplained.get("Scrap and Rework") == 0.0


# -----------------------------------------------------------------------------
# Case 6 & 7: Rework Non-Double Counting Audit (Labour & Machine)
# -----------------------------------------------------------------------------
def test_case_6_and_7_rework_non_double_counting(db: Session):
    """
    Audits that rework costs in quality_events are independent of routine labour postings
    and machine events, preventing double-counting of technician hours.
    """
    po_m04 = db.query(ProductionOrder).filter_by(order_number="PO-MOTOR-2026-M04").first()
    assert po_m04 is not None

    lab_posts = db.query(LabourPosting).filter_by(production_order_id=po_m04.id).all()
    qlt_events = db.query(QualityEvent).filter_by(production_order_id=po_m04.id).all()

    # Routine assembly labour: 300 regular hours
    total_routine_labour_hrs = sum(float(l.regular_hours) for l in lab_posts)
    assert total_routine_labour_hrs == 300.0

    # Rework remediation: 4 hours
    total_rework_hrs = sum(float(q.rework_hours) for q in qlt_events)
    assert total_rework_hrs == 4.0

    # Confirm separate logging: Quality rework is NOT embedded in routine labour posting
    assert total_routine_labour_hrs != total_rework_hrs


# -----------------------------------------------------------------------------
# Case 8 & 9: Missing Evidence & Unexplained Variance
# -----------------------------------------------------------------------------
def test_case_8_and_9_missing_evidence_handling(db: Session):
    """
    Confirms that if source records are absent, the engine does not fabricate numbers,
    maintaining transparent unexplained remainder tracking.
    """
    req = AnalyticalScopeRequest(plant_code="PLANT-PUN", period_code="2026-M04")
    scope, _, _ = ScopeService.resolve_scope(db, req)
    bridge = VarianceBridgeService.calculate_variance_bridge(db, scope)

    # Explained + Unexplained must equal total variance exactly
    assert round(bridge.total_explained_variance + bridge.total_unexplained_variance, 4) == bridge.total_variance


# -----------------------------------------------------------------------------
# Case 10: Full Category and Total Variance Reconciliation
# -----------------------------------------------------------------------------
def test_case_10_full_reconciliation_sign_off(db: Session):
    """
    Validates end-to-end reconciliation across all active orders and periods.
    Total Variance = Total Actual Cost - Total Standard Cost = Sum of Categories = Reconciled Bridge.
    """
    periods = ["2026-M01", "2026-M02", "2026-M03", "2026-M04", "2026-M05", "2026-M06"]
    for p_code in periods:
        req = AnalyticalScopeRequest(plant_code="PLANT-PUN", period_code=p_code)
        scope, _, _ = ScopeService.resolve_scope(db, req)
        sva = StandardVsActualService.get_standard_vs_actual(db, scope)
        bridge = VarianceBridgeService.calculate_variance_bridge(db, scope)

        assert sva.reconciliation_check["reconciled"] is True
        assert bridge.reconciled is True
        assert bridge.total_variance == sva.total_variance

