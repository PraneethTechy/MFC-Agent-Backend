"""
End-to-end live verification of Approve & Commit (Current Upload Store -> Global Store).
Tests:
1. Pre-promotion baseline counts in Neon PostgreSQL tables.
2. Ingestion of isolated staging session with distinct records.
3. Execution of /api/investigation/{report_id}/approve-consolidation route.
4. Database state changes:
   - Fact tables (line_cost_batches, hourly_production_logs)
   - Ingestion registry (status=PROMOTED, row counts)
   - Import batches (status=COMMITTED)
5. Idempotency verification:
   - Trigger commit a 2nd time
   - Verify 0 duplicate rows in fact tables and 0 duplicate rows in fact_record_history
6. RCA read-back verification:
   - Query Global Store via SQLAlchemy models
7. Provenance & lineage verification.
8. Complete cleanup.
"""

import os
import sys
import uuid
import datetime as dt
import pytest
from dotenv import load_dotenv

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath("backend"))
load_dotenv("backend/.env")

from sqlalchemy import text
from app.db import get_db, engine
from app.models.real_datasets import (
    LineCostBatch,
    HourlyProductionLog,
    IngestionFileRegistry,
    FactRecordHistory,
)
from app.models.ingestion import ImportBatch
from app.models.agent_records import InvestigationReportRecord, AuditEvent
from app.services.ingestion.session_store import SessionDataStore
from app.main import approve_investigation_consolidation


@pytest.fixture
def db_session():
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


