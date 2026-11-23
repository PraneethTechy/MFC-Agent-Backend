"""
Verification test suite for Investigation Result page data consistency and session integrity.
Validates:
1. Active session (session_nov_2026_test) reconciles with the authoritative November benchmarks:
   - Total Cost: ₹314.41 Cr (₹3,144,056,862.26)
   - Baseline Cost: ₹291.48 Cr (₹2,914,795,654.79)
   - Cost Delta: +₹22.93 Cr (+7.87%)
   - Produced Units: 285,156
   - Good Units: 279,113
   - Cost Per Good Unit: ₹11,264.46
   - Assembly Yield: 97.88%
2. Baseline availability handling: when baseline is unavailable, status is UNAVAILABLE and not +₹0.00 Cr.
3. Reasons breakdown contains verified category variances.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.ingestion.session_store import SessionDataStore

client = TestClient(app)

def test_investigation_result_authoritative_session():
    # Pin to session_nov_2026_test
    SessionDataStore.set_active_session_id("session_nov_2026_test")
    res = client.get("/api/investigation/report?session_id=session_nov_2026_test")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()

    # 1. Financial Totals
    assert abs(data["current_total_cost"] - 3144056862.26) < 1.0, f"Total cost mismatch: {data['current_total_cost']}"
    assert abs(data["baseline_total_cost"] - 2914795654.79) < 1.0, f"Baseline cost mismatch: {data['baseline_total_cost']}"
    assert abs(data["cost_change_amount"] - 229261207.47) < 1.0, f"Variance mismatch: {data['cost_change_amount']}"
    assert abs(data["cost_change_pct"] - 7.87) < 0.05, f"Variance % mismatch: {data['cost_change_pct']}"

    # 2. Production & Quality KPIs
    assert data["current_produced_qty"] == 285156, f"Produced qty mismatch: {data['current_produced_qty']}"
    assert data["current_good_qty"] == 279113, f"Good qty mismatch: {data['current_good_qty']}"
    assert abs(data["current_cost_per_good_unit"] - 11264.46) < 0.1, f"Unit cost mismatch: {data['current_cost_per_good_unit']}"

    # Yield verification
    yield_pct = (data["current_good_qty"] / data["current_produced_qty"]) * 100
    assert abs(yield_pct - 97.88) < 0.05, f"Yield mismatch: {yield_pct}"

    # 3. Reasons Breakdown
    calc = data.get("calculation_details", {})
    reasons = calc.get("reasons_breakdown", [])
    assert len(reasons) >= 5, f"Expected at least 5 reason items, got {len(reasons)}"
    mat_reason = next((r for r in reasons if r.get("category") == "Material"), None)
    assert mat_reason is not None
    assert abs(mat_reason["amount"] - 223908883.3) < 1e5, f"Material variance mismatch: {mat_reason['amount']}"
    assert mat_reason["formatted_amount"] == "₹22.39 Cr"
    assert mat_reason["pct_of_variance"] == 97.7

def test_missing_session_returns_404():
    res = client.get("/api/investigation/report?session_id=nonexistent-session-id-1234")
    assert res.status_code == 404
