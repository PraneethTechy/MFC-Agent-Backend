"""
Manufacturing Cost Agent - Streaming Inspector Test Suite
Validates:
1. Progressive event streaming via POST /api/import/inspect-stream
2. Real-time Pydantic event schema validation
3. 8-stage manufacturing inspection & Domo tool traces
4. Detection of blocking errors vs warnings
5. Unsupported format rejection
"""

import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_streaming_inspection_valid_manufacturing_cost():
    """Validates real-time event streaming for a valid manufacturing cost CSV."""
    csv_content = (
        "cost_record_id,posting_ts,plant_id,line_id,production_order_id,product_id,produced_qty,"
        "material_cost_inr,labour_cost_inr,machine_cost_inr,energy_cost_inr,scrap_rework_cost_inr\n"
        "REC-001,2026-10-15T08:00:00Z,IN-KA-01,SMT-L1,ORD-1001,SPH-PRO-256,500,4500000,120000,80000,30000,10000\n"
        "REC-002,2026-10-15T09:00:00Z,IN-KA-01,SMT-L1,ORD-1002,SPH-A15-256,400,3200000,95000,65000,24000,8000\n"
    )
    files = {"file": ("test_cost_batch.csv", csv_content.encode("utf-8"), "text/csv")}
    response = client.post("/api/import/inspect-stream", files=files, data={"dataset_type": "AUTO"})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    # Parse SSE events from response text
    raw_lines = response.text.split("\n\n")
    events = []
    for line in raw_lines:
        line = line.strip()
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            events.append(payload)

    assert len(events) >= 8, f"Expected at least 8 events, got {len(events)}"

    event_types = [e["event_type"] for e in events]
    assert "inspection_started" in event_types
    assert "stage_started" in event_types
    assert "check_completed" in event_types
    assert "tool_started" in event_types
    assert "tool_completed" in event_types
    assert "analysis_completed" in event_types

    # Verify final completed payload structure
    final_event = next(e for e in events if e["event_type"] == "analysis_completed")
    details = final_event["details"]
    assert details["dataset_type"] == "MANUFACTURING_COST"
    assert details["total_rows"] == 2
    assert details["eligible_rows"] == 2
    assert details["blocking_errors"] == 0
    assert details["is_promotable"] is True
    assert len(details["analyses_readiness"]) >= 4
    assert len(details["findings"]) >= 1


def test_streaming_inspection_unsupported_format():
    """Verifies that an unsupported file format (.txt) fails early with an informative event."""
    files = {"file": ("unsupported_data.txt", b"plain text data", "text/plain")}
    response = client.post("/api/import/inspect-stream", files=files, data={"dataset_type": "AUTO"})

    assert response.status_code == 200
    raw_lines = response.text.split("\n\n")
    events = [json.loads(l[6:]) for l in raw_lines if l.strip().startswith("data: ")]

    failed_event = next((e for e in events if e["event_type"] in ["check_failed", "inspection_failed"]), None)
    assert failed_event is not None
    assert "Unsupported format" in failed_event["message"] or "failed" in failed_event["message"].lower()


def test_streaming_inspection_detects_negative_value_blocking_error():
    """Verifies that negative costs are detected as blocking errors in data quality stage."""
    csv_content = (
        "cost_record_id,posting_ts,plant_id,line_id,production_order_id,product_id,produced_qty,"
        "material_cost_inr,labour_cost_inr,machine_cost_inr,energy_cost_inr,scrap_rework_cost_inr\n"
        "REC-ERR,2026-10-15T08:00:00Z,IN-KA-01,SMT-L1,ORD-1001,SPH-PRO-256,500,-99999,120000,80000,30000,10000\n"
    )
    files = {"file": ("negative_cost.csv", csv_content.encode("utf-8"), "text/csv")}
    response = client.post("/api/import/inspect-stream", files=files, data={"dataset_type": "AUTO"})

    assert response.status_code == 200
    raw_lines = response.text.split("\n\n")
    events = [json.loads(l[6:]) for l in raw_lines if l.strip().startswith("data: ")]

    final_event = next(e for e in events if e["event_type"] == "analysis_completed")
    details = final_event["details"]
    assert details["blocking_errors"] >= 1
    assert details["is_promotable"] is False
    assert "Blocked" in details["status_title"] or details["eligible_rows"] == 0


def test_streaming_inspection_multi_file_and_report_linking():
    """
    Validates:
    1. Multi-file upload stream
    2. Emission of report_id and inspection_id in analysis_completed
    3. Retrieval of exact cached report from GET /api/investigation/report
    """
    cost_csv = (
        "cost_record_id,posting_ts,plant_id,line_id,production_order_id,product_id,produced_qty,"
        "material_cost_inr,labour_cost_inr,machine_cost_inr,energy_cost_inr,scrap_rework_cost_inr\n"
        "REC-101,2026-10-15T08:00:00Z,IN-KA-01,SMT-L1,ORD-1001,SPH-PRO-256,500,4500000,120000,80000,30000,10000\n"
    )
    prod_csv = (
        "log_id,timestamp,plant_id,line_id,shift,product_id,units_produced,planned_units,operating_mins,downtime_mins\n"
        "LOG-001,2026-10-15T08:00:00Z,IN-KA-01,SMT-L1,Morning,SPH-PRO-256,500,500,60,0\n"
    )

    files = [
        ("files", ("cost_batch_oct.csv", cost_csv.encode("utf-8"), "text/csv")),
        ("files", ("prod_logs_oct.csv", prod_csv.encode("utf-8"), "text/csv")),
    ]
    response = client.post("/api/import/inspect-stream", files=files, data={"dataset_type": "AUTO"})

    assert response.status_code == 200
    raw_lines = response.text.split("\n\n")
    events = [json.loads(l[6:]) for l in raw_lines if l.strip().startswith("data: ")]

    final_event = next(e for e in events if e["event_type"] == "analysis_completed")
    details = final_event["details"]

    assert "report_id" in details
    assert "inspection_id" in details
    report_id = details["report_id"]
    inspection_id = details["inspection_id"]
    assert report_id is not None
    assert inspection_id is not None
    assert "cost_batch_oct.csv" in details.get("uploaded_files", [])

    # Fetch cached report directly by report_id
    rep_res = client.get(f"/api/investigation/report?report_id={report_id}")
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert rep_data["report_id"] == report_id
    assert rep_data["inspection_id"] == inspection_id
    assert rep_data["bridge"]["reconciled"] is True


