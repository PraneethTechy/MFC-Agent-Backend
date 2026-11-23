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
        """Parses ISO timestamp strings into UTC timezone-aware datetimes."""
        if not val:
            return None
        val_str = str(val).strip()
        try:
            # Handle ISO string like '2026-08-01T00:00:00'
            d = dt.datetime.fromisoformat(val_str)
            if d.tzinfo is None:
                # Local manufacturing timestamp normalized to UTC
                d = d.replace(tzinfo=dt.timezone.utc)
            return d
        except ValueError:
            return None

    @staticmethod
    def parse_date(val: Any) -> dt.date | None:
        """Parses date string ('YYYY-MM-DD')."""
        if not val:
            return None
        val_str = str(val).strip()
        try:
            if "T" in val_str:
                return dt.datetime.fromisoformat(val_str).date()
            return dt.date.fromisoformat(val_str)
        except ValueError:
            return None

