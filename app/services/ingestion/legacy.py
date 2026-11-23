"""
Manufacturing Cost Agent - Legacy Ingestion Service Support
Maintains backward compatibility for existing endpoints and test suites:
- IngestionService
- DATASET_SCHEMAS
- ingestion_service instance
"""

import csv
import io
import logging
import uuid
from typing import Any, BinaryIO
import openpyxl

logger = logging.getLogger("manufacturing_cost_agent.ingestion.legacy")

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

DATASET_SCHEMAS: dict[str, dict[str, Any]] = {
    "MANUFACTURING_COST": {
        "label": "Manufacturing Direct Cost",
        "required_fields": [
            "cost_record_id",
            "posting_ts",
            "plant_id",
            "line_id",
            "production_order_id",
            "product_id",
            "produced_qty",
            "material_cost_inr",
            "labour_cost_inr",
            "machine_cost_inr",
            "energy_cost_inr",
            "scrap_rework_cost_inr",
        ],
        "optional_fields": [
            "standard_cost_per_unit_inr",
            "currency",
            "costing_version",
        ],
        "aliases": {
            "cost_record_id": ["cost_record_id", "record_id", "cost_id", "id"],
            "posting_ts": ["posting_ts", "posting_date", "timestamp", "date", "event_ts", "cost_date"],
            "plant_id": ["plant_id", "plant_code", "plant", "facility_id", "facility"],
            "line_id": ["line_id", "line_code", "line", "production_line"],
            "production_order_id": ["production_order_id", "order_id", "order_number", "work_order"],
            "product_id": ["product_id", "product_code", "sku", "item_code", "part_number", "sku_id"],
            "produced_qty": ["produced_qty", "quantity", "qty", "produced_quantity", "volume", "units_produced"],
            "material_cost_inr": ["material_cost_inr", "material_cost", "direct_material", "material"],
            "labour_cost_inr": ["labour_cost_inr", "labor_cost_inr", "labour_cost", "labor_cost", "direct_labor"],
            "machine_cost_inr": ["machine_cost_inr", "machine_cost", "equipment_cost", "machine", "overhead_cost"],
            "energy_cost_inr": ["energy_cost_inr", "energy_cost", "power_cost", "electricity"],
            "scrap_rework_cost_inr": ["scrap_rework_cost_inr", "scrap_cost", "rework_cost", "scrap_and_rework"],
            "standard_cost_per_unit_inr": ["standard_cost_per_unit_inr", "standard_cost", "std_unit_cost", "standard_cost_per_unit", "cost_per_good_unit"],
            "currency": ["currency", "curr"],
            "costing_version": ["costing_version", "version", "cost_version"],
        },
    },
    "HOURLY_PRODUCTION": {
        "label": "Hourly Production Logs",
        "required_fields": [
            "event_id",
            "event_ts",
            "plant_id",
            "line_id",
            "product_id",
            "production_order_id",
            "actual_qty",
            "good_qty",
            "reject_qty",
        ],
        "optional_fields": [
            "target_qty",
            "rework_qty",
            "downtime_min",
            "downtime_reason",
            "shift_id",
            "operator_team",
            "source_system",
        ],
        "aliases": {
            "event_id": ["event_id", "log_id", "id", "production_log_id"],
            "event_ts": ["event_ts", "timestamp", "datetime", "reading_time", "posting_ts"],
            "plant_id": ["plant_id", "plant_code", "plant", "facility"],
            "line_id": ["line_id", "line_code", "line"],
            "product_id": ["product_id", "product_code", "sku", "item_code"],
            "production_order_id": ["production_order_id", "order_id", "work_order", "order_number"],
            "actual_qty": ["actual_qty", "actual_quantity", "produced_qty", "volume"],
            "good_qty": ["good_qty", "good_output", "passed_qty", "yield_qty"],
            "reject_qty": ["reject_qty", "rejected_qty", "scrap_qty", "defects"],
            "target_qty": ["target_qty", "planned_qty", "planned"],
            "rework_qty": ["rework_qty", "reworked"],
            "downtime_min": ["downtime_min", "downtime", "idle_minutes"],
            "downtime_reason": ["downtime_reason", "reason", "stop_reason"],
            "shift_id": ["shift_id", "shift"],
            "operator_team": ["operator_team", "team", "operator"],
            "source_system": ["source_system", "system"],
        },
    },
    "QUALITY_INSPECTION": {
        "label": "Quality Inspection Records",
        "required_fields": [
            "inspection_id",
            "inspection_ts",
            "plant_id",
            "line_id",
            "product_id",
            "serial_number",
            "disposition",
        ],
        "optional_fields": [
            "production_order_id",
            "station_id",
            "defect_code",
            "result",
            "severity",
            "measurement_value",
            "spec_min",
            "spec_max",
            "inspector_id",
        ],
        "aliases": {
            "inspection_id": ["inspection_id", "id", "audit_id"],
            "inspection_ts": ["inspection_ts", "inspection_date", "timestamp", "date"],
            "plant_id": ["plant_id", "plant_code", "plant"],
            "line_id": ["line_id", "line_code", "line"],
            "product_id": ["product_id", "product_code", "sku", "item_code"],
            "serial_number": ["serial_number", "serial", "unit_id", "vin"],
            "disposition": ["disposition", "status", "decision", "action"],
            "production_order_id": ["production_order_id", "order_id", "work_order"],
            "station_id": ["station_id", "station", "stage"],
            "defect_code": ["defect_code", "defect", "fault_code"],
            "result": ["result", "outcome", "pass_fail"],
            "severity": ["severity", "criticality"],
            "measurement_value": ["measurement_value", "measurement", "value"],
            "spec_min": ["spec_min", "min_limit"],
            "spec_max": ["spec_max", "max_limit"],
            "inspector_id": ["inspector_id", "inspector", "operator"],
        },
    },
    "BOM_COMPONENT": {
        "label": "BOM Components & Structure",
        "required_fields": [
            "bom_id",
            "product_id",
            "material_id",
            "component_qty",
        ],
        "optional_fields": [
            "scrap_factor",
            "revision",
            "effective_from",
            "effective_to",
        ],
        "aliases": {
            "bom_id": ["bom_id", "id", "assembly_id", "bom_code"],
            "product_id": ["product_id", "parent_product", "product_code", "assembly_code"],
            "material_id": ["material_id", "component_id", "material_code", "part_number"],
            "component_qty": ["component_qty", "quantity", "qty", "qty_per"],
            "scrap_factor": ["scrap_factor", "scrap_rate", "scrap_pct"],
            "revision": ["revision", "rev", "version"],
            "effective_from": ["effective_from", "start_date"],
            "effective_to": ["effective_to", "end_date"],
        },
    },
    "MATERIAL_PURCHASE": {
        "label": "Material Purchase Invoices",
        "required_fields": [
            "purchase_line_id",
            "purchase_order_id",
            "supplier_id",
            "material_id",
            "quantity",
            "unit_purchase_price_inr",
            "landed_unit_cost_inr",
        ],
        "optional_fields": [
            "supplier_name",
            "receiving_plant_id",
            "invoice_no",
            "invoice_date",
            "receipt_id",
            "receipt_date",
            "uom",
            "price_basis",
            "duty_per_unit_inr",
            "freight_per_unit_inr",
            "invoice_amount_inr",
            "duty_amount_inr",
            "freight_amount_inr",
            "landed_total_inr",
            "currency",
            "data_label",
        ],
        "aliases": {
            "purchase_line_id": ["purchase_line_id", "po_line_id", "line_id", "purchase_id", "purchase_record_id"],
            "purchase_order_id": ["purchase_order_id", "po_number", "order_id", "po_id"],
            "supplier_id": ["supplier_id", "vendor_id", "supplier_code", "vendor_code"],
            "supplier_name": ["supplier_name", "vendor_name", "supplier", "vendor"],
            "receiving_plant_id": ["receiving_plant_id", "plant_id", "plant_code", "plant"],
            "material_id": ["material_id", "part_number", "material_code", "item_code", "component_id"],
            "quantity": ["quantity", "qty", "purchase_qty", "ordered_qty", "received_quantity", "accepted_quantity"],
            "uom": ["uom", "unit"],
            "unit_purchase_price_inr": ["unit_purchase_price_inr", "purchase_price", "unit_price", "po_price", "purchase_unit_price", "reference_unit_price"],
            "price_basis": ["price_basis", "basis"],
            "duty_per_unit_inr": ["duty_per_unit_inr", "duty_unit", "unit_duty"],
            "freight_per_unit_inr": ["freight_per_unit_inr", "freight_unit", "unit_freight"],
            "landed_unit_cost_inr": ["landed_unit_cost_inr", "landed_cost", "unit_landed_cost", "landed_price"],
            "invoice_no": ["invoice_no", "invoice_number", "inv_no"],
            "invoice_date": ["invoice_date", "inv_date", "date"],
            "receipt_id": ["receipt_id", "grn_id", "receipt_no"],
            "receipt_date": ["receipt_date", "grn_date", "delivery_date"],
            "invoice_amount_inr": ["invoice_amount_inr", "invoice_total", "po_amount"],
            "duty_amount_inr": ["duty_amount_inr", "duty_total"],
            "freight_amount_inr": ["freight_amount_inr", "freight_total"],
            "landed_total_inr": ["landed_total_inr", "total_landed_cost", "total_amount"],
            "currency": ["currency", "curr"],
            "data_label": ["data_label", "label"],
        },
    },
    "MATERIAL_CONSUMPTION": {
        "label": "Material Consumption Records",
        "required_fields": [
            "consumption_id",
            "cost_record_id",
            "production_order_id",
            "product_id",
            "material_id",
            "net_consumed_qty",
            "unit_landed_cost_inr",
        ],
        "optional_fields": [
            "event_id",
            "plant_id",
            "line_id",
            "bom_id",
            "uom",
            "issued_qty",
            "returned_qty",
            "consumed_value_inr",
            "consumption_ts",
            "currency",
            "data_label",
        ],
        "aliases": {
            "consumption_id": ["consumption_id", "issue_id", "id", "trans_id"],
            "cost_record_id": ["cost_record_id", "cost_id", "batch_id"],
            "event_id": ["event_id", "prod_event_id"],
            "production_order_id": ["production_order_id", "order_id", "work_order"],
            "product_id": ["product_id", "product_code", "sku"],
            "plant_id": ["plant_id", "plant_code", "plant"],
            "line_id": ["line_id", "line_code", "line"],
            "bom_id": ["bom_id", "bom_code"],
            "material_id": ["material_id", "component_id", "part_number", "material_code"],
            "uom": ["uom", "unit"],
            "issued_qty": ["issued_qty", "issue_qty"],
            "returned_qty": ["returned_qty", "return_qty"],
            "net_consumed_qty": ["net_consumed_qty", "consumed_qty", "quantity", "actual_qty", "actual_quantity"],
            "unit_landed_cost_inr": ["unit_landed_cost_inr", "unit_cost", "unit_price"],
            "consumed_value_inr": ["consumed_value_inr", "total_cost", "consumption_value"],
            "consumption_ts": ["consumption_ts", "posting_date", "timestamp", "date"],
            "currency": ["currency", "curr"],
            "data_label": ["data_label", "label"],
        },
    },
    "QUALITY_REWORK_EVENTS": {
        "label": "Quality Rework & Defect Events",
        "required_fields": [
            "quality_event_id",
            "defect_code",
            "rejected_qty",
            "rework_qty",
            "actual_rework_expenditure_inr",
        ],
        "optional_fields": [
            "inspection_id",
            "scrap_inspection_id",
            "event_id",
            "cost_record_id",
            "production_order_id",
            "product_id",
            "plant_id",
            "line_id",
            "defect_type",
            "rework_hours",
            "rework_labour_rate_inr_per_hr",
            "rework_labour_cost_inr",
            "other_remediation_cost_inr",
            "event_ts",
            "currency",
            "data_label",
        ],
        "aliases": {
            "quality_event_id": ["quality_event_id", "event_id", "id", "rework_id", "rework_event_id"],
            "inspection_id": ["inspection_id", "audit_id"],
            "scrap_inspection_id": ["scrap_inspection_id"],
            "cost_record_id": ["cost_record_id", "cost_id"],
            "production_order_id": ["production_order_id", "order_id", "work_order"],
            "product_id": ["product_id", "product_code", "sku"],
            "plant_id": ["plant_id", "plant_code", "plant"],
            "line_id": ["line_id", "line_code", "line"],
            "defect_code": ["defect_code", "defect", "fault_code", "reason_code"],
            "defect_type": ["defect_type", "type", "category"],
            "rejected_qty": ["rejected_qty", "scrap_qty", "reject_qty", "scrap_quantity"],
            "rework_qty": ["rework_qty", "reworked_units", "rework_quantity"],
            "rework_hours": ["rework_hours", "hours", "rework_time"],
            "rework_labour_rate_inr_per_hr": ["rework_labour_rate_inr_per_hr", "labour_rate"],
            "rework_labour_cost_inr": ["rework_labour_cost_inr", "rework_cost", "labour_cost"],
            "other_remediation_cost_inr": ["other_remediation_cost_inr", "other_cost"],
            "actual_rework_expenditure_inr": ["actual_rework_expenditure_inr", "rework_expenditure", "total_rework_cost"],
            "event_ts": ["event_ts", "timestamp", "date"],
            "currency": ["currency", "curr"],
            "data_label": ["data_label", "label"],
        },
    },
    "PLANTS": {
        "label": "Manufacturing Plants",
        "required_fields": ["code", "name", "location"],
        "optional_fields": ["country", "currency", "capacity_hours_month"],
        "aliases": {
            "code": ["plant_code", "plant", "facility_code", "code", "site_id"],
            "name": ["plant_name", "facility_name", "name", "site_name"],
            "location": ["city", "location", "address"],
            "country": ["country", "nation"],
            "currency": ["curr", "currency"],
            "capacity_hours_month": ["capacity", "monthly_hours", "capacity_hours"],
        },
    },
    "PRODUCTS": {
        "label": "Products & Assemblies",
        "required_fields": ["code", "name", "product_group"],
        "optional_fields": ["uom", "standard_batch_size"],
        "aliases": {
            "code": ["product_code", "part_number", "item_code", "sku", "code"],
            "name": ["product_name", "description", "item_name", "name"],
            "product_group": ["group", "category", "family", "product_group"],
            "uom": ["uom", "unit", "unit_of_measure"],
            "standard_batch_size": ["batch_size", "lot_size", "standard_batch_size"],
        },
    },
    "MATERIALS": {
        "label": "Materials & Components",
        "required_fields": ["code", "name", "material_type", "base_uom"],
        "optional_fields": ["standard_unit_price", "currency"],
        "aliases": {
            "code": ["material_code", "part_code", "material_id", "code"],
            "name": ["material_name", "description", "name"],
            "material_type": ["type", "category", "material_type"],
            "base_uom": ["uom", "unit", "base_uom"],
            "standard_unit_price": ["std_price", "unit_cost", "standard_price", "standard_unit_price"],
            "currency": ["currency", "curr"],
        },
    },
    "SUPPLIERS": {
        "label": "Suppliers & Vendors",
        "required_fields": ["code", "name"],
        "optional_fields": ["country", "payment_terms", "reliability_rating"],
        "aliases": {
            "code": ["supplier_code", "vendor_id", "code", "vendor_code"],
            "name": ["supplier_name", "vendor_name", "name", "company_name"],
            "country": ["country", "nation"],
            "payment_terms": ["terms", "payment_terms"],
            "reliability_rating": ["rating", "score", "reliability_rating"],
        },
    },
    "PRODUCTION_ORDERS": {
        "label": "Production Work Orders",
        "required_fields": ["order_number", "plant_code", "product_code", "period_code", "planned_qty", "start_date"],
        "optional_fields": ["actual_qty", "scrap_qty", "rework_qty", "status", "completion_date"],
        "aliases": {
            "order_number": ["order_num", "order_id", "work_order", "wo_number", "order_number"],
            "plant_code": ["plant", "plant_id", "facility", "plant_code"],
            "product_code": ["product", "sku", "part_number", "product_code"],
            "period_code": ["period", "month", "fiscal_period", "period_code"],
            "planned_qty": ["planned", "target_qty", "order_qty", "planned_qty"],
            "actual_qty": ["actual", "completed_qty", "good_qty", "actual_qty"],
            "scrap_qty": ["scrap", "defects", "scrap_qty"],
            "rework_qty": ["rework", "rework_qty"],
            "status": ["status", "state", "order_status"],
            "start_date": ["start", "order_date", "release_date", "start_date"],
            "completion_date": ["close_date", "end_date", "completion_date"],
        },
    },
    "MATERIAL_POSTINGS": {
        "label": "Material Consumption Postings",
        "required_fields": ["order_number", "material_code", "posting_date", "actual_quantity", "unit_price"],
        "optional_fields": ["uom", "supplier_code", "lot_number", "freight_component", "duty_component", "currency"],
        "aliases": {
            "order_number": ["work_order", "order_id", "order_number", "wo"],
            "material_code": ["material", "part_number", "material_code"],
            "posting_date": ["date", "consumption_date", "posting_date"],
            "actual_quantity": ["qty", "quantity", "consumed_qty", "actual_quantity"],
            "unit_price": ["price", "rate", "po_price", "unit_price"],
            "uom": ["uom", "unit"],
            "supplier_code": ["supplier", "vendor", "supplier_code"],
            "lot_number": ["lot", "batch", "lot_number"],
            "freight_component": ["freight", "shipping", "freight_component"],
            "duty_component": ["duty", "tariff", "duty_component"],
            "currency": ["currency", "curr"],
        },
    },
    "LABOUR_POSTINGS": {
        "label": "Labour & Shift Postings",
        "required_fields": ["work_centre_code", "posting_date", "operation_name", "regular_hours", "hourly_rate"],
        "optional_fields": ["order_number", "shift", "overtime_hours", "overtime_premium_rate"],
        "aliases": {
            "work_centre_code": ["work_centre", "work_center", "cell", "machine", "work_centre_code"],
            "posting_date": ["date", "work_date", "posting_date"],
            "operation_name": ["operation", "process", "task", "operation_name"],
            "regular_hours": ["hours", "reg_hours", "direct_hours", "regular_hours"],
            "hourly_rate": ["rate", "wage_rate", "hourly_rate"],
            "order_number": ["order_id", "work_order", "order_number"],
            "shift": ["shift", "shift_num"],
            "overtime_hours": ["ot_hours", "overtime", "overtime_hours"],
            "overtime_premium_rate": ["ot_rate", "premium", "overtime_premium_rate"],
        },
    },
    "MACHINE_EVENTS": {
        "label": "Machine Operations & Downtime",
        "required_fields": ["work_centre_code", "event_date", "run_hours", "hourly_rate"],
        "optional_fields": ["order_number", "setup_hours", "downtime_hours", "downtime_reason"],
        "aliases": {
            "work_centre_code": ["machine", "work_centre", "work_center", "work_centre_code"],
            "event_date": ["date", "event_date"],
            "run_hours": ["run_time", "operating_hours", "run_hours"],
            "hourly_rate": ["machine_rate", "rate", "hourly_rate"],
            "order_number": ["work_order", "order_number"],
            "setup_hours": ["setup_time", "changeover_hours", "setup_hours"],
            "downtime_hours": ["downtime", "idle_hours", "downtime_hours"],
            "downtime_reason": ["reason", "stop_reason", "fault_code", "downtime_reason"],
        },
    },
    "ENERGY_READINGS": {
        "label": "Energy & Sub-meter Consumption",
        "required_fields": ["plant_code", "meter_reference", "reading_timestamp", "kwh_consumed", "tariff_rate"],
        "optional_fields": ["work_centre_code", "tariff_band", "is_idle_load"],
        "aliases": {
            "plant_code": ["plant", "facility", "plant_code"],
            "meter_reference": ["meter", "meter_id", "meter_name", "meter_reference"],
            "reading_timestamp": ["timestamp", "datetime", "reading_time", "reading_timestamp"],
            "kwh_consumed": ["kwh", "consumption", "units", "kwh_consumed"],
            "tariff_rate": ["rate", "cost_per_kwh", "tariff_rate"],
            "work_centre_code": ["work_centre", "machine", "work_centre_code"],
            "tariff_band": ["band", "tariff_band"],
            "is_idle_load": ["idle", "weekend_idle", "is_idle_load"],
        },
    },
    "QUALITY_EVENTS": {
        "label": "Quality, Scrap & Rework",
        "required_fields": ["order_number", "event_date", "defect_code", "defect_description"],
        "optional_fields": ["scrap_quantity", "rework_hours", "rework_cost", "lot_reference"],
        "aliases": {
            "order_number": ["order_id", "work_order", "order_number"],
            "event_date": ["date", "inspection_date", "event_date"],
            "defect_code": ["defect", "code", "reason_code", "defect_code"],
            "defect_description": ["description", "defect_name", "defect_description"],
            "scrap_quantity": ["scrap_qty", "rejected_units", "scrap_quantity"],
            "rework_hours": ["rework_time", "rework_hours"],
            "rework_cost": ["rework_cost", "repair_cost"],
            "lot_reference": ["lot", "batch", "lot_reference"],
        },
    },
    "OVERHEAD_POOLS": {
        "label": "Overhead Pools & Absorption",
        "required_fields": ["plant_code", "period_code", "cost_centre_code", "pool_name", "actual_amount", "planned_driver_capacity", "actual_driver_usage", "standard_absorption_rate"],
        "optional_fields": ["absorption_driver"],
        "aliases": {
            "plant_code": ["plant", "plant_code"],
            "period_code": ["period", "period_code"],
            "cost_centre_code": ["cost_centre", "cost_center", "cost_centre_code"],
            "pool_name": ["pool", "expense_type", "pool_name"],
            "actual_amount": ["actual_cost", "amount", "actual_amount"],
            "planned_driver_capacity": ["planned_capacity", "budget_driver", "planned_driver_capacity"],
            "actual_driver_usage": ["actual_capacity", "driver_usage", "actual_driver_usage"],
            "standard_absorption_rate": ["std_rate", "absorption_rate", "standard_absorption_rate"],
            "absorption_driver": ["driver", "driver_type", "absorption_driver"],
        },
    },
    "EQUIPMENT_DOWNTIME_ENERGY": {
        "label": "Equipment Downtime & Energy Telemetry",
        "required_fields": ["line_id", "unplanned_downtime_hours", "energy_kwh", "energy_cost"],
        "optional_fields": ["equipment_record_id", "run_id", "record_date", "shift_code", "plant_id", "scheduled_hours", "planned_downtime_hours", "run_hours", "downtime_reason_code", "tariff_per_kwh"],
        "aliases": {
            "equipment_record_id": ["equipment_record_id", "record_id", "id", "equipment_id"],
            "run_id": ["run_id", "production_run_id"],
            "record_date": ["record_date", "date", "event_date", "posting_date"],
            "shift_code": ["shift_code", "shift", "shift_id"],
            "plant_id": ["plant_id", "plant_code", "plant", "facility"],
            "line_id": ["line_id", "line_code", "line"],
            "scheduled_hours": ["scheduled_hours", "planned_hours"],
            "planned_downtime_hours": ["planned_downtime_hours", "setup_hours"],
            "unplanned_downtime_hours": ["unplanned_downtime_hours", "downtime_hours", "downtime", "idle_hours"],
            "run_hours": ["run_hours", "operating_hours", "operating_time"],
            "downtime_reason_code": ["downtime_reason_code", "downtime_reason", "reason_code", "fault_code"],
            "energy_kwh": ["energy_kwh", "kwh_consumed", "kwh", "power_consumption"],
            "tariff_per_kwh": ["tariff_per_kwh", "tariff_rate", "rate_per_kwh"],
            "energy_cost": ["energy_cost", "total_energy_cost", "cost"],
        },
    },
    "WORKFORCE_ATTENDANCE": {
        "label": "Workforce Attendance & Headcount",
        "required_fields": ["attendance_id", "plant_id", "line_id", "scheduled_headcount", "present_headcount", "absent_headcount"],
        "optional_fields": ["run_id", "attendance_date", "shift_code", "agency_cover_headcount", "overtime_hours"],
        "aliases": {
            "attendance_id": ["attendance_id", "id", "record_id"],
            "run_id": ["run_id", "production_run_id"],
            "attendance_date": ["attendance_date", "date", "work_date", "posting_date"],
            "shift_code": ["shift_code", "shift", "shift_id"],
            "plant_id": ["plant_id", "plant_code", "plant", "facility"],
            "line_id": ["line_id", "line_code", "line"],
            "scheduled_headcount": ["scheduled_headcount", "scheduled", "planned_headcount"],
            "present_headcount": ["present_headcount", "present", "actual_headcount"],
            "absent_headcount": ["absent_headcount", "absent", "absences"],
            "agency_cover_headcount": ["agency_cover_headcount", "agency_cover", "contractor_headcount"],
            "overtime_hours": ["overtime_hours", "overtime", "ot_hours"],
        },
    },
    "INVENTORY_TRANSACTIONS": {
        "label": "Inventory Movements & Stock Balances",
        "required_fields": ["plant_id", "component_id", "opening_qty", "closing_qty"],
        "optional_fields": ["transaction_date", "receipt_qty", "issue_qty", "adjustment_qty", "adjustment_reason"],
        "aliases": {
            "transaction_date": ["transaction_date", "date", "posting_date"],
            "plant_id": ["plant_id", "plant_code", "plant", "facility"],
            "component_id": ["component_id", "material_id", "part_number", "item_code"],
            "opening_qty": ["opening_qty", "opening_stock", "beginning_qty"],
            "receipt_qty": ["receipt_qty", "received_qty", "inward_qty"],
            "issue_qty": ["issue_qty", "issued_qty", "consumed_qty"],
            "adjustment_qty": ["adjustment_qty", "adjust_qty"],
            "closing_qty": ["closing_qty", "closing_stock", "ending_qty"],
            "adjustment_reason": ["adjustment_reason", "reason", "notes"],
        },
    },
}