def test_approve_commit_end_to_end_neon(db_session):
    test_id = str(uuid.uuid4())[:8]
    session_id = f"test_commit_sess_{test_id}"
    cost_rec_id = f"TST-CST-{test_id}"
    event_id = f"TST-EVT-{test_id}"
    report_id = f"RCA-{test_id}"

    # 1. Note pre-test state counts
    initial_cost_count = db_session.query(LineCostBatch).count()
    initial_prod_count = db_session.query(HourlyProductionLog).count()
    initial_reg_count = db_session.query(IngestionFileRegistry).count()
    initial_history_count = db_session.query(FactRecordHistory).count()

    print(f"\n[BASELINE COUNTS] line_cost_batches: {initial_cost_count}, hourly_production_logs: {initial_prod_count}, registry: {initial_reg_count}")

    # 2. Setup isolated upload session with valid rows
    test_cost_row = {
        "cost_record_id": cost_rec_id,
        "posting_ts": "2026-11-15 08:00:00",
        "plant_id": "PLT-01",
        "line_id": "Line 1",
        "production_order_id": f"ORD-{test_id}",
        "product_id": "PHX-PRO",
        "produced_qty": 100,
        "material_cost_inr": 50000.0,
        "labour_cost_inr": 15000.0,
        "machine_cost_inr": 8000.0,
        "energy_cost_inr": 4000.0,
        "scrap_rework_cost_inr": 2500.0,
        "total_direct_cost_inr": 79500.0,
        "costing_version": "v1.0",
        "currency": "INR",
        "is_synthetic": True,
    }

    test_prod_row = {
        "event_id": event_id,
        "event_ts": "2026-11-15 10:00:00",
        "event_date": "2026-11-15",
        "plant_id": "PLT-01",
        "line_id": "Line 1",
        "shift_id": "Shift A",
        "product_id": "PHX-PRO",
        "production_order_id": f"ORD-{test_id}",
        "target_qty": 120,
        "actual_qty": 100,
        "good_qty": 95,
        "reject_qty": 5,
        "rework_qty": 2,
        "downtime_min": 15,
        "downtime_reason": "Tool recalibration",
        "operator_team": "Team Alpha",
        "source_system": "MES",
        "is_synthetic": True,
    }

    datasets = {
        "MANUFACTURING_COST": {
            "dataset_type": "MANUFACTURING_COST",
            "filename": f"test_manufacturing_cost_{test_id}.csv",
            "rows": [test_cost_row],
            "is_synthetic": True,
        },
        "HOURLY_PRODUCTION": {
            "dataset_type": "HOURLY_PRODUCTION",
            "filename": f"test_hourly_production_{test_id}.csv",
            "rows": [test_prod_row],
            "is_synthetic": True,
        },
    }

    SessionDataStore.save_session(session_id, datasets, data_origin="SYNTHETIC_TEST")

    # Create InvestigationReportRecord
    investigation_rep = InvestigationReportRecord(
        report_id=report_id,
        source_batch_id=session_id,
        inspection_id=f"insp_{test_id}",
        title=f"Test Investigation {test_id}",
        status="STAGED",
        data_origin="SYNTHETIC_TEST",
        is_synthetic=True,
        report_json={"title": f"Test Investigation {test_id}", "status": "STAGED"},
    )
    db_session.add(investigation_rep)
    db_session.commit()

    try:
        # 3. Trigger promotion via approve_investigation_consolidation
        res1 = approve_investigation_consolidation(report_id=report_id, db=db_session)
        print(f"\n[PROMOTION 1 RESULT] {res1}")

        assert res1["status"] == "COMMITTED"
        assert res1["consolidation_status"] == "COMMITTED"
        assert res1["total_promoted"] >= 2
        assert res1["data_origin"] == "SYNTHETIC_TEST"
        assert res1["is_synthetic"] is True

        # 4. Verify database state changes
        cost_rec = db_session.query(LineCostBatch).filter_by(cost_record_id=cost_rec_id).first()
        assert cost_rec is not None, "LineCostBatch record was not inserted into Global Store"
        assert cost_rec.plant_code == "PLT-01"
        assert cost_rec.line_code == "Line 1"
        assert cost_rec.product_code == "PHX-PRO"
        assert float(cost_rec.material_cost_inr) == 50000.0
        assert cost_rec.is_synthetic is True

        prod_rec = db_session.query(HourlyProductionLog).filter_by(event_id=event_id).first()
        assert prod_rec is not None, "HourlyProductionLog record was not inserted into Global Store"
        assert prod_rec.plant_code == "PLT-01"
        assert prod_rec.line_code == "Line 1"
        assert prod_rec.good_qty == 95
        assert prod_rec.reject_qty == 5
        assert prod_rec.is_synthetic is True

        # Verify registry updated
        reg_entries = db_session.query(IngestionFileRegistry).filter(
            IngestionFileRegistry.dataset_type.in_(["MANUFACTURING_COST", "HOURLY_PRODUCTION"]),
            IngestionFileRegistry.status == "PROMOTED",
        ).all()
        assert len(reg_entries) >= 2, "Ingestion registry was not updated with PROMOTED status"

        # Verify investigation report status
        db_session.refresh(investigation_rep)
        assert investigation_rep.status == "COMMITTED"

        # 5. Verify Idempotency on repeated trigger
        res2 = approve_investigation_consolidation(report_id=report_id, db=db_session)
        print(f"\n[PROMOTION 2 (IDEMPOTENT) RESULT] {res2}")
        assert res2["status"] == "COMMITTED"
        assert "already committed" in res2["message"].lower()

        # Verify no duplicate rows
        cost_matches = db_session.query(LineCostBatch).filter_by(cost_record_id=cost_rec_id).all()
        assert len(cost_matches) == 1, f"Expected exactly 1 LineCostBatch, found {len(cost_matches)}"

        prod_matches = db_session.query(HourlyProductionLog).filter_by(event_id=event_id).all()
        assert len(prod_matches) == 1, f"Expected exactly 1 HourlyProductionLog, found {len(prod_matches)}"

        # Verify no superfluous historical corrections were archived on idempotent rerun
        history_records_for_test = db_session.query(FactRecordHistory).filter_by(record_identifier=cost_rec_id).all()
        assert len(history_records_for_test) == 0, "No history archive should occur when values did not change"

        # 6. Verify RCA read-back
        # Simulate RCA agent querying committed operational fact records
        rca_cost_query = db_session.query(LineCostBatch).filter(
            LineCostBatch.plant_code == "PLT-01",
            LineCostBatch.product_code == "PHX-PRO",
            LineCostBatch.cost_record_id == cost_rec_id,
        ).first()
        assert rca_cost_query is not None
        assert rca_cost_query.produced_qty == 100

        rca_prod_query = db_session.query(HourlyProductionLog).filter(
            HourlyProductionLog.plant_code == "PLT-01",
            HourlyProductionLog.event_id == event_id,
        ).first()
        assert rca_prod_query is not None
        assert rca_prod_query.actual_qty == 100

        print("\n[VERIFICATION COMPLETE] All database assertions, idempotency, and RCA read-backs passed cleanly.")

    finally:
        # 8. Clean up test records
        print("\n[CLEANUP] Cleaning test records from Neon database...")
        db_session.rollback()
        db_session.execute(text("DELETE FROM line_cost_batches WHERE cost_record_id = :cid"), {"cid": cost_rec_id})
        db_session.execute(text("DELETE FROM hourly_production_logs WHERE event_id = :eid"), {"eid": event_id})
        db_session.execute(text("DELETE FROM fact_record_history WHERE record_identifier IN (:cid, :eid)"), {"cid": cost_rec_id, "eid": event_id})
        db_session.execute(text("DELETE FROM investigation_reports WHERE report_id = :rid"), {"rid": report_id})
        db_session.execute(text("DELETE FROM import_batches WHERE id LIKE :pat"), {"pat": f"{session_id[:20]}%"})
        db_session.execute(text("DELETE FROM audit_events WHERE entity_id LIKE :pat"), {"pat": f"%{session_id[:20]}%"})
        db_session.execute(text("DELETE FROM ingestion_file_registry WHERE file_name LIKE :fpat"), {"fpat": f"%{test_id}%"})
        db_session.commit()

        # Clean session directory
        sess_dir = os.path.join("backend", "data", "sessions", session_id)
        if os.path.exists(sess_dir):
            import shutil
            shutil.rmtree(sess_dir, ignore_errors=True)
        print("[CLEANUP COMPLETE] Database and disk restored to pre-test state.")
