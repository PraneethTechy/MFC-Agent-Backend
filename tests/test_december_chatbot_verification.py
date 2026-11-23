import json
import requests

API_URL = "http://localhost:8000/api"
DEC_SESSION_ID = "83bc61af-e690-4c01-8386-5e8313147008"
NOV_SESSION_ID = "6e9668d6-9142-4b3b-b21a-eb87f0f0f301"

def test_scope_metadata():
    print("\n--- TEST 1: Scope Metadata for December Session ---")
    resp = requests.get(f"{API_URL}/investigation/scope-metadata?session_id={DEC_SESSION_ID}")
    assert resp.status_code == 200, f"Status code: {resp.status_code}"
    data = resp.json()
    print("Session ID:", data.get("session_id"))
    print("Origin Label:", data.get("origin_label"))
    print("Session Period Label:", data.get("session_period_label"))
    print("Periods:", [p["label"] for p in data.get("dimensions", {}).get("periods", [])])
    assert data.get("session_id") == DEC_SESSION_ID
    assert "December 2026" in data.get("origin_label", "")
    assert data.get("session_period_label") == "December 2026"
    print("PASS: Scope Metadata is dynamically December 2026!")

def test_december_comparison_chat():
    print("\n--- TEST 2: Ask AI with December Session (Cross-Store) ---")
    payload = {
        "question": "Why did manufacturing expenditure decrease?",
        "session_id": DEC_SESSION_ID,
        "investigation_mode": "UPLOAD_SESSION_WITH_GLOBAL_COMPARISON",
    }
    resp = requests.post(f"{API_URL}/investigation/ask", json=payload)
    assert resp.status_code == 200, f"Status code: {resp.status_code}, error: {resp.text}"
    data = resp.json()
    
    exec_summary = data.get("executive_summary", "")
    data_origin = data.get("data_origin", "")
    session_id = data.get("session_id", "")
    
    print("\nResponse Status:", data.get("status"))
    print("Session ID in response:", session_id)
    print("Data Origin:", data_origin)
    print("Executive Summary:\n", exec_summary)
    
    assert DEC_SESSION_ID in session_id, f"Expected {DEC_SESSION_ID} in session_id, got: {session_id}"
    assert DEC_SESSION_ID in data_origin, f"Expected {DEC_SESSION_ID} in data_origin, got: {data_origin}"
    assert "7920f1b9" not in data_origin, f"Stale session found in data_origin: {data_origin}"
    
    # Verify accurate periods
    assert "October" in exec_summary or "Oct" in exec_summary, "Baseline October missing in summary"
    assert "December" in exec_summary or "Dec" in exec_summary, "Current December missing in summary"
    assert "from December 2026" not in exec_summary or "to December 2026" not in exec_summary, "Found duplicate December in from/to"
    assert "64.20" in exec_summary, "64.20 Cr delta missing"
    assert "366.92" in exec_summary, "366.92 Cr baseline missing"
    assert "302.72" in exec_summary, "302.72 Cr current missing"
    assert "17.50%" in exec_summary, "17.50% missing"
    print("\nPASS: December Ask AI response correctly uses October as baseline, December as current, and ₹64.20 Cr delta!")

def test_global_mode():
    print("\n--- TEST 3: Ask AI in GLOBAL_ONLY mode ---")
    payload = {
        "question": "Why did manufacturing cost increase?",
        "session_id": "GLOBAL",
        "investigation_mode": "GLOBAL_ONLY",
    }
    resp = requests.post(f"{API_URL}/investigation/ask", json=payload)
    assert resp.status_code == 200, f"Status code: {resp.status_code}, error: {resp.text}"
    data = resp.json()
    print("Data Origin:", data.get("data_origin"))
    assert "REAL_COMMITTED_STORE" in data.get("data_origin", "")
    print("PASS: Global mode returns REAL_COMMITTED_STORE!")

def test_november_regression():
    print("\n--- TEST 4: Regression Test with November Session ---")
    payload = {
        "question": "Why did manufacturing cost decrease?",
        "session_id": NOV_SESSION_ID,
        "investigation_mode": "UPLOAD_SESSION_WITH_GLOBAL_COMPARISON",
    }
    resp = requests.post(f"{API_URL}/investigation/ask", json=payload)
    assert resp.status_code == 200, f"Status code: {resp.status_code}, error: {resp.text}"
    data = resp.json()
    print("Session ID in response:", data.get("session_id"))
    print("Data Origin:", data.get("data_origin"))
    print("Executive Summary:", data.get("executive_summary")[:200], "...")
    assert NOV_SESSION_ID in data.get("data_origin", "")
    assert "November" in data.get("executive_summary", "") or "Nov" in data.get("executive_summary", "")
    print("PASS: November regression test succeeded!")

if __name__ == "__main__":
    test_scope_metadata()
    test_december_comparison_chat()
    test_global_mode()
    test_november_regression()
    print("\n==========================================")
    print("ALL 4 ACCEPTANCE TESTS PASSED SUCCESSFULLY!")
    print("==========================================")
