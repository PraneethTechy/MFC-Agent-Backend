"""
Test Suite: Overview Provenance Data Modes and Global Store Integrity
Validates:
1. PRODUCTION mode strictly excludes synthetic records (returns exactly 5,000 baseline records, ₹1,402.47 Cr, 1,369,863 costed units, 2,424,184 MES units).
2. DEMO mode includes eligible committed synthetic records (returns 6,800 records, ₹2,008.36 Cr, 1,930,948 costed units, 2,985,269 MES units).
3. Both modes exclude staged/unapproved uploads.
4. All Overview metrics apply the same provenance policy consistently.
5. Changing modes does not modify database records.
6. Existing date, plant, product, and line filters continue working across both modes.
7. Backend restart / settings preserve the configured mode.
"""

import os
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import func

from app.main import app
from app.config import settings
from app.db import SessionLocal
from app.models.real_datasets import LineCostBatch, HourlyProductionLog


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_01_production_mode_excludes_synthetic_records(client):
    """Verifies PRODUCTION mode excludes synthetic records across all metrics."""
    res = client.get("/api/dashboard/overview?data_mode=PRODUCTION")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()

    assert data["data_mode"] == "PRODUCTION"

    # Provenance Composition
    comp = data["provenance_composition"]
    assert comp["data_mode"] == "PRODUCTION"
    assert comp["synthetic_cost_records"] == 0
    assert comp["real_cost_records"] == 5000
    assert comp["total_cost_records"] == 5000
    assert comp["is_pure_production"] is True
    assert comp["synthetic_cost_cr"] == 0.0
    assert comp["real_cost_cr"] == 1402.47

    # KPIs
    kpis = data["kpis"]
    assert abs(kpis["total_direct_cost_inr"] - 14024712024.30) < 1.0
    assert kpis["total_direct_cost_cr"] == 1402.47
    assert kpis["total_costed_units"] == 1369863.0
    assert kpis["direct_costed_batches"] == 5000

    # Production Performance (MES)
    prod = data["production"]
    assert prod["total_produced"] == 2424184.0
    assert prod["good_output"] == 2378960.0
    assert prod["rejected_output"] == 45224.0
    assert prod["yield_pct"] == 98.13
    assert prod["is_synthetic"] is False
    assert prod["data_origin"] == "REAL_PRODUCTION_BASELINE"

    # Monthly Trend (Aug, Sep, Oct baseline months only)
    trend = data["monthly_trend"]
    assert len(trend) == 3
    months = [m["month"] for m in trend]
    assert months == ["2026-08", "2026-09", "2026-10"]


def test_02_demo_mode_includes_eligible_committed_synthetic_records(client):
    """Verifies DEMO mode includes eligible committed synthetic records."""
    res = client.get("/api/dashboard/overview?data_mode=DEMO")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()

    assert data["data_mode"] == "DEMO"

    # Provenance Composition
    comp = data["provenance_composition"]
    assert comp["data_mode"] == "DEMO"
    assert comp["real_cost_records"] == 5000
    assert comp["synthetic_cost_records"] == 1800
    assert comp["total_cost_records"] == 6800
    assert comp["real_cost_cr"] == 1402.47
    assert comp["synthetic_cost_cr"] == 605.89
    assert comp["total_cost_cr"] == 2008.36

    # KPIs
    kpis = data["kpis"]
    assert abs(kpis["total_direct_cost_inr"] - 20083564541.35) < 1.0
    assert kpis["total_direct_cost_cr"] == 2008.36
    assert kpis["total_costed_units"] == 1930948.0
    assert kpis["direct_costed_batches"] == 6800

    # Production Performance (MES)
    prod = data["production"]
    assert prod["total_produced"] == 2985269.0
    assert prod["good_output"] == 2928606.0
    assert prod["rejected_output"] == 56663.0
    assert prod["yield_pct"] == 98.10
    assert prod["is_synthetic"] is True

    # Monthly Trend (Aug, Sep, Oct, Nov)
    trend = data["monthly_trend"]
    assert len(trend) == 4
    months = [m["month"] for m in trend]
    assert months == ["2026-08", "2026-09", "2026-10", "2026-11"]


def test_03_both_modes_exclude_staged_unapproved_uploads(client, db):
    """Verifies that unapproved staging records (is_current=False) never appear in either mode."""
    existing_batch_id = db.query(LineCostBatch.ingestion_batch_id).first()[0]
    test_record = LineCostBatch(
        cost_record_id="CST-STAGING-TEST-9999",
        production_order_id="ORD-STAGING-9999",
        plant_code="IN-KA-01",
        line_code="Line 1",
        product_code="SPH-PRO-256",
        posting_ts=datetime(2026, 12, 1, 10, 0, 0, tzinfo=timezone.utc),
        produced_qty=Decimal("99999"),
        material_cost_inr=Decimal("10000000.00"),
        labour_cost_inr=Decimal("1000000.00"),
        machine_cost_inr=Decimal("500000.00"),
        energy_cost_inr=Decimal("200000.00"),
        scrap_rework_cost_inr=Decimal("100000.00"),
        total_direct_cost_inr=Decimal("11800000.00"),
        source_standard_cost_per_unit=Decimal("100.00"),
        costing_version="STD-2026-V1",
        currency="INR",
        ingestion_batch_id=existing_batch_id,
        is_synthetic=False,
        is_current=False,  # Unapproved staged record
        created_at=datetime.now(timezone.utc),
    )
    db.add(test_record)
    db.commit()

    try:
        # Check PRODUCTION mode
        res_prod = client.get("/api/dashboard/overview?data_mode=PRODUCTION").json()
        assert res_prod["provenance_composition"]["total_cost_records"] == 5000
        assert res_prod["kpis"]["total_costed_units"] == 1369863.0
        assert res_prod["kpis"]["total_direct_cost_cr"] == 1402.47

        # Check DEMO mode
        res_demo = client.get("/api/dashboard/overview?data_mode=DEMO").json()
        assert res_demo["provenance_composition"]["total_cost_records"] == 6800
        assert res_demo["kpis"]["total_costed_units"] == 1930948.0
        assert res_demo["kpis"]["total_direct_cost_cr"] == 2008.36
    finally:
        db.query(LineCostBatch).filter(LineCostBatch.cost_record_id == "CST-STAGING-TEST-9999").delete()
        db.commit()


