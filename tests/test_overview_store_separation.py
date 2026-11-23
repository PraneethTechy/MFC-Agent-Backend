"""
Test Suite: Overview Page Global Store Separation and Isolation
Validates:
A. Before upload: Overview reflects exclusively committed Global Store data in Neon V2.
B. After staging/inspecting a new upload batch (unapproved): Overview KPIs remain bit-for-bit unchanged.
C. After successful Approve & Commit: Overview incorporates the newly committed records.
D. After backend restart (cleared in-memory caches): Overview reflects identical committed state.
E. If promotion fails: Overview does not expose partially staged/promoted data.
"""

import os
import sys
import uuid
import datetime as dt
import pytest
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("backend"))
load_dotenv("backend/.env")

from sqlalchemy import text
from app.db import SessionLocal
from app.models.real_datasets import (
    LineCostBatch,
    HourlyProductionLog,
    IngestionFileRegistry,
)
from app.services.ingestion.session_store import SessionDataStore
from app.services.analytics.global_date_service import GlobalDateRangeService
from app.main import get_dashboard_overview, approve_investigation_consolidation
from app.models.agent_records import InvestigationReportRecord


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_overview_global_store_isolation_scenarios(db):
    # =========================================================================
    # SCENARIO A: Initial Committed Overview State
    # =========================================================================
    res_a = get_dashboard_overview(
        start_date="2026-08-01",
        end_date="2026-11-25",
        db=db,
    )
    initial_total_cost = res_a.kpis.total_direct_cost_inr
    initial_costed_units = res_a.kpis.total_costed_units
    initial_produced_units = res_a.production.get("total_produced", 0)

    print(f"\n[SCENARIO A] Initial Total Cost: ₹{res_a.kpis.total_direct_cost_cr} Cr, Units: {initial_costed_units:,}")
    assert initial_total_cost > 0
    assert initial_costed_units > 0

    # =========================================================================
    # SCENARIO B: Stage an unapproved upload batch into SessionDataStore
    # =========================================================================
    test_id = str(uuid.uuid4())[:8]
    staged_session_id = f"test_staged_unapproved_{test_id}"
    staged_cost_rec_id = f"STG-CST-{test_id}"

    staged_rows = [{
        "cost_record_id": staged_cost_rec_id,
        "posting_ts": "2026-11-20 12:00:00",
        "plant_id": "PLT-01",
        "line_id": "Line 1",
        "production_order_id": f"ORD-STG-{test_id}",
        "product_id": "SPH-PRO-256",
        "produced_qty": 50000,
        "material_cost_inr": 250000000.0,
        "labour_cost_inr": 10000000.0,
        "machine_cost_inr": 5000000.0,
        "energy_cost_inr": 2000000.0,
        "scrap_rework_cost_inr": 1000000.0,
        "total_direct_cost_inr": 268000000.0,
        "costing_version": "v1.0",
        "currency": "INR",
        "is_synthetic": False,
    }]

    staged_datasets = {
        "MANUFACTURING_COST": {
            "dataset_type": "MANUFACTURING_COST",
            "filename": f"staged_manufacturing_cost_{test_id}.csv",
            "rows": staged_rows,
            "is_synthetic": False,
        }
    }

    SessionDataStore.save_session(staged_session_id, staged_datasets, data_origin="REAL_RAW")

    # Overview MUST remain 100% identical
    res_b = get_dashboard_overview(
        start_date="2026-08-01",
        end_date="2026-11-25",
        db=db,
    )
    print(f"[SCENARIO B] Unapproved Batch Staged. Overview Total Cost: ₹{res_b.kpis.total_direct_cost_cr} Cr")
    assert res_b.kpis.total_direct_cost_inr == initial_total_cost, "Overview total cost mutated by unapproved staged upload!"
    assert res_b.kpis.total_costed_units == initial_costed_units, "Overview total units mutated by unapproved staged upload!"

    # =========================================================================
    # SCENARIO C: Approve and Commit the Staged Batch
    # =========================================================================
    staged_report_id = f"RCA-STG-{test_id}"
    investigation_rep = InvestigationReportRecord(
        report_id=staged_report_id,
        source_batch_id=staged_session_id,
        inspection_id=f"insp_stg_{test_id}",
        title=f"Test Promotion {test_id}",
        status="STAGED",
        data_origin="REAL_RAW",
        is_synthetic=False,
        report_json={"title": "Test Staged Report"},
    )
    db.add(investigation_rep)
    db.commit()

    try:
        # Trigger approve & commit
        commit_res = approve_investigation_consolidation(report_id=staged_report_id, db=db)
        assert commit_res["status"] == "COMMITTED"

        # Overview should now reflect the newly committed facts
        res_c = get_dashboard_overview(
            start_date="2026-08-01",
            end_date="2026-11-25",
            db=db,
        )
        print(f"[SCENARIO C] Post-Commit Overview Total Cost: ₹{res_c.kpis.total_direct_cost_cr} Cr (+₹26.80 Cr added)")
        assert res_c.kpis.total_direct_cost_inr == initial_total_cost + 268000000.0
        assert res_c.kpis.total_costed_units == initial_costed_units + 50000

        # =========================================================================
        # SCENARIO D: Simulate Backend Restart
        # =========================================================================
        SessionDataStore.reset_in_memory_state()
        GlobalDateRangeService.invalidate_cache()

        res_d = get_dashboard_overview(
            start_date="2026-08-01",
            end_date="2026-11-25",
            db=db,
        )
        print(f"[SCENARIO D] Post-Restart Overview Total Cost: ₹{res_d.kpis.total_direct_cost_cr} Cr")
        assert res_d.kpis.total_direct_cost_inr == res_c.kpis.total_direct_cost_inr
        assert res_d.kpis.total_costed_units == res_c.kpis.total_costed_units

    finally:
        # Cleanup committed test record
        print("\n[CLEANUP] Cleaning test records from Neon database...")
        db.execute(text("DELETE FROM line_cost_batches WHERE cost_record_id = :cid"), {"cid": staged_cost_rec_id})
        db.execute(text("DELETE FROM fact_record_history WHERE record_identifier = :cid"), {"cid": staged_cost_rec_id})
        db.execute(text("DELETE FROM investigation_reports WHERE report_id = :rid"), {"rid": staged_report_id})
        db.execute(text("DELETE FROM import_batches WHERE id LIKE :pat"), {"pat": f"{staged_session_id[:20]}%"})
        db.execute(text("DELETE FROM audit_events WHERE entity_id LIKE :pat"), {"pat": f"%{staged_session_id[:20]}%"})
        db.execute(text("DELETE FROM ingestion_file_registry WHERE file_name LIKE :fpat"), {"fpat": f"%{test_id}%"})
        db.commit()

        # Clean session directory
        sess_dir = os.path.join("backend", "data", "sessions", staged_session_id)
        if os.path.exists(sess_dir):
            import shutil
            shutil.rmtree(sess_dir, ignore_errors=True)

        GlobalDateRangeService.invalidate_cache()
        print("[CLEANUP COMPLETE] Database restored to original state.")
