"""
test_universal_analytics.py
Universal Dataset-Driven Manufacturing Analytics & Intelligent Chart System Verification Suite.
"""

import pytest
import os
import sys
from fastapi.testclient import TestClient

# Ensure backend app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.db import get_db
from app.services.investigation.investigation_engine import InvestigationEngineService

client = TestClient(app)

NOV_SESSION_ID = "6e9668d6-9142-4b3b-b21a-eb87f0f0f301"
DEC_SESSION_ID = "83bc61af-e690-4c01-8386-5e8313147008"


def test_november_weekly_chart_zero_value_fix_and_reconciliation():
    """
    Verify November upload report:
    1. Weekly trend records are NOT zero (was the critical bug).
    2. Sum of weekly costs equals sum of daily costs.
    3. Sum of daily costs equals total_manufacturing_cost.
    4. available_granularities contains only ['Daily', 'Weekly'] for single month.
    """
    db = next(get_db())
    try:
        report = InvestigationEngineService.generate_report(
            db=db,
            inspection_id=NOV_SESSION_ID,
        )

        assert report is not None
        assert report.reporting_period_label is not None
        assert "November" in report.reporting_period_label

        # Verify daily trend
        daily = report.daily_cost_trend
        assert len(daily) == 30, f"Expected 30 days of November, got {len(daily)}"
        daily_sum = sum(d["cost"] for d in daily)
        assert daily_sum > 0, "Daily cost sum must be greater than zero"

        # Verify weekly trend (The bug was 4 bars displaying 0.00 Cr)
        weekly = report.weekly_cost_trend
        assert len(weekly) == 4, f"Expected 4 weeks, got {len(weekly)}"
        for w in weekly:
            assert w["cost"] > 0, f"Week {w['label']} cost must be > 0, got {w['cost']}"
            assert "0.00" not in w["formatted_cost"], f"Week {w['label']} formatted_cost was zero: {w['formatted_cost']}"

        weekly_sum = sum(w["cost"] for w in weekly)

        # Mathematical reconciliation: sum(weekly) == sum(daily) == total_cost
        assert abs(daily_sum - weekly_sum) < 1.0, f"Daily sum {daily_sum} != Weekly sum {weekly_sum}"
        assert abs(report.current_total_cost - weekly_sum) < 1.0, (
            f"Current total cost {report.current_total_cost} != Weekly sum {weekly_sum}"
        )

        # Granularity contract
        assert report.available_granularities == ["Daily", "Weekly"], (
            f"Single-month dataset should only have Daily and Weekly, got {report.available_granularities}"
        )
        assert report.default_granularity == "Daily"

        # Check reporting context
        ctx = report.reporting_context
        assert ctx.get("is_single_month") is True
        assert ctx.get("reporting_period") == "2026-11"
        assert ctx.get("total_records") is not None and ctx.get("total_records") > 0

    finally:
        db.close()


def test_december_partial_period_analytics_and_reconciliation():
    """
    Verify December upload report:
    1. Correctly derived as Dec 01-25 partial period.
    2. Sum of weekly costs equals sum of daily costs equals total_manufacturing_cost.
    3. Baseline is day-aligned to days 1-25.
    4. available_granularities contains only ['Daily', 'Weekly'].
    """
    db = next(get_db())
    try:
        report = InvestigationEngineService.generate_report(
            db=db,
            inspection_id=DEC_SESSION_ID,
        )

        assert report is not None
        assert report.reporting_period_label is not None
        assert "Dec" in report.reporting_period_label
        assert report.is_partial_period is True
        assert report.min_date == "2026-12-01"
        assert report.max_date == "2026-12-25"

        daily = report.daily_cost_trend
        assert len(daily) == 25, f"Expected 25 days of December, got {len(daily)}"
        daily_sum = sum(d["cost"] for d in daily)
        assert daily_sum > 0

        weekly = report.weekly_cost_trend
        assert len(weekly) == 4, f"Expected 4 weeks for Dec 1-25, got {len(weekly)}"
        for w in weekly:
            assert w["cost"] > 0, f"Week {w['label']} cost must be > 0, got {w['cost']}"

        weekly_sum = sum(w["cost"] for w in weekly)

        # Mathematical reconciliation
        assert abs(daily_sum - weekly_sum) < 1.0, f"Daily sum {daily_sum} != Weekly sum {weekly_sum}"
        assert abs(report.current_total_cost - weekly_sum) < 1.0, (
            f"Current total cost {report.current_total_cost} != Weekly sum {weekly_sum}"
        )

        # Baseline day-alignment check
        assert report.baseline_min_date == "2026-10-01" or report.baseline_min_date == "2026-11-01"
        assert report.baseline_max_date == "2026-10-25" or report.baseline_max_date == "2026-11-25"

        # Granularities
        assert report.available_granularities == ["Daily", "Weekly"]

    finally:
        db.close()


def test_api_investigation_report_endpoint_contracts():
    """
    Test the FastAPI /investigation/report endpoint for schema compliance.
    """
    res = client.get(f"/api/investigation/report?session_id={NOV_SESSION_ID}&bypass_cache=true")
    assert res.status_code == 200
    data = res.json()

    assert "daily_cost_trend" in data
    assert "weekly_cost_trend" in data
    assert "available_granularities" in data
    assert "default_granularity" in data
    assert "reporting_context" in data

    assert data["available_granularities"] == ["Daily", "Weekly"]
    assert len(data["weekly_cost_trend"]) == 4
    assert data["weekly_cost_trend"][0]["cost"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