DATASET_SCHEMAS["BOM_COMPONENTS"] = DATASET_SCHEMAS["BOM_COMPONENT"]
DATASET_SCHEMAS["EQUIPMENT_ENERGY"] = DATASET_SCHEMAS["EQUIPMENT_DOWNTIME_ENERGY"]
DATASET_SCHEMAS["d1_hourly_production"] = DATASET_SCHEMAS["HOURLY_PRODUCTION"]
DATASET_SCHEMAS["d2_manufacturing_cost"] = DATASET_SCHEMAS["MANUFACTURING_COST"]
DATASET_SCHEMAS["d3_bom_components"] = DATASET_SCHEMAS["BOM_COMPONENT"]
DATASET_SCHEMAS["d4_quality_inspection"] = DATASET_SCHEMAS["QUALITY_INSPECTION"]
DATASET_SCHEMAS["d5_production_traceability"] = DATASET_SCHEMAS["PRODUCTION_ORDERS"]
DATASET_SCHEMAS["d6_material_consumption"] = DATASET_SCHEMAS["MATERIAL_CONSUMPTION"]
DATASET_SCHEMAS["d7_inventory_transactions"] = DATASET_SCHEMAS["INVENTORY_TRANSACTIONS"]
DATASET_SCHEMAS["d8_procurement_supplier"] = DATASET_SCHEMAS["MATERIAL_PURCHASE"]
DATASET_SCHEMAS["d9_equipment_energy"] = DATASET_SCHEMAS["EQUIPMENT_DOWNTIME_ENERGY"]
DATASET_SCHEMAS["d10_workforce_attendance_allocation"] = DATASET_SCHEMAS["WORKFORCE_ATTENDANCE"]


