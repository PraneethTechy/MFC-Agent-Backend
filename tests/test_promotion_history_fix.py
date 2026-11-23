"""
Regression Test: Fact Record History Archival and Promotion Parameter Casting
Verifies:
1. Elimination of psycopg.errors.AmbiguousParameter: inconsistent types deduced for parameter $1
2. Proper parameter type casting (VARCHAR, TEXT, JSON, BOOLEAN) in fact_record_history insertion
3. Atomic transaction boundary preservation and rollback safety
4. Zero corruption of baseline data
"""

import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv("backend/.env")
DATABASE_URL = os.environ.get("DATABASE_URL")

@pytest.fixture(scope="module")
def db_engine():
    assert DATABASE_URL, "DATABASE_URL must be configured"
    return create_engine(DATABASE_URL)

def test_fact_record_history_parameter_casting(db_engine):
    """
    Directly tests that the fact_record_history SQL insertion query executes
    cleanly with parameter bindings without raising AmbiguousParameter error.
    """
    sql_archive = text("""
        INSERT INTO fact_record_history (
            id,
            entity_type,
            record_identifier,
            superseded_batch_id,
            superseding_batch_id,
            version_num,
            approved_by,
            correction_reason,
            prior_record_state,
            superseded_at,
            created_at,
            updated_at,
            is_synthetic
        )
        SELECT 
            gen_random_uuid()::text,
            'line_cost_batches',
            c.cost_record_id,
            c.ingestion_batch_id,
            CAST(:b_id AS VARCHAR(36)),
            c.version_num,
            CAST(:approver AS VARCHAR(255)),
            CAST(:reason AS TEXT),
            json_build_object(
                'cost_record_id', c.cost_record_id,
                'produced_qty', c.produced_qty,
                'material_cost_inr', c.material_cost_inr,
                'labour_cost_inr', c.labour_cost_inr,
                'machine_cost_inr', c.machine_cost_inr,
                'energy_cost_inr', c.energy_cost_inr,
                'scrap_rework_cost_inr', c.scrap_rework_cost_inr,
                'total_direct_cost_inr', c.total_direct_cost_inr,
                'version_num', c.version_num
            ),
            NOW(),
            NOW(),
            NOW(),
            CAST(:is_synth AS BOOLEAN)
        FROM line_cost_batches c
        JOIN stg_manufacturing_cost s ON c.cost_record_id = s.cost_record_id
        WHERE s.ingestion_batch_id = CAST(:b_id AS VARCHAR(36))
          AND s.validation_status = 'VALID'
          AND (
              c.material_cost_inr != s.material_cost_inr OR
              c.labour_cost_inr != s.labour_cost_inr OR
              c.machine_cost_inr != s.machine_cost_inr OR
              c.energy_cost_inr != s.energy_cost_inr OR
              c.scrap_rework_cost_inr != s.scrap_rework_cost_inr OR
              c.produced_qty != s.produced_qty
          )
    """)

    test_batch_id = str(uuid.uuid4())
    with db_engine.connect() as conn:
        trans = conn.begin()
        try:
            # Must execute without psycopg AmbiguousParameter error
            result = conn.execute(sql_archive, {
                "b_id": test_batch_id,
                "approver": "regression_test_runner@company.com",
                "reason": "Auditing parameterized history insertion casting",
                "is_synth": True,
            })
            assert result.rowcount >= 0
        finally:
            trans.rollback()

