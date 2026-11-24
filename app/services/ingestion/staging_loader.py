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
from decimal import Decimal
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
    @staticmethod
    def load_manufacturing_cost_chunk(
        session: Session,
        batch_id: str,
        checksum: str,
        chunk: list[dict[str, Any]],
        column_mapping: dict[str, str] | None = None,
    ) -> int:
        records: list[StgManufacturingCost] = []
        mapping = column_mapping or {}

        for row in chunk:
            cost_rec_id = (
                (row.get(mapping.get("cost_record_id")) if mapping.get("cost_record_id") in row else None)
                or row.get("cost_record_id")
                or row.get("cost_id")
                or row.get("record_id")
            )

            mapped_ts = mapping.get("posting_ts") or mapping.get("cost_date") or mapping.get("posting_date")
            ts = (
                (CsvReader.parse_datetime(row.get(mapped_ts)) if mapped_ts and mapped_ts in row else None)
                or CsvReader.parse_datetime(
                    row.get("cost_date")
                    or row.get("posting_ts")
                    or row.get("posting_date")
                    or row.get("production_timestamp")
                    or row.get("date")
                    or row.get("timestamp")
                )
            )

            mapped_plant = mapping.get("plant_id") or mapping.get("plant_code")
            plant_id = (
                (row.get(mapped_plant) if mapped_plant and mapped_plant in row else None)
                or row.get("plant_id")
                or row.get("plant_code")
                or row.get("plant")
            )

            mapped_line = mapping.get("line_id") or mapping.get("line_code")
            line_id = (
                (row.get(mapped_line) if mapped_line and mapped_line in row else None)
                or row.get("line_id")
                or row.get("line_code")
                or row.get("line")
            )

            mapped_po = mapping.get("production_order_id")
            po_id = (
                (row.get(mapped_po) if mapped_po and mapped_po in row else None)
                or row.get("production_order_id")
                or row.get("order_id")
                or row.get("run_id")
                or row.get("work_order")
            )

            mapped_prod = mapping.get("product_id") or mapping.get("sku_id") or mapping.get("product_code")
            product_id = (
                (row.get(mapped_prod) if mapped_prod and mapped_prod in row else None)
                or row.get("product_id")
                or row.get("sku_id")
                or row.get("product_code")
                or row.get("sku")
                or row.get("item_code")
            )

            mapped_qty = mapping.get("produced_qty") or mapping.get("units_produced")
            produced_qty = (
                (CsvReader.parse_decimal(row.get(mapped_qty)) if mapped_qty and mapped_qty in row else None)
                or CsvReader.parse_decimal(
                    row.get("produced_qty")
                    or row.get("units_produced")
                    or row.get("produced_quantity")
                    or row.get("good_units")
                    or row.get("quantity")
                )
            )

            mat_cost = CsvReader.parse_decimal(
                (row.get(mapping.get("material_cost_inr")) if mapping.get("material_cost_inr") in row else None)
                or row.get("material_cost_inr")
                or row.get("material_cost")
            )
            lab_cost = CsvReader.parse_decimal(
                (row.get(mapping.get("labour_cost_inr")) if mapping.get("labour_cost_inr") in row else None)
                or row.get("labour_cost_inr")
                or row.get("labour_cost")
            )
            mac_cost = CsvReader.parse_decimal(
                (row.get(mapping.get("machine_cost_inr")) if mapping.get("machine_cost_inr") in row else None)
                or row.get("machine_cost_inr")
                or row.get("overhead_cost")
                or row.get("machine_cost")
            )
            nrg_cost = CsvReader.parse_decimal(
                (row.get(mapping.get("energy_cost_inr")) if mapping.get("energy_cost_inr") in row else None)
                or row.get("energy_cost_inr")
                or row.get("energy_cost")
            )
            scr_cost = CsvReader.parse_decimal(
                (row.get(mapping.get("scrap_rework_cost_inr")) if mapping.get("scrap_rework_cost_inr") in row else None)
                or row.get("scrap_rework_cost_inr")
                or row.get("rework_cost")
                or row.get("scrap_cost")
                or row.get("scrap_rework_cost")
            )
            std_cost = CsvReader.parse_decimal(
                (row.get(mapping.get("standard_cost_per_unit_inr")) if mapping.get("standard_cost_per_unit_inr") in row else None)
                or row.get("standard_cost_per_unit_inr")
                or row.get("cost_per_good_unit")
            )

            rec = StgManufacturingCost(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                cost_record_id=cost_rec_id,
                posting_ts=ts,
                plant_id=plant_id,
                line_id=line_id,
                production_order_id=po_id,
                product_id=product_id,
                produced_qty=produced_qty,
                material_cost_inr=mat_cost,
                labour_cost_inr=lab_cost,
                machine_cost_inr=mac_cost,
                energy_cost_inr=nrg_cost,
                scrap_rework_cost_inr=scr_cost,
                source_standard_cost_per_unit=std_cost,
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
        column_mapping: dict[str, str] | None = None,
    ) -> int:
        records: list[StgHourlyProduction] = []
        mapping = column_mapping or {}

        for row in chunk:
            ev_id = (
                (row.get(mapping.get("event_id")) if mapping.get("event_id") in row else None)
                or row.get("event_id")
                or row.get("run_id")
                or row.get("production_record_id")
                or row.get("production_run_id")
            )

            ev_ts = (
                (CsvReader.parse_datetime(row.get(mapping.get("event_ts"))) if mapping.get("event_ts") in row else None)
                or CsvReader.parse_datetime(
                    row.get("event_ts")
                    or row.get("shift_start")
                    or row.get("run_date")
                    or row.get("event_timestamp")
                    or row.get("production_timestamp")
                    or row.get("timestamp")
                    or row.get("date")
                )
            )

            ev_date = (
                (CsvReader.parse_date(row.get(mapping.get("event_date"))) if mapping.get("event_date") in row else None)
                or CsvReader.parse_date(
                    row.get("event_date")
                    or row.get("run_date")
                    or row.get("production_date")
                    or (str(row.get("shift_start"))[:10] if row.get("shift_start") else None)
                    or row.get("date")
                )
            )

            plant_id = (
                (row.get(mapping.get("plant_id")) if mapping.get("plant_id") in row else None)
                or row.get("plant_id")
                or row.get("plant_code")
                or row.get("plant")
            )
            line_id = (
                (row.get(mapping.get("line_id")) if mapping.get("line_id") in row else None)
                or row.get("line_id")
                or row.get("line_code")
                or row.get("line")
            )
            shift_id = (
                (row.get(mapping.get("shift_id")) if mapping.get("shift_id") in row else None)
                or row.get("shift_id")
                or row.get("shift_code")
                or row.get("shift")
                or "SHIFT-1"
            )
            product_id = (
                (row.get(mapping.get("product_id")) if mapping.get("product_id") in row else None)
                or row.get("product_id")
                or row.get("sku_id")
                or row.get("product_code")
                or row.get("sku")
            )
            po_id = (
                (row.get(mapping.get("production_order_id")) if mapping.get("production_order_id") in row else None)
                or row.get("production_order_id")
                or row.get("order_id")
            )

            tgt_qty = CsvReader.parse_decimal(
                (row.get(mapping.get("target_qty")) if mapping.get("target_qty") in row else None)
                or row.get("target_qty")
                or row.get("planned_qty")
            )
            act_qty = CsvReader.parse_decimal(
                (row.get(mapping.get("actual_qty")) if mapping.get("actual_qty") in row else None)
                or row.get("actual_qty")
                or row.get("produced_qty")
            )
            good_qty = CsvReader.parse_decimal(
                (row.get(mapping.get("good_qty")) if mapping.get("good_qty") in row else None)
                or row.get("good_qty")
            )
            rej_qty = CsvReader.parse_decimal(
                (row.get(mapping.get("reject_qty")) if mapping.get("reject_qty") in row else None)
                or row.get("reject_qty")
                or row.get("scrap_qty")
                or row.get("rejected_qty")
            )
            rwk_qty = CsvReader.parse_decimal(
                (row.get(mapping.get("rework_qty")) if mapping.get("rework_qty") in row else None)
                or row.get("rework_qty")
            )

            downtime = CsvReader.parse_decimal(
                (row.get(mapping.get("downtime_min")) if mapping.get("downtime_min") in row else None)
                or row.get("downtime_min")
                or row.get("downtime_minutes")
            ) or Decimal("0.0")

            rec = StgHourlyProduction(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                event_id=ev_id,
                event_ts=ev_ts,
                event_date=ev_date,
                plant_id=plant_id,
                line_id=line_id,
                shift_id=shift_id,
                product_id=product_id,
                production_order_id=po_id,
                target_qty=tgt_qty,
                actual_qty=act_qty,
                good_qty=good_qty,
                reject_qty=rej_qty,
                rework_qty=rwk_qty,
                downtime_min=downtime,
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
        column_mapping: dict[str, str] | None = None,
    ) -> int:
        records: list[StgQualityInspection] = []
        mapping = column_mapping or {}

        for row in chunk:
            ts = CsvReader.resolve_inspection_timestamp(row, mapping)

            # Product ID / SKU resolution
            mapped_prod = mapping.get("product_id")
            product_id = (
                (row.get(mapped_prod) if mapped_prod and mapped_prod in row else None)
                or row.get("product_id")
                or row.get("product_code")
                or row.get("sku_id")
                or row.get("sku")
                or row.get("item_code")
                or row.get("material_id")
            )

            # Plant ID resolution
            mapped_plant = mapping.get("plant_id")
            plant_id = (
                (row.get(mapped_plant) if mapped_plant and mapped_plant in row else None)
                or row.get("plant_id")
                or row.get("plant_code")
                or row.get("plant")
            )

            # Line ID resolution
            mapped_line = mapping.get("line_id")
            line_id = (
                (row.get(mapped_line) if mapped_line and mapped_line in row else None)
                or row.get("line_id")
                or row.get("line_code")
                or row.get("line")
            )

            # Production Order ID / Run ID resolution
            mapped_po = mapping.get("production_order_id")
            po_id = (
                (row.get(mapped_po) if mapped_po and mapped_po in row else None)
                or row.get("production_order_id")
                or row.get("run_id")
                or row.get("order_id")
                or row.get("work_order")
            )
            insp_id = row.get("inspection_id")
            if not po_id:
                po_id = f"PO-{insp_id}" if insp_id else "PO-UNASSIGNED"

            # Serial number resolution
            mapped_serial = mapping.get("serial_number")
            serial_num = (
                (row.get(mapped_serial) if mapped_serial and mapped_serial in row else None)
                or row.get("serial_number")
                or row.get("serial")
                or row.get("unit_id")
                or (f"SN-{insp_id}" if insp_id else None)
            )

            # Result and defect analysis
            failed_qty_str = str(row.get("failed_qty") or "").strip()
            is_explicit_fail = False
            try:
                if failed_qty_str and float(failed_qty_str) > 0:
                    is_explicit_fail = True
            except ValueError:
                pass

            res_val = row.get("result") or row.get("inspection_result")
            if not res_val:
                res_val = "FAIL" if is_explicit_fail else "PASS"
            res_val = str(res_val).upper().strip()
            if res_val not in ("PASS", "FAIL"):
                res_val = "FAIL" if "FAIL" in res_val else "PASS"

            disp_val = row.get("disposition")
            if not disp_val:
                disp_val = "REWORK" if is_explicit_fail else "RELEASE"
            disp_val = str(disp_val).upper().strip()
            if disp_val not in ("RELEASE", "REWORK", "HOLD", "SCRAP"):
                disp_val = "REWORK" if is_explicit_fail else "RELEASE"

            defect_cd = row.get("defect_code") or row.get("defect") or row.get("fault_code")
            if not defect_cd:
                defect_candidates = [
                    ("display_defect", "DEF-DISP-01"),
                    ("solder_defect", "DEF-SLD-01"),
                    ("camera_defect", "DEF-CAM-01"),
                    ("cosmetic_defect", "DEF-COS-01"),
                    ("functional_defect", "DEF-FUNC-01"),
                    ("other_defect", "DEF-OTH-01"),
                ]
                highest_count = 0.0
                highest_code = "NONE"
                for col_name, code in defect_candidates:
                    try:
                        v = float(row.get(col_name) or 0)
                        if v > highest_count:
                            highest_count = v
                            highest_code = code
                    except ValueError:
                        pass
                defect_cd = highest_code if is_explicit_fail and highest_code != "NONE" else ("NONE" if res_val == "PASS" else "DEF-QUALITY-FAIL")

            sev_val = row.get("severity") or row.get("defect_severity")
            if not sev_val:
                sev_val = "NONE" if res_val == "PASS" else "MAJOR"

            rec = StgQualityInspection(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                inspection_id=insp_id,
                inspection_ts=ts,
                plant_id=plant_id,
                line_id=line_id,
                station_id=row.get("station_id") or "STN-MAIN",
                product_id=product_id,
                serial_number=serial_num,
                production_order_id=po_id,
                inspection_stage=row.get("inspection_stage") or row.get("inspection_type", "FINAL"),
                defect_code=defect_cd,
                result=res_val,
                severity=sev_val,
                measurement_value=CsvReader.parse_decimal(row.get("measurement_value")) if row.get("measurement_value") else None,
                spec_min=CsvReader.parse_decimal(row.get("spec_min")) if row.get("spec_min") else None,
                spec_max=CsvReader.parse_decimal(row.get("spec_max")) if row.get("spec_max") else None,
                inspector_id=row.get("inspector_id") or "INSP-QMS",
                disposition=disp_val,
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
        column_mapping: dict[str, str] | None = None,
    ) -> int:
        records: list[StgBomComponent] = []
        mapping = column_mapping or {}

        for row in chunk:
            b_id = (
                (row.get(mapping.get("bom_id")) if mapping.get("bom_id") in row else None)
                or row.get("bom_id")
                or row.get("bom_record_id")
            )
            p_id = (
                (row.get(mapping.get("product_id")) if mapping.get("product_id") in row else None)
                or row.get("product_id")
                or row.get("sku_id")
                or row.get("product_code")
            )
            m_id = (
                (row.get(mapping.get("material_id")) if mapping.get("material_id") in row else None)
                or row.get("material_id")
                or row.get("component_id")
                or row.get("material_code")
            )
            c_qty = CsvReader.parse_decimal(
                (row.get(mapping.get("component_qty")) if mapping.get("component_qty") in row else None)
                or row.get("component_qty")
                or row.get("component_quantity_per_unit")
            )
            s_fac = CsvReader.parse_decimal(
                (row.get(mapping.get("scrap_factor")) if mapping.get("scrap_factor") in row else None)
                or row.get("scrap_factor")
                or 0.0
            )

            rec = StgBomComponent(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                bom_id=b_id,
                product_id=p_id,
                material_id=m_id,
                component_qty=c_qty,
                scrap_factor=s_fac,
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
        column_mapping: dict[str, str] | None = None,
    ) -> int:
        records: list[StgMaterialPurchase] = []
        mapping = column_mapping or {}

        for row in chunk:
            po_id = (
                (row.get(mapping.get("purchase_order_id")) if mapping.get("purchase_order_id") in row else None)
                or row.get("purchase_order_id")
                or row.get("po_id")
                or row.get("order_id")
            )
            po_line = str(row.get("po_line") or "1")
            rec_id = (
                (row.get(mapping.get("purchase_record_id")) if mapping.get("purchase_record_id") in row else None)
                or row.get("purchase_record_id")
                or row.get("purchase_line_id")
                or (f"{po_id}-{po_line}" if po_id else None)
            )
            grn_id = (
                (row.get(mapping.get("goods_receipt_id")) if mapping.get("goods_receipt_id") in row else None)
                or row.get("goods_receipt_id")
                or row.get("receipt_id")
                or (f"GRN-{po_id}-{po_line}" if po_id else None)
            )
            rcpt_date = (
                (CsvReader.parse_date(row.get(mapping.get("receipt_date"))) if mapping.get("receipt_date") in row else None)
                or CsvReader.parse_date(row.get("receipt_date") or row.get("order_date") or row.get("invoice_date"))
            )
            supp_id = (
                (row.get(mapping.get("supplier_id")) if mapping.get("supplier_id") in row else None)
                or row.get("supplier_id")
                or row.get("supplier_code")
            )
            comp_id = (
                (row.get(mapping.get("material_id")) if mapping.get("material_id") in row else None)
                or row.get("component_id")
                or row.get("material_id")
                or row.get("material_code")
            )
            lot_id = row.get("lot_no") or row.get("material_lot_id") or f"LOT-{rec_id}"

            rec_qty = CsvReader.parse_decimal(
                (row.get(mapping.get("quantity")) if mapping.get("quantity") in row else None)
                or row.get("received_qty")
                or row.get("ordered_qty")
                or row.get("received_quantity")
                or row.get("quantity")
            )
            rej_qty = CsvReader.parse_decimal(row.get("rejected_qty") or row.get("rejected_quantity") or 0.0)
            acc_qty = CsvReader.parse_decimal(row.get("accepted_qty") or row.get("accepted_quantity") or rec_qty)

            u_price = CsvReader.parse_decimal(
                (row.get(mapping.get("unit_purchase_price_inr")) if mapping.get("unit_purchase_price_inr") in row else None)
                or row.get("unit_price")
                or row.get("purchase_unit_price")
                or row.get("unit_purchase_price_inr")
            )
            landed_cost = CsvReader.parse_decimal(
                row.get("landed_unit_cost") or row.get("landed_unit_cost_inr") or u_price
            )

            rec = StgMaterialPurchase(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                purchase_record_id=rec_id,
                purchase_order_id=po_id,
                goods_receipt_id=grn_id,
                receipt_date=rcpt_date,
                supplier_id=supp_id,
                supplier_name=row.get("supplier_name", f"Supplier {supp_id}"),
                component_id=comp_id,
                material_lot_id=lot_id,
                received_quantity=rec_qty,
                rejected_quantity=rej_qty,
                accepted_quantity=acc_qty,
                reference_unit_price=u_price,
                purchase_unit_price=u_price,
                duty_cost=CsvReader.parse_decimal(row.get("duty_cost") or 0.0),
                freight_cost=CsvReader.parse_decimal(row.get("freight_cost") or 0.0),
                landed_unit_cost=landed_cost,
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
        column_mapping: dict[str, str] | None = None,
    ) -> int:
        records: list[StgMaterialConsumption] = []
        mapping = column_mapping or {}

        for row in chunk:
            cons_id = (
                (row.get(mapping.get("consumption_id")) if mapping.get("consumption_id") in row else None)
                or row.get("consumption_id")
                or row.get("consumption_record_id")
            )
            po_id = (
                (row.get(mapping.get("production_order_id")) if mapping.get("production_order_id") in row else None)
                or row.get("production_order_id")
                or row.get("order_id")
            )
            p_date = (
                (CsvReader.parse_date(row.get(mapping.get("consumption_date"))) if mapping.get("consumption_date") in row else None)
                or CsvReader.parse_date(row.get("consumption_date") or row.get("production_date") or row.get("date"))
            )
            plant_id = (
                (row.get(mapping.get("plant_id")) if mapping.get("plant_id") in row else None)
                or row.get("plant_id")
                or row.get("plant_code")
            )
            line_id = (
                (row.get(mapping.get("line_id")) if mapping.get("line_id") in row else None)
                or row.get("line_id")
                or row.get("line_code")
            )
            product_id = (
                (row.get(mapping.get("product_id")) if mapping.get("product_id") in row else None)
                or row.get("product_id")
                or row.get("sku_id")
                or row.get("product_code")
                or row.get("sku")
            )
            comp_id = (
                (row.get(mapping.get("material_id")) if mapping.get("material_id") in row else None)
                or row.get("component_id")
                or row.get("material_id")
                or row.get("material_code")
            )

            act_qty = CsvReader.parse_decimal(
                (row.get(mapping.get("net_consumed_qty")) if mapping.get("net_consumed_qty") in row else None)
                or row.get("actual_qty")
                or row.get("net_consumed_quantity")
                or row.get("net_consumed_qty")
            )
            std_qty = CsvReader.parse_decimal(
                row.get("standard_qty") or row.get("bom_allowed_quantity") or act_qty
            )
            u_cost = CsvReader.parse_decimal(
                (row.get(mapping.get("unit_landed_cost_inr")) if mapping.get("unit_landed_cost_inr") in row else None)
                or row.get("unit_cost")
                or row.get("landed_unit_cost")
                or row.get("unit_landed_cost_inr")
            )
            mat_cost = CsvReader.parse_decimal(
                row.get("material_cost") or row.get("consumed_value_inr") or (act_qty * u_cost if act_qty and u_cost else 0.0)
            )

            rec = StgMaterialConsumption(
                ingestion_batch_id=batch_id,
                file_checksum_sha256=checksum,
                source_row_number=row.get("_source_row_number", 0),
                consumption_record_id=cons_id,
                production_order_id=po_id,
                cost_record_id=row.get("cost_record_id") or (f"MCR-{po_id}" if po_id else "MCR-UNASSIGNED"),
                production_date=p_date,
                plant_id=plant_id,
                line_id=line_id,
                product_id=product_id,
                component_id=comp_id,
                bom_record_id=row.get("bom_record_id") or row.get("bom_id") or (f"BOM-{product_id}" if product_id else "BOM-DEFAULT"),
                material_lot_id=row.get("lot_no") or row.get("material_lot_id") or f"LOT-{cons_id}",
                goods_receipt_id=row.get("goods_receipt_id") or f"GRN-{cons_id}",
                issued_quantity=act_qty,
                returned_quantity=Decimal("0.0"),
                net_consumed_quantity=act_qty,
                bom_allowed_quantity=std_qty,
                scrap_quantity=Decimal("0.0"),
                unit_of_measure=row.get("unit_of_measure") or row.get("uom", "EA"),
                landed_unit_cost=u_cost,
                consumed_value_inr=mat_cost,
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
        column_mapping: dict[str, str] | None = None,
    ) -> int:
        records: list[StgQualityReworkEvent] = []
        mapping = column_mapping or {}

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
                product_id=row.get("product_id") or row.get("sku_id"),
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
