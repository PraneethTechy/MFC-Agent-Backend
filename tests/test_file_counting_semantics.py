import hashlib
import io
import pytest
from app.db import SessionLocal
from app.services.ingestion.streaming_inspector import StreamingInspectorService
from app.services.investigation.investigation_engine import InvestigationEngineService


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_scope_counting_semantics_single_csv(db_session):
    """
    Verifies that when 1 CSV file is uploaded:
    - uploaded_files_count == 1
    - dataset_types_count == 1
    - datasets_analyzed == 1
    - records_parsed matches file rows
    """
    inspection_datasets = {
        "MANUFACTURING_COST": {
            "filename": "cost_batch.csv",
            "dataset_type": "MANUFACTURING_COST",
            "rows": [
                {
                    "posting_ts": "2026-10-01",
                    "plant_id": "P1",
                    "line_id": "L1",
                    "product_id": "SKU-A",
                    "total_direct_cost_inr": "1000",
                }
            ],
            "valid_count": 1,
        }
    }

    report = InvestigationEngineService.generate_report(
        db=db_session,
        inspection_id="insp_single_test",
        uploaded_files=["cost_batch.csv"],
        inspection_datasets=inspection_datasets,
    )

    assert report.scope.uploaded_files_count == 1
    assert report.scope.datasets_analyzed == 1
    assert report.scope.dataset_types_count == 1
    assert report.scope.records_parsed == 1
    assert report.scope.uploaded_files == ["cost_batch.csv"]
    assert report.scope.duplicate_files_detected == []


def test_scope_counting_semantics_duplicate_detection(db_session):
    """
    Verifies that if the same file is passed twice in uploaded_files:
    - deduplicates to 1 unique physical file
    - reports uploaded_files_count == 1
    - duplicate_files_detected records the duplicate
    """
    inspection_datasets = {
        "MANUFACTURING_COST": {
            "filename": "duplicate_cost.csv",
            "dataset_type": "MANUFACTURING_COST",
            "rows": [{"posting_ts": "2026-10-01", "total_direct_cost_inr": "500"}],
            "valid_count": 1,
        }
    }

    report = InvestigationEngineService.generate_report(
        db=db_session,
        inspection_id="insp_dupe_test",
        uploaded_files=["duplicate_cost.csv", "duplicate_cost.csv"],
        inspection_datasets=inspection_datasets,
    )

    assert report.scope.uploaded_files_count == 1
    assert report.scope.datasets_analyzed == 1
    assert report.scope.uploaded_files == ["duplicate_cost.csv"]
    assert "duplicate_cost.csv" in report.scope.duplicate_files_detected


def test_scope_counting_semantics_two_distinct_files(db_session):
    """
    Verifies that when 2 distinct files are uploaded:
    - uploaded_files_count == 2
    - dataset_types_count == 2
    - datasets_analyzed == 2
    """
    inspection_datasets = {
        "MANUFACTURING_COST": {
            "filename": "cost.csv",
            "dataset_type": "MANUFACTURING_COST",
            "rows": [{"posting_ts": "2026-10-01", "total_direct_cost_inr": "1000"}],
            "valid_count": 1,
        },
        "HOURLY_PRODUCTION": {
            "filename": "production.csv",
            "dataset_type": "HOURLY_PRODUCTION",
            "rows": [{"event_date": "2026-10-01", "actual_qty": "50"}],
            "valid_count": 1,
        },
    }

    report = InvestigationEngineService.generate_report(
        db=db_session,
        inspection_id="insp_two_files_test",
        uploaded_files=["cost.csv", "production.csv"],
        inspection_datasets=inspection_datasets,
    )

    assert report.scope.uploaded_files_count == 2
    assert report.scope.datasets_analyzed == 2
    assert report.scope.dataset_types_count == 2
    assert len(report.scope.uploaded_files) == 2
    assert report.scope.records_parsed == 2


@pytest.mark.anyio
async def test_streaming_inspector_duplicate_file_filter(db_session):
    """
    Verifies that StreamingInspectorService deduplicates identical file contents
    and emits a duplicate warning event without double counting.
    """
    inspector = StreamingInspectorService(db=db_session)
    csv_bytes = b"cost_record_id,posting_ts,plant_id,line_id,production_order_id,product_id,produced_qty,material_cost_inr,labour_cost_inr,machine_cost_inr,energy_cost_inr,scrap_rework_cost_inr,standard_cost_per_unit_inr,currency,costing_version\nCST-1,2026-10-01T00:00:00,IN-TN-01,SMT-L1,PO-1,SPH-A15-128,100,50000,1000,500,200,100,11800,INR,V1\n"
    
    files_data = [
        {"filename": "fact_cost.csv", "file_bytes": csv_bytes},
        {"filename": "fact_cost.csv", "file_bytes": csv_bytes},  # duplicate payload
    ]

    events = [e async for e in inspector.stream_inspection(files_data=files_data)]
    
    # Verify duplicate warning was emitted
    dupe_warnings = [e for e in events if e.check_id == "duplicate_upload_detection"]
    assert len(dupe_warnings) == 1
    assert "fact_cost.csv" in dupe_warnings[0].message

    # Verify final report counts exactly 1 file
    comp = [e for e in events if e.event_type == "analysis_completed"][0]
    assert len(comp.details["uploaded_files"]) == 1
