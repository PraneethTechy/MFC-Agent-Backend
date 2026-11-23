import pytest
from app.db import SessionLocal
from app.services.ingestion.streaming_inspector import StreamingInspectorService
from app.services.investigation.report_cache import get_cached_report


@pytest.mark.anyio
async def test_streaming_inspection_single_cost_csv():
    db = SessionLocal()
    try:
        inspector = StreamingInspectorService(db=db)
        with open("backend/data/raw/fact_manufacturing_cost.csv", "rb") as f:
            data = f.read()

        events = []
        async for evt in inspector.stream_inspection(
            filename="fact_manufacturing_cost.csv",
            file_bytes=data,
        ):
            events.append(evt)

        # 1. Verify cross_dataset stage emitted WARNING (not PASSED) because production logs are absent
        cross_events = [e for e in events if e.stage == "cross_dataset"]
        assert len(cross_events) >= 2
        warning_evts = [e for e in cross_events if e.status == "WARNING"]
        assert len(warning_evts) == 1
        assert "UNAVAILABLE" in warning_evts[0].message
        assert "Hourly production logs were not provided" in warning_evts[0].message

        # 2. Verify completion event and generated report
        completion_evts = [e for e in events if e.event_type == "analysis_completed"]
        assert len(completion_evts) == 1
        final_details = completion_evts[0].details
        report_id = final_details.get("report_id")
        assert report_id is not None

        # 3. Retrieve durable report from database
        persisted_report = get_cached_report(report_id, db=db)
        assert persisted_report is not None
        assert persisted_report.scope.datasets_analyzed == 1
        assert persisted_report.scope.cost_records_count == 5000
        assert "unavailable" in persisted_report.scope.matched_production_label.lower()
        assert persisted_report.current_cost_per_good_unit is None
        assert persisted_report.current_good_qty is None

        # 4. Check findings
        classifications = {f.finding_id: f.evidence_classification for f in persisted_report.findings}
        assert classifications["FND-01"] == "PROVEN"
        assert classifications["FND-03"] == "UNAVAILABLE"
        assert classifications["FND-04"] == "UNAVAILABLE"

    finally:
        db.close()

