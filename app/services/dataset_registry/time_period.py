"""
Manufacturing Dataset Registry - Flexible Time-Period & Granularity Resolver
Handles multi-format date extraction, period parsing (day, multi-day, week, month, custom range),
dataset coverage validation, and granularity alignment.
Never hardcodes August-October 2026 as a universal analysis boundary.
"""

from dataclasses import dataclass, asdict
import datetime as dt
import re
from typing import Any, Optional

from .models import GranularityType

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")
MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
WEEK_PATTERN = re.compile(r"^(\d{4})-W(\d{1,2})$", re.IGNORECASE)


@dataclass
class ResolvedPeriodScope:
    """Normalized temporal window for an investigation query."""
    raw_input: str
    period_type: str  # 'SINGLE_DAY', 'MULTI_DAY', 'WEEK', 'MONTH', 'CUSTOM_RANGE', 'COMPARISON', 'ALL_COMMITTED'
    start_date: Optional[dt.date] = None
    end_date: Optional[dt.date] = None
    baseline_start_date: Optional[dt.date] = None
    baseline_end_date: Optional[dt.date] = None
    iso_period_code: Optional[str] = None
    is_future_period: bool = False

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.start_date:
            d["start_date"] = self.start_date.isoformat()
        if self.end_date:
            d["end_date"] = self.end_date.isoformat()
        if self.baseline_start_date:
            d["baseline_start_date"] = self.baseline_start_date.isoformat()
        if self.baseline_end_date:
            d["baseline_end_date"] = self.baseline_end_date.isoformat()
        return d

    def model_dump(self) -> dict[str, Any]:
        return self.dict()


@dataclass
class CoverageAssessment:
    """Result of assessing a dataset's temporal coverage against an investigation scope."""
    dataset_id: str
    dataset_name: str
    granularity: GranularityType
    coverage_status: str  # 'FULL_COVERAGE', 'PARTIAL_COVERAGE', 'OUT_OF_BOUNDS', 'STATIC_SPEC'
    diagnostic_message: str
    dataset_start: Optional[dt.date] = None
    dataset_end: Optional[dt.date] = None
    missing_lead_days: int = 0
    missing_lag_days: int = 0
    coverage_percentage: float = 100.0

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["granularity"] = self.granularity.value if hasattr(self.granularity, "value") else str(self.granularity)
        if self.dataset_start:
            d["dataset_start"] = self.dataset_start.isoformat()
        if self.dataset_end:
            d["dataset_end"] = self.dataset_end.isoformat()
        return d

    def model_dump(self) -> dict[str, Any]:
        return self.dict()


