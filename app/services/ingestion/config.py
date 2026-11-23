"""
Manufacturing Cost Agent - Ingestion Configuration & Constants
Defines expected checksums, dataset schemas, file paths, and financial invariants.
"""

from decimal import Decimal
from typing import Any

# Approved SHA-256 Checksums for the Four Source Datasets
EXPECTED_CHECKSUMS: dict[str, str] = {
    "fact_manufacturing_cost.csv": "444212efe15a93952bda90889e51b3d0e3fffe8a56ede5c71735de9665671cbc",
    "fact_hourly_production.csv": "cdd5e0b3444132886b688fe51416db8111bc24e33bbab1decee2810b6b31b370",
    "fact_quality_inspection.csv": "cf137596cce7b76eb4aa29916349094172c6bf14c6e1b34eaf1720a1f3ae22d1",
    "fact_bom_component.csv": "aa7849e2b5c466d07ee12682a58ffcf79324a0b9dc67d9d2183c01313c26847d",
}

# Expected Row Counts
EXPECTED_ROW_COUNTS: dict[str, int] = {
    "fact_manufacturing_cost.csv": 5000,
    "fact_hourly_production.csv": 8832,
    "fact_quality_inspection.csv": 16000,
    "fact_bom_component.csv": 48,
}

# Expected Financial Totals (Verified across all 5,000 cost records)
EXPECTED_COST_TOTALS: dict[str, Decimal] = {
    "material_cost_inr": Decimal("13359506779.21"),
    "labour_cost_inr": Decimal("370630471.87"),
    "machine_cost_inr": Decimal("211672766.11"),
    "energy_cost_inr": Decimal("65075725.60"),
    "scrap_rework_cost_inr": Decimal("17826281.51"),
    "total_direct_actual_cost": Decimal("14024712024.30"),
}

# Production Quantity Metrics
EXPECTED_PRODUCTION_METRICS = {
    "total_production_records": 8832,
    "matched_cost_records": 5000,
    "unmatched_production_records": 3832,
    "costed_produced_qty": Decimal("1369863.0"),
    "costed_good_qty": Decimal("1344258.0"),
    "total_factory_produced_qty": Decimal("2424184.0"),
    "total_factory_good_qty": Decimal("2378960.0"),
    "volume_coverage_pct": Decimal("56.508"),
}

# Quality Metrics
EXPECTED_QUALITY_METRICS = {
    "total_inspections": 16000,
    "pass_count": 15439,
    "fail_count": 561,
    "rework_count": 192,
    "hold_count": 185,
    "scrap_count": 184,
    "distinct_serials": 15999,
}

# File Upload and Processing Parameters
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
CHUNK_SIZE_ROWS = 2500

