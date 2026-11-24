"""
Manufacturing Cost Agent - Streaming CSV Reader
Provides robust streaming parsing with UTF-8 BOM stripping, whitespace cleanup,
and Decimal/DateTime type coercion.
"""

import csv
import datetime as dt
from decimal import Decimal, InvalidOperation
import io
import os
from typing import Any, Generator, Iterator


class CsvReader:
    """Streams and cleans manufacturing CSV records without large memory spikes."""

    @staticmethod
    def stream_csv(file_path: str, chunk_size: int = 2500) -> Generator[list[dict[str, Any]], None, None]:
        """
        Streams a CSV file in chunks of dictionaries with cleaned keys and values.
        Strips UTF-8 BOM ('\\ufeff') automatically.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return

            cleaned_fieldnames = [k.strip() for k in reader.fieldnames if k]
            
            chunk: list[dict[str, Any]] = []
            row_num = 1
            for raw_row in reader:
                row_num += 1
                cleaned_row: dict[str, Any] = {"_source_row_number": row_num}
                for k, v in raw_row.items():
                    if k is not None:
                        clean_key = k.strip()
                        clean_val = v.strip() if isinstance(v, str) else v
                        cleaned_row[clean_key] = clean_val
                chunk.append(cleaned_row)

                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []

            if chunk:
                yield chunk

    @staticmethod
    def parse_decimal(val: Any, default: Decimal = Decimal("0.0")) -> Decimal:
        """Safe Decimal parser."""
        if val is None or val == "":
            return default
        try:
            return Decimal(str(val))
        except (InvalidOperation, TypeError, ValueError):
            return default

    @staticmethod
    def parse_datetime(val: Any) -> dt.datetime | None:
        """Parses ISO and common timestamp strings into UTC timezone-aware datetimes."""
        if not val:
            return None
        val_str = str(val).strip()
        if not val_str or val_str.lower() in ("none", "null", "n/a", "na", "-"):
            return None
        try:
            # Handle ISO string like '2026-08-01T00:00:00' or with timezone
            d = dt.datetime.fromisoformat(val_str)
            if d.tzinfo is None:
                # Local manufacturing timestamp normalized to UTC
                d = d.replace(tzinfo=dt.timezone.utc)
            return d
        except ValueError:
            pass

        # Try common manufacturing timestamp formats
        common_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%d-%m-%Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ]
        for fmt in common_formats:
            try:
                parsed = dt.datetime.strptime(val_str, fmt)
                return parsed.replace(tzinfo=dt.timezone.utc)
            except ValueError:
                continue

        return None

    @staticmethod
    def parse_date(val: Any) -> dt.date | None:
        """Parses date string ('YYYY-MM-DD')."""
        if not val:
            return None
        val_str = str(val).strip()
        if not val_str or val_str.lower() in ("none", "null", "n/a", "na", "-"):
            return None
        try:
            if "T" in val_str:
                return dt.datetime.fromisoformat(val_str).date()
            return dt.date.fromisoformat(val_str)
        except ValueError:
            pass

        for fmt in ("%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return dt.datetime.strptime(val_str, fmt).date()
            except ValueError:
                continue

        return None

    @classmethod
    def combine_date_and_time(cls, date_val: Any, time_val: Any) -> dt.datetime | None:
        """
        Combines separate date and time values into a single UTC-aware timestamp.
        Only succeeds when both date and time represent genuine, parseable values.
        Preserves original timestamp and timezone semantics.
        """
        if not date_val or not time_val:
            return None
        d_str = str(date_val).strip()
        t_str = str(time_val).strip()
        if not d_str or not t_str or d_str.lower() in ("none", "null", "n/a") or t_str.lower() in ("none", "null", "n/a"):
            return None

        # Verify date part is valid
        parsed_d = cls.parse_date(d_str)
        if not parsed_d:
            return None

        # Attempt parsing combined ISO string
        combined = f"{parsed_d.isoformat()} {t_str}"
        return cls.parse_datetime(combined)

    @classmethod
    def resolve_inspection_timestamp(
        cls,
        row: dict[str, Any],
        column_mapping: dict[str, str] | None = None,
    ) -> dt.datetime | None:
        """
        Extracts genuine inspection timestamp from source row data.
        Never fabricates defaults or current system time.
        Supports:
        1. Explicit column mapping (e.g. mapping['inspection_ts'])
        2. Direct timestamp candidates (inspection_ts, inspection_timestamp, timestamp, datetime, event_ts, event_timestamp, audit_ts)
        3. Separate date and time columns (inspection_date + inspection_time, date + time, event_date + event_time)
        4. Date-only candidates (inspection_date, date, event_date, audit_date) normalized to midnight UTC
        """
        if not row:
            return None

        mapping = column_mapping or {}

        # 1. Check custom column mapping
        mapped_ts_col = mapping.get("inspection_ts")
        mapped_date_col = mapping.get("inspection_date") or (mapped_ts_col if mapped_ts_col and "date" in mapped_ts_col.lower() else None)
        mapped_time_col = mapping.get("inspection_time")

        val_ts = row.get(mapped_ts_col) if mapped_ts_col and mapped_ts_col in row else None
        val_date = row.get(mapped_date_col) if mapped_date_col and mapped_date_col in row else None
        val_time = row.get(mapped_time_col) if mapped_time_col and mapped_time_col in row else None

        # 2. Search direct timestamp aliases
        if not val_ts:
            for k in ("inspection_ts", "inspection_timestamp", "timestamp", "datetime", "date_time", "event_ts", "event_timestamp", "audit_ts"):
                if row.get(k):
                    val_ts = row.get(k)
                    break

        # 3. Search separate date and time aliases
        if not val_date:
            for k in ("inspection_date", "date", "event_date", "audit_date"):
                if row.get(k):
                    val_date = row.get(k)
                    break

        if not val_time:
            for k in ("inspection_time", "time", "event_time", "shift_time"):
                if row.get(k):
                    val_time = row.get(k)
                    break

        # 4. If separate date and time both exist, combine them
        if val_date and val_time:
            combined = cls.combine_date_and_time(val_date, val_time)
            if combined:
                return combined

        # 5. If a direct timestamp was provided, parse it
        if val_ts:
            parsed_ts = cls.parse_datetime(val_ts)
            if parsed_ts:
                return parsed_ts

        # 6. If only a date was provided, parse as date and convert to midnight UTC
        if val_date:
            parsed_dt = cls.parse_datetime(val_date)
            if parsed_dt:
                return parsed_dt
            parsed_d = cls.parse_date(val_date)
            if parsed_d:
                return dt.datetime(parsed_d.year, parsed_d.month, parsed_d.day, 0, 0, 0, tzinfo=dt.timezone.utc)

        return None