class TimePeriodResolver:
    """Enterprise time-period and granularity resolver for manufacturing data."""

    # Reference operational timestamp for distinguishing historical vs planned/future simulations
    # (Default baseline from factory ground-truth, but completely configurable)
    DEFAULT_OPERATIONAL_REFERENCE_DATE = dt.date(2026, 10, 31)

    @classmethod
    def resolve_period(
        cls,
        period_str: Optional[str],
        reference_date: Optional[dt.date] = None,
    ) -> ResolvedPeriodScope:
        """
        Parses and standardizes any period string into a strict ResolvedPeriodScope.
        Supports:
        - None or 'ALL': Covers all committed historical data.
        - Month: '2026-10', '2026-08', 'Oct 2026'
        - Single day: '2026-08-15'
        - Multi-day range: '2026-08-01 to 2026-08-10', '2026-08-01:2026-08-10'
        - Week: '2026-W32', '2026-W41'
        - Comparison: '2026-10 vs 2026-09'
        """
        ref_dt = reference_date or cls.DEFAULT_OPERATIONAL_REFERENCE_DATE

        if not period_str or str(period_str).strip().upper() in ("ALL", "ALL_PERIODS", "ALL_COMMITTED", ""):
            return ResolvedPeriodScope(
                raw_input=period_str or "ALL",
                period_type="ALL_COMMITTED",
                start_date=None,
                end_date=None,
                iso_period_code="ALL",
                is_future_period=False,
            )

        raw = str(period_str).strip()

        # 1. Comparison check: "2026-10 vs 2026-09"
        if " vs " in raw.lower() or " versus " in raw.lower():
            parts = re.split(r"\s+(?:vs|versus)\s+", raw, flags=re.IGNORECASE)
            if len(parts) == 2:
                curr_res = cls.resolve_period(parts[0], ref_dt)
                base_res = cls.resolve_period(parts[1], ref_dt)
                return ResolvedPeriodScope(
                    raw_input=raw,
                    period_type="COMPARISON",
                    start_date=curr_res.start_date,
                    end_date=curr_res.end_date,
                    baseline_start_date=base_res.start_date,
                    baseline_end_date=base_res.end_date,
                    iso_period_code=f"{curr_res.iso_period_code}_vs_{base_res.iso_period_code}",
                    is_future_period=curr_res.is_future_period or base_res.is_future_period,
                )

        # 2. Month pattern: "2026-10"
        m_match = MONTH_PATTERN.match(raw)
        if m_match:
            year, month = int(m_match.group(1)), int(m_match.group(2))
            start_d = dt.date(year, month, 1)
            # Find last day of month
            if month == 12:
                end_d = dt.date(year, 12, 31)
            else:
                end_d = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
            
            is_future = end_d > ref_dt
            return ResolvedPeriodScope(
                raw_input=raw,
                period_type="MONTH",
                start_date=start_d,
                end_date=end_d,
                iso_period_code=f"{year:04d}-{month:02d}",
                is_future_period=is_future,
            )

        # 3. ISO Week pattern: "2026-W32"
        w_match = WEEK_PATTERN.match(raw)
        if w_match:
            year, week = int(w_match.group(1)), int(w_match.group(2))
            # First day of ISO week
            start_d = dt.date.fromisocalendar(year, week, 1)
            end_d = dt.date.fromisocalendar(year, week, 7)
            is_future = end_d > ref_dt
            return ResolvedPeriodScope(
                raw_input=raw,
                period_type="WEEK",
                start_date=start_d,
                end_date=end_d,
                iso_period_code=f"{year:04d}-W{week:02d}",
                is_future_period=is_future,
            )

        # 4. Multi-day range: "2026-08-01 to 2026-08-10" or "2026-08-01:2026-08-10"
        if " to " in raw.lower() or ":" in raw:
            parts = re.split(r"\s+to\s+|:", raw, flags=re.IGNORECASE)
            if len(parts) == 2:
                d1 = cls._parse_iso_date(parts[0])
                d2 = cls._parse_iso_date(parts[1])
                if d1 and d2:
                    if d1 > d2:
                        d1, d2 = d2, d1
                    is_future = d2 > ref_dt
                    return ResolvedPeriodScope(
                        raw_input=raw,
                        period_type="CUSTOM_RANGE",
                        start_date=d1,
                        end_date=d2,
                        iso_period_code=f"{d1.isoformat()}_to_{d2.isoformat()}",
                        is_future_period=is_future,
                    )

        # 5. Single date: "2026-08-15"
        single_d = cls._parse_iso_date(raw)
        if single_d:
            is_future = single_d > ref_dt
            return ResolvedPeriodScope(
                raw_input=raw,
                period_type="SINGLE_DAY",
                start_date=single_d,
                end_date=single_d,
                iso_period_code=single_d.isoformat(),
                is_future_period=is_future,
            )

        # Fallback to arbitrary string scope
        return ResolvedPeriodScope(
            raw_input=raw,
            period_type="CUSTOM_RANGE",
            start_date=None,
            end_date=None,
            iso_period_code=raw,
            is_future_period=False,
        )

    @classmethod
    def assess_dataset_coverage(
        cls,
        dataset_or_id: Any,
        requested_scope: Optional[ResolvedPeriodScope] = None,
        dataset_name: Optional[str] = None,
        granularity: Optional[GranularityType] = None,
        dataset_date_range_str: Optional[str] = None,
    ) -> CoverageAssessment:
        """
        Determines whether a dataset covers the user's requested time window.
        Correctly distinguishes static reference data, full coverage, partial coverage,
        and unpopulated/out-of-bounds ranges.
        Supports both (dataset_def, requested_scope) and (id, name, granularity, range_str, requested_scope).
        """
        if hasattr(dataset_or_id, "dataset_id") and requested_scope is not None:
            dataset_id = dataset_or_id.dataset_id
            ds_name = dataset_or_id.name
            ds_granularity = dataset_or_id.default_granularity
            ds_range = None
            if hasattr(dataset_or_id, "physical_sources") and dataset_or_id.physical_sources:
                ds_range = dataset_or_id.physical_sources[0].available_date_range
            req_scope = requested_scope
        elif isinstance(dataset_name, str) and granularity is not None:
            dataset_id = str(dataset_or_id)
            ds_name = dataset_name
            ds_granularity = granularity
            ds_range = dataset_date_range_str
            req_scope = requested_scope
        else:
            dataset_id = getattr(dataset_or_id, "dataset_id", str(dataset_or_id))
            ds_name = getattr(dataset_or_id, "name", dataset_name or dataset_id)
            ds_granularity = getattr(dataset_or_id, "default_granularity", granularity or GranularityType.HOURLY)
            ds_range = getattr(dataset_or_id, "available_date_range", dataset_date_range_str)
            req_scope = requested_scope

        # Static reference data (BOM, equipment master, shift catalog) is always available
        if ds_granularity == GranularityType.STATIC_SPEC or not ds_range or str(ds_range).lower() in ("static / none", "none", "static master catalog", "static sourcing list"):
            return CoverageAssessment(
                dataset_id=dataset_id,
                dataset_name=ds_name,
                granularity=ds_granularity,
                coverage_status="STATIC_SPEC",
                dataset_start=None,
                dataset_end=None,
                coverage_percentage=100.0,
                diagnostic_message="Dataset is non-temporal engineering reference master; available across all periods.",
            )

        # Parse dataset date range (e.g. "2026-08-01 to 2026-10-31")
        d_start, d_end = cls._parse_range_string(str(ds_range))
        if not d_start or not d_end:
            return CoverageAssessment(
                dataset_id=dataset_id,
                dataset_name=ds_name,
                granularity=ds_granularity,
                coverage_status="STATIC_SPEC",
                dataset_start=None,
                dataset_end=None,
                coverage_percentage=100.0,
                diagnostic_message="Dataset has unparsed temporal bounds; treated as reference.",
            )

        # If user asked for ALL, coverage is full
        if not req_scope or req_scope.period_type == "ALL_COMMITTED" or not req_scope.start_date:
            return CoverageAssessment(
                dataset_id=dataset_id,
                dataset_name=ds_name,
                granularity=ds_granularity,
                coverage_status="FULL_COVERAGE",
                dataset_start=d_start,
                dataset_end=d_end,
                coverage_percentage=100.0,
                diagnostic_message=f"Dataset covers committed range {d_start.isoformat()} to {d_end.isoformat()}.",
            )

        req_start = req_scope.start_date
        req_end = req_scope.end_date or req_scope.start_date
        total_req_days = max(1, (req_end - req_start).days + 1)

        # Check overlap
        overlap_start = max(req_start, d_start)
        overlap_end = min(req_end, d_end)

        if overlap_start > overlap_end:
            # Completely out of bounds
            return CoverageAssessment(
                dataset_id=dataset_id,
                dataset_name=ds_name,
                granularity=ds_granularity,
                coverage_status="OUT_OF_BOUNDS",
                dataset_start=d_start,
                dataset_end=d_end,
                coverage_percentage=0.0,
                diagnostic_message=f"Dataset date range ({d_start.isoformat()} to {d_end.isoformat()}) has zero overlap with requested window ({req_start.isoformat()} to {req_end.isoformat()}).",
            )

        overlap_days = max(0, (overlap_end - overlap_start).days + 1)
        cov_pct = round((overlap_days / total_req_days) * 100.0, 1)

        lead_gap = max(0, (d_start - req_start).days)
        lag_gap = max(0, (req_end - d_end).days)

        if cov_pct >= 99.0:
            status = "FULL_COVERAGE"
            msg = f"Dataset completely covers the requested window ({req_start.isoformat()} to {req_end.isoformat()})."
        else:
            status = "PARTIAL_COVERAGE"
            msg = f"Dataset covers {cov_pct}% of requested period ({overlap_days}/{total_req_days} days). Missing {lead_gap} leading days, {lag_gap} trailing days."

        return CoverageAssessment(
            dataset_id=dataset_id,
            dataset_name=ds_name,
            granularity=ds_granularity,
            coverage_status=status,
            dataset_start=d_start,
            dataset_end=d_end,
            missing_lead_days=lead_gap,
            missing_lag_days=lag_gap,
            coverage_percentage=cov_pct,
            diagnostic_message=msg,
        )

    @classmethod
    def validate_granularity_compatibility(
        cls,
        granularity_a: Any,
        granularity_b: Any,
    ) -> dict[str, Any]:
        """
        Validates whether two granularities can be joined or aggregated directly.
        Returns a dict with 'compatible' and 'message' keys.
        """
        g_a = granularity_a.value if hasattr(granularity_a, "value") else str(granularity_a)
        g_b = granularity_b.value if hasattr(granularity_b, "value") else str(granularity_b)

        if g_a == g_b:
            return {"compatible": True, "message": "Granularities are identical."}

        if g_a == "STATIC_SPEC" or g_b == "STATIC_SPEC":
            return {"compatible": True, "message": "Reference master can join to any transactional granularity."}

        # Directional compatibility: Source Granularity -> Query Target Granularity
        if g_a == "HOURLY" and g_b in ("SHIFT", "DAILY", "MONTH", "WEEK"):
            return {"compatible": True, "message": f"Hourly records can be aggregated into {g_b} windows."}

        if g_a == "DAILY" and g_b in ("MONTH", "SINGLE_DAY", "MULTI_DAY", "WEEK"):
            return {"compatible": True, "message": f"Daily records can satisfy {g_b} queries."}

        if g_a == "DAILY" and g_b == "HOURLY":
            return {"compatible": False, "message": "Daily dataset cannot provide hourly resolution without estimation."}

        if g_a == "BATCH_SLOT" and g_b == "HOURLY":
            return {"compatible": True, "message": "Batch slots match hourly production slots on timestamp + line."}

        if g_a == "TRANSACTION" and g_b in ("HOURLY", "SHIFT", "DAILY", "MONTH"):
            return {"compatible": True, "message": f"Individual transactions can be rolled up to {g_b} buckets."}

        return {
            "compatible": False,
            "message": f"Incompatible granularities: {g_a} cannot be joined to {g_b} without explicit calendar alignment.",
        }

    @staticmethod
    def _parse_iso_date(s: str) -> Optional[dt.date]:
        match = DATE_PATTERN.match(str(s).strip())
        if match:
            try:
                return dt.date.fromisoformat(match.group(0))
            except ValueError:
                return None
        return None

    @classmethod
    def _parse_range_string(cls, s: str) -> tuple[Optional[dt.date], Optional[dt.date]]:
        parts = re.split(r"\s+to\s+", s.strip(), flags=re.IGNORECASE)
        if len(parts) == 2:
            d1 = cls._parse_iso_date(parts[0])
            d2 = cls._parse_iso_date(parts[1])
            return d1, d2
        return None, None
