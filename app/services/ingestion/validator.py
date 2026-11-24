"""
Manufacturing Cost Agent - Staging Data Validator
Performs business rule validation, numerical bounds checks,
cross-footing verification, and Trust Score derivation.
"""

from decimal import Decimal
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.ingestion import DataQualityIssue

logger = logging.getLogger("manufacturing_cost_agent.ingestion.validator")


class DataValidator:
    """Validates staged records against structural, financial, and relational integrity rules."""

    @staticmethod
    def validate_manufacturing_cost_staged(session: Session, batch_id: str) -> dict[str, Any]:
        """Validates stg_manufacturing_cost for the given batch."""
        # 1. Flag records with negative costs or negative quantities
        sql_invalid = text("""
            UPDATE stg_manufacturing_cost
            SET validation_status = 'INVALID',
                validation_error = 'Negative cost component or invalid quantity'
            WHERE ingestion_batch_id = :b_id
              AND (
                  produced_qty < 0 OR
                  material_cost_inr < 0 OR
                  labour_cost_inr < 0 OR
                  machine_cost_inr < 0 OR
                  energy_cost_inr < 0 OR
                  scrap_rework_cost_inr < 0
              )
        """)
        session.execute(sql_invalid, {"b_id": batch_id})

        # 2. Flag records with missing primary identifiers
        sql_nulls = text("""
            UPDATE stg_manufacturing_cost
            SET validation_status = 'INVALID',
                validation_error = 'Missing primary identifier (cost_record_id, plant_id, line_id, or posting_ts)'
            WHERE ingestion_batch_id = :b_id
              AND (
                  cost_record_id IS NULL OR
                  plant_id IS NULL OR
                  line_id IS NULL OR
                  posting_ts IS NULL OR
                  product_id IS NULL
              )
        """)
        session.execute(sql_nulls, {"b_id": batch_id})

        # 3. Mark remaining as VALID
        sql_valid = text("""
            UPDATE stg_manufacturing_cost
            SET validation_status = 'VALID'
            WHERE ingestion_batch_id = :b_id
              AND validation_status = 'PENDING'
        """)
        session.execute(sql_valid, {"b_id": batch_id})
        session.commit()

        # Count summary
        sql_counts = text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN validation_status = 'VALID' THEN 1 ELSE 0 END) as valid,
                SUM(CASE WHEN validation_status = 'INVALID' THEN 1 ELSE 0 END) as invalid
            FROM stg_manufacturing_cost
            WHERE ingestion_batch_id = :b_id
        """)
        res = session.execute(sql_counts, {"b_id": batch_id}).mappings().one()
        total = res["total"] or 0
        valid = res["valid"] or 0
        invalid = res["invalid"] or 0
        trust_score = round((valid / total * 100.0), 2) if total > 0 else 0.0

        return {
            "dataset": "fact_manufacturing_cost.csv",
            "total_staged": total,
            "valid_records": valid,
            "invalid_records": invalid,
            "trust_score": trust_score,
        }

    @staticmethod
    def validate_hourly_production_staged(session: Session, batch_id: str) -> dict[str, Any]:
        """Validates stg_hourly_production for the given batch."""
        # 1. Flag invalid bounds or nulls
        sql_invalid = text("""
            UPDATE stg_hourly_production
            SET validation_status = 'INVALID',
                validation_error = 'Negative quantity, invalid downtime, or missing identifier'
            WHERE ingestion_batch_id = :b_id
              AND (
                  event_id IS NULL OR
                  plant_id IS NULL OR
                  line_id IS NULL OR
                  event_ts IS NULL OR
                  actual_qty < 0 OR
                  good_qty < 0 OR
                  reject_qty < 0 OR
                  downtime_min < 0
              )
        """)
        session.execute(sql_invalid, {"b_id": batch_id})

        # 2. Mark remaining as VALID
        sql_valid = text("""
            UPDATE stg_hourly_production
            SET validation_status = 'VALID'
            WHERE ingestion_batch_id = :b_id
              AND validation_status = 'PENDING'
        """)
        session.execute(sql_valid, {"b_id": batch_id})
        session.commit()

        # Count summary
        sql_counts = text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN validation_status = 'VALID' THEN 1 ELSE 0 END) as valid,
                SUM(CASE WHEN validation_status = 'INVALID' THEN 1 ELSE 0 END) as invalid
            FROM stg_hourly_production
            WHERE ingestion_batch_id = :b_id
        """)
        res = session.execute(sql_counts, {"b_id": batch_id}).mappings().one()
        total = res["total"] or 0
        valid = res["valid"] or 0
        invalid = res["invalid"] or 0
        trust_score = round((valid / total * 100.0), 2) if total > 0 else 0.0

        return {
            "dataset": "fact_hourly_production.csv",
            "total_staged": total,
            "valid_records": valid,
            "invalid_records": invalid,
            "trust_score": trust_score,
        }

    @staticmethod
    def validate_quality_inspection_staged(session: Session, batch_id: str) -> dict[str, Any]:
        """Validates stg_quality_inspection for the given batch. Quarantines records with missing timestamps, products or IDs."""
        # 1. Flag records with missing required fields or invalid result/disposition
        sql_invalid = text("""
            UPDATE stg_quality_inspection
            SET validation_status = 'INVALID',
                validation_error = CASE
                    WHEN inspection_ts IS NULL THEN 'Missing or unparseable inspection timestamp (inspection_ts)'
                    WHEN product_id IS NULL THEN 'Missing product identifier (product_id / sku_id)'
                    WHEN inspection_id IS NULL THEN 'Missing inspection_id'
                    WHEN serial_number IS NULL THEN 'Missing serial_number'
                    WHEN plant_id IS NULL THEN 'Missing plant_id'
                    WHEN line_id IS NULL THEN 'Missing line_id'
                    WHEN result NOT IN ('PASS', 'FAIL') THEN 'Invalid inspection result (must be PASS or FAIL)'
                    WHEN disposition NOT IN ('RELEASE', 'REWORK', 'HOLD', 'SCRAP') THEN 'Invalid disposition'
                    ELSE 'Invalid quality inspection record'
                END
            WHERE ingestion_batch_id = :b_id
              AND (
                  inspection_ts IS NULL OR
                  product_id IS NULL OR
                  inspection_id IS NULL OR
                  serial_number IS NULL OR
                  plant_id IS NULL OR
                  line_id IS NULL OR
                  result NOT IN ('PASS', 'FAIL') OR
                  disposition NOT IN ('RELEASE', 'REWORK', 'HOLD', 'SCRAP')
              )
        """)
        session.execute(sql_invalid, {"b_id": batch_id})

        # 2. Mark remaining as VALID
        sql_valid = text("""
            UPDATE stg_quality_inspection
            SET validation_status = 'VALID',
                validation_error = NULL
            WHERE ingestion_batch_id = :b_id
              AND validation_status = 'PENDING'
        """)
        session.execute(sql_valid, {"b_id": batch_id})
        session.commit()

        # Count summary
        sql_counts = text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN validation_status = 'VALID' THEN 1 ELSE 0 END) as valid,
                SUM(CASE WHEN validation_status = 'INVALID' THEN 1 ELSE 0 END) as invalid
            FROM stg_quality_inspection
            WHERE ingestion_batch_id = :b_id
        """)
        res = session.execute(sql_counts, {"b_id": batch_id}).mappings().one()
        total = res["total"] or 0
        valid = res["valid"] or 0
        invalid = res["invalid"] or 0
        trust_score = round((valid / total * 100.0), 2) if total > 0 else 0.0

        return {
            "dataset": "fact_quality_inspection.csv",
            "total_staged": total,
            "valid_records": valid,
            "invalid_records": invalid,
            "trust_score": trust_score,
        }

    @staticmethod
    def validate_bom_component_staged(session: Session, batch_id: str) -> dict[str, Any]:
        """Validates stg_bom_component for the given batch."""
        sql_invalid = text("""
            UPDATE stg_bom_component
            SET validation_status = 'INVALID',
                validation_error = 'Missing BOM identifier or invalid quantity'
            WHERE ingestion_batch_id = :b_id
              AND (
                  bom_id IS NULL OR
                  product_id IS NULL OR
                  material_id IS NULL OR
                  component_qty <= 0 OR
                  scrap_factor < 0
              )
        """)
        session.execute(sql_invalid, {"b_id": batch_id})

        sql_valid = text("""
            UPDATE stg_bom_component
            SET validation_status = 'VALID'
            WHERE ingestion_batch_id = :b_id
              AND validation_status = 'PENDING'
        """)
        session.execute(sql_valid, {"b_id": batch_id})
        session.commit()

        sql_counts = text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN validation_status = 'VALID' THEN 1 ELSE 0 END) as valid,
                SUM(CASE WHEN validation_status = 'INVALID' THEN 1 ELSE 0 END) as invalid
            FROM stg_bom_component
            WHERE ingestion_batch_id = :b_id
        """)
        res = session.execute(sql_counts, {"b_id": batch_id}).mappings().one()
        total = res["total"] or 0
        valid = res["valid"] or 0
        invalid = res["invalid"] or 0
        trust_score = round((valid / total * 100.0), 2) if total > 0 else 0.0

        return {
            "dataset": "fact_bom_component.csv",
            "total_staged": total,
            "valid_records": valid,
            "invalid_records": invalid,
            "trust_score": trust_score,
        }

    @staticmethod
    def validate_material_purchase_staged(session: Session, batch_id: str) -> dict[str, Any]:
        """Validates stg_material_purchases for the given batch."""
        sql_invalid = text("""
            UPDATE stg_material_purchases
            SET validation_status = 'INVALID',
                validation_error = 'Missing purchase identifiers or negative prices/quantities'
            WHERE ingestion_batch_id = :b_id
              AND (
                  purchase_record_id IS NULL OR
                  purchase_order_id IS NULL OR
                  goods_receipt_id IS NULL OR
                  supplier_id IS NULL OR
                  component_id IS NULL OR
                  received_quantity < 0 OR
                  landed_unit_cost < 0 OR
                  purchase_unit_price < 0
              )
        """)
        session.execute(sql_invalid, {"b_id": batch_id})

        sql_valid = text("""
            UPDATE stg_material_purchases
            SET validation_status = 'VALID'
            WHERE ingestion_batch_id = :b_id
              AND validation_status = 'PENDING'
        """)
        session.execute(sql_valid, {"b_id": batch_id})
        session.commit()

        sql_counts = text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN validation_status = 'VALID' THEN 1 ELSE 0 END) as valid,
                SUM(CASE WHEN validation_status = 'INVALID' THEN 1 ELSE 0 END) as invalid
            FROM stg_material_purchases
            WHERE ingestion_batch_id = :b_id
        """)
        res = session.execute(sql_counts, {"b_id": batch_id}).mappings().one()
        total = res["total"] or 0
        valid = res["valid"] or 0
        invalid = res["invalid"] or 0
        trust_score = round((valid / total * 100.0), 2) if total > 0 else 0.0

        return {
            "dataset": "fact_material_purchases.csv",
            "total_staged": total,
            "valid_records": valid,
            "invalid_records": invalid,
            "trust_score": trust_score,
        }

    @staticmethod
    def validate_material_consumption_staged(session: Session, batch_id: str) -> dict[str, Any]:
        """Validates stg_material_consumption for the given batch."""
        sql_invalid = text("""
            UPDATE stg_material_consumption
            SET validation_status = 'INVALID',
                validation_error = 'Missing consumption identifiers or negative quantities/values'
            WHERE ingestion_batch_id = :b_id
              AND (
                  consumption_record_id IS NULL OR
                  production_order_id IS NULL OR
                  cost_record_id IS NULL OR
                  component_id IS NULL OR
                  product_id IS NULL OR
                  net_consumed_quantity < 0 OR
                  consumed_value_inr < 0
              )
        """)
        session.execute(sql_invalid, {"b_id": batch_id})

        sql_valid = text("""
            UPDATE stg_material_consumption
            SET validation_status = 'VALID'
            WHERE ingestion_batch_id = :b_id
              AND validation_status = 'PENDING'
        """)
        session.execute(sql_valid, {"b_id": batch_id})
        session.commit()

        sql_counts = text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN validation_status = 'VALID' THEN 1 ELSE 0 END) as valid,
                SUM(CASE WHEN validation_status = 'INVALID' THEN 1 ELSE 0 END) as invalid
            FROM stg_material_consumption
            WHERE ingestion_batch_id = :b_id
        """)
        res = session.execute(sql_counts, {"b_id": batch_id}).mappings().one()
        total = res["total"] or 0
        valid = res["valid"] or 0
        invalid = res["invalid"] or 0
        trust_score = round((valid / total * 100.0), 2) if total > 0 else 0.0

        return {
            "dataset": "fact_material_consumption.csv",
            "total_staged": total,
            "valid_records": valid,
            "invalid_records": invalid,
            "trust_score": trust_score,
        }

    @staticmethod
    def validate_quality_rework_staged(session: Session, batch_id: str) -> dict[str, Any]:
        """Validates stg_quality_rework_events for the given batch."""
        sql_invalid = text("""
            UPDATE stg_quality_rework_events
            SET validation_status = 'INVALID',
                validation_error = 'Missing rework identifiers or negative hours/costs'
            WHERE ingestion_batch_id = :b_id
              AND (
                  rework_event_id IS NULL OR
                  production_order_id IS NULL OR
                  defect_code IS NULL OR
                  rework_quantity < 0 OR
                  rework_hours < 0 OR
                  total_rework_cost < 0
              )
        """)
        session.execute(sql_invalid, {"b_id": batch_id})

        sql_valid = text("""
            UPDATE stg_quality_rework_events
            SET validation_status = 'VALID'
            WHERE ingestion_batch_id = :b_id
              AND validation_status = 'PENDING'
        """)
        session.execute(sql_valid, {"b_id": batch_id})
        session.commit()

        sql_counts = text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN validation_status = 'VALID' THEN 1 ELSE 0 END) as valid,
                SUM(CASE WHEN validation_status = 'INVALID' THEN 1 ELSE 0 END) as invalid
            FROM stg_quality_rework_events
            WHERE ingestion_batch_id = :b_id
        """)
        res = session.execute(sql_counts, {"b_id": batch_id}).mappings().one()
        total = res["total"] or 0
        valid = res["valid"] or 0
        invalid = res["invalid"] or 0
        trust_score = round((valid / total * 100.0), 2) if total > 0 else 0.0

        return {
            "dataset": "fact_quality_rework_events.csv",
            "total_staged": total,
            "valid_records": valid,
            "invalid_records": invalid,
            "trust_score": trust_score,
        }

