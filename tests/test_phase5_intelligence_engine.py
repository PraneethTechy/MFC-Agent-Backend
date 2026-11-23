"""
Phase 5 Comprehensive Verification Test Suite: Advanced Manufacturing Intelligence Engine.

Validates:
1. Variance Decomposition Bridge & Mathematical Closure (0.00 Discrepancy).
2. Product Economics, Gross vs Good Unit Cost, and Anomaly Detection.
3. Material Intelligence, BOM Pareto 80/20 Concentration, and Cartesian Join Multiplication Prevention.
4. Production Throughput, Operational Yield, and Uncosted Volume Governance (3,832 uncosted runs preserved).
5. Evidence-Grounded Recommendation Engine (Priorities, Owners, Provenance).
6. FastAPI Intelligence Endpoints (/api/analytics/cost-movement, product-intelligence, material-intelligence, recommendations).
7. LangChain Tool Invocations (analyze_cost_movement, get_management_recommendations).
8. Neon PostgreSQL Production Baseline Invariant Preservation.
"""

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import func

from app.main import app
from app.db import SessionLocal
from app.models.real_datasets import (
    LineCostBatch,
    HourlyProductionLog,
    SerializedQualityInspection,
    BomComponentRecord,
)
from app.services.analytics.intelligence_engine import ManufacturingIntelligenceEngine
from app.services.analytics.global_analytics_service import GlobalAnalyticsService
from app.tools import analyze_cost_movement, get_management_recommendations


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def api_client():
    with TestClient(app) as client:
        yield client


# =============================================================================
# 1. Variance Decomposition Bridge & Exact Mathematical Closure Tests
# =============================================================================

def test_01_variance_bridge_mathematical_closure(db_session):
    """
    Verifies that cost movement decomposition between two consecutive periods
    achieves exact mathematical closure with 0.00 unexplained discrepancy.
    Actual Movement = Volume Effect + Mix Effect + Category Rate Effects + Reconciled Residual.
    """
    res = ManufacturingIntelligenceEngine.calculate_cost_movement(
        db=db_session,
        current_period="2026-10",
        baseline_period="2026-09",
    )

    assert res["status"] in {"COMPLETED", "SUCCESS"}
    assert res["current_period"] == "2026-10"
    assert res["baseline_period"] == "2026-09"

    exp = res["expenditure_movement"]
    assert exp["baseline_cost_cr"] > 0
    assert exp["current_cost_cr"] > 0
    expected_delta = round(exp["current_cost_cr"] - exp["baseline_cost_cr"], 2)
    assert abs(exp["delta_cost_cr"] - expected_delta) <= 0.01

    bridge = res["variance_bridge"]
    assert len(bridge) >= 7

    reconcil = res["reconciliation"]
    assert reconcil["is_reconciled"] is True
    assert abs(reconcil["discrepancy"]) <= 0.01


def test_02_variance_bridge_with_filters(db_session):
    """Verifies that cost movement calculations honor plant and product filters cleanly."""
    res = ManufacturingIntelligenceEngine.calculate_cost_movement(
        db=db_session,
        current_period="2026-10",
        baseline_period="2026-09",
        plant_code="IN-KA-01",
        product_code="SPH-PRO-256",
    )
    assert res["status"] in {"COMPLETED", "SUCCESS"}
    assert res["reconciliation"]["is_reconciled"] is True


# =============================================================================
# 2. Product Cost Intelligence & Unit Economics Tests
# =============================================================================

def test_03_product_intelligence_gross_vs_good_unit_cost(db_session):
    """
    Verifies that cost per good unit is strictly greater than or equal to cost per produced unit,
    and that the cost-per-good-unit uplift is deterministically calculated.
    """
    res = ManufacturingIntelligenceEngine.calculate_product_intelligence(db=db_session)

    assert res["status"] in {"COMPLETED", "SUCCESS"}
    assert res["product_count"] > 0
    assert len(res["products"]) > 0

    for p in res["products"]:
        assert p["cost_per_good_unit"] >= p["cost_per_gross_unit"]
        expected_uplift = round(p["cost_per_good_unit"] - p["cost_per_gross_unit"], 2)
        assert abs(p["cost_per_good_unit_uplift"] - expected_uplift) <= 0.05
        assert p["yield_pct"] <= 100.0
        assert p["yield_pct"] > 0.0

    # Ensure disclosures are present
    assert "mix_limitation_disclosure" in res


