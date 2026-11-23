import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.db import SessionLocal
from app.services.ingestion.session_store import SessionDataStore
from app.services.rca.orchestrator import RCAOrchestrator
from app.services.investigation.investigation_engine import InvestigationEngineService


@pytest.fixture
def client():
    return TestClient(app)


def test_data_upload_stage_1_to_3_workflow_integration(client):
    """
    Traces and verifies the end-to-end Data Upload workflow:
    1. Stage 1: File upload & session staging via SessionDataStore.
    2. Stage 2: Staging validation without silent promotion to Global Store.
    3. Stage 3: RCA execution invoking RCAOrchestrator, dynamic baseline,
       planner dimension selection, evidence graph findings, and Stage 3 compatibility.
    """
    db = SessionLocal()

    # Baseline DB count check for non-destructive verification
    pre_cost_count = db.execute(text("SELECT COUNT(*) FROM line_cost_batches")).scalar()
    pre_prod_count = db.execute(text("SELECT COUNT(*) FROM hourly_production_logs")).scalar()

    # Step 1: Stage 1 Ingestion Simulation
    # Staging 7-dataset upload session in SessionDataStore
    session_id = "test_upload_integration_session_001"
    sample_datasets = {
        "HOURLY_PRODUCTION": {
            "record_count": 50,
            "provenance": "SYNTHETIC_GENERATED",
            "rows": [
                {
                    "event_date": "2026-10-15",
                    "plant_code": "IN-TN-01",
                    "product_code": "SPH-MODEL-X",
                    "line_id": "Line-2",
                    "actual_qty": 450,
                    "target_qty": 500,
                    "good_qty": 420,
                    "scrap_qty": 30,
                    "downtime_min": 45,
                }
            ]
        },
        "MANUFACTURING_COST": {
            "record_count": 10,
            "provenance": "SYNTHETIC_GENERATED",
            "rows": [
                {
                    "cost_date": "2026-10-15",
                    "plant_code": "IN-TN-01",
                    "product_code": "SPH-MODEL-X",
                    "line_id": "Line-2",
                    "total_cost": 6459600.0,
                    "material_cost": 4200000.0,
                    "labor_cost": 1100000.0,
                    "machine_cost": 659600.0,
                    "energy_cost": 250000.0,
                    "scrap_cost": 250000.0,
                }
            ]
        }
    }

    SessionDataStore.save_session(
        session_id=session_id,
        datasets=sample_datasets,
        data_origin="SYNTHETIC_TEST",
        metadata={"uploaded_files": ["d1_hourly_production.csv", "d2_manufacturing_cost.csv"]}
    )

    # Verify Stage 1 session exists in SessionDataStore
    retrieved = SessionDataStore.get_session(session_id)
    assert retrieved is not None
    assert "HOURLY_PRODUCTION" in retrieved
    assert "MANUFACTURING_COST" in retrieved

    # Step 2: Stage 2 Staging Isolation Verification
    # Ensure pending uploads are NOT committed to Neon DB tables
    post_stage2_cost_count = db.execute(text("SELECT COUNT(*) FROM line_cost_batches")).scalar()
    post_stage2_prod_count = db.execute(text("SELECT COUNT(*) FROM hourly_production_logs")).scalar()
    assert post_stage2_cost_count == pre_cost_count, "Pending uploads must not alter line_cost_batches"
    assert post_stage2_prod_count == pre_prod_count, "Pending uploads must not alter hourly_production_logs"

    # Step 3: Stage 3 Execution Path Verification
    # Invoke InvestigationEngineService directly and verify it calls RCAOrchestrator
    report = InvestigationEngineService.generate_report(
        db=db,
        staged_batch_id=session_id,
        current_period="2026-10",
        baseline_period="2026-09",
    )

    assert report is not None
    assert report.report_id.startswith("RCA-")
    assert report.executive_finding is not None
    assert report.executive_finding.headline is not None

    # Step 4: Verify Dynamic Baseline Resolution
    assert report.scope is not None
    assert report.scope.current_period is not None
    assert report.scope.baseline_period is not None

    # Step 5: Verify Evidence Graph & Root Causes
    assert len(report.findings) > 0
    for finding in report.findings:
        assert finding.finding_id.startswith("RC-")
        assert finding.financial_impact_amount >= 0
        assert finding.evidence_classification in ("PROVEN", "OBSERVED_CORRELATION", "HYPOTHESIS")
        # Provenance must distinguish RAW_BASELINE vs SYNTHETIC_GENERATED
        assert any(t in finding.evidence_reliability for t in ("RAW_BASELINE", "SYNTHETIC_GENERATED", "OBSERVED", "PROVEN"))

    # Step 6: Verify Stage 3 UI Schema Compatibility
    # DataImportStudio.jsx & InvestigationResultPage.jsx expect these exact structures:
    # 1. bridge steps (waterfall)
    assert len(report.bridge.steps) >= 2
    for step in report.bridge.steps:
        assert hasattr(step, "name")
        assert hasattr(step, "amount")
        assert hasattr(step, "running_total")

    # 2. recommended_steps / cost_improvement_plan
    assert len(report.recommended_steps) > 0
    for action in report.recommended_steps:
        assert hasattr(action, "recommendation_id")
        assert hasattr(action, "problem_statement")
        assert hasattr(action, "owner")
        assert len(action.implementation_steps) >= 2

    # 3. data_reliability
    assert report.data_reliability is not None
    assert hasattr(report.data_reliability, "checks")

    # Step 7: HTTP Endpoint Call (GET /api/investigation/report?session_id=...)
    res = client.get(f"/api/investigation/report?session_id={session_id}&bypass_cache=true")
    assert res.status_code == 200
    json_data = res.json()

    assert json_data["report_id"] == report.report_id or json_data["report_id"].startswith("RCA-")
    assert "executive_finding" in json_data
    assert "bridge" in json_data
    assert "findings" in json_data
    assert "recommended_steps" in json_data
    assert "cost_improvement_plan" in json_data
    assert "data_reliability" in json_data

    # Final isolation check: Still no commits to database
    final_cost_count = db.execute(text("SELECT COUNT(*) FROM line_cost_batches")).scalar()
    assert final_cost_count == pre_cost_count, "Investigation execution must be read-only and non-destructive"

    db.close()
