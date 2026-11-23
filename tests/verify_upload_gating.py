import requests
import sys

BASE_URL = "http://localhost:8000/api"

def test_invalid_session_returns_404():
    res = requests.get(f"{BASE_URL}/investigation/session/non-existent-session-xyz")
    assert res.status_code == 404, f"Expected 404, got {res.status_code}"
    print("[PASS] GET /api/investigation/session/non-existent-session-xyz -> 404")

def test_invalid_report_session_returns_404():
    res = requests.get(f"{BASE_URL}/investigation/report?session_id=non-existent-session-xyz")
    assert res.status_code == 404, f"Expected 404, got {res.status_code}"
    print("[PASS] GET /api/investigation/report?session_id=non-existent-session-xyz -> 404")

def test_valid_benchmark_session_returns_200():
    res = requests.get(f"{BASE_URL}/investigation/session/session_nov_2026_test")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert "total_rows" in data, "Missing total_rows in session details"
    assert "datasets" in data, "Missing datasets in session details"
    print(f"[PASS] GET /api/investigation/session/session_nov_2026_test -> 200 (rows: {data.get('total_rows')})")

def test_valid_benchmark_report_returns_200_with_deterministic_figures():
    res = requests.get(f"{BASE_URL}/investigation/report?session_id=session_nov_2026_test")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    report = res.json()
    curr_cost = round(report["current_total_cost"] / 1e7, 2)
    base_cost = round(report["baseline_total_cost"] / 1e7, 2)
    diff = round(curr_cost - base_cost, 2)
    cost_per_good = report["current_cost_per_good_unit"]
    produced = report["current_produced_qty"]
    good = report["current_good_qty"]

    assert curr_cost == 314.41, f"Expected curr_cost 314.41, got {curr_cost}"
    assert base_cost == 291.48, f"Expected base_cost 291.48, got {base_cost}"
    assert diff == 22.93, f"Expected diff 22.93, got {diff}"
    assert round(cost_per_good, 2) == 11264.46, f"Expected cost_per_good 11264.46, got {cost_per_good}"
    assert produced == 285156, f"Expected produced 285156, got {produced}"
    assert good == 279113, f"Expected good 279113, got {good}"
    print(f"[PASS] Deterministic metrics verified: Cost=Rs {curr_cost} Cr, Produced={produced:,}, Good={good:,}, Cost/Unit=Rs {cost_per_good:,.2f}")

def test_inspect_stream_assigns_real_uuid():
    sample_csv = "posting_date,plant_code,line_code,product_code,total_cost_inr\n2026-11-01,PLANT-01,LINE-01,SPH-A15-128,100000.0\n"
    files = {"files": ("test_fact_manufacturing_cost.csv", sample_csv, "text/csv")}
    res = requests.post(f"{BASE_URL}/import/inspect-stream", files=files, stream=True)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    
    found_session_id = None
    for line in res.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            if decoded.startswith("data: "):
                import json
                evt = json.loads(decoded[6:])
                sid = evt.get("details", {}).get("session_id")
                if sid:
                    found_session_id = sid
                    break
    assert found_session_id is not None, "Did not receive session_id in inspection stream"
    assert len(found_session_id) >= 32, f"Expected UUID session_id, got: {found_session_id}"
    print(f"[PASS] Real UUID session assigned from inspect-stream: {found_session_id}")

if __name__ == "__main__":
    test_invalid_session_returns_404()
    test_invalid_report_session_returns_404()
    test_valid_benchmark_session_returns_200()
    test_valid_benchmark_report_returns_200_with_deterministic_figures()
    test_inspect_stream_assigns_real_uuid()
    print("\nALL 5 WORKFLOW INTEGRITY & ACCESS CONTROL CHECKS PASSED!")