def test_04_all_overview_metrics_apply_same_provenance_policy(client):
    """Verifies mathematical consistency across all cards for both policies."""
    for mode, expected_cr, expected_mes_out in [
        ("PRODUCTION", 1402.47, 2424184.0),
        ("DEMO", 2008.36, 2985269.0),
    ]:
        res = client.get(f"/api/dashboard/overview?data_mode={mode}")
        assert res.status_code == 200
        d = res.json()

        # 1. KPI Total Cost matches category breakdown sum
        total_inr = d["kpis"]["total_direct_cost_inr"]
        cat_sum_inr = sum(c["actual_cost_inr"] for c in d["categories"])
        assert abs(total_inr - cat_sum_inr) < 1.0, f"Mode {mode}: Categories sum mismatch"

        # 2. Monthly trend sum matches total cost
        trend_sum_inr = sum(m["cost_inr"] for m in d["monthly_trend"])
        assert abs(total_inr - trend_sum_inr) < 1.0, f"Mode {mode}: Monthly trend sum mismatch"

        # 3. Products sum matches total cost
        prod_sum_inr = sum(p["total_expenditure_inr"] for p in d["products"])
        assert abs(total_inr - prod_sum_inr) < 1.0, f"Mode {mode}: Products sum mismatch"

        # 4. Sankey production reconciliation
        prod = d["production"]
        assert prod["total_produced"] == prod["good_output"] + prod["rejected_output"]
        assert prod["total_produced"] == expected_mes_out


def test_05_changing_modes_does_not_modify_database_records(client, db):
    """Verifies that requesting different data modes does not mutate database records."""
    count_cost_before = db.query(func.count(LineCostBatch.id)).scalar()
    count_mes_before = db.query(func.count(HourlyProductionLog.id)).scalar()
    sum_cost_before = db.query(func.sum(LineCostBatch.total_direct_cost_inr)).scalar()

    # Perform multiple mode switches
    client.get("/api/dashboard/overview?data_mode=PRODUCTION")
    client.get("/api/dashboard/overview?data_mode=DEMO")
    client.get("/api/dashboard/overview?data_mode=PRODUCTION")
    client.get("/api/dashboard/overview?data_mode=DEMO")

    count_cost_after = db.query(func.count(LineCostBatch.id)).scalar()
    count_mes_after = db.query(func.count(HourlyProductionLog.id)).scalar()
    sum_cost_after = db.query(func.sum(LineCostBatch.total_direct_cost_inr)).scalar()

    assert count_cost_before == count_cost_after == 6800
    assert count_mes_before == count_mes_after == 10632
    assert abs(float(sum_cost_before) - float(sum_cost_after)) < 0.001


def test_06_scope_filters_work_consistently_across_both_modes(client):
    """Verifies plant, product, line, and date filters work in both modes."""
    for mode in ["PRODUCTION", "DEMO"]:
        # Plant filter
        res = client.get(f"/api/dashboard/overview?data_mode={mode}&plant_code=IN-KA-01")
        assert res.status_code == 200
        d = res.json()
        assert d["kpis"]["direct_costed_batches"] > 0
        assert d["kpis"]["total_direct_cost_cr"] > 0

        # Product filter
        res = client.get(f"/api/dashboard/overview?data_mode={mode}&product_code=SPH-PRO-256")
        assert res.status_code == 200
        d = res.json()
        assert len(d["products"]) == 1
        assert d["products"][0]["product_code"] == "SPH-PRO-256"

        # Date range filter (September only)
        res = client.get(f"/api/dashboard/overview?data_mode={mode}&start_date=2026-09-01&end_date=2026-09-30")
        assert res.status_code == 200
        d = res.json()
        assert len(d["monthly_trend"]) == 1
        assert d["monthly_trend"][0]["month"] == "2026-09"


def test_07_backend_configuration_preserves_configured_default_mode(client):
    """Verifies that settings.data_mode governs default behavior when no query param is sent."""
    original_mode = getattr(settings, "data_mode", "DEMO")

    try:
        # Default with DEMO
        settings.data_mode = "DEMO"
        res_default = client.get("/api/dashboard/overview").json()
        assert res_default["data_mode"] == "DEMO"
        assert res_default["provenance_composition"]["total_cost_records"] == 6800

        # Change settings to PRODUCTION
        settings.data_mode = "PRODUCTION"
        res_prod_default = client.get("/api/dashboard/overview").json()
        assert res_prod_default["data_mode"] == "PRODUCTION"
        assert res_prod_default["provenance_composition"]["total_cost_records"] == 5000
    finally:
        settings.data_mode = original_mode
