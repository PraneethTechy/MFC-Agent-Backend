import os
import asyncio
import pytest
from app.services.ingestion.streaming_inspector import StreamingInspectorService
from app.db import SessionLocal
from app.services.investigation.report_cache import get_cached_report

CSV_PATH = r"C:\Users\gwc\Downloads\manufacturing-agent-test-dataset\manufacturing-agent-test-dataset\csv"

FILES_TO_TEST = [
    "test_fact_manufacturing_cost.csv",
    "test_fact_hourly_production.csv",
    "test_fact_bom_component.csv",
    "test_fact_material_purchase.csv",
    "test_fact_material_consumption.csv",
    "test_fact_quality_inspection.csv",
    "test_fact_quality_rework_events.csv",
]

def test_seven_datasets_end_to_end():
    if not os.path.exists(CSV_PATH):
        pytest.skip(f"Test dataset path not found at {CSV_PATH}")

    files_data = []
    for f in FILES_TO_TEST:
        fp = os.path.join(CSV_PATH, f)
        if not os.path.exists(fp):
            pytest.skip(f"Missing test fixture: {fp}")
        with open(fp, "rb") as fh:
            files_data.append({"filename": f, "file_bytes": fh.read()})

    async def _run():
        db = SessionLocal()
        try:
            svc = StreamingInspectorService(db=db)
            final_report = None
            async for evt in svc.stream_inspection(files_data=files_data):
                if evt.event_type in ("analysis_completed", "inspection_completed"):
                    final_report = evt.details

            assert final_report is not None, "Final inspection report should be emitted"
            rep_id = final_report.get("report_id")
            assert rep_id is not None

            report_obj = get_cached_report(rep_id, db=db)
            assert report_obj is not None, "Report must be persisted and retrievable"

            # Assertions
            assert report_obj.scope.uploaded_files_count == 7
            assert report_obj.scope.dataset_types_count == 7
            assert report_obj.scope.cost_records_count == 1800
            assert report_obj.data_origin == "SYNTHETIC_TEST"
            assert report_obj.current_produced_qty == 285156.0
            assert report_obj.current_good_qty == 279113.0
            assert report_obj.baseline_produced_qty == 275929.0
            assert report_obj.baseline_good_qty == 270533.0
            assert report_obj.baseline_cost_per_good_unit == pytest.approx(10774.27, rel=1e-2)
            assert report_obj.current_cost_per_good_unit == pytest.approx(11264.46, rel=1e-2)
            assert report_obj.baseline_cost_per_produced_unit == pytest.approx(10563.57, rel=1e-2)
            assert report_obj.current_cost_per_produced_unit == pytest.approx(11025.74, rel=1e-2)
            assert len(report_obj.findings) >= 5

            # Labour finding assertion
            lab_finding = report_obj.findings[1]
            assert lab_finding.title == "Direct Labour Expenditure Movement"
            assert lab_finding.evidence_classification == "PROVEN"

            # Material variance 3-way orthogonal decomposition assertion
            mat_finding = report_obj.findings[2]
            assert "Material Variance Decomposition" in mat_finding.title
            assert mat_finding.evidence_classification == "OBSERVED_CORRELATION"
            assert mat_finding.supporting_metrics.get("material_price_effect") == pytest.approx(96649227.02, rel=1e-2)
            assert mat_finding.supporting_metrics.get("volume_mix_effect") == pytest.approx(91577311.66, rel=1e-2)
            assert mat_finding.supporting_metrics.get("consumption_usage_effect") == pytest.approx(35682344.62, rel=1e-2)
            assert mat_finding.supporting_metrics.get("reconciled_sum") == pytest.approx(223908883.30, rel=1e-2)
            assert mat_finding.supporting_metrics.get("unexplained_residual") == 0.0
            assert mat_finding.supporting_metrics.get("purchase_order_ppv") == pytest.approx(99574379.99, rel=1e-2)

            # Waterfall bridge reconciliation
            assert report_obj.bridge.reconciled is True
            assert report_obj.bridge.unexplained_remainder == 0.0

            # Data reliability assertion (total physical source records: 40,369)
            assert report_obj.data_reliability.score is None
            assert report_obj.data_reliability.total_records_evaluated == 40369
            assert report_obj.data_reliability.matching_coverage_pct == 100.0
            assert report_obj.data_reliability.reconciliation_status == "RECONCILED (100% MATCH)"
            assert len(report_obj.data_reliability.checks) >= 6
            assert len(report_obj.scope.file_manifest) == 7
            assert sum(m["total_rows"] for m in report_obj.scope.file_manifest) == 40369
        finally:
            if rep_id:
                try:
                    from app.models.agent_records import InvestigationReportRecord
                    db.query(InvestigationReportRecord).filter_by(report_id=rep_id).delete()
                    db.commit()
                except Exception:
                    db.rollback()
            db.close()

    asyncio.run(_run())
