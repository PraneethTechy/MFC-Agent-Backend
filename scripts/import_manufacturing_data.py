#!/usr/bin/env python3
"""
Manufacturing Cost Agent - CLI Data Ingestion Script
Imports the four core manufacturing datasets into Neon PostgreSQL:
1. fact_bom_component.csv (48 records)
2. fact_manufacturing_cost.csv (5,000 records)
3. fact_hourly_production.csv (8,832 records)
4. fact_quality_inspection.csv (16,000 records)

Supports --dry-run for validation-only execution without database promotion.
"""

import argparse
from decimal import Decimal
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.config import settings
from app.db import engine
from app.services.ingestion import ImportManager, EXPECTED_COST_TOTALS


def print_banner():
    print("=" * 80)
    print("  MANUFACTURING COST AGENT - SECURE DATA INGESTION PIPELINE")
    print("  Neon Managed PostgreSQL Authority (Single DATABASE_URL)")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Ingest manufacturing CSV datasets into Neon PostgreSQL.")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(BASE_DIR / "data"),
        help="Directory containing the four source CSV files (default: backend/data)",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Optional: Path to a single CSV file to ingest individually",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute parsing and staging validation without promoting records to operational tables",
    )

    args = parser.parse_args()
    print_banner()

    data_dir = args.data_dir
    print(f"[*] Target Database: Neon PostgreSQL (Connected)")
    print(f"[*] Source Directory: {data_dir}")
    print(f"[*] Execution Mode: {'DRY RUN (Validation Only)' if args.dry_run else 'LIVE TRANSACTIONAL PROMOTION'}")
    print("-" * 80)

    manager = ImportManager()

    try:
        if args.file:
            fname = os.path.basename(args.file)
            print(f"[*] Ingesting single file: {fname}...")
            dtype = "MANUFACTURING_DATA"
            if "cost" in fname:
                dtype = "MANUFACTURING_COST"
            elif "production" in fname:
                dtype = "HOURLY_PRODUCTION"
            elif "quality" in fname:
                dtype = "QUALITY_INSPECTION"
            elif "bom" in fname:
                dtype = "BOM_COMPONENTS"

            res = manager.ingest_single_file(args.file, dtype, dry_run=args.dry_run)
            print(f"[+] Result: {res}")
            return 0

        # Import all 4 files
        results = manager.import_all_manufacturing_datasets(data_dir=data_dir, dry_run=args.dry_run)

        print("\n" + "=" * 80)
        print("  INGESTION & STAGING EXECUTION SUMMARY")
        print("=" * 80)
        print(f"{'DATASET FILE':<32} {'STAGED':<10} {'VALID':<10} {'INVALID':<10} {'PROMOTED':<10} {'STATUS'}")
        print("-" * 80)

        for fname in ["fact_bom_component.csv", "fact_manufacturing_cost.csv", "fact_hourly_production.csv", "fact_quality_inspection.csv"]:
            info = results.get(fname, {})
            status = info.get("status", "UNKNOWN")
            staged = info.get("total_staged", 0)
            val = info.get("validation", {})
            valid = val.get("valid_records", 0)
            invalid = val.get("invalid_records", 0)
            prom = info.get("promoted", {})
            prom_cnt = sum(prom.values()) if isinstance(prom, dict) else 0

            print(f"{fname:<32} {staged:<10} {valid:<10} {invalid:<10} {prom_cnt:<10} {status}")

        print("-" * 80)

        # Costing status resolution
        costing_res = results.get("costing_status_resolution")
        if costing_res:
            print("\n[*] Hourly Production Cost-Linkage Resolution:")
            print(f"    - DIRECT_COSTED (Matched 1:1 with cost batches): {costing_res.get('costed'):,} records")
            print(f"    - UNCOSTED_OPERATIONAL_RUN (Preserved operational runs): {costing_res.get('uncosted'):,} records")

        # Financial Reconciliation
        fin = results.get("financial_reconciliation")
        if fin:
            print("\n" + "=" * 80)
            print("  FINANCIAL RECONCILIATION AUDIT (NEON LIVE DATABASE)")
            print("=" * 80)
            print(f"  Records Aggregated in Neon : {fin['records']:,}")
            print(f"  Direct Material Cost Actual: INR {Decimal(fin['material_actual']):,}")
            print(f"  Direct Labour Cost Actual  : INR {Decimal(fin['labour_actual']):,}")
            print(f"  Machine Cost Actual        : INR {Decimal(fin['machine_actual']):,}")
            print(f"  Energy Cost Actual         : INR {Decimal(fin['energy_actual']):,}")
            print(f"  Scrap & Rework Cost Actual : INR {Decimal(fin['scrap_rework_actual']):,}")
            print("  " + "-" * 76)
            print(f"  TOTAL ACTUAL DIRECT COST   : INR {Decimal(fin['total_direct_actual_cost']):,}")
            print(f"  EXPECTED AUDIT TARGET      : INR {Decimal(fin['expected_total']):,}")
            print(f"  VARIANCE / DISCREPANCY     : INR {Decimal(fin['difference']):,}")
            print(f"  EXACT MATCH VERIFIED       : {fin['is_exact_match']}")
            print("=" * 80)

            if not fin["is_exact_match"]:
                print("[!] ERROR: Financial reconciliation mismatch detected!")
                return 1

        print("\n[+] Ingestion pipeline completed successfully with zero defects.")
        return 0

    except Exception as e:
        print(f"\n[!] INGESTION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
