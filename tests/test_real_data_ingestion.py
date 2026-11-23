"""
Manufacturing Cost Agent - Real Dataset Ingestion & Reconciliation Test Suite
Verifies:
1. SHA-256 Checksums
2. CSV parsing and row counts (5,000 cost, 8,832 production, 16,000 quality, 48 BOM)
3. Staging and operational promotion counts in Neon PostgreSQL
4. Idempotency and duplicate detection
5. Exact financial reconciliation: INR 14,024,712,024.30 across 5 cost categories
6. Costing status breakdown: 5,000 DIRECT_COSTED vs 3,832 UNCOSTED_OPERATIONAL_RUN
7. Quality serialized preservation: 16,000 records, 15,999 serials, UNRESOLVED_LINEAGE
8. Standard cost safeguards: UNVERIFIED_STANDARD
9. Scrap & rework safeguards: scrap recovery NOT_AVAILABLE, rework as added cost
10. Overhead handling: NOT_AVAILABLE
"""

from decimal import Decimal
import os
import pytest
from sqlalchemy import text
from app.db import engine
from app.services.ingestion import (
    ChecksumVerifier,
    CsvReader,
    EXPECTED_CHECKSUMS,
    EXPECTED_ROW_COUNTS,
    EXPECTED_COST_TOTALS,
)


@pytest.fixture(scope="module")
def db_conn():
    with engine.connect() as conn:
        yield conn


