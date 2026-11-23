"""
Automated Test Suite for Manufacturing Cost Agent - Phase 2 Data Foundation
Tests database models, CSV/XLSX parsing, column mapping, validation rules,
data trust score calculation, analytical views, and synthetic dataset consistency.
"""

import io
import openpyxl
import pytest
from app.db import Base
from app.db_views import V_COST_FACTS_SQL, V_VARIANCE_FACTS_SQL
from app.services.ingestion import IngestionService, DATASET_SCHEMAS
from app.services.validation import ValidationService
from app.services.synthetic_generator import SyntheticDatasetGenerator


def test_database_models_metadata():
    """Verify that all required manufacturing tables and relationships are registered."""
    tables = Base.metadata.tables
    expected_tables = [
        "plants",
        "production_lines",
        "work_centres",
        "products",
        "materials",
        "suppliers",
        "units_of_measure",
        "unit_conversions",
        "calendar_periods",
        "exchange_rates",
        "costing_versions",
        "standard_cost_items",
        "bills_of_materials",
        "bom_items",
        "routings",
        "routing_steps",
        "production_orders",
        "production_outputs",
        "material_postings",
        "labour_postings",
        "machine_events",
        "energy_readings",
        "quality_events",
        "overhead_pools",
        "supplier_price_history",
        "analysis_runs",
        "scenario_runs",
        "recommendations",
        "audit_events",
        "import_batches",
        "data_quality_issues",
    ]
    for table_name in expected_tables:
        assert table_name in tables, f"Expected table '{table_name}' missing from Base metadata."


def test_csv_parsing():
    """Verify CSV file parsing with standard python csv module."""
    service = IngestionService()
    csv_data = (
        "code,name,location,country\n"
        "PLANT-1,Alpha Works,Pune,India\n"
        "PLANT-2,Beta Works,Chennai,India\n"
    ).encode("utf-8")

    headers, rows = service.parse_file("plants.csv", csv_data)
    assert headers == ["code", "name", "location", "country"]
    assert len(rows) == 2
    assert rows[0]["code"] == "PLANT-1"
    assert rows[1]["location"] == "Chennai"


def test_xlsx_parsing():
    """Verify XLSX file parsing using openpyxl."""
    service = IngestionService()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["code", "name", "product_group"])
    ws.append(["PRD-01", "Motor 15kW", "Motors"])
    ws.append(["PRD-02", "Gearbox 4:1", "Transmissions"])

    buffer = io.BytesIO()
    wb.save(buffer)
    xlsx_bytes = buffer.getvalue()

    headers, rows = service.parse_file("products.xlsx", xlsx_bytes)
    assert headers == ["code", "name", "product_group"]
    assert len(rows) == 2
    assert rows[0]["code"] == "PRD-01"
    assert rows[1]["name"] == "Gearbox 4:1"


def test_column_mapping_suggestion():
    """Verify intelligent alias mapping for manufacturing datasets."""
    service = IngestionService()
    file_headers = ["facility_code", "facility_name", "city", "unrelated_column"]

    suggested = service.suggest_mappings("PLANTS", file_headers)
    assert suggested.get("code") == "facility_code"
    assert suggested.get("name") == "facility_name"
    assert suggested.get("location") == "city"


def test_validation_missing_required_fields():
    """Verify validation flags missing mandatory fields as blocking errors."""
    validator = ValidationService()
    rows = [
        {"facility_code": "PLANT-1", "facility_name": "", "city": "Pune"},  # missing name
    ]
    mapping = {"code": "facility_code", "name": "facility_name", "location": "city"}

    result = validator.validate_batch("PLANTS", rows, mapping)
    assert result["is_valid"] is False
    assert result["error_count"] >= 1
    assert any(i["rule_code"] == "ERR_MISSING_MANDATORY_VALUE" for i in result["issues"])


def test_validation_duplicate_key_detection():
    """Verify duplicate primary/compound business key detection."""
    validator = ValidationService()
    rows = [
        {"code": "PLANT-A", "name": "Facility A1", "location": "Pune"},
        {"code": "PLANT-A", "name": "Facility A2", "location": "Mumbai"},  # duplicate code
    ]
    mapping = {"code": "code", "name": "name", "location": "location"}

    result = validator.validate_batch("PLANTS", rows, mapping)
    assert result["is_valid"] is False
    assert any(i["rule_code"] == "ERR_DUPLICATE_POSTING" for i in result["issues"])


