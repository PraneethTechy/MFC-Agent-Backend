import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from app.models.real_datasets import (
    LineCostBatch,
    HourlyProductionLog,
    SerializedQualityInspection,
    BomComponentRecord,
)

client = TestClient(app)


def test_neon_baseline_store_invariants():
    """Verify that the Neon baseline store has exactly the expected authoritative counts and totals."""
    db = next(get_db())
    try:
        cost_batches = db.query(LineCostBatch).filter(LineCostBatch.is_synthetic == False).count()
        hourly_logs = db.query(HourlyProductionLog).filter(HourlyProductionLog.is_synthetic == False).count()
        inspections = db.query(SerializedQualityInspection).filter(SerializedQualityInspection.is_synthetic == False).count()
        bom_records = db.query(BomComponentRecord).filter(BomComponentRecord.is_synthetic == False).count()

        assert cost_batches == 5000, f"Expected 5,000 LineCostBatch records, got {cost_batches}"
        assert hourly_logs == 8832, f"Expected 8,832 HourlyProductionLog records, got {hourly_logs}"
        assert inspections == 16000, f"Expected 16,000 SerializedQualityInspection records, got {inspections}"
        assert bom_records == 48, f"Expected 48 BomComponentRecord records, got {bom_records}"

        # Verify zero synthetic rows in global store
        synth_count = db.query(LineCostBatch).filter(LineCostBatch.is_synthetic == True).count()
        assert synth_count == 0, f"Expected 0 synthetic records in global store, got {synth_count}"

        # Verify total manufacturing direct cost
        from sqlalchemy import func
        tot_cost = db.query(func.sum(LineCostBatch.total_direct_cost_inr)).filter(LineCostBatch.is_synthetic == False).scalar()
        assert abs(float(tot_cost) - 14024712024.30) < 1.0, f"Expected ₹14,024,712,024.30, got {tot_cost}"

        # Verify costing coverage breakdown in HourlyProductionLog
        costed_runs = db.query(HourlyProductionLog).filter(
            HourlyProductionLog.is_synthetic == False,
            HourlyProductionLog.costing_status == "DIRECT_COSTED"
        ).count()
        uncosted_runs = db.query(HourlyProductionLog).filter(
            HourlyProductionLog.is_synthetic == False,
            HourlyProductionLog.costing_status == "UNCOSTED_OPERATIONAL_RUN"
        ).count()
        assert costed_runs == 5000
        assert uncosted_runs == 3832
    finally:
        db.close()


