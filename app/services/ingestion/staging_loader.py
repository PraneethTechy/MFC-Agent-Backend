"""
Manufacturing Cost Agent - Staging Loader
Bulk loads raw CSV records into PostgreSQL staging tables with audit tracking.
Supports all seven manufacturing dataset families:
1. fact_manufacturing_cost.csv
2. fact_hourly_production.csv
3. fact_quality_inspection.csv
4. fact_bom_component.csv
5. test_fact_material_purchases.csv / MATERIAL_PURCHASE
6. test_fact_material_consumption.csv / MATERIAL_CONSUMPTION
7. test_fact_quality_rework_events.csv / QUALITY_REWORK_EVENTS
"""

import logging
from typing import Any
from sqlalchemy.orm import Session
from app.models.real_datasets import (
    StgManufacturingCost,
    StgHourlyProduction,
    StgQualityInspection,
    StgBomComponent,
    StgMaterialPurchase,
    StgMaterialConsumption,
    StgQualityReworkEvent,
)
from .csv_reader import CsvReader

logger = logging.getLogger("manufacturing_cost_agent.ingestion.staging_loader")


class StagingLoader:
    """Inserts streaming CSV chunks into database staging tables."""

    @staticmethod
    def load_manufacturing_cost_chunk(
        session: Session,
        batch_id: str,
        checksum: str,
        chunk: list[dict[str, Any]],
    ) -> int:
        records: list[StgManufacturingCost] = []
        for row in chunk:
            rec = StgManufacturingCost(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                cost_record_id=row.get("cost_record_id"),
                posting_ts=CsvReader.parse_datetime(
                    row.get("posting_ts")
                    or row.get("production_timestamp")
                    or row.get("posting_date")
                    or row.get("date")
                ),
                plant_id=row.get("plant_id"),
                line_id=row.get("line_id"),
                production_order_id=row.get("production_order_id"),
                product_id=row.get("product_id"),
                produced_qty=CsvReader.parse_decimal(
                    row.get("produced_qty")
                    or row.get("produced_quantity")
                    or row.get("quantity")
                ),
                material_cost_inr=CsvReader.parse_decimal(row.get("material_cost_inr") or row.get("material_cost")),
                labour_cost_inr=CsvReader.parse_decimal(row.get("labour_cost_inr") or row.get("labour_cost")),
                machine_cost_inr=CsvReader.parse_decimal(row.get("machine_cost_inr") or row.get("machine_cost")),
                energy_cost_inr=CsvReader.parse_decimal(row.get("energy_cost_inr") or row.get("energy_cost")),
                scrap_rework_cost_inr=CsvReader.parse_decimal(row.get("scrap_rework_cost_inr") or row.get("scrap_rework_cost")),
                source_standard_cost_per_unit=CsvReader.parse_decimal(row.get("standard_cost_per_unit_inr")),
                currency=row.get("currency", "INR"),
                costing_version=row.get("costing_version", "COST-2026-Q3"),
                validation_status="PENDING",
            )
            records.append(rec)
        session.bulk_save_objects(records)
        session.flush()
        return len(records)

    @staticmethod
    def load_hourly_production_chunk(
        session: Session,
        batch_id: str,
        checksum: str,
        chunk: list[dict[str, Any]],
    ) -> int:
        records: list[StgHourlyProduction] = []
        for row in chunk:
            rec = StgHourlyProduction(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                event_id=row.get("event_id") or row.get("production_record_id"),
                event_ts=CsvReader.parse_datetime(
                    row.get("event_ts")
                    or row.get("event_timestamp")
                    or row.get("production_timestamp")
                    or row.get("timestamp")
                ),
                event_date=CsvReader.parse_date(
                    row.get("event_date")
                    or row.get("production_date")
                    or row.get("date")
                ),
                plant_id=row.get("plant_id"),
                line_id=row.get("line_id"),
                shift_id=row.get("shift_id", "SHIFT-1"),
                product_id=row.get("product_id"),
                production_order_id=row.get("production_order_id"),
                target_qty=CsvReader.parse_decimal(row.get("target_qty") or row.get("planned_qty")),
                actual_qty=CsvReader.parse_decimal(row.get("actual_qty")),
                good_qty=CsvReader.parse_decimal(row.get("good_qty")),
                reject_qty=CsvReader.parse_decimal(row.get("reject_qty") or row.get("rejected_qty")),
                rework_qty=CsvReader.parse_decimal(row.get("rework_qty")),
                downtime_min=CsvReader.parse_decimal(row.get("downtime_min") or row.get("downtime_minutes")),
                downtime_reason=row.get("downtime_reason"),
                operator_team=row.get("operator_team"),
                source_system=row.get("source_system", "MES"),
                data_quality=row.get("data_quality", "PENDING_CLASSIFICATION"),
                validation_status="PENDING",
            )
            records.append(rec)
        session.bulk_save_objects(records)
        session.flush()
        return len(records)

    @staticmethod
    def load_quality_inspection_chunk(
        session: Session,
        batch_id: str,
        checksum: str,
        chunk: list[dict[str, Any]],
    ) -> int:
        records: list[StgQualityInspection] = []
        for row in chunk:
            rec = StgQualityInspection(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                inspection_id=row.get("inspection_id"),
                inspection_ts=CsvReader.parse_datetime(row.get("inspection_ts") or row.get("inspection_timestamp")),
                plant_id=row.get("plant_id"),
                line_id=row.get("line_id"),
                station_id=row.get("station_id", "STN-MAIN"),
                product_id=row.get("product_id"),
                serial_number=row.get("serial_number") or f"SN-{row.get('inspection_id')}",
                production_order_id=row.get("production_order_id"),
                inspection_stage=row.get("inspection_stage") or row.get("inspection_type", "FINAL"),
                defect_code=row.get("defect_code", "NONE"),
                result=row.get("result") or row.get("inspection_result", "PASS"),
                severity=row.get("severity") or row.get("defect_severity", "NONE"),
                measurement_value=CsvReader.parse_decimal(row.get("measurement_value")) if row.get("measurement_value") else None,
                spec_min=CsvReader.parse_decimal(row.get("spec_min")) if row.get("spec_min") else None,
                spec_max=CsvReader.parse_decimal(row.get("spec_max")) if row.get("spec_max") else None,
                inspector_id=row.get("inspector_id"),
                disposition=row.get("disposition", "RELEASE"),
                spec_revision=row.get("spec_revision"),
                source_system=row.get("source_system", "QMS"),
                validation_status="PENDING",
            )
            records.append(rec)
        session.bulk_save_objects(records)
        session.flush()
        return len(records)

    @staticmethod
    def load_bom_component_chunk(
        session: Session,
        batch_id: str,
        checksum: str,
        chunk: list[dict[str, Any]],
    ) -> int:
        records: list[StgBomComponent] = []
        for row in chunk:
            rec = StgBomComponent(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                bom_id=row.get("bom_id") or row.get("bom_record_id"),
                product_id=row.get("product_id"),
                material_id=row.get("material_id") or row.get("component_id"),
                component_qty=CsvReader.parse_decimal(row.get("component_qty") or row.get("component_quantity_per_unit")),
                scrap_factor=CsvReader.parse_decimal(row.get("scrap_factor")),
                revision=row.get("revision", "REV-C"),
                effective_from=CsvReader.parse_date(row.get("effective_from")),
                effective_to=CsvReader.parse_date(row.get("effective_to")),
                validation_status="PENDING",
            )
            records.append(rec)
        session.bulk_save_objects(records)
        session.flush()
        return len(records)

    @staticmethod
    def load_material_purchase_chunk(
        session: Session,
        batch_id: str,
        checksum: str,
        chunk: list[dict[str, Any]],
    ) -> int:
        records: list[StgMaterialPurchase] = []
        for row in chunk:
            rec = StgMaterialPurchase(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                purchase_record_id=row.get("purchase_record_id") or row.get("purchase_line_id"),
                purchase_order_id=row.get("purchase_order_id"),
                goods_receipt_id=row.get("goods_receipt_id") or row.get("receipt_id"),
                receipt_date=CsvReader.parse_date(row.get("receipt_date") or row.get("invoice_date")),
                supplier_id=row.get("supplier_id") or row.get("supplier_code"),
                supplier_name=row.get("supplier_name", "Unknown Supplier"),
                component_id=row.get("component_id") or row.get("material_code") or row.get("material_id"),
                material_lot_id=row.get("material_lot_id") or row.get("receipt_id") or f"LOT-{row.get('purchase_line_id') or row.get('purchase_record_id')}",
                received_quantity=CsvReader.parse_decimal(row.get("received_quantity") or row.get("quantity")),
                rejected_quantity=CsvReader.parse_decimal(row.get("rejected_quantity") or 0.0),
                accepted_quantity=CsvReader.parse_decimal(row.get("accepted_quantity") or row.get("quantity")),
                reference_unit_price=CsvReader.parse_decimal(row.get("reference_unit_price") or row.get("unit_purchase_price_inr")),
                purchase_unit_price=CsvReader.parse_decimal(row.get("purchase_unit_price") or row.get("unit_purchase_price_inr")),
                duty_cost=CsvReader.parse_decimal(row.get("duty_cost") or row.get("duty_per_unit_inr")),
                freight_cost=CsvReader.parse_decimal(row.get("freight_cost") or row.get("freight_per_unit_inr")),
                landed_unit_cost=CsvReader.parse_decimal(row.get("landed_unit_cost") or row.get("landed_unit_cost_inr")),
                currency=row.get("currency", "INR"),
                data_origin=row.get("data_label") or row.get("data_origin", "REAL"),
                validation_status="PENDING",
            )
            records.append(rec)
        session.bulk_save_objects(records)
        session.flush()
        return len(records)

    @staticmethod
    def load_material_consumption_chunk(
        session: Session,
        batch_id: str,
        checksum: str,
        chunk: list[dict[str, Any]],
    ) -> int:
        records: list[StgMaterialConsumption] = []
        for row in chunk:
            c_ts = row.get("consumption_ts")
            p_date = row.get("production_date") or (str(c_ts)[:10] if c_ts else None)
            rec = StgMaterialConsumption(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                consumption_record_id=row.get("consumption_record_id") or row.get("consumption_id"),
                production_order_id=row.get("production_order_id"),
                cost_record_id=row.get("cost_record_id"),
                production_date=CsvReader.parse_date(p_date),
                plant_id=row.get("plant_id"),
                line_id=row.get("line_id"),
                product_id=row.get("product_id"),
                component_id=row.get("component_id") or row.get("material_code") or row.get("material_id"),
                bom_record_id=row.get("bom_record_id") or row.get("bom_id"),
                material_lot_id=row.get("material_lot_id") or f"LOT-{row.get('consumption_id') or row.get('consumption_record_id')}",
                goods_receipt_id=row.get("goods_receipt_id") or f"GRN-{row.get('consumption_id') or row.get('consumption_record_id')}",
                issued_quantity=CsvReader.parse_decimal(row.get("issued_quantity") or row.get("issued_qty")),
                returned_quantity=CsvReader.parse_decimal(row.get("returned_quantity") or row.get("returned_qty") or 0.0),
                net_consumed_quantity=CsvReader.parse_decimal(row.get("net_consumed_quantity") or row.get("net_consumed_qty")),
                bom_allowed_quantity=CsvReader.parse_decimal(row.get("bom_allowed_quantity") or row.get("net_consumed_qty")),
                scrap_quantity=CsvReader.parse_decimal(row.get("scrap_quantity") or 0.0),
                unit_of_measure=row.get("unit_of_measure") or row.get("uom", "PCS"),
                landed_unit_cost=CsvReader.parse_decimal(row.get("landed_unit_cost") or row.get("unit_landed_cost_inr")),
                consumed_value_inr=CsvReader.parse_decimal(row.get("consumed_value_inr")),
                data_origin=row.get("data_label") or row.get("data_origin", "REAL"),
                validation_status="PENDING",
            )
            records.append(rec)
        session.bulk_save_objects(records)
        session.flush()
        return len(records)

    @staticmethod
    def load_quality_rework_chunk(
        session: Session,
        batch_id: str,
        checksum: str,
        chunk: list[dict[str, Any]],
    ) -> int:
        records: list[StgQualityReworkEvent] = []
        for row in chunk:
            ev_ts = row.get("event_timestamp") or row.get("event_ts")
            ev_date = row.get("event_date") or (str(ev_ts)[:10] if ev_ts else None)
            rec = StgQualityReworkEvent(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                rework_event_id=row.get("rework_event_id") or row.get("quality_event_id"),
                inspection_id=row.get("inspection_id"),
                production_order_id=row.get("production_order_id"),
                event_timestamp=CsvReader.parse_datetime(ev_ts),
                event_date=CsvReader.parse_date(ev_date),
                plant_id=row.get("plant_id"),
                line_id=row.get("line_id"),
                product_id=row.get("product_id"),
                defect_code=row.get("defect_code"),
                rework_type=row.get("rework_type") or row.get("defect_type", "REWORK"),
                rework_quantity=CsvReader.parse_decimal(row.get("rework_quantity") or row.get("rework_qty")),
                scrap_quantity=CsvReader.parse_decimal(row.get("scrap_quantity") or row.get("rejected_qty") or 0.0),
                rework_hours=CsvReader.parse_decimal(row.get("rework_hours")),
                labour_cost=CsvReader.parse_decimal(row.get("labour_cost") or row.get("rework_labour_cost_inr")),
                material_cost=CsvReader.parse_decimal(row.get("material_cost") or 0.0),
                scrap_cost=CsvReader.parse_decimal(row.get("scrap_cost") or row.get("other_remediation_cost_inr") or 0.0),
                total_rework_cost=CsvReader.parse_decimal(row.get("total_rework_cost") or row.get("actual_rework_expenditure_inr")),
                disposition=row.get("disposition", "PARTIAL_SCRAP"),
                data_origin=row.get("data_label") or row.get("data_origin", "REAL"),
                validation_status="PENDING",
            )
            records.append(rec)
        session.bulk_save_objects(records)
        session.flush()
        return len(records)
