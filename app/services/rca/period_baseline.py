"""
Manufacturing RCA - Dynamic Period & Comparison Baseline Resolver
Handles flexible time period detection, granularity alignment, and hybrid historical
comparison baseline resolution across:
1. Previous Month (convenient 1-click comparison)
2. All Available History (full eligible historical coverage up to investigation cutoff)
3. Selected Historical Months (multi-month combination with weighted calculations)
4. Custom Date Range (arbitrary historical date boundaries)

Strictly eliminates hardcoded date boundaries and excludes synthetic/staged records.
"""

from dataclasses import dataclass, field
import datetime as dt
import logging
import re
from typing import Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("manufacturing_cost_agent.rca.period_baseline")


@dataclass
class DynamicComparisonScope:
    """Resolved investigation temporal window and its comparable historical baseline."""
    investigation_period_label: str
    baseline_period_label: str
    current_start_date: dt.date
    current_end_date: dt.date
    baseline_start_date: dt.date
    baseline_end_date: dt.date
    granularity: str  # 'DAILY', 'WEEKLY', 'MONTHLY', 'CUSTOM'
    comparison_mode: str = "PREVIOUS_MONTH"  # 'PREVIOUS_MONTH', 'ALL_AVAILABLE', 'SELECTED_MONTHS', 'CUSTOM_RANGE'
    baseline_months: list[str] = field(default_factory=list)
    is_comparable: bool = True
    incomparability_reason: Optional[str] = None
    is_partial_period: bool = False
    partial_period_note: Optional[str] = None
    total_investigation_days: int = 30
    total_baseline_days: int = 30
    historical_periods_available: list[str] = field(default_factory=list)
    available_historical_months: list[dict[str, Any]] = field(default_factory=list)
    min_historical_date: Optional[str] = None
    max_historical_date: Optional[str] = None
    coverage_summary: Optional[str] = None
    is_unequal_duration: bool = False
    is_aggregate_history: bool = False
    comparison_note: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation_period_label": self.investigation_period_label,
            "baseline_period_label": self.baseline_period_label,
            "current_start_date": self.current_start_date.isoformat(),
            "current_end_date": self.current_end_date.isoformat(),
            "baseline_start_date": self.baseline_start_date.isoformat(),
            "baseline_end_date": self.baseline_end_date.isoformat(),
            "granularity": self.granularity,
            "comparison_mode": self.comparison_mode,
            "baseline_months": self.baseline_months,
            "is_comparable": self.is_comparable,
            "incomparability_reason": self.incomparability_reason,
            "is_partial_period": self.is_partial_period,
            "partial_period_note": self.partial_period_note,
            "total_investigation_days": self.total_investigation_days,
            "total_baseline_days": self.total_baseline_days,
            "historical_periods_available": self.historical_periods_available,
            "available_historical_months": self.available_historical_months,
            "min_historical_date": self.min_historical_date,
            "max_historical_date": self.max_historical_date,
            "coverage_summary": self.coverage_summary,
            "is_unequal_duration": self.is_unequal_duration,
            "is_aggregate_history": self.is_aggregate_history,
            "comparison_note": self.comparison_note,
        }


