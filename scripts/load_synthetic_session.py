import sys
import urllib.parse
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.config import settings
from app.db import engine, SessionLocal, text
from app.services.ingestion.promotion_service import PromotionService

def load_synthetic_sessions():
    print("=" * 70)
    print("  LOADING SYNTHETIC SESSIONS (NOV 2026 BENCHMARK) INTO NEON V2")
    print("=" * 70)

    # 1. Endpoint Guard
    parsed = urllib.parse.urlparse(settings.sqlalchemy_database_url)
    assert parsed.hostname == "ep-billowing-leaf-bd3682lx-pooler.c-8.us-east-2.aws.neon.tech", "Wrong host!"
    assert "ep-muddy-resonance" not in settings.database_url, "Old host detected!"
    print(f"[*] Target Endpoint Host: {parsed.hostname}")

    session = SessionLocal()
    try:
        res = PromotionService.promote_session(session, "session_nov_2026_test")
        print("\n[+] Promotion results:")
        for k, v in res.items():
            print(f"    - {k}: {v}")
    finally:
        session.close()

    # 2. Check counts
    with engine.connect() as conn:
        purch_cnt = conn.execute(text("SELECT count(*) FROM material_purchase_records;")).scalar()
        cons_cnt = conn.execute(text("SELECT count(*) FROM material_consumption_records;")).scalar()
        rework_cnt = conn.execute(text("SELECT count(*) FROM quality_rework_event_records;")).scalar()
        total_costs = conn.execute(text("SELECT count(*) FROM line_cost_batches;")).scalar()
        real_costs = conn.execute(text("SELECT count(*) FROM line_cost_batches WHERE is_synthetic = false;")).scalar()
        synth_costs = conn.execute(text("SELECT count(*) FROM line_cost_batches WHERE is_synthetic = true;")).scalar()

    print("\n" + "=" * 70)
    print("  DATABASE STATUS POST-PROMOTION")
    print("=" * 70)
    print(f"  material_purchase_records      : {purch_cnt:,} rows")
    print(f"  material_consumption_records   : {cons_cnt:,} rows")
    print(f"  quality_rework_event_records   : {rework_cnt:,} rows")
    print(f"  line_cost_batches total        : {total_costs:,} (Real: {real_costs:,}, Synth: {synth_costs:,})")

    return 0

if __name__ == "__main__":
    sys.exit(load_synthetic_sessions())
