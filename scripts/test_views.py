import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.db import engine, text
from app.db_views import V_COST_FACTS_SQL, V_VARIANCE_FACTS_SQL

with engine.connect() as conn:
    try:
        conn.execute(text(V_COST_FACTS_SQL))
        conn.commit()
        print("V_COST_FACTS_SQL succeeded")
    except Exception as e:
        print("V_COST_FACTS_SQL failed:", e)

    try:
        conn.execute(text(V_VARIANCE_FACTS_SQL))
        conn.commit()
        print("V_VARIANCE_FACTS_SQL succeeded")
    except Exception as e:
        print("V_VARIANCE_FACTS_SQL failed:", e)
