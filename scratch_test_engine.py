import sys
import os

sys.path.insert(0, os.path.abspath("backend"))

from app.db import SessionLocal
from app.models.master_data import Material

db = SessionLocal()
try:
    mats = db.query(Material).all()
    print(f"Materials count: {len(mats)}")
    for m in mats:
        print(f" - {m.code}: {m.name} | Std Price: ₹{m.standard_unit_price}")
finally:
    db.close()