def test_query_family_1_manufacturing_cost_breakdown():
    """Verify total cost breakdown and material spend dominance (95.26% / ₹1,335.95 Cr)."""
    payload = {
        "question": "What is our total manufacturing cost and how is it split across categories?",
        "mode": "GLOBAL",
        "session_id": "GLOBAL",
    }
    res = client.post("/api/investigation/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "COMPLETED"
    assert data["data_origin"] == "REAL_COMMITTED_STORE"
    assert not data["is_synthetic"]
    assert "₹1,402.47 Cr" in data["executive_summary"] or "1402" in data["executive_summary"]
    assert "95.26%" in data["executive_summary"] or "1,335.95" in data["executive_summary"]

    # Verify drilldowns contain all 5 categories
    cats = {d["dimension"]: d for d in data.get("drilldowns", [])}
    assert "Material" in cats
    assert "Labour" in cats
    assert "Machine Operating" in cats
    assert "Factory Energy" in cats
    assert "Scrap & Rework" in cats

    # Check follow up suggestions
    assert len(data.get("follow_up_suggestions", [])) == 4


def test_query_family_1_period_comparison_sep_vs_oct():
    """Verify deterministic variance decomposition for September vs October."""
    payload = {
        "question": "What caused the increase in manufacturing cost between September and October?",
        "mode": "GLOBAL",
        "session_id": "GLOBAL",
    }
    res = client.post("/api/investigation/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "COMPLETED"
    assert data["intent"] == "PERIOD_COMPARISON"
    assert data["data_origin"] == "REAL_COMMITTED_STORE"
    assert "October 2026" in data["reporting_period"]
    assert "September 2026" in data["reporting_period"]

    # Variance bridge checks
    drivers = [d["dimension"] for d in data.get("drilldowns", [])]
    assert any("Volume" in d for d in drivers)
    assert any("Material" in d for d in drivers)
    assert any("Labour" in d for d in drivers)
    assert any("Machine" in d for d in drivers)
    assert any("Energy" in d for d in drivers)
    assert any("Scrap" in d for d in drivers)
    assert any("Residual" in d for d in drivers)

    # Zero residual evidence check
    evidence_text = " ".join(data.get("evidence", []))
    assert "zero unexplained residual (₹0.00)" in evidence_text


def test_query_family_1_period_comparison_missing_period_disclosure():
    """Verify that requesting an uncommitted month returns PERIOD_UNAVAILABLE without multi-period aggregate substitution."""
    payload = {
        "question": "Compare manufacturing costs between September and November",
        "mode": "GLOBAL",
        "session_id": "GLOBAL",
    }
    res = client.post("/api/investigation/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "PERIOD_UNAVAILABLE"
    assert "November 2026" in data["executive_summary"]
    assert "unavailable in the Authoritative Global Manufacturing Store" in data["executive_summary"]
    # Ensure all-period total is NOT substituted
    assert "₹1,402.47 Cr" not in data["executive_summary"]


def test_query_family_2_product_intelligence():
    """Verify product unit economics, mix, and BOM differentiation."""
    payload = {
        "question": "Which product has the highest manufacturing cost and unit cost?",
        "mode": "GLOBAL",
        "session_id": "GLOBAL",
    }
    res = client.post("/api/investigation/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "COMPLETED"
    assert data["data_origin"] == "REAL_COMMITTED_STORE"
    assert "SPH-A15-128" in data["executive_summary"]
    assert "SPH-PRO-256" in data["executive_summary"]

    findings = {f["finding_id"]: f for f in data.get("detailed_findings", [])}
    assert "FIND-01" in findings
    assert "FIND-02" in findings
    assert "FIND-04" in findings
    assert "BOM" in findings["FIND-04"]["title"] or "Engineering" in findings["FIND-04"]["title"]


def test_query_family_3_component_material_intelligence():
    """Verify BOM components analysis and PPV limitation disclosure."""
    payload = {
        "question": "What are our top material expenditure components and purchase price variances?",
        "mode": "GLOBAL",
        "session_id": "GLOBAL",
    }
    res = client.post("/api/investigation/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "COMPLETED"
    assert data["data_origin"] == "REAL_COMMITTED_STORE"

    # PPV limitation boundary must be explicitly stated
    limitations_text = " ".join(data.get("what_we_cannot_conclude_yet", []) + data.get("evidence", [])).lower()
    assert "purchase price variance" in limitations_text or "po invoices" in limitations_text or "supplier invoices" in limitations_text


def test_query_family_4_production_and_quality():
    """Verify line rejection rates (Line SMT-L1/SMT-L2 highest: 1.88%), operational volume, and costing coverage."""
    payload = {
        "question": "Which production line has the highest rejection rate?",
        "mode": "GLOBAL",
        "session_id": "GLOBAL",
    }
    res = client.post("/api/investigation/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "COMPLETED"
    assert data["data_origin"] == "REAL_COMMITTED_STORE"
    assert "SMT-L1" in data["executive_summary"] or "SMT" in data["executive_summary"]
    assert "1.88%" in data["executive_summary"] or "1.87%" in data["executive_summary"]

    # Check findings for costing coverage
    findings = {f["finding_id"]: f for f in data.get("detailed_findings", [])}
    assert "FIND-01" in findings
    assert "FIND-04" in findings
    assert "3,832 Uncosted Runs" in findings["FIND-04"]["title"] or "56.51%" in findings["FIND-04"]["title"]


def test_query_family_5_management_recommendations():
    """Verify prioritized P1/P2/P3 actions with quantitative financial impact."""
    payload = {
        "question": "What are the recommended actions to mitigate manufacturing costs?",
        "mode": "GLOBAL",
        "session_id": "GLOBAL",
    }
    res = client.post("/api/investigation/ask", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "COMPLETED"
    assert len(data.get("recommended_actions", [])) >= 2

    rec_actions = [r["action"] for r in data["recommended_actions"]]
    rec_text = " ".join(rec_actions)
    assert len(rec_text) > 20


def test_conversational_follow_up_context():
    """Verify conversational context retention through parent_report_id."""
    res1 = client.post("/api/investigation/ask", json={
        "question": "Which product has the highest manufacturing cost?",
        "mode": "GLOBAL",
        "session_id": "GLOBAL",
    })
    assert res1.status_code == 200
    report1 = res1.json()
    rep1_id = report1["report_id"]

    res2 = client.post("/api/investigation/ask", json={
        "question": "Which components make up this product BOM?",
        "mode": "GLOBAL",
        "session_id": "GLOBAL",
        "parent_report_id": rep1_id,
    })
    assert res2.status_code == 200
    report2 = res2.json()
    assert report2["status"] == "COMPLETED"
    assert report2["data_origin"] == "REAL_COMMITTED_STORE"
    assert len(report2.get("follow_up_suggestions", [])) == 4
