"""
Unit and regression tests for Deterministic Root-Cause Investigation Engine.
Verifies period-over-period variance calculation, waterfall reconciliation,
Pareto driver rankings, and evidence classifications.
"""

import pytest
from app.db import SessionLocal
from app.services.investigation import (
    InvestigationEngineService,
    generate_cache_key,
    get_cached_report,
    set_cached_report,
    clear_report_cache,
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_investigation_report_generation(db_session):
    """Verifies that the investigation report generates without errors on real data."""
    report = InvestigationEngineService.generate_report(
        db=db_session,
        baseline_period="2026-09",
        current_period="2026-10",
    )
    assert report is not None
    assert report.report_id.startswith("INV-")
    assert report.data_origin == "REAL"
    assert report.scope.datasets_analyzed == 4
    assert report.baseline_total_cost > 0
    assert report.current_total_cost > 0


def test_waterfall_bridge_reconciliation(db_session):
    """Verifies that the variance waterfall bridge strictly reconciles."""
    report = InvestigationEngineService.generate_report(
        db=db_session,
        baseline_period="2026-09",
        current_period="2026-10",
    )
    bridge = report.bridge
    assert bridge.reconciled is True
    assert bridge.unexplained_remainder == 0.0

    # Verify first step is START and last step is END
    assert bridge.steps[0].step_type == "START"
    assert bridge.steps[-1].step_type == "END"

    # Verify starting and ending amounts
    assert round(bridge.steps[0].amount, 2) == round(report.baseline_total_cost, 2)
    assert round(bridge.steps[-1].amount, 2) == round(report.current_total_cost, 2)


def test_findings_evidence_classification(db_session):
    """Verifies that all findings carry valid evidence classifications."""
    report = InvestigationEngineService.generate_report(
        db=db_session,
        baseline_period="2026-09",
        current_period="2026-10",
    )
    valid_classes = {"PROVEN", "OBSERVED", "OBSERVED_CORRELATION", "HYPOTHESIS", "LIMITATION", "UNAVAILABLE"}
    assert len(report.findings) >= 3

    for f in report.findings:
        assert f.evidence_classification in valid_classes
        assert f.title is not None
        assert f.short_explanation is not None

    # First finding should be PROVEN material concentration
    assert report.findings[0].evidence_classification == "PROVEN"
    assert "Material" in report.findings[0].title


def test_category_movements_sum_to_explained_variance(db_session):
    """Verifies that individual category movements match the bridge total explained."""
    report = InvestigationEngineService.generate_report(
        db=db_session,
        baseline_period="2026-09",
        current_period="2026-10",
    )
    assert len(report.category_breakdown) == 5

    cat_sum = sum(c.change_amount for c in report.category_breakdown)
    assert round(cat_sum, 2) == round(report.bridge.total_explained, 2)


def test_product_comparison_coverage(db_session):
    """Verifies product cost movements are computed for all active SKUs."""
    report = InvestigationEngineService.generate_report(
        db=db_session,
        baseline_period="2026-09",
        current_period="2026-10",
    )
    assert len(report.product_comparison) == 3
    sku_set = {p.product_code for p in report.product_comparison}
    assert "SPH-PRO-256" in sku_set
    assert "SPH-A15-256" in sku_set
    assert "SPH-A15-128" in sku_set

    for prod in report.product_comparison:
        assert prod.baseline_cost_per_unit > 0
        assert prod.current_cost_per_unit > 0
        assert prod.good_units_produced > 0


def test_cache_mechanism(db_session):
    """Verifies caching behavior."""
    clear_report_cache()
    key = generate_cache_key("2026-09", "2026-10")
    assert get_cached_report(key) is None

    report = InvestigationEngineService.generate_report(
        db=db_session,
        baseline_period="2026-09",
        current_period="2026-10",
    )
    set_cached_report(key, report)
    cached = get_cached_report(key)
    assert cached is not None
    assert cached.report_id == report.report_id


def test_durable_report_persistence_and_api(db_session):
    """
    Verifies that reports are permanently stored in Neon DB and survive
    an in-memory cache clear, and can be retrieved via FastAPI endpoints.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.investigation.report_cache import (
        persist_investigation_report,
        list_investigation_history,
    )

    client = TestClient(app)

    # 1. Generate report and persist to DB
    report = InvestigationEngineService.generate_report(
        db=db_session,
        baseline_period="2026-09",
        current_period="2026-10",
        inspection_id="test-insp-durable-001",
    )
    persist_investigation_report(
        db=db_session,
        report=report,
        inspection_id="test-insp-durable-001",
        title="Durable Test Report",
        status="COMPLETED",
    )

    # 2. Clear in-memory cache completely to simulate backend restart
    clear_report_cache()
    assert get_cached_report(report.report_id, db=None) is None

    # 3. Retrieve from DB via get_cached_report with db_session
    restored = get_cached_report(report.report_id, db=db_session)
    assert restored is not None
    assert restored.report_id == report.report_id
    assert restored.current_total_cost == report.current_total_cost

    # 4. Test GET /api/investigation/reports (history list)
    resp = client.get("/api/investigation/reports")
    assert resp.status_code == 200
    history = resp.json()
    assert isinstance(history, list)
    assert any(h["report_id"] == report.report_id for h in history)

    # 5. Test GET /api/investigation/report/{report_id}
    resp = client.get(f"/api/investigation/report/{report.report_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_id"] == report.report_id
    assert "bridge" in data
    assert "findings" in data

    # 6. Test GET /api/investigation/report/{non_existent} returns 404
    resp_404 = client.get("/api/investigation/report/non-existent-report-99999")
    assert resp_404.status_code == 404

    # 7. Clean up test record to prevent test pollution of production investigation history
    try:
        from app.models.agent_records import InvestigationReportRecord
        db_session.query(InvestigationReportRecord).filter_by(report_id=report.report_id).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()


def test_single_uploaded_cost_csv_isolation(db_session):
    """
    TEST A, B, C: Verifies that uploading ONLY ONE manufacturing cost CSV:
    1. Analyzes ONLY the uploaded file rows (strict boundary isolation).
    2. Does NOT query or combine the 5,000 historical Neon DB records.
    3. Produces exact actual totals from the uploaded rows.
    4. Sets production matching, unit costs, and output quantities to UNAVAILABLE (None).
    5. Marks PPV and operational yield findings as UNAVAILABLE.
    """
    custom_cost_rows = [
        {
            "cost_record_id": f"TEST-CST-{i}",
            "posting_ts": f"2026-10-{i+1:02d}T10:00:00",
            "plant_id": "PLANT-A",
            "line_id": "LINE-1",
            "product_id": "CUSTOM-WIDGET-01",
            "produced_qty": "100",
            "material_cost_inr": "50000.00",
            "labour_cost_inr": "10000.00",
            "machine_cost_inr": "5000.00",
            "energy_cost_inr": "2000.00",
            "scrap_rework_cost_inr": "1000.00",
            "total_direct_cost_inr": "68000.00",
        }
        for i in range(10)
    ]

    inspection_datasets = {
        "MANUFACTURING_COST": {
            "filename": "custom_single_cost.csv",
            "dataset_type": "MANUFACTURING_COST",
            "rows": custom_cost_rows,
            "column_mapping": {
                "posting_ts": "posting_ts",
                "plant_id": "plant_id",
                "line_id": "line_id",
                "product_id": "product_id",
                "produced_qty": "produced_qty",
                "material_cost_inr": "material_cost_inr",
                "labour_cost_inr": "labour_cost_inr",
                "machine_cost_inr": "machine_cost_inr",
                "energy_cost_inr": "energy_cost_inr",
                "scrap_rework_cost_inr": "scrap_rework_cost_inr",
                "total_direct_cost_inr": "total_direct_cost_inr",
            },
            "valid_count": 10,
            "rejected_count": 0,
        }
    }

    report = InvestigationEngineService.generate_report(
        db=db_session,
        inspection_id="insp_test_single_csv",
        uploaded_files=["custom_single_cost.csv"],
        inspection_datasets=inspection_datasets,
    )

    # 1. Scope verifies strict upload boundary
    assert report.scope.datasets_analyzed == 1
    assert report.scope.cost_records_count == 10
    assert report.scope.products_count == 1
    assert "unavailable" in report.scope.matched_production_label.lower()

    # 2. Financial totals strictly match the 10 custom rows (10 * 68,000 = 680,000), NOT 14.02B
    assert report.current_total_cost == 680000.00
    assert report.category_breakdown[0].current_amount == 500000.00  # Material
    assert report.category_breakdown[1].current_amount == 100000.00  # Labour

    # 3. Denominators and unit costs are UNAVAILABLE (None)
    assert report.current_cost_per_good_unit is None
    assert report.current_produced_qty is None
    assert report.current_good_qty is None
    assert report.baseline_cost_per_good_unit is None

    # 4. Product cost comparison has unit cost set to None
    assert len(report.product_comparison) == 1
    prod = report.product_comparison[0]
    assert prod.product_code == "CUSTOM-WIDGET-01"
    assert prod.current_cost_per_unit is None
    assert prod.good_units_produced is None
    assert prod.current_total_cost == 680000.00

    # 5. Root-Cause Findings check
    classifications = {f.finding_id: f.evidence_classification for f in report.findings}
    assert classifications.get("FND-01") == "PROVEN"  # Material Concentration
    assert classifications.get("FND-03") == "UNAVAILABLE"  # PPV/MUV Split
    assert classifications.get("FND-04") == "UNAVAILABLE"  # Operational Output / Production


def test_multi_dataset_cost_and_production_matching(db_session):
    """
    Verifies that uploading BOTH cost and production datasets enables matching,
    good unit calculations, and production metrics without querying global DB tables.
    """
    cost_rows = [
        {
            "posting_ts": "2026-10-01T10:00:00",
            "plant_id": "PLANT-A",
            "line_id": "LINE-1",
            "product_id": "SPH-PRO-256",
            "material_cost_inr": "90000",
            "labour_cost_inr": "5000",
            "machine_cost_inr": "3000",
            "energy_cost_inr": "1500",
            "scrap_rework_cost_inr": "500",
            "total_direct_cost_inr": "100000",
        }
    ]
    prod_rows = [
        {
            "event_date": "2026-10-01",
            "plant_id": "PLANT-A",
            "line_id": "LINE-1",
            "product_id": "SPH-PRO-256",
            "actual_qty": "100",
            "good_qty": "95",
            "reject_qty": "5",
        }
    ]

    inspection_datasets = {
        "MANUFACTURING_COST": {
            "filename": "cost.csv",
            "dataset_type": "MANUFACTURING_COST",
            "rows": cost_rows,
            "column_mapping": {
                "posting_ts": "posting_ts",
                "plant_id": "plant_id",
                "line_id": "line_id",
                "product_id": "product_id",
                "material_cost_inr": "material_cost_inr",
                "labour_cost_inr": "labour_cost_inr",
                "machine_cost_inr": "machine_cost_inr",
                "energy_cost_inr": "energy_cost_inr",
                "scrap_rework_cost_inr": "scrap_rework_cost_inr",
                "total_direct_cost_inr": "total_direct_cost_inr",
            },
            "valid_count": 1,
        },
        "HOURLY_PRODUCTION": {
            "filename": "production.csv",
            "dataset_type": "HOURLY_PRODUCTION",
            "rows": prod_rows,
            "column_mapping": {
                "event_date": "event_date",
                "plant_id": "plant_id",
                "line_id": "line_id",
                "product_id": "product_id",
                "actual_qty": "actual_qty",
                "good_qty": "good_qty",
                "reject_qty": "reject_qty",
            },
            "valid_count": 1,
        },
    }

    report = InvestigationEngineService.generate_report(
        db=db_session,
        inspection_id="insp_multi_dataset",
        uploaded_files=["cost.csv", "production.csv"],
        inspection_datasets=inspection_datasets,
    )

    assert report.scope.datasets_analyzed == 2
    assert "matched" in report.scope.matched_production_label.lower()
    assert report.current_total_cost == 100000.0
    assert report.current_good_qty == 95.0
    assert report.current_produced_qty == 100.0
    assert report.current_cost_per_good_unit == round(100000.0 / 95.0, 2)



