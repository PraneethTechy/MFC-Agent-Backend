"""
Product Comparison Service
Provides authoritative, independent reporting period filtering and comparison metrics for products.
Strictly queries committed records in Neon PostgreSQL (is_synthetic == False).
"""

from decimal import Decimal
import datetime as dt
import calendar
import logging
from typing import Any, Optional
from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session

from app.models.real_datasets import (
    LineCostBatch,
    HourlyProductionLog,
    BomComponentRecord,
)

logger = logging.getLogger("manufacturing_cost_agent.analytics.product_comparison")


class ProductComparisonService:
    @staticmethod
    def get_period_options_for_product(db: Session, product_code: Optional[str] = None) -> dict[str, Any]:
        """
        Dynamically derives period filter options from committed Global Store records:
        - All Available History
        - Current Month (latest complete calendar month)
        - Previous Month (month prior to Current Month)
        - Last 30 Days (rolling 30-day window ending at max available date)
        - Last 90 Days (rolling 90-day window ending at max available date)
        - Custom Date Range (allows start_date and end_date bounded by [min_date, max_date])
        """
        q = db.query(
            func.min(cast(LineCostBatch.posting_ts, Date)),
            func.max(cast(LineCostBatch.posting_ts, Date))
        ).filter(LineCostBatch.is_synthetic == False)

        if product_code and product_code != "All Products":
            q = q.filter(LineCostBatch.product_code == product_code)

        min_d, max_d = q.first()
        if not min_d or not max_d:
            # Fallback to overall store bounds
            q_all = db.query(
                func.min(cast(LineCostBatch.posting_ts, Date)),
                func.max(cast(LineCostBatch.posting_ts, Date))
            ).filter(LineCostBatch.is_synthetic == False)
            min_d, max_d = q_all.first()

        if not min_d or not max_d:
            return {
                "product_code": product_code,
                "min_date": None,
                "max_date": None,
                "presets": [],
            }

        def fmt(d: dt.date) -> str:
            return d.strftime("%b %d, %Y")

        def month_name(year: int, month: int) -> str:
            return dt.date(year, month, 1).strftime("%B %Y")

        presets = []

        # 1. All Available History
        presets.append({
            "id": "ALL_HISTORY",
            "name": "All Available History",
            "description": f"Full committed history ({fmt(min_d)} – {fmt(max_d)})",
            "start_date": min_d.isoformat(),
            "end_date": max_d.isoformat(),
            "display_range": f"{fmt(min_d)} – {fmt(max_d)}",
            "days": (max_d - min_d).days + 1,
        })

        # Discover complete calendar months
        complete_months = []
        curr_y, curr_m = min_d.year, min_d.month
        end_y, end_m = max_d.year, max_d.month

        while (curr_y < end_y) or (curr_y == end_y and curr_m <= end_m):
            last_day = calendar.monthrange(curr_y, curr_m)[1]
            m_start = dt.date(curr_y, curr_m, 1)
            m_end = dt.date(curr_y, curr_m, last_day)
            if m_start >= min_d and m_end <= max_d:
                complete_months.append((curr_y, curr_m, m_start, m_end))
            if curr_m == 12:
                curr_y += 1
                curr_m = 1
            else:
                curr_m += 1

        # 2. Current Month (latest complete calendar month)
        if len(complete_months) >= 1:
            y, m, m_start, m_end = complete_months[-1]
            presets.append({
                "id": "CURRENT_MONTH",
                "name": "Current Month",
                "description": f"{month_name(y, m)} ({fmt(m_start)} – {fmt(m_end)})",
                "start_date": m_start.isoformat(),
                "end_date": m_end.isoformat(),
                "display_range": f"{fmt(m_start)} – {fmt(m_end)}",
                "days": (m_end - m_start).days + 1,
            })

        # 3. Previous Month
        if len(complete_months) >= 2:
            prev_y, prev_m, prev_start, prev_end = complete_months[-2]
            presets.append({
                "id": "PREVIOUS_MONTH",
                "name": "Previous Month",
                "description": f"{month_name(prev_y, prev_m)} ({fmt(prev_start)} – {fmt(prev_end)})",
                "start_date": prev_start.isoformat(),
                "end_date": prev_end.isoformat(),
                "display_range": f"{fmt(prev_start)} – {fmt(prev_end)}",
                "days": (prev_end - prev_start).days + 1,
            })

        # 4. Last 30 Days (rolling 30-day window ending at max available date)
        start_30 = max(min_d, max_d - dt.timedelta(days=29))
        presets.append({
            "id": "LAST_30_DAYS",
            "name": "Last 30 Days",
            "description": f"Rolling 30 days ({fmt(start_30)} – {fmt(max_d)})",
            "start_date": start_30.isoformat(),
            "end_date": max_d.isoformat(),
            "display_range": f"{fmt(start_30)} – {fmt(max_d)}",
            "days": (max_d - start_30).days + 1,
        })

        # 5. Last 90 Days (rolling 90-day window ending at max available date)
        start_90 = max(min_d, max_d - dt.timedelta(days=89))
        presets.append({
            "id": "LAST_90_DAYS",
            "name": "Last 90 Days",
            "description": f"Rolling 90 days ({fmt(start_90)} – {fmt(max_d)})",
            "start_date": start_90.isoformat(),
            "end_date": max_d.isoformat(),
            "display_range": f"{fmt(start_90)} – {fmt(max_d)}",
            "days": (max_d - start_90).days + 1,
        })

        # 6. Custom Range indicator
        presets.append({
            "id": "CUSTOM",
            "name": "Custom Date Range",
            "description": f"Select specific date range within {fmt(min_d)} – {fmt(max_d)}",
            "start_date": min_d.isoformat(),
            "end_date": max_d.isoformat(),
            "display_range": "Custom Range",
            "days": (max_d - min_d).days + 1,
        })

        return {
            "product_code": product_code,
            "min_date": min_d.isoformat(),
            "max_date": max_d.isoformat(),
            "min_date_formatted": fmt(min_d),
            "max_date_formatted": fmt(max_d),
            "presets": presets,
        }

    @staticmethod
    def get_product_metrics_for_period(
        db: Session,
        product_code: str,
        start_date_str: str,
        end_date_str: str,
        period_preset_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Computes deterministic metrics strictly for committed records in Neon (is_synthetic == False):
        - Total Expenditure = sum of direct manufacturing cost (material + labour + machine + energy + scrap)
        - Cost per Good Unit = total expenditure / good production
        - Cost per Gross Unit = total expenditure / gross production
        - Gross Production = total produced units
        - Good Production = total units passing final quality check
        - Rejected Quantity = gross production - good production
        - Factory Yield = (good production / gross production) * 100
        - Normalized daily run rates (Daily Cost, Daily Output)
        """
        try:
            start_d = dt.date.fromisoformat(start_date_str)
            end_d = dt.date.fromisoformat(end_date_str)
        except Exception:
            raise ValueError(f"Invalid date format: {start_date_str} to {end_date_str}. Expected YYYY-MM-DD.")

        if start_d > end_d:
            raise ValueError(f"Start date ({start_date_str}) cannot be after end date ({end_date_str}).")

        days_in_period = max(1, (end_d - start_d).days + 1)

        def fmt(d: dt.date) -> str:
            return d.strftime("%b %d, %Y")

        display_range = f"{fmt(start_d)} – {fmt(end_d)}"

        # Query LineCostBatch (Strictly is_synthetic == False)
        cost_q = db.query(
            func.count(LineCostBatch.id).label("batches_count"),
            func.sum(LineCostBatch.produced_qty).label("produced_qty"),
            func.sum(LineCostBatch.material_cost_inr).label("mat_cost"),
            func.sum(LineCostBatch.labour_cost_inr).label("lab_cost"),
            func.sum(LineCostBatch.machine_cost_inr).label("mac_cost"),
            func.sum(LineCostBatch.energy_cost_inr).label("nrg_cost"),
            func.sum(LineCostBatch.scrap_rework_cost_inr).label("scr_cost"),
            func.sum(LineCostBatch.total_direct_cost_inr).label("total_cost"),
        ).filter(
            LineCostBatch.is_synthetic == False,
            LineCostBatch.product_code == product_code,
            cast(LineCostBatch.posting_ts, Date) >= start_d,
            cast(LineCostBatch.posting_ts, Date) <= end_d,
        )

        cost_res = cost_q.first()
        batches_count = int(cost_res.batches_count or 0)
        produced_qty = float(cost_res.produced_qty or 0.0)
        total_cost = float(cost_res.total_cost or 0.0)
        mat_cost = float(cost_res.mat_cost or 0.0)
        lab_cost = float(cost_res.lab_cost or 0.0)
        mac_cost = float(cost_res.mac_cost or 0.0)
        nrg_cost = float(cost_res.nrg_cost or 0.0)
        scr_cost = float(cost_res.scr_cost or 0.0)

        # Query HourlyProductionLog for operational yield (Strictly is_synthetic == False)
        yield_q = db.query(
            func.sum(HourlyProductionLog.actual_qty),
            func.sum(HourlyProductionLog.good_qty),
            func.sum(HourlyProductionLog.reject_qty)
        ).filter(
            HourlyProductionLog.is_synthetic == False,
            HourlyProductionLog.product_code == product_code,
            HourlyProductionLog.event_date >= start_d,
            HourlyProductionLog.event_date <= end_d,
        )
        yield_res = yield_q.first()
        act_qty = float(yield_res[0] or produced_qty)
        raw_good_qty = float(yield_res[1] or produced_qty)

        yield_pct = round((raw_good_qty / act_qty * 100.0), 2) if act_qty > 0 else 100.0

        # Deterministic salable good units and rejected quantity
        yield_rate = (yield_pct / 100.0) if yield_pct > 0 else 1.0
        good_qty = round(produced_qty * yield_rate, 2)
        rejected_qty = max(0.0, round(produced_qty - good_qty, 2))

        # Financial unit metrics
        cost_per_gross_unit = round(total_cost / produced_qty, 2) if produced_qty > 0 else 0.0
        cost_per_good_unit = round(total_cost / good_qty, 2) if good_qty > 0 else 0.0
        cost_cr = round(total_cost / 1e7, 2)

        # Normalized Daily Run Rates
        daily_cost_inr = round(total_cost / days_in_period, 2) if days_in_period > 0 else 0.0
        daily_cost_cr = round((total_cost / 1e7) / days_in_period, 4) if days_in_period > 0 else 0.0
        daily_output_units = round(produced_qty / days_in_period, 1) if days_in_period > 0 else 0.0
        daily_good_units = round(good_qty / days_in_period, 1) if days_in_period > 0 else 0.0

        # Component count from BOM
        bom_count_q = db.query(func.count(BomComponentRecord.id)).filter(
            BomComponentRecord.product_code == product_code,
            BomComponentRecord.is_synthetic == False
        )
        bom_count = bom_count_q.scalar() or 0

        has_data = batches_count > 0 and produced_qty > 0

        return {
            "product_code": product_code,
            "product_name": f"Smartphone Model {product_code}",
            "segment": "Flagship 256GB" if "256" in product_code else "Standard 128GB",
            "period_preset_id": period_preset_id,
            "start_date": start_date_str,
            "end_date": end_date_str,
            "display_range": display_range,
            "days_in_period": days_in_period,
            "has_data": has_data,
            "no_data_message": None if has_data else f"No committed records found for {product_code} in the period ({display_range}).",
            "batches_count": batches_count,
            "cost_inr": total_cost,
            "cost_cr": cost_cr,
            "produced_qty": produced_qty,
            "good_qty": good_qty,
            "rejected_qty": rejected_qty,
            "yield_pct": yield_pct,
            "cost_per_produced_unit": cost_per_gross_unit,
            "cost_per_good_unit": cost_per_good_unit,
            "daily_cost_inr": daily_cost_inr,
            "daily_cost_cr": daily_cost_cr,
            "daily_output_units": daily_output_units,
            "daily_good_units": daily_good_units,
            "bom_components_count": int(bom_count),
            "breakdown": {
                "material_inr": mat_cost,
                "labour_inr": lab_cost,
                "machine_inr": mac_cost,
                "energy_inr": nrg_cost,
                "scrap_inr": scr_cost,
            },
            "data_origin": "COMMITTED_GLOBAL_STORE",
            "is_synthetic": False,
        }

    @classmethod
    def compare_products_multi(cls, db: Session, items: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Evaluates independent reporting period metrics for each compared product.
        Analyzes whether timeframes are identical or differ and produces normalized comparisons.
        """
        results = []
        for item in items:
            p_code = item.get("product_code")
            s_date = item.get("start_date")
            e_date = item.get("end_date")
            preset_id = item.get("period_preset_id")
            if not p_code or not s_date or not e_date:
                continue
            metrics = cls.get_product_metrics_for_period(
                db=db,
                product_code=p_code,
                start_date_str=s_date,
                end_date_str=e_date,
                period_preset_id=preset_id,
            )
            results.append(metrics)

        # Check if all periods are identical
        unique_ranges = {(r["start_date"], r["end_date"]) for r in results}
        periods_differ = len(unique_ranges) > 1

        coverage_note = None
        if periods_differ:
            coverage_note = (
                "Comparing non-identical timeframes across selected products. "
                "Normalized daily run-rates (Daily Spend and Daily Output) are displayed alongside actual totals "
                "to provide an accurate, balanced comparison across differing date spans."
            )

        # Comparison statistics (min/max highlighting)
        stats = None
        if len(results) >= 2:
            good_costs = [r["cost_per_good_unit"] for r in results if r["has_data"] and r["cost_per_good_unit"] > 0]
            gross_costs = [r["cost_per_produced_unit"] for r in results if r["has_data"] and r["cost_per_produced_unit"] > 0]
            yields = [r["yield_pct"] for r in results if r["has_data"]]
            rejects = [r["rejected_qty"] for r in results if r["has_data"]]
            daily_costs = [r["daily_cost_cr"] for r in results if r["has_data"]]
            daily_outputs = [r["daily_output_units"] for r in results if r["has_data"]]

            stats = {
                "minGoodCost": min(good_costs) if good_costs else 0,
                "maxGoodCost": max(good_costs) if good_costs else 0,
                "minGrossCost": min(gross_costs) if gross_costs else 0,
                "maxGrossCost": max(gross_costs) if gross_costs else 0,
                "minYield": min(yields) if yields else 0,
                "maxYield": max(yields) if yields else 0,
                "minReject": min(rejects) if rejects else 0,
                "maxReject": max(rejects) if rejects else 0,
                "minDailyCost": min(daily_costs) if daily_costs else 0,
                "maxDailyCost": max(daily_costs) if daily_costs else 0,
                "minDailyOutput": min(daily_outputs) if daily_outputs else 0,
                "maxDailyOutput": max(daily_outputs) if daily_outputs else 0,
            }

        return {
            "products": results,
            "periods_differ": periods_differ,
            "coverage_note": coverage_note,
            "stats": stats,
            "data_origin": "COMMITTED_GLOBAL_STORE",
            "is_synthetic": False,
        }