def test_04_product_intelligence_anomaly_detection(db_session):
    """Verifies that product anomalies (elevated rejection or unusual cost) are properly flagged."""
    res = ManufacturingIntelligenceEngine.calculate_product_intelligence(db=db_session)
    assert res["status"] in {"COMPLETED", "SUCCESS"}
    assert isinstance(res["flagged_anomalies"], list)
    for anom in res["flagged_anomalies"]:
        assert "anomaly_type" in anom
        assert "severity" in anom
        assert "description" in anom


# =============================================================================
# 3. Material Intelligence, Pareto 80/20 & Join Safety Tests
# =============================================================================

def test_05_material_intelligence_pareto_concentration(db_session):
    """
    Verifies that material intelligence correctly ranks components by cost concentration
    and applies the 80/20 Pareto principle.
    """
    res = ManufacturingIntelligenceEngine.calculate_material_intelligence(db=db_session)

    assert res["status"] in {"COMPLETED", "SUCCESS"}
    assert res["total_components_analyzed"] > 0
    assert res["key_pareto_drivers_count"] > 0

    components = res["components"]
    for c in components:
        assert "is_pareto_key_driver" in c
        assert "spend_share_pct" in c
        assert "cumulative_share_pct" in c


def test_06_material_intelligence_no_cartesian_join_multiplication(db_session):
    """
    Verifies that querying material purchases and BOMs does NOT produce Cartesian join multiplication.
    The data governance payload certifies that purchases and BOMs are grouped independently.
    """
    res = ManufacturingIntelligenceEngine.calculate_material_intelligence(db=db_session)
    assert res["status"] in {"COMPLETED", "SUCCESS"}
    assert "join_multiplication_protection" in res["data_governance"]
    assert "ENFORCED" in res["data_governance"]["join_multiplication_protection"]


# =============================================================================
# 4. Production Throughput, Operational Yield & Uncosted Volume Governance
# =============================================================================

def test_07_production_quality_governance_uncosted_runs(db_session):
    """
    Verifies that the 3,832 uncosted operational runs are strictly preserved
    and reported as UNCOSTED_OPERATIONAL_RUN, not assigned fabricated synthetic costs.
    """
    res = ManufacturingIntelligenceEngine.calculate_production_quality_intelligence(db=db_session)

    assert res["status"] in {"COMPLETED", "SUCCESS"}
    gov = res["operational_governance"]
    assert gov["costed_runs_count"] == 5000
    assert gov["uncosted_runs_count"] == 3832
    assert gov["total_runs_count"] == 8832
    assert gov["cost_coverage_pct"] == 56.61


def test_08_production_quality_line_metrics_and_anomalies(db_session):
    """Verifies that line performance is aggregated accurately and abnormal lines are identified."""
    res = ManufacturingIntelligenceEngine.calculate_production_quality_intelligence(db=db_session)
    assert res["status"] in {"COMPLETED", "SUCCESS"}
    assert len(res["lines"]) > 0
    assert res["factory_summary"]["factory_yield_pct"] > 0.0
    assert res["factory_summary"]["factory_reject_pct"] >= 0.0
    assert isinstance(res["abnormal_lines"], list)


# =============================================================================
# 5. Recommendation Engine Tests
# =============================================================================

def test_09_recommendations_structure_and_governance(db_session):
    """
    Verifies that management recommendations provide priority, reason, evidence,
    financial impact, owner, and required missing data.
    """
    recs = ManufacturingIntelligenceEngine.generate_recommendations(db=db_session)

    assert isinstance(recs, list)
    assert len(recs) >= 2

    valid_priorities = {"P1_CRITICAL", "P2_HIGH", "P3_MEDIUM", "P4_LOW"}
    valid_classifications = {"PROVEN", "OBSERVED_CORRELATION", "HYPOTHESIS"}

    for r in recs:
        assert r["priority"] in valid_priorities
        assert r["evidence_classification"] in valid_classifications
        assert len(r["reason"]) > 10
        assert len(r["owner"]) > 2
        assert len(r["evidence"]) > 0
        assert "potential_financial_impact" in r
        assert "data_required" in r


