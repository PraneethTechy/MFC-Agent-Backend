import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from fastapi.testclient import TestClient
from app.main import app

def test_screenshot_scenario():
    print("=" * 70)
    print("  TESTING EXACT USER SCREENSHOT INVESTIGATION SCENARIO")
    print("=" * 70)

    client = TestClient(app)

    payload = {
        "message": "Why did the manufacturing cost per good unit increase for Smartphone Model X in October 2026?",
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
        "product_code": "SPH-PRO-256",
        "plant_code": "IN-TN-01",
        "line_code": "FAL-L1",
        "cost_category": "All Categories",
        "observed_issue": "Cost per good unit higher than expected",
        "expected_value": 14500.0,
        "actual_value": 15380.0,
        "known_changes": ["Supplier Change", "Process Change"],
        "additional_context": "New display supplier has been onboarded from October. Also, minor rework increase observed in assembly.",
        "selected_dataset_ids": [
            "d1_hourly_production",
            "d2_manufacturing_cost",
            "d3_bom_components",
            "d4_quality_inspection",
            "d5_production_traceability",
            "d6_material_consumption",
            "d7_inventory_transactions",
            "d8_procurement_supplier",
            "d9_equipment_energy",
            "d10_workforce_attendance_allocation",
        ],
        "dataset_stores": {
            "d1_hourly_production": "GLOBAL_STORE",
            "d2_manufacturing_cost": "GLOBAL_STORE",
            "d3_bom_components": "GLOBAL_STORE",
            "d4_quality_inspection": "GLOBAL_STORE",
            "d5_production_traceability": "GLOBAL_STORE",
            "d6_material_consumption": "GLOBAL_STORE",
            "d7_inventory_transactions": "GLOBAL_STORE",
            "d8_procurement_supplier": "GLOBAL_STORE",
            "d9_equipment_energy": "GLOBAL_STORE",
            "d10_workforce_attendance_allocation": "GLOBAL_STORE",
        },
        "investigation_mode": "customized"
    }

    print("[*] Submitting unified investigation request to /api/investigation/run-unified...")
    res = client.post("/api/investigation/run-unified", json=payload)
    print(f"[*] Response Status Code: {res.status_code}")

    if res.status_code != 200:
        print("[!] Response Error:", res.text)
        return 1

    data = res.json()
    print("\n[+] Response received successfully!")
    print(f"[*] Conversation ID: {data.get('conversation_id')}")
    print(f"[*] Tool Traces count: {len(data.get('tool_traces', []))}")
    for idx, trace in enumerate(data.get("tool_traces", [])):
        print(f"    Trace {idx+1}: {trace.get('tool')}")

    print("\n[+] AI Agent Message Preview (First 400 chars):")
    print(data.get("message", "")[:400] + "...")

    return 0

if __name__ == "__main__":
    sys.exit(test_screenshot_scenario())
