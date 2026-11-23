"""
Unit and integration test for Product Comparison Service with Independent Reporting Periods.
Verifies:
1. Dynamic period options derived from committed Global Store records (is_synthetic == False).
2. Deterministic calculation of metrics per product:
   - Total Expenditure
   - Cost per Good Unit
   - Cost per Gross Unit
   - Gross Production
   - Good Production
   - Rejected Quantity
   - Factory Yield %
   - Normalized Daily Run Rates
3. Independent date filtering per product (e.g. SPH-A15-128 in Aug vs SPH-A15-256 in Sep).
4. No-data state handling for periods with zero records.
5. Strict Global Store only (is_synthetic == False).
"""

import pytest
from app.db import SessionLocal
from app.services.analytics.product_comparison_service import ProductComparisonService


def test_period_options_derived_from_db():
    db = SessionLocal()
    try:
        options = ProductComparisonService.get_period_options_for_product(db, "SPH-A15-128")
        assert options is not None
        assert options["min_date"] == "2026-08-01"
        assert options["max_date"] == "2026-10-31"

        preset_ids = [p["id"] for p in options["presets"]]
        assert "ALL_HISTORY" in preset_ids
        assert "CURRENT_MONTH" in preset_ids
        assert "PREVIOUS_MONTH" in preset_ids
        assert "LAST_30_DAYS" in preset_ids
        assert "LAST_90_DAYS" in preset_ids
        assert "CUSTOM" in preset_ids

        # Check CURRENT_MONTH matches Oct 2026
        curr_m = next(p for p in options["presets"] if p["id"] == "CURRENT_MONTH")
        assert curr_m["start_date"] == "2026-10-01"
        assert curr_m["end_date"] == "2026-10-31"

        # Check PREVIOUS_MONTH matches Sep 2026
        prev_m = next(p for p in options["presets"] if p["id"] == "PREVIOUS_MONTH")
        assert prev_m["start_date"] == "2026-09-01"
        assert prev_m["end_date"] == "2026-09-30"
    finally:
        db.close()


def test_independent_product_metrics():
    db = SessionLocal()
    try:
        # Aug 2026 for SPH-A15-128
        res_aug = ProductComparisonService.get_product_metrics_for_period(
            db, "SPH-A15-128", "2026-08-01", "2026-08-31", "CURRENT_MONTH"
        )
        assert res_aug["has_data"] is True
        assert res_aug["cost_cr"] > 100.0  # ~164.99 Cr
        assert res_aug["produced_qty"] > 100000
        assert res_aug["yield_pct"] > 95.0
        assert res_aug["good_qty"] > 0
        assert res_aug["rejected_qty"] > 0
        assert res_aug["cost_per_good_unit"] > res_aug["cost_per_produced_unit"]
        assert res_aug["daily_cost_cr"] > 0
        assert res_aug["daily_output_units"] > 0
        assert res_aug["is_synthetic"] is False

        # Sep 2026 for SPH-A15-256
        res_sep = ProductComparisonService.get_product_metrics_for_period(
            db, "SPH-A15-256", "2026-09-01", "2026-09-30", "PREVIOUS_MONTH"
        )
        assert res_sep["has_data"] is True
        assert res_sep["cost_cr"] > 100.0
        assert res_sep["produced_qty"] > 100000
        assert res_sep["is_synthetic"] is False

        # Multi-product comparison
        multi = ProductComparisonService.compare_products_multi(db, [
            {
                "product_code": "SPH-A15-128",
                "start_date": "2026-08-01",
                "end_date": "2026-08-31",
                "period_preset_id": "PREVIOUS_MONTH"
            },
            {
                "product_code": "SPH-A15-256",
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
                "period_preset_id": "CURRENT_MONTH"
            }
        ])
        assert len(multi["products"]) == 2
        assert multi["periods_differ"] is True
        assert multi["coverage_note"] is not None
        assert multi["stats"] is not None
    finally:
        db.close()


def test_missing_data_period():
    db = SessionLocal()
    try:
        # A date range in 2025 where no data exists
        res_empty = ProductComparisonService.get_product_metrics_for_period(
            db, "SPH-A15-128", "2025-01-01", "2025-01-31"
        )
        assert res_empty["has_data"] is False
        assert res_empty["cost_cr"] == 0.0
        assert res_empty["produced_qty"] == 0.0
        assert res_empty["no_data_message"] is not None
        assert "No committed records found" in res_empty["no_data_message"]
    finally:
        db.close()
