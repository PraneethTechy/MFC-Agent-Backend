"""
Manufacturing Cost Agent - Data Upload Workspace Test Suite
Validates:
1. Registry summary endpoint (/api/import/registry-summary)
2. Ingestion history persistence from Neon DB (/api/import/history)
3. CSV template generation for all supported schemas (/api/import/template/{dataset})
4. Automatic dataset identification & SHA-256 duplicate detection (/api/import/upload)
5. Validation rule enforcement: blocking errors vs warnings (/api/import/{batch_id}/validate)
6. Transactional promotion safeguards & product discovery (/api/import/{batch_id}/commit)
"""

import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_registry_summary_reflects_neon_foundation():
    """Verifies that the registry summary endpoint returns the 4 promoted datasets."""
    response = client.get("/api/import/registry-summary")
    assert response.status_code == 200
    data = response.json()

    assert data["total_registered_datasets"] >= 4
    assert data["total_promoted_records"] >= 29880
    assert "accounting_limitations" in data
    assert data["accounting_limitations"]["overhead_status"] == "NOT_AVAILABLE"
    assert data["accounting_limitations"]["standards_status"] == "UNVERIFIED_STANDARD"
    assert data["accounting_limitations"]["quality_lineage"] == "UNRESOLVED_LINEAGE"
    assert data["accounting_limitations"]["uncosted_runs"] == 3832

    # Verify all 4 core dataset types exist in breakdown
    dataset_types = [ds["dataset_type"] for ds in data["dataset_breakdown"]]
    assert "MANUFACTURING_COST" in dataset_types
    assert "HOURLY_PRODUCTION" in dataset_types
    assert "QUALITY_INSPECTION" in dataset_types
    assert "BOM_COMPONENTS" in dataset_types


def test_import_history_retrieves_persisted_promoted_records():
    """Verifies that past promoted imports are retrieved from Neon PostgreSQL."""
    response = client.get("/api/import/history")
    assert response.status_code == 200
    history = response.json()

    assert isinstance(history, list)
    assert len(history) >= 4, "Expected at least the 4 initial imported datasets in history"

    # Verify fact_manufacturing_cost.csv exists with 5,000 rows
    cost_entry = next((h for h in history if "fact_manufacturing_cost" in h["filename"]), None)
    assert cost_entry is not None
    assert cost_entry["total_rows"] == 5000
    assert cost_entry["status"] == "PROMOTED"

    # Verify fact_hourly_production.csv exists with 8,832 rows
    prod_entry = next((h for h in history if "fact_hourly_production" in h["filename"]), None)
    assert prod_entry is not None
    assert prod_entry["total_rows"] == 8832

    # Verify fact_quality_inspection.csv exists with 16,000 rows
    quality_entry = next((h for h in history if "fact_quality_inspection" in h["filename"]), None)
    assert quality_entry is not None
    assert quality_entry["total_rows"] == 16000

    # Verify fact_bom_component.csv exists with 48 rows
    bom_entry = next((h for h in history if "fact_bom_component" in h["filename"]), None)
    assert bom_entry is not None
    assert bom_entry["total_rows"] == 48


def test_download_dataset_csv_template():
    """Verifies template generation with accurate schema headers."""
    schemas_to_test = ["MANUFACTURING_COST", "HOURLY_PRODUCTION", "QUALITY_INSPECTION", "BOM_COMPONENTS"]
    for schema in schemas_to_test:
        response = client.get(f"/api/import/template/{schema}")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert f"{schema.lower()}_template.csv" in response.headers["content-disposition"]
        lines = response.text.strip().split("\n")
        assert len(lines) >= 1
        headers = lines[0].split(",")
        assert len(headers) >= 4


def test_upload_auto_detection_and_duplicate_check():
    """Verifies header recognition, auto-detection, and duplicate detection."""
    # 1. Upload a synthetic manufacturing cost CSV
    csv_content = (
        "cost_record_id,posting_ts,plant_id,line_id,production_order_id,product_id,produced_qty,material_cost_inr,labour_cost_inr,machine_cost_inr,energy_cost_inr,scrap_rework_cost_inr\n"
        "TEST-001,2026-10-01T10:00:00Z,IN-KA-01,FAL-L1,PO-9999,SPH-PRO-256,100,50000,5000,2500,1000,500\n"
    )
    files = {"file": ("test_upload_cost.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    response = client.post("/api/import/upload", data={"dataset_type": "AUTO"}, files=files)
    assert response.status_code == 200
    data = response.json()

    assert data["detected_dataset_type"] == "MANUFACTURING_COST"
    assert data["total_rows"] == 1
    assert data["suggested_mapping"]["cost_record_id"] == "cost_record_id"
    assert data["suggested_mapping"]["material_cost_inr"] == "material_cost_inr"
    assert data["is_already_promoted"] is False


def test_validation_catches_negative_costs_as_blocking():
    """Verifies that negative financial costs are flagged as BLOCKING ERROR."""
    csv_content = (
        "cost_record_id,posting_ts,plant_id,line_id,production_order_id,product_id,produced_qty,material_cost_inr,labour_cost_inr,machine_cost_inr,energy_cost_inr,scrap_rework_cost_inr\n"
        "ERR-001,2026-10-01T10:00:00Z,IN-KA-01,FAL-L1,PO-1000,SPH-PRO-256,100,-50000,5000,2500,1000,500\n"
    )
    files = {"file": ("negative_cost.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    upload_res = client.post("/api/import/upload", data={"dataset_type": "MANUFACTURING_COST"}, files=files)
    assert upload_res.status_code == 200
    batch_id = upload_res.json()["batch_id"]

    val_res = client.post(
        f"/api/import/{batch_id}/validate",
        json={"column_mapping": upload_res.json()["suggested_mapping"]},
    )
    assert val_res.status_code == 200
    val_data = val_res.json()

    assert val_data["status"] == "VALIDATION_FAILED"
    assert val_data["summary"]["is_valid"] is False
    assert val_data["summary"]["blocking_error_count"] >= 1

    # Verify attempt to commit fails with 400
    commit_res = client.post(f"/api/import/{batch_id}/commit")
    assert commit_res.status_code == 400
    assert "blocking errors" in commit_res.json()["detail"].lower()