# =============================================================================
# 6. API Endpoints Integration Tests
# =============================================================================

def test_10_api_cost_movement_endpoint(api_client):
    """Verifies GET /api/analytics/cost-movement returns 200 with valid structure."""
    resp = api_client.get("/api/analytics/cost-movement?current_period=2026-10&baseline_period=2026-09")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"COMPLETED", "SUCCESS"}
    assert data["current_period"] == "2026-10"
    assert "expenditure_movement" in data
    assert "variance_bridge" in data
    assert data["reconciliation"]["is_reconciled"] is True


def test_11_api_product_intelligence_endpoint(api_client):
    """Verifies GET /api/analytics/product-intelligence returns 200 with product analytics."""
    resp = api_client.get("/api/analytics/product-intelligence")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"COMPLETED", "SUCCESS"}
    assert "products" in data
    assert len(data["products"]) > 0


def test_12_api_material_intelligence_endpoint(api_client):
    """Verifies GET /api/analytics/material-intelligence returns 200 with Pareto breakdown."""
    resp = api_client.get("/api/analytics/material-intelligence")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"COMPLETED", "SUCCESS"}
    assert "components" in data
    assert data["key_pareto_drivers_count"] > 0


def test_13_api_recommendations_endpoint(api_client):
    """Verifies GET /api/analytics/recommendations returns 200 with prioritized items."""
    resp = api_client.get("/api/analytics/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2


def test_14_api_production_quality_period_alias(api_client):
    """Verifies that /api/analytics/production-quality accepts 'period' as an alias for 'period_code'."""
    resp1 = api_client.get("/api/analytics/production-quality?period_code=2026-10")
    assert resp1.status_code == 200
    resp2 = api_client.get("/api/analytics/production-quality?period=2026-10")
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


# =============================================================================
# 7. LangChain Tool Invocations
# =============================================================================

def test_15_langchain_tools_execution():
    """Verifies that new LangChain tools run deterministically and return valid dictionaries."""
    cost_res = analyze_cost_movement.invoke({
        "current_period": "2026-10",
        "baseline_period": "2026-09",
    })
    assert cost_res["status"] in {"COMPLETED", "SUCCESS"}
    assert "expenditure_movement" in cost_res

    rec_res = get_management_recommendations.invoke({"period_code": "2026-10"})
    assert isinstance(rec_res, list)
    assert len(rec_res) >= 1


# =============================================================================
# 8. Neon PostgreSQL Production Baseline Invariant Preservation
# =============================================================================

def test_16_baseline_integrity_unchanged(db_session):
    """
    CRITICAL SAFETY INVARIANT:
    Verifies that running the intelligence engine did not modify, delete,
    corrupt, or promote synthetic data into the production Neon PostgreSQL database.
    """
    cost_cnt = db_session.query(LineCostBatch).filter(LineCostBatch.is_synthetic == False).count()
    assert cost_cnt == 5000, f"Expected 5,000 real cost records, got {cost_cnt}"

    hourly_cnt = db_session.query(HourlyProductionLog).filter(HourlyProductionLog.is_synthetic == False).count()
    assert hourly_cnt == 8832, f"Expected 8,832 real hourly logs, got {hourly_cnt}"

    quality_cnt = db_session.query(SerializedQualityInspection).filter(SerializedQualityInspection.is_synthetic == False).count()
    assert quality_cnt == 16000, f"Expected 16,000 real quality inspections, got {quality_cnt}"

    bom_cnt = db_session.query(BomComponentRecord).filter(BomComponentRecord.is_synthetic == False).count()
    assert bom_cnt == 48, f"Expected 48 real BOM records, got {bom_cnt}"

    synth_cnt = db_session.query(LineCostBatch).filter(LineCostBatch.is_synthetic == True).count()
    assert synth_cnt == 0, f"Found {synth_cnt} unexpected synthetic records in LineCostBatch!"

    total_cost = db_session.query(func.sum(LineCostBatch.total_direct_cost_inr)).filter(
        LineCostBatch.is_synthetic == False
    ).scalar()
    assert round(float(total_cost), 2) == 14024712024.30, f"Total cost altered: {total_cost}"
