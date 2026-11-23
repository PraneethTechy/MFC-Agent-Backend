"""
Manufacturing Cost Agent - Import Manager (Master Orchestrator)
Coordinates end-to-end ingestion lifecycle:
1. File verification & SHA-256 check
2. File registry logging
3. Staging insertion
4. Business validation & Trust Scoring
5. Cross-dataset transformation (costing status resolution)
6. Transactional promotion
7. Post-promotion financial verification
"""

from decimal import Decimal
import logging
import os
import uuid
from typing import Any
from sqlalchemy.orm import Session
from app.db import engine
from app.models.ingestion import ImportBatch
from app.models.real_datasets import IngestionFileRegistry
from .config import (
    EXPECTED_CHECKSUMS,
    EXPECTED_ROW_COUNTS,
    EXPECTED_COST_TOTALS,
    CHUNK_SIZE_ROWS,
)
from .checksum import ChecksumVerifier
from .csv_reader import CsvReader
from .staging_loader import StagingLoader
from .validator import DataValidator
from .transformer import DataTransformer
from .promotion_service import PromotionService

logger = logging.getLogger("manufacturing_cost_agent.ingestion.import_manager")


class ImportManager:
    """Master controller for manufacturing data ingestion."""

    def __init__(self, db_session: Session | None = None):
        self.session = db_session or Session(engine)

    def verify_and_register_file(self, file_path: str, dataset_type: str) -> tuple[str, bool]:
        """
        Calculates SHA-256 and checks if file was already successfully promoted.
        Returns: (file_checksum, is_already_promoted)
        """
        file_name = os.path.basename(file_path)
        is_valid_hash, computed_hash, expected_hash = ChecksumVerifier.verify_source_file(file_path)
        
        if not is_valid_hash:
            raise ValueError(
                f"Checksum mismatch for {file_name}! Computed: {computed_hash}, Expected: {expected_hash}"
            )

        # Check registry for idempotency
        reg = self.session.query(IngestionFileRegistry).filter_by(file_checksum_sha256=computed_hash).first()
        if reg and reg.status == "PROMOTED":
            return computed_hash, True

        # Register or update registry record
        file_size = os.path.getsize(file_path)
        if not reg:
            reg = IngestionFileRegistry(
                id=str(uuid.uuid4()),
                file_name=file_name,
                file_checksum_sha256=computed_hash,
                file_size_bytes=file_size,
                dataset_type=dataset_type,
                total_rows_detected=EXPECTED_ROW_COUNTS.get(file_name, 0),
                status="STAGED",
            )
            self.session.add(reg)
        else:
            reg.status = "STAGED"
            reg.error_summary = None

        self.session.commit()
        return computed_hash, False

    def ingest_single_file(
        self,
        file_path: str,
        dataset_type: str,
        dry_run: bool = False,
        promote_now: bool = True,
    ) -> dict[str, Any]:
        """
        Stages, validates, and optionally promotes a single manufacturing CSV file.
        """
        file_name = os.path.basename(file_path)
        checksum, is_already_promoted = self.verify_and_register_file(file_path, dataset_type)

        if is_already_promoted and not dry_run:
            logger.info(f"File {file_name} already promoted under checksum {checksum}. Skipping.")
            return {
                "file_name": file_name,
                "status": "ALREADY_PROMOTED",
                "checksum": checksum,
                "message": "File was already successfully promoted to Neon PostgreSQL.",
            }

        batch_id = str(uuid.uuid4())
        batch = ImportBatch(
            id=batch_id,
            original_filename=file_name,
            dataset_type=dataset_type,
            processing_status="STAGING",
        )
        self.session.add(batch)
        self.session.commit()

        # Stream and stage chunks
        total_staged = 0
        for chunk in CsvReader.stream_csv(file_path, chunk_size=CHUNK_SIZE_ROWS):
            if "manufacturing_cost" in file_name:
                total_staged += StagingLoader.load_manufacturing_cost_chunk(self.session, batch_id, checksum, chunk)
            elif "hourly_production" in file_name:
                total_staged += StagingLoader.load_hourly_production_chunk(self.session, batch_id, checksum, chunk)
            elif "quality_inspection" in file_name:
                total_staged += StagingLoader.load_quality_inspection_chunk(self.session, batch_id, checksum, chunk)
            elif "bom_component" in file_name:
                total_staged += StagingLoader.load_bom_component_chunk(self.session, batch_id, checksum, chunk)
            elif "material_purchase" in file_name:
                total_staged += StagingLoader.load_material_purchase_chunk(self.session, batch_id, checksum, chunk)
            elif "material_consumption" in file_name:
                total_staged += StagingLoader.load_material_consumption_chunk(self.session, batch_id, checksum, chunk)
            elif "quality_rework" in file_name or "rework_event" in file_name:
                total_staged += StagingLoader.load_quality_rework_chunk(self.session, batch_id, checksum, chunk)

        batch.total_rows = total_staged
        batch.processing_status = "STAGED"
        self.session.commit()

        # Run Validation
        if "manufacturing_cost" in file_name:
            val_res = DataValidator.validate_manufacturing_cost_staged(self.session, batch_id)
        elif "hourly_production" in file_name:
            val_res = DataValidator.validate_hourly_production_staged(self.session, batch_id)
        elif "quality_inspection" in file_name:
            val_res = DataValidator.validate_quality_inspection_staged(self.session, batch_id)
        elif "bom_component" in file_name:
            val_res = DataValidator.validate_bom_component_staged(self.session, batch_id)
        elif "material_purchase" in file_name:
            val_res = DataValidator.validate_material_purchase_staged(self.session, batch_id)
        elif "material_consumption" in file_name:
            val_res = DataValidator.validate_material_consumption_staged(self.session, batch_id)
        elif "quality_rework" in file_name or "rework_event" in file_name:
            val_res = DataValidator.validate_quality_rework_staged(self.session, batch_id)
        else:
            val_res = {"valid_records": total_staged, "invalid_records": 0, "trust_score": 100.0}

        batch.valid_rows = val_res.get("valid_records", 0)
        batch.rejected_rows = val_res.get("invalid_records", 0)
        batch.processing_status = "VALIDATED"
        self.session.commit()

        if dry_run or not promote_now:
            return {
                "file_name": file_name,
                "batch_id": batch_id,
                "status": "DRY_RUN_VALIDATED" if dry_run else "VALIDATED_STAGED",
                "checksum": checksum,
                "total_staged": total_staged,
                "validation": val_res,
            }

        # Promote
        promoted_res = PromotionService.promote_batch(self.session, batch_id)

        return {
            "file_name": file_name,
            "batch_id": batch_id,
            "status": "PROMOTED",
            "checksum": checksum,
            "total_staged": total_staged,
            "validation": val_res,
            "promoted": promoted_res,
        }

    def import_all_manufacturing_datasets(self, data_dir: str, dry_run: bool = False) -> dict[str, Any]:
        """
        Executes end-to-end ingestion for all 4 manufacturing CSV datasets.
        """
        order = [
            ("fact_bom_component.csv", "BOM_COMPONENTS"),
            ("fact_manufacturing_cost.csv", "MANUFACTURING_COST"),
            ("fact_hourly_production.csv", "HOURLY_PRODUCTION"),
            ("fact_quality_inspection.csv", "QUALITY_INSPECTION"),
        ]

        overall_results: dict[str, Any] = {}
        batch_ids: dict[str, str] = {}

        # Phase 1: Stage and Validate all files (without immediate promotion)
        for fname, dtype in order:
            fpath = os.path.join(data_dir, fname)
            if not os.path.exists(fpath):
                alt_fpath = os.path.join(data_dir, "raw", fname)
                if os.path.exists(alt_fpath):
                    fpath = alt_fpath
                else:
                    raise FileNotFoundError(f"Missing required manufacturing dataset: {fpath}")

            logger.info(f"Staging and validating {fname}...")
            res = self.ingest_single_file(fpath, dtype, dry_run=dry_run, promote_now=False)
            overall_results[fname] = res
            if "batch_id" in res:
                batch_ids[fname] = res["batch_id"]

        # Phase 2: Resolve Costing Status for Hourly Production
        if "fact_hourly_production.csv" in batch_ids:
            prod_batch = batch_ids["fact_hourly_production.csv"]
            cost_batch = batch_ids.get("fact_manufacturing_cost.csv")
            trans_res = DataTransformer.resolve_production_costing_status(
                self.session,
                prod_batch_id=prod_batch,
                cost_batch_id=cost_batch,
            )
            overall_results["costing_status_resolution"] = trans_res

        # Phase 3: Transactional Promotion (if not dry run)
        if not dry_run:
            for fname, _ in order:
                if fname in batch_ids:
                    b_id = batch_ids[fname]
                    prom_res = PromotionService.promote_batch(self.session, b_id)
                    overall_results[fname]["promoted"] = prom_res
                    overall_results[fname]["status"] = "PROMOTED"

            # Phase 4: Financial Reconciliation Verification
            from sqlalchemy import text
            sql_recon = text("""
                SELECT 
                    COUNT(*) as record_count,
                    SUM(material_cost_inr) as material,
                    SUM(labour_cost_inr) as labour,
                    SUM(machine_cost_inr) as machine,
                    SUM(energy_cost_inr) as energy,
                    SUM(scrap_rework_cost_inr) as scrap_rework,
                    SUM(total_direct_cost_inr) as total_direct_cost
                FROM line_cost_batches
            """)
            recon_row = self.session.execute(sql_recon).mappings().one()
            
            actual_total = recon_row["total_direct_cost"] or Decimal("0.0")
            expected_total = EXPECTED_COST_TOTALS["total_direct_actual_cost"]
            diff = abs(actual_total - expected_total)
            
            overall_results["financial_reconciliation"] = {
                "records": recon_row["record_count"],
                "material_actual": str(recon_row["material"]),
                "labour_actual": str(recon_row["labour"]),
                "machine_actual": str(recon_row["machine"]),
                "energy_actual": str(recon_row["energy"]),
                "scrap_rework_actual": str(recon_row["scrap_rework"]),
                "total_direct_actual_cost": str(actual_total),
                "expected_total": str(expected_total),
                "difference": str(diff),
                "is_exact_match": (diff == Decimal("0.00")),
            }

        return overall_results