class DynamicBaselineResolver:
    """Resolves dynamic baseline comparison periods without hardcoded calendar assumptions."""

    @classmethod
    def resolve_scope(
        cls,
        db: Optional[Session] = None,
        uploaded_records: Optional[list[dict[str, Any]]] = None,
        current_period_str: Optional[str] = None,
        baseline_period_str: Optional[str] = None,
        baseline_mode: Optional[str] = None,
        baseline_months: Optional[list[str]] = None,
        baseline_start_date: Optional[str] = None,
        baseline_end_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> DynamicComparisonScope:
        """
        Dynamically derives the current investigation window and its historical baseline,
        supporting:
        - PREVIOUS_MONTH (standard 1-month baseline)
        - ALL_AVAILABLE (full eligible history up to investigation cutoff)
        - SELECTED_MONTHS (multi-month aggregated baseline)
        - CUSTOM_RANGE (user-specified date range)
        """
        # 1. Discover all committed non-synthetic historical months from Neon PostgreSQL
        db_month_records: list[dict[str, Any]] = []
        if db:
            try:
                res = db.execute(text(
                    "SELECT to_char(posting_ts, 'YYYY-MM') as ym, "
                    "MIN(posting_ts::date) as m_start, "
                    "MAX(posting_ts::date) as m_end, "
                    "COUNT(*) as record_count "
                    "FROM line_cost_batches "
                    "WHERE is_synthetic = false "
                    "GROUP BY ym ORDER BY ym ASC"
                )).mappings().fetchall()
                for r in res:
                    if r["ym"]:
                        db_month_records.append({
                            "id": r["ym"],
                            "label": dt.date.fromisoformat(f"{r['ym']}-01").strftime("%B %Y"),
                            "short_label": dt.date.fromisoformat(f"{r['ym']}-01").strftime("%b %Y"),
                            "start_date": str(r["m_start"]),
                            "end_date": str(r["m_end"]),
                            "record_count": int(r["record_count"]),
                        })
            except Exception as e:
                logger.warning("Could not query line_cost_batches for historical periods: %s", e)

        # 2. Extract date boundaries from uploaded records if provided
        dates_in_upload: list[dt.date] = []
        if uploaded_records:
            date_keys = [
                "posting_ts", "event_ts", "event_date", "consumption_ts",
                "invoice_date", "inspection_ts", "date", "created_at",
                "cost_date", "consumption_date", "inspection_date",
                "record_date", "attendance_date", "receipt_date",
                "transaction_date", "order_date", "run_date"
            ]
            for r in uploaded_records[:2000]:  # sample up to 2000 records for fast resolution
                for k in date_keys:
                    val = r.get(k)
                    if val:
                        s_val = str(val)[:10]
                        try:
                            d = dt.date.fromisoformat(s_val)
                            dates_in_upload.append(d)
                            break
                        except ValueError:
                            pass

        # 3. Determine current period boundaries
        curr_start: Optional[dt.date] = None
        curr_end: Optional[dt.date] = None
        granularity = "MONTHLY"

        if start_date and end_date:
            try:
                curr_start = dt.date.fromisoformat(start_date[:10])
                curr_end = dt.date.fromisoformat(end_date[:10])
                days_diff = (curr_end - curr_start).days + 1
                if days_diff == 1:
                    granularity = "DAILY"
                elif 5 <= days_diff <= 8:
                    granularity = "WEEKLY"
                elif 28 <= days_diff <= 31 and curr_start.day == 1:
                    granularity = "MONTHLY"
                else:
                    granularity = "CUSTOM"
            except ValueError:
                pass

        if not curr_start and current_period_str:
            norm_period = current_period_str.strip()
            if re.match(r"^\d{4}-\d{2}$", norm_period):
                y, m = int(norm_period[:4]), int(norm_period[5:7])
                curr_start = dt.date(y, m, 1)
                next_m = dt.date(y + 1, 1, 1) if m == 12 else dt.date(y, m + 1, 1)
                curr_end = next_m - dt.timedelta(days=1)
                granularity = "MONTHLY"
            elif re.match(r"^\d{4}-W\d{1,2}$", norm_period, re.I):
                try:
                    curr_start = dt.date.fromisocalendar(int(norm_period[:4]), int(norm_period[6:]), 1)
                    curr_end = curr_start + dt.timedelta(days=6)
                    granularity = "WEEKLY"
                except ValueError:
                    pass

        if not curr_start and dates_in_upload:
            curr_start = min(dates_in_upload)
            curr_end = max(dates_in_upload)
            days_diff = (curr_end - curr_start).days + 1
            if days_diff == 1:
                granularity = "DAILY"
            elif 5 <= days_diff <= 8:
                granularity = "WEEKLY"
            elif 28 <= days_diff <= 31:
                granularity = "MONTHLY"
            else:
                granularity = "CUSTOM"

        # Fallback if no dates detected at all
        if not curr_start or not curr_end:
            curr_start = dt.date(2026, 11, 1)
            curr_end = dt.date(2026, 11, 30)
            granularity = "MONTHLY"

        # 4. Filter eligible historical months: MUST BE STRICTLY BEFORE current investigation start date
        curr_ym_str = curr_start.strftime("%Y-%m")
        eligible_historical_months = [
            m for m in db_month_records if m["id"] < curr_ym_str
        ]

        available_periods = [m["id"] for m in eligible_historical_months]
        min_hist_date_str = eligible_historical_months[0]["start_date"] if eligible_historical_months else None
        max_hist_date_str = eligible_historical_months[-1]["end_date"] if eligible_historical_months else None

        min_hist_date = dt.date.fromisoformat(min_hist_date_str) if min_hist_date_str else dt.date(2026, 8, 1)
        max_hist_date = dt.date.fromisoformat(max_hist_date_str) if max_hist_date_str else dt.date(2026, 10, 31)

        # 5. Resolve Hybrid Comparison Baseline
        resolved_mode = "PREVIOUS_MONTH"
        base_start: Optional[dt.date] = None
        base_end: Optional[dt.date] = None
        resolved_months: list[str] = []
        base_label = ""
        coverage_summary = ""

        # Normalize input baseline string if passed
        norm_b_str = (baseline_period_str or "").strip()

        # Check for PREVIOUS_EQUIVALENT_PERIOD mode
        if (
            baseline_mode in ("PREVIOUS_EQUIVALENT_PERIOD", "PREVIOUS_PERIOD", "EQUIVALENT_PERIOD")
            or norm_b_str.upper() in ("PREVIOUS_EQUIVALENT_PERIOD", "PREVIOUS EQUIVALENT PERIOD", "PREVIOUS PERIOD", "EQUIVALENT PERIOD")
            or "EQUIVALENT" in norm_b_str.upper()
        ):
            resolved_mode = "PREVIOUS_EQUIVALENT_PERIOD"
            inv_duration_days = (curr_end - curr_start).days + 1
            base_end = curr_start - dt.timedelta(days=1)
            base_start = base_end - dt.timedelta(days=inv_duration_days - 1)
            if base_start < min_hist_date:
                base_start = min_hist_date
            base_label = f"Prev Equivalent ({base_start.strftime('%b %d')} – {base_end.strftime('%b %d, %Y')})"
            coverage_summary = f"Equivalent duration ({inv_duration_days} days immediately preceding investigation)"
            m_cursor = dt.date(base_start.year, base_start.month, 1)
            end_m = dt.date(base_end.year, base_end.month, 1)
            resolved_months = []
            while m_cursor <= end_m:
                ym_str = m_cursor.strftime("%Y-%m")
                if ym_str in available_periods:
                    resolved_months.append(ym_str)
                if m_cursor.month == 12:
                    m_cursor = dt.date(m_cursor.year + 1, 1, 1)
                else:
                    m_cursor = dt.date(m_cursor.year, m_cursor.month + 1, 1)

        # Check for ALL_AVAILABLE mode
        elif (
            baseline_mode == "ALL_AVAILABLE"
            or norm_b_str.upper() in ("ALL_AVAILABLE", "ALL", "ALL_HISTORY", "ALL AVAILABLE HISTORY")
            or "ALL AVAILABLE" in norm_b_str.upper()
        ):
            resolved_mode = "ALL_AVAILABLE"
            base_start = min_hist_date
            base_end = max_hist_date
            resolved_months = [m["id"] for m in eligible_historical_months]
            start_lbl = base_start.strftime("%b")
            end_lbl = base_end.strftime("%b %Y")
            base_label = f"All available history: {start_lbl}–{end_lbl}"
            coverage_summary = f"{len(resolved_months)} historical month(s) aggregated ({base_start.strftime('%b %d')} – {base_end.strftime('%b %d, %Y')})"

        # Check for CUSTOM_RANGE mode
        elif (
            baseline_mode == "CUSTOM_RANGE"
            or norm_b_str.startswith("CUSTOM:")
            or (baseline_start_date and baseline_end_date)
        ):
            resolved_mode = "CUSTOM_RANGE"
            c_start_str = baseline_start_date
            c_end_str = baseline_end_date

            if norm_b_str.startswith("CUSTOM:"):
                parts = norm_b_str.split(":")
                if len(parts) >= 3:
                    c_start_str = parts[1]
                    c_end_str = parts[2]

            try:
                base_start = dt.date.fromisoformat(str(c_start_str)[:10])
                base_end = dt.date.fromisoformat(str(c_end_str)[:10])
                if base_start > base_end:
                    base_start, base_end = base_end, base_start
                # Ensure end date does not cross into investigation period
                if base_end >= curr_start:
                    base_end = curr_start - dt.timedelta(days=1)
                base_label = f"{base_start.strftime('%b %d')} – {base_end.strftime('%b %d, %Y')}"
                c_days = (base_end - base_start).days + 1
                coverage_summary = f"Custom date range: {c_days} days ({base_label})"
            except Exception as ex:
                logger.warning("Invalid custom range (%s to %s): %s", c_start_str, c_end_str, ex)
                base_start = None
                base_end = None

        # Check for SELECTED_MONTHS (multi-month) mode
        elif (
            baseline_mode == "SELECTED_MONTHS"
            or (baseline_months and len(baseline_months) > 0)
            or ("," in norm_b_str and not norm_b_str.startswith("CUSTOM"))
            or ("+" in norm_b_str)
        ):
            resolved_mode = "SELECTED_MONTHS"
            m_candidates: list[str] = []
            if baseline_months:
                if isinstance(baseline_months, str):
                    m_candidates = [m.strip() for m in baseline_months.split(",") if m.strip()]
                else:
                    m_candidates = [str(m).strip() for m in baseline_months if str(m).strip()]
            elif "," in norm_b_str:
                m_candidates = [m.strip() for m in norm_b_str.split(",") if m.strip()]
            elif "+" in norm_b_str:
                # E.g. "Sep 2026 + Oct 2026"
                m_matches = re.findall(r"\b(20\d\d[-/]\d{2})\b", norm_b_str)
                if not m_matches:
                    for part in norm_b_str.split("+"):
                        p_clean = part.strip().lower()
                        for m_info in db_month_records:
                            if m_info["short_label"].lower() in p_clean or m_info["label"].lower() in p_clean:
                                m_matches.append(m_info["id"])
                m_candidates = m_matches

            # Filter candidates to only valid eligible historical months
            valid_m = [m for m in m_candidates if m in available_periods]
            if not valid_m and m_candidates:
                # Attempt regex match on candidates
                for c in m_candidates:
                    match = re.match(r"^(\d{4})[-/](\d{1,2})$", c)
                    if match:
                        formatted = f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"
                        if formatted in available_periods:
                            valid_m.append(formatted)

            valid_m = sorted(list(set(valid_m)))
            if valid_m:
                resolved_months = valid_m
                # Find start of earliest month and end of latest month
                earliest_ym = valid_m[0]
                latest_ym = valid_m[-1]
                e_y, e_m = int(earliest_ym[:4]), int(earliest_ym[5:7])
                l_y, l_m = int(latest_ym[:4]), int(latest_ym[5:7])

                base_start = dt.date(e_y, e_m, 1)
                l_next = dt.date(l_y + 1, 1, 1) if l_m == 12 else dt.date(l_y, l_m + 1, 1)
                base_end = l_next - dt.timedelta(days=1)

                # Build concise display label (e.g. "Sep 2026 + Oct 2026")
                labels = [
                    dt.date(int(ym[:4]), int(ym[5:7]), 1).strftime("%b %Y")
                    for ym in valid_m
                ]
                base_label = " + ".join(labels)
                coverage_summary = f"{len(valid_m)} selected month(s) combined ({base_label})"
            else:
                base_start = None

        # Fallback to single month or PREVIOUS_MONTH
        if not base_start:
            # Check if norm_b_str is a single valid month YYYY-MM
            m_match = re.match(r"^(\d{4})[-/](\d{1,2})$", norm_b_str)
            if m_match:
                y, m = int(m_match.group(1)), int(m_match.group(2))
                cand_ym = f"{y:04d}-{m:02d}"
                if cand_ym in available_periods:
                    base_start = dt.date(y, m, 1)
                    next_m = dt.date(y + 1, 1, 1) if m == 12 else dt.date(y, m + 1, 1)
                    base_end = next_m - dt.timedelta(days=1)
                    base_label = base_start.strftime("%b %Y")
                    resolved_mode = "PREVIOUS_MONTH"
                    resolved_months = [cand_ym]

        if not base_start:
            # Immediate prior month to curr_start
            resolved_mode = "PREVIOUS_MONTH"
            if curr_start.month == 1:
                base_start = dt.date(curr_start.year - 1, 12, 1)
                base_end = dt.date(curr_start.year - 1, 12, 31)
            else:
                prev_m = curr_start.month - 1
                base_start = dt.date(curr_start.year, prev_m, 1)
                next_base_m = dt.date(curr_start.year, curr_start.month, 1)
                base_end = next_base_m - dt.timedelta(days=1)
            base_label = base_start.strftime("%b %Y")
            resolved_months = [base_start.strftime("%Y-%m")]
            coverage_summary = f"Immediate prior complete calendar month ({base_label})"

        if not base_label:
            base_label = cls._format_period_label(base_start, base_end, granularity)

        # 6. Format labels and check comparability
        curr_label = cls._format_period_label(curr_start, curr_end, granularity)

        inv_days = (curr_end - curr_start).days + 1
        base_days = (base_end - base_start).days + 1

        is_unequal = (abs(inv_days - base_days) > 3) and resolved_mode not in ("MONTHLY", "PREVIOUS_EQUIVALENT_PERIOD")
        is_agg_hist = (resolved_mode == "ALL_AVAILABLE")

        is_comparable = True
        incomparability_reason = None
        comparison_note = None

        if resolved_mode == "ALL_AVAILABLE":
            is_comparable = True
            is_unequal = True
            comparison_note = f"Aggregate Historical Reference ({base_days} days, Aug 01 – Oct 31, 2026). Normalized run-rate comparison applied."
            coverage_summary = f"Full available historical reference ({base_days} days, {len(resolved_months)} months)"
        elif is_unequal:
            is_comparable = False
            incomparability_reason = (
                f"Investigation duration ({inv_days} days) differs significantly from baseline "
                f"duration ({base_days} days). Aggregations require normalized run-rate scaling."
            )
            comparison_note = f"Normalized run-rate comparison ({base_days} baseline days vs {inv_days} investigation days)."
        elif resolved_mode == "PREVIOUS_EQUIVALENT_PERIOD":
            is_comparable = True
            comparison_note = f"Exact equivalent duration ({inv_days} days immediately preceding investigation)."
        elif resolved_mode in ("ALL_AVAILABLE", "SELECTED_MONTHS") and len(resolved_months) > 1:
            coverage_summary = f"{len(resolved_months)} historical month(s) aggregated ({base_days} days total)"

        is_partial = False
        partial_note = None
        if granularity == "MONTHLY" and inv_days < 28:
            is_partial = True
            partial_note = f"Partial monthly period detected ({inv_days} days of data)."

        return DynamicComparisonScope(
            investigation_period_label=curr_label,
            baseline_period_label=base_label,
            current_start_date=curr_start,
            current_end_date=curr_end,
            baseline_start_date=base_start,
            baseline_end_date=base_end,
            granularity=granularity,
            comparison_mode=resolved_mode,
            baseline_months=resolved_months,
            is_comparable=is_comparable,
            incomparability_reason=incomparability_reason,
            is_partial_period=is_partial,
            partial_period_note=partial_note,
            total_investigation_days=inv_days,
            total_baseline_days=base_days,
            historical_periods_available=available_periods,
            available_historical_months=eligible_historical_months,
            min_historical_date=min_hist_date_str,
            max_historical_date=max_hist_date_str,
            coverage_summary=coverage_summary,
            is_unequal_duration=is_unequal,
            is_aggregate_history=is_agg_hist,
            comparison_note=comparison_note,
        )

    @staticmethod
    def _format_period_label(start: dt.date, end: dt.date, granularity: str) -> str:
        """Formats human-readable period label matching enterprise accounting conventions."""
        if granularity == "MONTHLY" and start.day == 1 and (end.day >= 28):
            return start.strftime("%b %Y")  # e.g. "Oct 2026", "Nov 2026"
        elif granularity == "WEEKLY":
            iso_yr, iso_wk, _ = start.isocalendar()
            return f"W{iso_wk:02d} {iso_yr} ({start.strftime('%b %d')} - {end.strftime('%b %d')})"
        elif granularity == "DAILY":
            return start.strftime("%b %d, %Y")
        else:
            return f"{start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}"
