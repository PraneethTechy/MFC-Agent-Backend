import sys
import urllib.parse
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.config import settings
from app.db import engine, init_db, text

def run_init():
    print("=" * 70)
    print("  MANUFACTURING RCA V2 - DATABASE SCHEMA INITIALIZATION")
    print("=" * 70)

    # 1. Strict Endpoint Safety Guard
    parsed = urllib.parse.urlparse(settings.sqlalchemy_database_url)
    expected_host = "ep-billowing-leaf-bd3682lx-pooler.c-8.us-east-2.aws.neon.tech"
    
    print(f"[*] Target Endpoint Host: {parsed.hostname}")
    print(f"[*] Target Database: {parsed.path.lstrip('/')}")
    
    assert parsed.hostname == expected_host, f"CRITICAL ABORT: Host {parsed.hostname} does NOT match expected {expected_host}"
    assert "ep-muddy-resonance" not in settings.database_url, "CRITICAL ABORT: Old shared Neon host detected in connection string!"

    print("[+] Endpoint Safety Guard PASSED. Proceeding with schema creation...")

    # 2. Initialize Database Schema & Views
    success = init_db()
    if not success:
        print("[!] Error: init_db returned False.")
        return 1

    # 3. Verify created tables in public schema
    with engine.connect() as conn:
        tables = conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;"
        )).fetchall()
        views = conn.execute(text(
            "SELECT table_name FROM information_schema.views WHERE table_schema = 'public' ORDER BY table_name;"
        )).fetchall()

    print(f"\n[+] Schema initialized successfully!")
    print(f"[+] Total tables created in public: {len(tables)}")
    for t in tables:
        print(f"    - {t[0]}")
        
    print(f"\n[+] Total views created in public: {len(views)}")
    for v in views:
        print(f"    - {v[0]}")

    return 0

if __name__ == "__main__":
    sys.exit(run_init())