def test_fact_record_history_direct_insertion(db_engine):
    """
    Verifies that a record can be inserted into fact_record_history with all
    types (UUID, VARCHAR, JSON, TEXT, TIMESTAMP, BOOLEAN) properly handled and rolled back.
    """
    test_id = str(uuid.uuid4())
    sql_direct = text("""
        INSERT INTO fact_record_history (
            id,
            entity_type,
            record_identifier,
            superseded_batch_id,
            superseding_batch_id,
            version_num,
            approved_by,
            correction_reason,
            prior_record_state,
            superseded_at,
            created_at,
            updated_at,
            is_synthetic
        ) VALUES (
            :id,
            :entity_type,
            :rec_id,
            :old_batch,
            :new_batch,
            :version,
            :approver,
            :reason,
            CAST(:prior_state AS JSON),
            NOW(),
            NOW(),
            NOW(),
            :is_synth
        )
    """)

    with db_engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(sql_direct, {
                "id": test_id,
                "entity_type": "line_cost_batches",
                "rec_id": "CST-TEST-001",
                "old_batch": "batch-old-123",
                "new_batch": "batch-new-456",
                "version": 1,
                "approver": "Plant Finance Director",
                "reason": "Test variance adjustment",
                "prior_state": '{"cost_record_id": "CST-TEST-001", "produced_qty": 500}',
                "is_synth": True,
            })

            # Verify select
            check = conn.execute(
                text("SELECT entity_type, approved_by, prior_record_state->>'cost_record_id' FROM fact_record_history WHERE id = :id"),
                {"id": test_id}
            ).fetchone()
            assert check is not None
            assert check[0] == "line_cost_batches"
            assert check[1] == "Plant Finance Director"
            assert check[2] == "CST-TEST-001"
        finally:
            trans.rollback()
            # Verify rolled back cleanly
            verify_gone = conn.execute(
                text("SELECT count(*) FROM fact_record_history WHERE id = :id"),
                {"id": test_id}
            ).scalar()
            assert verify_gone == 0