def test_validation_negative_financial_values():
    """Verify negative prices or quantities are rejected for standard transactions."""
    validator = ValidationService()
    rows = [
        {
            "order_number": "WO-101",
            "material_code": "MAT-01",
            "posting_date": "2026-03-15",
            "transaction_type": "STANDARD_ISSUE",
            "actual_quantity": "-50.0",  # Negative prohibited for standard issue
            "unit_price": "65.0",
        }
    ]
    mapping = {
        "order_number": "order_number",
        "material_code": "material_code",
        "posting_date": "posting_date",
        "transaction_type": "transaction_type",
        "actual_quantity": "actual_quantity",
        "unit_price": "unit_price",
    }
    result = validator.validate_batch("MATERIAL_POSTINGS", rows, mapping)
    assert result["is_valid"] is False
    assert any(i["rule_code"] == "ERR_NEGATIVE_VALUE_PROHIBITED" for i in result["issues"])


def test_validation_legitimate_negative_adjustment():
    """Verify legitimate negative accounting adjustments are accepted with a warning."""
    validator = ValidationService()
    rows = [
        {
            "order_number": "WO-102",
            "material_code": "MAT-01",
            "posting_date": "2026-03-16",
            "transaction_type": "PURCHASE_RETURN",
            "actual_quantity": "-15.0",  # Legitimate negative return
            "unit_price": "65.0",
        }
    ]
    mapping = {
        "order_number": "order_number",
        "material_code": "material_code",
        "posting_date": "posting_date",
        "transaction_type": "transaction_type",
        "actual_quantity": "actual_quantity",
        "unit_price": "unit_price",
    }
    result = validator.validate_batch("MATERIAL_POSTINGS", rows, mapping)
    # Row must NOT be rejected
    assert result["is_valid"] is True
    assert result["rejected_rows_count"] == 0
    assert result["valid_rows_count"] == 1
    # Must contain accounting adjustment warning
    assert any(i["rule_code"] == "WARN_ACCOUNTING_ADJUSTMENT" for i in result["issues"])


def test_validation_compound_business_key_distinction():
    """Verify compound business key differentiates multiple materials on one order vs real duplicates."""
    validator = ValidationService()
    rows = [
        # Same order, different material -> VALID
        {
            "order_number": "WO-200",
            "material_code": "MAT-STEEL",
            "posting_date": "2026-03-20",
            "lot_number": "LOT-1",
            "actual_quantity": "50.0",
            "unit_price": "65.0",
        },
        {
            "order_number": "WO-200",
            "material_code": "MAT-COPPER",
            "posting_date": "2026-03-20",
            "lot_number": "LOT-1",
            "actual_quantity": "10.0",
            "unit_price": "680.0",
        },
        # Exact duplicate: same order, same material, same date, same lot -> REJECTED
        {
            "order_number": "WO-200",
            "material_code": "MAT-STEEL",
            "posting_date": "2026-03-20",
            "lot_number": "LOT-1",
            "actual_quantity": "50.0",
            "unit_price": "65.0",
        },
    ]
    mapping = {
        "order_number": "order_number",
        "material_code": "material_code",
        "posting_date": "posting_date",
        "lot_number": "lot_number",
        "actual_quantity": "actual_quantity",
        "unit_price": "unit_price",
    }
    result = validator.validate_batch("MATERIAL_POSTINGS", rows, mapping)
    assert result["is_valid"] is False
    assert result["rejected_rows_count"] == 1
    assert result["valid_rows_count"] == 2
    assert any(i["rule_code"] == "ERR_DUPLICATE_POSTING" for i in result["issues"])


def test_validation_mass_balance_yield():
    """Verify manufacturing mass balance validation flags overconsumption and high scrap ratios."""
    validator = ValidationService()
    rows = [
        {
            "order_number": "PO-999",
            "plant_code": "PLANT-PUN",
            "product_code": "PRD-MOTOR-01",
            "period_code": "2026-M01",
            "start_date": "2026-03-01",
            "planned_qty": "100.0",
            "actual_qty": "160.0",
            "scrap_qty": "50.0",  # High scrap (>5%) and over-production (>150%)
        }
    ]
    mapping = {
        "order_number": "order_number",
        "plant_code": "plant_code",
        "product_code": "product_code",
        "period_code": "period_code",
        "start_date": "start_date",
        "planned_qty": "planned_qty",
        "actual_qty": "actual_qty",
        "scrap_qty": "scrap_qty",
    }
    result = validator.validate_batch("PRODUCTION_ORDERS", rows, mapping)
    assert any(i["rule_code"] == "WARN_HIGH_SCRAP_PERCENTAGE" for i in result["issues"])
    assert any(i["rule_code"] == "WARN_EXCESSIVE_OVER_PRODUCTION" for i in result["issues"])


