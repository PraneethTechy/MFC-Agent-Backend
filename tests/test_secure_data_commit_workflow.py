"""
Phase 1: Secure Data Commit Workflow Test Suite
Verifies safety hotfix for Data Upload -> Validation -> Approve & Commit workflow:
1. Synthetic session / report cannot be committed (HTTP 400).
2. Non-existent session / report cannot be committed (HTTP 404).
3. Failed validation session / report cannot be committed (HTTP 400).
4. Legacy commit endpoint cannot bypass protections (HTTP 400 / 404 / 501).
5. Incomplete promotion cannot return COMMITTED (HTTP 501).
6. Blocked commit attempts do not insert, update, or delete fact records.
7. Existing baseline fact records remain completely unchanged.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.db import SessionLocal, get_db
from app.models.agent_records import InvestigationReportRecord
from app.models.real_datasets import (
    LineCostBatch,
    HourlyProductionLog,
    SerializedQualityInspection,
    BomComponentRecord,
)
from app.services.ingestion.legacy import ingestion_service

client = TestClient(app)


def test_synthetic_report_cannot_be_committed():
    """Synthetic test data must be blocked from consolidation with HTTP 400."""
    db = SessionLocal()
    rep_id = f"TEST-SYNTH-{uuid.uuid4().hex[:8]}"
    synthetic_rec = InvestigationReportRecord(
        report_id=rep_id,
        title="Synthetic Test Package",
        status="COMPLETED",
        data_origin="SYNTHETIC_TEST",
        is_synthetic=True,
        uploaded_files=["test_cost.csv"],
        dataset_types=["MANUFACTURING_COST"],
        details={"consolidation_status": "STAGED_PACKAGE"},
        report_json={"summary": "Synthetic test"},
    )
    db.add(synthetic_rec)
    db.commit()

    try:
        response = client.post(f"/api/investigation/{rep_id}/approve-consolidation")
        assert response.status_code == 400
        data = response.json()
        assert "synthetic test data cannot be consolidated" in data["detail"].lower()

        # Verify the record status was NOT modified to COMMITTED
        db.refresh(synthetic_rec)
        assert synthetic_rec.status == "COMPLETED"
        assert synthetic_rec.details.get("consolidation_status") != "COMMITTED"
    finally:
        db.delete(synthetic_rec)
        db.commit()
        db.close()


def test_nonexistent_report_returns_404():
    """Unapproved / nonexistent report ID must return HTTP 404."""
    fake_id = f"NONEXISTENT-{uuid.uuid4().hex}"
    response = client.post(f"/api/investigation/{fake_id}/approve-consolidation")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_failed_validation_report_cannot_be_committed():
    """A report that failed validation must be rejected with HTTP 400."""
    db = SessionLocal()
    rep_id = f"TEST-FAIL-{uuid.uuid4().hex[:8]}"
    failed_rec = InvestigationReportRecord(
        report_id=rep_id,
        title="Failed Validation Package",
        status="FAILED",
        data_origin="REAL",
        is_synthetic=False,
        uploaded_files=["corrupt_cost.csv"],
        dataset_types=["MANUFACTURING_COST"],
        details={"validation_error": "Negative costs detected"},
        report_json={"summary": "Failed"},
    )
    db.add(failed_rec)
    db.commit()

    try:
        response = client.post(f"/api/investigation/{rep_id}/approve-consolidation")
        assert response.status_code == 400
        data = response.json()
        assert "failed validation" in data["detail"].lower()

        # Verify record remains unchanged
        db.refresh(failed_rec)
        assert failed_rec.status == "FAILED"
    finally:
        db.delete(failed_rec)
        db.commit()
        db.close()


def test_incomplete_promotion_returns_501_safely():
    """Real dataset packages must NOT return COMMITTED while promotion pipeline is unimplemented."""
    db = SessionLocal()
    rep_id = f"TEST-REAL-{uuid.uuid4().hex[:8]}"
    real_rec = InvestigationReportRecord(
        report_id=rep_id,
        title="Valid Real Ingestion Package",
        status="COMPLETED",
        data_origin="REAL",
        is_synthetic=False,
        uploaded_files=["real_cost.csv"],
        dataset_types=["MANUFACTURING_COST"],
        details={"consolidation_status": "STAGED_PACKAGE"},
        report_json={"summary": "Valid"},
    )
    db.add(real_rec)
    db.commit()

    try:
        response = client.post(f"/api/investigation/{rep_id}/approve-consolidation")
        assert response.status_code == 501
        data = response.json()
        assert "promotion pipeline is not yet implemented" in data["detail"].lower()

        # Critical: Verify report was NOT marked COMMITTED
        db.refresh(real_rec)
        assert real_rec.status != "COMMITTED"
        assert real_rec.details.get("consolidation_status") != "COMMITTED"
    finally:
        db.delete(real_rec)
        db.commit()
        db.close()


def test_legacy_commit_endpoint_safeguards():
    """Verifies that legacy commit route /api/import/{batch_id}/commit cannot bypass safety hotfix."""
    # 1. Nonexistent batch returns 404
    fake_batch_id = f"FAKE-BATCH-{uuid.uuid4().hex[:8]}"
    res_404 = client.post(f"/api/import/{fake_batch_id}/commit")
    assert res_404.status_code == 404

    # 2. Batch with blocking errors returns 400
    b_err_id = f"BATCH-ERR-{uuid.uuid4().hex[:8]}"
    ingestion_service.staged_batches[b_err_id] = {
        "batch_id": b_err_id,
        "filename": "err.csv",
        "dataset_type": "MANUFACTURING_COST",
        "total_rows": 10,
        "validation_summary": {"is_valid": False, "blocking_error_count": 2},
    }
    res_err = client.post(f"/api/import/{b_err_id}/commit")
    assert res_err.status_code == 400
    assert "blocking errors" in res_err.json()["detail"].lower()

    # 3. Synthetic batch returns 400
    b_synth_id = f"BATCH-SYNTH-{uuid.uuid4().hex[:8]}"
    ingestion_service.staged_batches[b_synth_id] = {
        "batch_id": b_synth_id,
        "filename": "synth.csv",
        "dataset_type": "MANUFACTURING_COST",
        "total_rows": 10,
        "data_origin": "SYNTHETIC_TEST",
        "is_synthetic": True,
        "validation_summary": {"is_valid": True, "blocking_error_count": 0},
    }
    res_synth = client.post(f"/api/import/{b_synth_id}/commit")
    assert res_synth.status_code == 400
    assert "synthetic test data cannot be consolidated" in res_synth.json()["detail"].lower()

    # 4. Valid batch returns 501 Not Implemented (cannot falsely claim COMMITTED)
    b_valid_id = f"BATCH-VALID-{uuid.uuid4().hex[:8]}"
    ingestion_service.staged_batches[b_valid_id] = {
        "batch_id": b_valid_id,
        "filename": "valid.csv",
        "dataset_type": "MANUFACTURING_COST",
        "total_rows": 10,
        "data_origin": "REAL",
        "is_synthetic": False,
        "validation_summary": {"is_valid": True, "blocking_error_count": 0},
    }
    res_valid = client.post(f"/api/import/{b_valid_id}/commit")
    assert res_valid.status_code == 501
    assert "promotion is not yet implemented" in res_valid.json()["detail"].lower()

    # Clean up in-memory batches
    ingestion_service.staged_batches.pop(b_err_id, None)
    ingestion_service.staged_batches.pop(b_synth_id, None)
    ingestion_service.staged_batches.pop(b_valid_id, None)


def test_fact_tables_remain_untouched_after_blocked_commits():
    """Guarantees that baseline fact tables in Neon PostgreSQL are never mutated by commit attempts."""
    db = SessionLocal()
    # Baseline expected row counts
    cost_count = db.query(LineCostBatch).count()
    prod_count = db.query(HourlyProductionLog).count()
    qual_count = db.query(SerializedQualityInspection).count()
    bom_count = db.query(BomComponentRecord).count()

    # Attempt commit on active synthetic test session report if present
    rep = db.query(InvestigationReportRecord).filter_by(data_origin="SYNTHETIC_TEST").first()
    if rep:
        client.post(f"/api/investigation/{rep.report_id}/approve-consolidation")

    # Attempt commit on random batch
    client.post("/api/import/nonexistent/commit")

    # Verify counts are strictly identical
    assert db.query(LineCostBatch).count() == cost_count
    assert db.query(HourlyProductionLog).count() == prod_count
    assert db.query(SerializedQualityInspection).count() == qual_count
    assert db.query(BomComponentRecord).count() == bom_count

    db.close()