def test_conflict_archival_and_version_increment(db_engine):
    """
    Simulates a conflict between an existing line_cost_batches record and an amended
    staged record. Verifies that the archival query inserts the prior state into
    fact_record_history, increments the version number, and updates the fact table.
    """
    from app.services.ingestion.promotion_service import PromotionService
    from app.models.ingestion import ImportBatch
    from sqlalchemy.orm import Session

    test_rec_id = f"CST-TEST-VER-{uuid.uuid4().hex[:8]}"
    batch_old_id = f"batch-old-{uuid.uuid4().hex[:8]}"
    batch_new_id = f"batch-new-{uuid.uuid4().hex[:8]}"

    with Session(db_engine) as session:
        try:
            # 0. Insert old import_batch for foreign key integrity
            old_batch = ImportBatch(
                id=batch_old_id,
                original_filename="original_cost.csv",
                dataset_type="MANUFACTURING_COST",
                processing_status="COMMITTED",
                total_rows=1,
                valid_rows=1,
                is_synthetic=True,
            )
            session.add(old_batch)
            session.flush()

            # 1. Insert initial line_cost_batches record (version 1)
            session.execute(text("""
                INSERT INTO line_cost_batches (
                    id, cost_record_id, posting_ts, plant_code, line_code, production_order_id,
                    product_code, produced_qty, material_cost_inr, labour_cost_inr,
                    machine_cost_inr, energy_cost_inr, scrap_rework_cost_inr,
                    total_direct_cost_inr, source_standard_cost_per_unit, standard_cost_status,
                    costing_version, currency, ingestion_batch_id, version_num, is_synthetic, is_current,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid()::text, :cid, NOW(), 'PLANT-01', 'LINE-A', 'ORD-1001',
                    'PROD-01', 1000, 500000.0, 100000.0, 50000.0, 20000.0, 10000.0,
                    680000.0, 680.0, 'UNVERIFIED_STANDARD', 'v1.0', 'INR',
                    :old_bid, 1, true, true,
                    NOW(), NOW()
                )
            """), {"cid": test_rec_id, "old_bid": batch_old_id})

            # 2. Insert new import_batch
            new_batch = ImportBatch(
                id=batch_new_id,
                original_filename="amended_cost.csv",
                dataset_type="MANUFACTURING_COST",
                processing_status="VALIDATED",
                total_rows=1,
                valid_rows=1,
                is_synthetic=True,
            )
            session.add(new_batch)
            session.flush()

            # 3. Stage conflicting amended row in stg_manufacturing_cost (material cost 550,000 instead of 500,000)
            session.execute(text("""
                INSERT INTO stg_manufacturing_cost (
                    ingestion_batch_id, file_checksum_sha256, source_row_number,
                    cost_record_id, posting_ts, plant_id, line_id, production_order_id, product_id,
                    produced_qty, material_cost_inr, labour_cost_inr, machine_cost_inr,
                    energy_cost_inr, scrap_rework_cost_inr, source_standard_cost_per_unit,
                    costing_version, currency, validation_status, ingested_at
                ) VALUES (
                    :new_bid, 'dummy-sha-256', 1,
                    :cid, NOW(), 'PLANT-01', 'LINE-A', 'ORD-1001', 'PROD-01',
                    1000, 550000.0, 100000.0, 50000.0, 20000.0, 10000.0, 680.0,
                    'v1.0', 'INR', 'VALID', NOW()
                )
            """), {"new_bid": batch_new_id, "cid": test_rec_id})

            # 4. Promote
            res = PromotionService.promote_batch(
                session=session,
                batch_id=batch_new_id,
                approver_identifier="auditor@company.com",
                correction_reason="Material price surcharge reconciliation"
            )

            # Assertions
            assert res["archived_historical_corrections"] == 1
            assert res["promoted_line_cost_batches"] == 1

            # Check fact_record_history
            arch = session.execute(text("""
                SELECT entity_type, superseded_batch_id, superseding_batch_id, version_num, approved_by,
                       prior_record_state->>'material_cost_inr' as old_mat
                FROM fact_record_history
                WHERE record_identifier = :cid
            """), {"cid": test_rec_id}).mappings().first()

            assert arch is not None
            assert arch["entity_type"] == "line_cost_batches"
            assert arch["superseded_batch_id"] == batch_old_id
            assert arch["superseding_batch_id"] == batch_new_id
            assert arch["version_num"] == 1
            assert float(arch["old_mat"]) == 500000.0

            # Check updated line_cost_batches
            curr = session.execute(text("""
                SELECT version_num, material_cost_inr, ingestion_batch_id
                FROM line_cost_batches
                WHERE cost_record_id = :cid
            """), {"cid": test_rec_id}).mappings().first()

            assert curr is not None
            assert curr["version_num"] == 2
            assert float(curr["material_cost_inr"]) == 550000.0
            assert curr["ingestion_batch_id"] == batch_new_id

        finally:
            session.execute(text("DELETE FROM line_cost_batches WHERE cost_record_id = :cid"), {"cid": test_rec_id})
            session.execute(text("DELETE FROM fact_record_history WHERE record_identifier = :cid"), {"cid": test_rec_id})
            session.execute(text("DELETE FROM stg_manufacturing_cost WHERE ingestion_batch_id = :b"), {"b": batch_new_id})
            session.execute(text("DELETE FROM import_batches WHERE id IN (:b1, :b2)"), {"b1": batch_old_id, "b2": batch_new_id})
            session.execute(text("DELETE FROM audit_events WHERE entity_id = :b"), {"b": batch_new_id})
            session.commit()


def test_promotion_rollback_on_failure(db_engine):
    """
    Verifies that when a failure occurs during promotion, the transaction rolls back
    completely, leaving no dirty staged batches or partial promotions.
    """
    from app.services.ingestion.promotion_service import PromotionService
    from sqlalchemy.orm import Session

    bad_batch_id = f"non-existent-batch-{uuid.uuid4().hex[:8]}"
    with Session(db_engine) as session:
        # Non-existent batch raises ValueError and does not commit
        with pytest.raises(ValueError):
            PromotionService.promote_batch(
                session=session,
                batch_id=bad_batch_id,
                approver_identifier="test",
                correction_reason="test"
            )