def test_validation_warning_missing_downtime_reason():
    """Verify missing downtime reason is flagged as a warning without blocking row."""
    validator = ValidationService()
    rows = [
        {
            "work_centre_code": "WC-01",
            "event_date": "2026-04-10",
            "run_hours": "7.5",
            "downtime_hours": "1.5",
            "downtime_reason": "",  # Missing downtime reason
            "hourly_rate": "1200.0",
        }
    ]
    mapping = {
        "work_centre_code": "work_centre_code",
        "event_date": "event_date",
        "run_hours": "run_hours",
        "downtime_hours": "downtime_hours",
        "downtime_reason": "downtime_reason",
        "hourly_rate": "hourly_rate",
    }
    result = validator.validate_batch("MACHINE_EVENTS", rows, mapping)
    assert result["warning_count"] >= 1
    assert any(i["rule_code"] == "WARN_MISSING_DOWNTIME_REASON" for i in result["issues"])


def test_data_trust_score_calculation():
    """Verify the 6-dimension Data Trust Score computation."""
    validator = ValidationService()
    trust = validator.calculate_trust_score(total_rows=100, valid_rows=95, error_count=5, warning_count=4)

    assert "overall_score" in trust
    assert "dimensions" in trust
    assert trust["dimensions"]["validity"] == 95.0
    assert 80.0 <= trust["overall_score"] <= 100.0
    assert trust["grade"] in ("A", "B")


def test_analytical_views_sql_syntax():
    """Verify SQL syntax definitions of analytical views and audited requirements."""
    assert "CREATE OR REPLACE VIEW v_cost_facts" in V_COST_FACTS_SQL
    assert "CREATE OR REPLACE VIEW v_variance_facts" in V_VARIANCE_FACTS_SQL
    assert "actual_material_cost" in V_COST_FACTS_SQL
    assert "total_cost_variance" in V_VARIANCE_FACTS_SQL

    # Audited view requirements (Master Prompt 2.1)
    # 1. No hardcoded costing versions
    assert "'AOP-2026-V1'" not in V_COST_FACTS_SQL
    assert "'AOP-2026-V1'" not in V_VARIANCE_FACTS_SQL
    # 2. Dynamic costing version join in variance facts
    assert "costing_versions cv" in V_VARIANCE_FACTS_SQL
    # 3. Energy allocation distinction
    assert "is_energy_estimated" in V_COST_FACTS_SQL
    assert "energy_allocation_method" in V_COST_FACTS_SQL
    # 4. Overhead volume vs spending variance separation
    assert "overhead_volume_variance" in V_VARIANCE_FACTS_SQL
    assert "overhead_spending_variance" in V_VARIANCE_FACTS_SQL


def test_neon_configuration_parameters():
    """Verify Neon PostgreSQL single connection configuration and SSL requirements."""
    from app.config import settings

    # Single connection URL architecture
    assert hasattr(settings, "database_url")
    assert settings.database_url is not None

    # Normalization ensures postgresql+psycopg scheme
    assert settings.sqlalchemy_database_url.startswith("postgresql+psycopg://")

    # SSL parameters preserved
    assert "sslmode=require" in settings.database_url


def test_neon_live_connection_and_views():
    """Verify actual Neon connectivity, version check, and view execution."""
    from app.config import settings
    from app.db import check_db_connection, engine
    from sqlalchemy import text

    if not settings.is_database_configured:
        pytest.skip("Neon connection unconfigured; skipping live database test.")

    check = check_db_connection()
    assert check["status"] == "connected"
    assert check["database"] == "neondb"
    assert check["current_user"] == "neondb_owner"
    assert "PostgreSQL" in check["version"]
    assert check["ssl_active"] is True

    # Analytical views execution in real Neon
    with engine.connect() as conn:
        cf_cnt = conn.execute(text("SELECT count(*) FROM v_cost_facts;")).scalar()
        vf_cnt = conn.execute(text("SELECT count(*) FROM v_variance_facts;")).scalar()
        assert cf_cnt is not None
        assert vf_cnt is not None


def test_synthetic_dataset_generator():
    """Verify synthetic dataset generator covers all 6 cost categories and 3 plants."""
    generator = SyntheticDatasetGenerator()
    summary = generator.generate_all(db=None)

    assert summary["plants"] == 3
    assert summary["calendar_periods"] == 6
    assert summary["products"] >= 3
    assert len(summary["cost_categories_represented"]) == 6
    assert len(summary["documented_scenarios"]) == 6