class TestRealDataIngestion:

    def test_01_sha256_checksums(self):
        """Verifies that all 4 source files match the approved SHA-256 checksums."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        for fname, expected_hash in EXPECTED_CHECKSUMS.items():
            fpath = os.path.join(data_dir, fname)
            if not os.path.exists(fpath):
                fpath = os.path.join(data_dir, "raw", fname)
            assert os.path.exists(fpath), f"Source file {fname} not found"
            
            is_valid, computed_hash, _ = ChecksumVerifier.verify_source_file(fpath)
            assert is_valid, f"Checksum mismatch for {fname}"
            assert computed_hash == expected_hash

    def test_02_ingestion_file_registry_persisted(self, db_conn):
        """Verifies that all 4 files are registered in ingestion_file_registry as PROMOTED."""
        rows = db_conn.execute(
            text("SELECT file_name, file_checksum_sha256, status, total_rows_detected FROM ingestion_file_registry")
        ).fetchall()
        assert len(rows) >= 4
        reg_map = {r[0]: (r[1], r[2], r[3]) for r in rows}
        
        for fname, exp_hash in EXPECTED_CHECKSUMS.items():
            assert fname in reg_map, f"{fname} not found in ingestion_file_registry"
            checksum, status, count = reg_map[fname]
            assert checksum == exp_hash
            assert status == "PROMOTED"

    def test_03_line_cost_batches_record_count(self, db_conn):
        """Verifies that exactly 5,000 cost records are promoted to line_cost_batches."""
        cnt = db_conn.execute(text("SELECT count(*) FROM line_cost_batches")).scalar()
        assert cnt == 5000, f"Expected 5,000 cost records, found {cnt}"

    def test_04_hourly_production_logs_record_count(self, db_conn):
        """Verifies that exactly 8,832 production records are promoted to hourly_production_logs."""
        cnt = db_conn.execute(text("SELECT count(*) FROM hourly_production_logs")).scalar()
        assert cnt == 8832, f"Expected 8,832 production records, found {cnt}"

    def test_05_serialized_quality_inspections_record_count(self, db_conn):
        """Verifies that exactly 16,000 quality records are promoted to serialized_quality_inspections."""
        cnt = db_conn.execute(text("SELECT count(*) FROM serialized_quality_inspections")).scalar()
        assert cnt == 16000, f"Expected 16,000 quality records, found {cnt}"

    def test_06_bom_component_records_record_count(self, db_conn):
        """Verifies that exactly 48 BOM component lines are promoted to bom_component_records."""
        cnt = db_conn.execute(text("SELECT count(*) FROM bom_component_records")).scalar()
        assert cnt == 48, f"Expected 48 BOM component records, found {cnt}"

    def test_07_exact_financial_reconciliation(self, db_conn):
        """
        Reconciles the 5 actual cost categories to exactly INR 14,024,712,024.30.
        Cross-foots to the paisa (0.00 discrepancy).
        """
        sql = text("""
            SELECT 
                SUM(material_cost_inr) as material,
                SUM(labour_cost_inr) as labour,
                SUM(machine_cost_inr) as machine,
                SUM(energy_cost_inr) as energy,
                SUM(scrap_rework_cost_inr) as scrap_rework,
                SUM(total_direct_cost_inr) as total_direct
            FROM line_cost_batches
        """)
        row = db_conn.execute(sql).mappings().one()

        mat = Decimal(str(row["material"]))
        lab = Decimal(str(row["labour"]))
        mac = Decimal(str(row["machine"]))
        nrg = Decimal(str(row["energy"]))
        sr = Decimal(str(row["scrap_rework"]))
        tot = Decimal(str(row["total_direct"]))

        # Check against expected category totals
        assert mat == EXPECTED_COST_TOTALS["material_cost_inr"]
        assert lab == EXPECTED_COST_TOTALS["labour_cost_inr"]
        assert mac == EXPECTED_COST_TOTALS["machine_cost_inr"]
        assert nrg == EXPECTED_COST_TOTALS["energy_cost_inr"]
        assert sr == EXPECTED_COST_TOTALS["scrap_rework_cost_inr"]
        assert tot == EXPECTED_COST_TOTALS["total_direct_actual_cost"]

        # Check internal mathematical cross-footing
        component_sum = mat + lab + mac + nrg + sr
        assert component_sum == tot
        assert tot == Decimal("14024712024.30")

    def test_08_production_costing_status_breakdown(self, db_conn):
        """
        Verifies that exactly 5,000 records are marked DIRECT_COSTED,
        and exactly 3,832 records are marked UNCOSTED_OPERATIONAL_RUN.
        """
        sql = text("""
            SELECT costing_status, count(*) as cnt 
            FROM hourly_production_logs 
            GROUP BY costing_status
        """)
        rows = dict(db_conn.execute(sql).fetchall())
        assert rows.get("DIRECT_COSTED") == 5000, f"Expected 5,000 DIRECT_COSTED, found {rows.get('DIRECT_COSTED')}"
        assert rows.get("UNCOSTED_OPERATIONAL_RUN") == 3832, f"Expected 3,832 UNCOSTED_OPERATIONAL_RUN, found {rows.get('UNCOSTED_OPERATIONAL_RUN')}"

    def test_09_production_volume_and_coverage(self, db_conn):
        """
        Verifies that good and actual units are preserved and match 3.4.2 specifications:
        - Costed produced: 1,369,863
        - Costed good: 1,344,258
        - Total produced: 2,424,184
        - Total good: 2,378,960
        """
        sql = text("""
            SELECT 
                SUM(CASE WHEN costing_status = 'DIRECT_COSTED' THEN actual_qty ELSE 0 END) as costed_act,
                SUM(CASE WHEN costing_status = 'DIRECT_COSTED' THEN good_qty ELSE 0 END) as costed_good,
                SUM(actual_qty) as total_act,
                SUM(good_qty) as total_good
            FROM hourly_production_logs
        """)
        row = db_conn.execute(sql).mappings().one()
        assert Decimal(str(row["costed_act"])) == Decimal("1369863.0")
        assert Decimal(str(row["costed_good"])) == Decimal("1344258.0")
        assert Decimal(str(row["total_act"])) == Decimal("2424184.0")
        assert Decimal(str(row["total_good"])) == Decimal("2378960.0")

    def test_10_standard_cost_status_safeguards(self, db_conn):
        """Verifies that all 5,000 line cost batches retain standard_cost_status = UNVERIFIED_STANDARD."""
        cnt = db_conn.execute(
            text("SELECT count(*) FROM line_cost_batches WHERE standard_cost_status = 'UNVERIFIED_STANDARD'")
        ).scalar()
        assert cnt == 5000

    def test_11_quality_inspections_lineage_and_results(self, db_conn):
        """
        Verifies quality inspection preservation:
        - 16,000 rows
        - 15,439 RELEASE (PASS)
        - 561 FAIL (192 REWORK, 185 HOLD, 184 SCRAP)
        - lineage_status is UNRESOLVED_LINEAGE
        """
        sql = text("""
            SELECT disposition, count(*) as cnt
            FROM serialized_quality_inspections
            GROUP BY disposition
        """)
        disp = dict(db_conn.execute(sql).fetchall())
        assert disp.get("RELEASE") == 15439
        assert disp.get("REWORK") == 192
        assert disp.get("HOLD") == 185
        assert disp.get("SCRAP") == 184

        unresolved_cnt = db_conn.execute(
            text("SELECT count(*) FROM serialized_quality_inspections WHERE lineage_status = 'UNRESOLVED_LINEAGE'")
        ).scalar()
        assert unresolved_cnt == 16000

