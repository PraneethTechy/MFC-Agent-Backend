"""
Manufacturing Cost Agent - Global Date Range Service
Authoritative discovery of Global Manufacturing Store reporting periods.
Guarantees:
- Derives min_date, max_date, and complete calendar month presets strictly from committed database facts.
- Strictly separates Global Store coverage from active upload sessions (e.g. December staging).
- Automatically adapts when new records (e.g. December or January 2027) are promoted into the Global Store.
- Generates only the 3 permitted presets:
    1. All Available Data
    2. Latest Complete Month (only when supported)
    3. Previous Complete Month (only when supported)
- Caches results with TTL and provides explicit cache invalidation hook for PromotionService.
"""

import calendar
import datetime as dt
import logging
from typing import Any, Optional
from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session

from app.models.real_datasets import LineCostBatch, HourlyProductionLog

logger = logging.getLogger("manufacturing_cost_agent.analytics.date_range")


class GlobalDateRangeService:
    _cached_results: dict[Optional[bool], dict[str, Any]] = {}
    _cache_timestamps: dict[Optional[bool], float] = {}
    _cache_ttl_seconds: float = 300.0  # 5 minutes

    @classmethod
    def invalidate_cache(cls):
        """Invalidates in-memory date range cache (called after ingestion/promotion)."""
        cls._cached_results.clear()
        cls._cache_timestamps.clear()
        logger.info("Global Store date range cache invalidated.")

    @classmethod
    def get_global_date_bounds(cls, db: Session, is_synthetic: Optional[bool] = None) -> dict[str, Any]:
        """
        Determines the authoritative minimum and maximum dates across the Global Manufacturing Store.
        Caches results with TTL and allows explicit invalidation after data promotion.
        Supports filtering to baseline-only (is_synthetic=False) or full store (is_synthetic=None).
        """
        now = dt.datetime.now(dt.timezone.utc).timestamp()
        cached = cls._cached_results.get(is_synthetic)
        cached_ts = cls._cache_timestamps.get(is_synthetic)
        if cached and cached_ts and (now - cached_ts < cls._cache_ttl_seconds):
            return cached

        # Query actual min and max dates across line_cost_batches and hourly_production_logs
        cost_min, cost_max = None, None
        try:
            cost_q = db.query(
                func.min(cast(LineCostBatch.posting_ts, Date)),
                func.max(cast(LineCostBatch.posting_ts, Date))
            ).filter(LineCostBatch.is_current == True)
            if is_synthetic is not None:
                cost_q = cost_q.filter(LineCostBatch.is_synthetic == is_synthetic)
            cost_min, cost_max = cost_q.first()
        except Exception as e:
            logger.warning("Error querying LineCostBatch date bounds: %s", e)

        prod_min, prod_max = None, None
        try:
            prod_q = db.query(
                func.min(HourlyProductionLog.event_date),
                func.max(HourlyProductionLog.event_date)
            ).filter(HourlyProductionLog.is_current == True)
            if is_synthetic is not None:
                prod_q = prod_q.filter(HourlyProductionLog.is_synthetic == is_synthetic)
            prod_min, prod_max = prod_q.first()
        except Exception as e:
            logger.warning("Error querying HourlyProductionLog date bounds: %s", e)

        valid_mins = [d for d in (cost_min, prod_min) if d is not None]
        valid_maxs = [d for d in (cost_max, prod_max) if d is not None]

        if not valid_mins or not valid_maxs:
            result = {
                "min_date": None,
                "max_date": None,
                "min_date_formatted": "",
                "max_date_formatted": "",
                "default_period": "No Data Available",
                "default_start_date": "",
                "default_end_date": "",
                "presets": [],
                "complete_months_count": 0,
            }
            return result

        min_d = min(valid_mins)
        max_d = max(valid_maxs)

        if min_d > max_d:
            min_d, max_d = max_d, min_d

        def fmt(d: dt.date) -> str:
            return d.strftime("%b %d, %Y")

        def month_fmt(year: int, month: int) -> str:
            return dt.date(year, month, 1).strftime("%B %Y")

        presets = []

        # 1. All Available Data
        all_available_label = f"{fmt(min_d)} - {fmt(max_d)}"
        presets.append({
            "id": "ALL_AVAILABLE",
            "name": "All Available Data",
            "description": "Full Global Store historical coverage",
            "start_date": min_d.isoformat(),
            "end_date": max_d.isoformat(),
            "display_range": all_available_label,
            "badge": "Full Coverage",
        })

        # Discover complete calendar months within [min_d, max_d]
        complete_months = []
        curr_y, curr_m = min_d.year, min_d.month
        end_y, end_m = max_d.year, max_d.month

        while (curr_y < end_y) or (curr_y == end_y and curr_m <= end_m):
            last_day = calendar.monthrange(curr_y, curr_m)[1]
            m_start = dt.date(curr_y, curr_m, 1)
            m_end = dt.date(curr_y, curr_m, last_day)

            # A month is complete only if both its start and end are fully bounded in [min_d, max_d]
            if m_start >= min_d and m_end <= max_d:
                complete_months.append((curr_y, curr_m, m_start, m_end))

            if curr_m == 12:
                curr_y += 1
                curr_m = 1
            else:
                curr_m += 1

        # 2. Latest Complete Month (only when available)
        if len(complete_months) >= 1:
            y, m, m_start, m_end = complete_months[-1]
            presets.append({
                "id": "LATEST_COMPLETE_MONTH",
                "name": "Latest Complete Month",
                "description": f"{month_fmt(y, m)} manufacturing actuals",
                "start_date": m_start.isoformat(),
                "end_date": m_end.isoformat(),
                "display_range": f"{fmt(m_start)} - {fmt(m_end)}",
                "badge": month_fmt(y, m),
            })

        # 3. Previous Complete Month (only when available)
        if len(complete_months) >= 2:
            y, m, m_start, m_end = complete_months[-2]
            presets.append({
                "id": "PREVIOUS_COMPLETE_MONTH",
                "name": "Previous Complete Month",
                "description": f"{month_fmt(y, m)} comparison baseline",
                "start_date": m_start.isoformat(),
                "end_date": m_end.isoformat(),
                "display_range": f"{fmt(m_start)} - {fmt(m_end)}",
                "badge": month_fmt(y, m),
            })

        result = {
            "min_date": min_d.isoformat(),
            "max_date": max_d.isoformat(),
            "min_date_formatted": fmt(min_d),
            "max_date_formatted": fmt(max_d),
            "default_period": all_available_label,
            "default_start_date": min_d.isoformat(),
            "default_end_date": max_d.isoformat(),
            "presets": presets,
            "complete_months_count": len(complete_months),
        }

        cls._cached_results[is_synthetic] = result
        cls._cache_timestamps[is_synthetic] = now
        return result