class IngestionService:
    """Manages file ingestion lifecycle and column mappings for legacy endpoints."""

    def __init__(self):
        self.staged_batches: dict[str, dict[str, Any]] = {}

    def parse_file(self, filename: str, file_bytes: bytes) -> tuple[list[str], list[dict[str, Any]]]:
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size exceeds maximum limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.")

        lower_name = filename.lower()
        if lower_name.endswith(".csv"):
            return self._parse_csv(file_bytes)
        elif lower_name.endswith(".xlsx"):
            return self._parse_xlsx(file_bytes)
        else:
            raise ValueError("Unsupported file format. Please upload a .csv or .xlsx file.")

    def _parse_csv(self, file_bytes: bytes) -> tuple[list[str], list[dict[str, Any]]]:
        try:
            text_content = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text_content = file_bytes.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text_content))
        headers = reader.fieldnames or []
        cleaned_headers = [h.strip() for h in headers if h and h.strip()]

        rows = []
        for raw_row in reader:
            cleaned_row = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items() if k}
            rows.append(cleaned_row)

        return cleaned_headers, rows

    def _parse_xlsx(self, file_bytes: bytes) -> tuple[list[str], list[dict[str, Any]]]:
        workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheet = workbook.active
        if not sheet:
            return [], []

        rows_iter = sheet.iter_rows(values_only=True)
        try:
            raw_headers = next(rows_iter)
        except StopIteration:
            return [], []

        headers = [str(h).strip() for h in raw_headers if h is not None]
        data_rows: list[dict[str, Any]] = []

        for row_vals in rows_iter:
            if not any(row_vals):
                continue
            row_dict = {}
            for h, v in zip(headers, row_vals):
                row_dict[h] = str(v).strip() if v is not None else ""
            data_rows.append(row_dict)

        return headers, data_rows

    def auto_map_columns(self, dataset_type: str, source_headers: list[str]) -> dict[str, str]:
        if dataset_type == "BOM_COMPONENTS":
            dataset_type = "BOM_COMPONENT"
        schema = DATASET_SCHEMAS.get(dataset_type)
        if not schema:
            return {}

        mapping: dict[str, str] = {}
        aliases: dict[str, list[str]] = schema.get("aliases", {})
        normalized_headers = {h.lower().replace(" ", "_"): h for h in source_headers}

        for target_field, alias_list in aliases.items():
            for alias in alias_list:
                clean_alias = alias.lower().replace(" ", "_")
                if clean_alias in normalized_headers:
                    mapping[target_field] = normalized_headers[clean_alias]
                    break

        return mapping

    def suggest_mappings(self, dataset_type: str, source_headers: list[str]) -> dict[str, str]:
        """Alias for auto_map_columns for backward compatibility."""
        return self.auto_map_columns(dataset_type, source_headers)

    def detect_dataset_type(self, headers: list[str]) -> tuple[str, float]:
        """
        Infers the most matching dataset schema based on header overlap and unambiguous signature patterns.
        Returns (best_dataset_type, confidence_score_0_to_1).
        """
        normalized_headers = {h.lower().replace(" ", "_").replace("-", "_") for h in headers}

        # Signature 1: WORKFORCE_ATTENDANCE
        if any(h in normalized_headers for h in ["attendance_id", "absent_headcount", "present_headcount", "scheduled_headcount", "agency_cover_headcount"]):
            return "WORKFORCE_ATTENDANCE", 1.0

        # Signature 2: EQUIPMENT_DOWNTIME_ENERGY
        if any(h in normalized_headers for h in ["equipment_record_id", "unplanned_downtime_hours", "planned_downtime_hours", "downtime_reason_code", "energy_kwh"]):
            return "EQUIPMENT_DOWNTIME_ENERGY", 1.0

        # Signature 3: INVENTORY_TRANSACTIONS
        if any(h in normalized_headers for h in ["opening_qty", "closing_qty", "issue_qty", "adjustment_qty", "adjustment_reason", "inventory_txn_id"]):
            return "INVENTORY_TRANSACTIONS", 1.0

        # Signature 4: QUALITY_INSPECTION
        if any(h in normalized_headers for h in ["inspection_id", "display_defect", "solder_defect", "inspected_qty", "failed_qty"]):
            return "QUALITY_INSPECTION", 1.0

        # Signature 5: MATERIAL_PURCHASE
        if any(h in normalized_headers for h in ["po_id", "po_line", "purchase_line_id", "purchase_order_id", "on_time_flag"]):
            return "MATERIAL_PURCHASE", 1.0

        # Signature 6: MATERIAL_CONSUMPTION
        if any(h in normalized_headers for h in ["consumption_id", "bom_qty_per_unit", "standard_qty", "net_consumed_qty"]):
            return "MATERIAL_CONSUMPTION", 1.0

        # Signature 7: MANUFACTURING_COST
        if any(h in normalized_headers for h in ["cost_record_id", "cost_per_good_unit", "total_direct_cost_inr", "standard_cost_per_unit_inr", "cost_date"]):
            return "MANUFACTURING_COST", 1.0

        # Signature 8: HOURLY_PRODUCTION
        if any(h in normalized_headers for h in ["run_id", "shift_code", "rework_recovered_qty", "actual_qty", "good_qty", "event_id"]):
            return "HOURLY_PRODUCTION", 1.0

        # Signature 9: PRODUCTION_ORDERS
        if "production_order_id" in normalized_headers and any(h in normalized_headers for h in ["planned_qty", "order_date", "order_number"]) and "consumption_id" not in normalized_headers and "run_id" not in normalized_headers and "cost_record_id" not in normalized_headers:
            return "PRODUCTION_ORDERS", 1.0

        # Signature 10: BOM_COMPONENT
        if any(h in normalized_headers for h in ["bom_id", "component_qty", "scrap_factor"]):
            return "BOM_COMPONENT", 1.0

        best_type = "MANUFACTURING_COST"
        best_score = 0.0

        for ds_type, schema in DATASET_SCHEMAS.items():
            if ds_type == "BOM_COMPONENTS":
                continue
            req_fields = schema.get("required_fields", [])
            aliases = schema.get("aliases", {})
            matches = 0
            for field in req_fields:
                field_aliases = [field.lower()] + [a.lower().replace(" ", "_") for a in aliases.get(field, [])]
                if any(alias in normalized_headers for alias in field_aliases):
                    matches += 1
            score = matches / len(req_fields) if req_fields else 0.0
            if score > best_score:
                best_score = score
                best_type = ds_type

        return best_type, best_score

    def stage_upload(self, filename: str, dataset_type: str, file_bytes: bytes) -> dict[str, Any]:
        headers, raw_rows = self.parse_file(filename, file_bytes)

        # Auto-detect dataset type if requested or not specified
        detected_type, confidence = self.detect_dataset_type(headers)
        if not dataset_type or dataset_type == "AUTO" or dataset_type not in DATASET_SCHEMAS:
            dataset_type = detected_type

        mapping = self.auto_map_columns(dataset_type, headers)

        schema = DATASET_SCHEMAS[dataset_type]
        missing_required = [f for f in schema["required_fields"] if f not in mapping]

        batch_id = str(uuid.uuid4())
        staged_batch = {
            "batch_id": batch_id,
            "filename": filename,
            "dataset_type": dataset_type,
            "detected_dataset_type": detected_type,
            "detection_confidence": round(confidence * 100, 1),
            "total_rows": len(raw_rows),
            "headers": headers,
            "detected_mapping": mapping,
            "suggested_mapping": mapping,
            "missing_required_fields": missing_required,
            "is_valid_schema": len(missing_required) == 0,
            "preview_rows": raw_rows[:20],
            "raw_rows": raw_rows,
            "status": "STAGED",
        }

        self.staged_batches[batch_id] = staged_batch
        return staged_batch

    def get_staged_batch(self, batch_id: str) -> dict[str, Any] | None:
        return self.staged_batches.get(batch_id)


ingestion_service = IngestionService()
