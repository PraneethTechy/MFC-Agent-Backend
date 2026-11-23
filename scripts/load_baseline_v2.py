import sys
import urllib.parse
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.config import settings
from app.db import engine, SessionLocal, text
from app.services.ingestion import ImportManager

def load_baseline():
    print("=" * 70)
    print("  LOADING D1-D4 BASELINE DATASETS INTO NEON V2")
    print("=" * 70)

    # 1. Endpoint Guard
    parsed = urllib.parse.urlparse(settings.sqlalchemy_database_url)
    assert parsed.hostname == "ep-billowing-leaf-bd3682lx-pooler.c-8.us-east-2.aws.neon.tech", "Wrong host!"
    assert "ep-muddy-resonance" not in settings.database_url, "Old host detected!"
    print(f"[*] Target Endpoint Host: {parsed.hostname}")

    # 2. Run ImportManager on raw data
    data_dir = str(BASE_DIR / "data" / "raw")
    print(f"[*] Raw Data Directory: {data_dir}")

    manager = ImportManager()
    results = manager.import_all_manufacturing_datasets(data_dir=data_dir, dry_run=False)

    print("\n[*] Import results summary:")
    for k, v in results.items():
        if isinstance(v, dict):
            status = v.get("status")
            staged = v.get("total_staged")
            promoted = v.get("promoted")
            print(f"    - {k}: status={status}, staged={staged}, promoted={promoted}")

    # 3. Verify counts in Neon database
    with engine.connect() as conn:
        cost_cnt = conn.execute(text("SELECT count(*) FROM line_cost_batches;")).scalar()
        prod_cnt = conn.execute(text("SELECT count(*) FROM hourly_production_logs;")).scalar()
        qual_cnt = conn.execute(text("SELECT count(*) FROM serialized_quality_inspections;")).scalar()
        bom_cnt = conn.execute(text("SELECT count(*) FROM bom_component_records;")).scalar()
        total_cost = conn.execute(text("SELECT SUM(total_direct_cost_inr) FROM line_cost_batches;")).scalar()

    print("\n" + "=" * 70)
    print("  NEON DATABASE VERIFICATION (D1-D4 BASELINE)")
    print("=" * 70)
    print(f"  line_cost_batches              : {cost_cnt:,} (expected 5,000)")
    print(f"  hourly_production_logs         : {prod_cnt:,} (expected 8,832)")
    print(f"  serialized_quality_inspections : {qual_cnt:,} (expected 16,000)")
    print(f"  bom_component_records          : {bom_cnt:,} (expected 48)")
    print(f"  Total baseline facts           : {cost_cnt + prod_cnt + qual_cnt + bom_cnt:,} (expected 29,880)")
    print(f"  Total direct cost INR          : {Decimal(str(total_cost)):,} (expected 14,024,712,024.3000)")

    assert cost_cnt == 5000, f"Expected 5000, got {cost_cnt}"
    assert prod_cnt == 8832, f"Expected 8832, got {prod_cnt}"
    assert qual_cnt == 16000, f"Expected 16000, got {qual_cnt}"
    assert bom_cnt == 48, f"Expected 48, got {bom_cnt}"
    assert Decimal(str(total_cost)) == Decimal("14024712024.3000"), f"Cost mismatch: {total_cost}"

    print("\n[+] D1-D4 BASELINE LOADED AND RECONCILED WITH ZERO DEFECTS!")
    return 0

if __name__ == "__main__":
    sys.exit(load_baseline())
