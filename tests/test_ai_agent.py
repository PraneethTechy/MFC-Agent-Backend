"""
Test Suite for AI Cost Investigator Agent (Master Prompt 4 & Master Prompt 4.2)
Covers Domo integration, Agent Loop, Strict Evidence Governance (Master Prompt 4.2),
Unverified Standards rules, Price/Usage split unavailability, BOM safety, and Tool De-duplication.
"""

from decimal import Decimal
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app, run_agent
from app.domo_llm import DomoTextLLM
from app.agent import _parse_and_validate_action
from app.tools import (
    validate_cost_data,
    get_cost_summary,
    get_standard_vs_actual,
    calculate_variance_bridge,
    rank_cost_drivers,
    inspect_bom_components,
    investigate_variance,
)


# =============================================================================
# 1. Domo Integration Tests (Mocked & Error Handling)
# =============================================================================

def test_domo_llm_mocked_success():
    """Verify DomoTextLLM formats payload and parses text response correctly."""
    llm = DomoTextLLM()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "output": '{"action": "final", "answer": "Analysis complete."}',
        "modelProviderUsage": {"inputTokens": 100, "outputTokens": 20, "totalTokens": 120},
    }

    with patch("httpx.Client.post", return_value=mock_response):
        res = llm.invoke("Test prompt")
        assert '{"action": "final", "answer": "Analysis complete."}' in res


def test_domo_llm_auth_failure():
    """Verify DomoTextLLM raises clear RuntimeError on 401/403."""
    llm = DomoTextLLM()
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": "Invalid token"}

    with patch("httpx.Client.post", return_value=mock_response):
        with pytest.raises(RuntimeError) as exc_info:
            llm.invoke("Test prompt")
        assert "authentication failed" in str(exc_info.value).lower()


def test_domo_llm_timeout():
    """Verify DomoTextLLM raises TimeoutError on httpx.TimeoutException."""
    import httpx
    llm = DomoTextLLM(timeout=5.0)

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Read timeout")):
        with pytest.raises(TimeoutError) as exc_info:
            llm.invoke("Test prompt")
        assert "timed out" in str(exc_info.value).lower()


# =============================================================================
# 2. Agent Action Parsing & Validation Tests
# =============================================================================

def test_parse_valid_tool_call():
    """Verify parsing and validating an approved tool call."""
    raw = '{"action": "get_cost_summary", "input": {"plant_code": "IN-KA-01"}}'
    action = _parse_and_validate_action(raw)
    assert action["action"] == "get_cost_summary"
    assert action["input"]["plant_code"] == "IN-KA-01"


def test_parse_valid_final_answer():
    """Verify parsing and validating a final answer."""
    raw = '{"action": "final", "answer": "Material is the largest cost driver."}'
    action = _parse_and_validate_action(raw)
    assert action["action"] == "final"
    assert "Material is the largest" in action["answer"]


def test_parse_markdown_wrapped_json():
    """Verify parsing handles markdown code fences gracefully."""
    raw = '```json\n{"action": "final", "answer": "Clean output"}\n```'
    action = _parse_and_validate_action(raw)
    assert action["action"] == "final"
    assert action["answer"] == "Clean output"


def test_parse_unsupported_tool():
    """Verify unrecognized tools are caught and flagged."""
    raw = '{"action": "delete_all_records", "input": {}}'
    action = _parse_and_validate_action(raw)
    assert action["action"] == "unsupported_tool"
    assert action["tool_name"] == "delete_all_records"


# =============================================================================
# 3. Master Prompt 4.2 Evidence Governance & Safety Tests
# =============================================================================

def test_unverified_standard_cannot_produce_proven_finding():
    """Verify standard_vs_actual explicitly classifies finding as OBSERVED_CORRELATION, not PROVEN."""
    res = get_standard_vs_actual.invoke({"product_code": "SPH-PRO-256"})
    assert res["status"] == "PROVISIONAL_COMPARISON"
    assert res["standard_approval_status"] == "UNVERIFIED_STANDARD"
    assert res["finding_classification"] == "OBSERVED_CORRELATION"
    assert "CANNOT be classified as PROVEN" in res["governance_note"]


def test_missing_purchase_prices_and_split_unavailability():
    """Verify variance bridge discloses PRICE_USAGE_SPLIT_NOT_AVAILABLE."""
    res = calculate_variance_bridge.invoke({"product_code": "SPH-PRO-256"})
    assert res["status"] == "PROVISIONAL_BRIDGE"
    assert res["material_split_disclosure"] == "PRICE_USAGE_SPLIT_NOT_AVAILABLE"

    # Verify material component contains explicit split notice
    mat_comp = next(c for c in res["bridge_components"] if c["category"] == "Material")
    assert mat_comp["price_usage_split"] == "PRICE_USAGE_SPLIT_NOT_AVAILABLE"
    assert mat_comp["evidence_classification"] == "OBSERVED_CORRELATION"


def test_bom_speculation_labelled_hypothesis():
    """Verify BOM inspection discloses that price data is unavailable and component difference is HYPOTHESIS."""
    res = inspect_bom_components.invoke({"product_code": "SPH-PRO-256"})
    assert res["status"] == "SUCCESS"
    assert res["components_count"] == 16
    assert res["price_data_available"] is False
    assert "MUST be classified as a HYPOTHESIS" in res["governance_note"]


def test_confidence_not_arbitrary():
    """Verify investigation returns structured confidence assessment, not arbitrary LLM score."""
    res = investigate_variance.invoke({"product_code": "SPH-PRO-256"})
    assert res["status"] == "INVESTIGATION_COMPLETE"
    assert "OBSERVED_CORRELATION" in res["confidence_assessment"]
    assert "HYPOTHESIS / NOT_ASSESSED" in res["confidence_assessment"]
    assert len(res["proven_findings"]) >= 3
    assert len(res["hypotheses"]) >= 2
    assert any("PRICE_USAGE_SPLIT_NOT_AVAILABLE" in u for u in res["unavailable_evidence"])


def test_tool_get_cost_summary_exact_totals():
    """Verify get_cost_summary returns exact Neon totals down to ₹0.00 discrepancy."""
    res = get_cost_summary.invoke({})
    assert res["status"] == "SUCCESS"
    assert res["batches_analyzed"] == 5000
    assert abs(res["total_direct_actual_cost_inr"] - 14024712024.30) < 0.01

    cats = res["categories"]
    assert abs(cats["material_cost"]["actual_cost"] - 13359506779.21) < 0.01
    assert abs(cats["labour_cost"]["actual_cost"] - 370630471.87) < 0.01
    assert abs(cats["machine_cost"]["actual_cost"] - 211672766.11) < 0.01
    assert abs(cats["energy_cost"]["actual_cost"] - 65075725.60) < 0.01
    assert abs(cats["scrap_and_rework_cost"]["actual_cost"] - 17826281.51) < 0.01
    assert cats["factory_overhead"]["status"] == "NOT_AVAILABLE"


def test_tool_rank_cost_drivers():
    """Verify rank_cost_drivers ranks Material first as PROVEN dominant driver."""
    res = rank_cost_drivers.invoke({})
    assert res["status"] == "SUCCESS"
    drivers = res["ranked_drivers"]
    assert len(drivers) == 5
    assert drivers[0]["category"] == "Material"
    assert drivers[0]["rank"] == 1
    assert drivers[0]["evidence_classification"] == "PROVEN"


def test_tool_deduplication_prevents_duplicate_calls():
    """Verify repeated identical tool calls are de-duplicated by the agent loop."""
    from app.agent import run_agent
    loop_response = '{"action": "get_cost_summary", "input": {"product_code": "SPH-PRO-256"}}'
    
    with patch("langchain_core.runnables.base.RunnableSequence.invoke", return_value=loop_response):
        answer, traces, meta = run_agent("Duplicate test", [], max_steps=4)
        # First call executes, subsequent calls with identical input are de-duplicated
        summary_traces = [t for t in traces if t.get("tool") == "get_cost_summary"]
        assert len(summary_traces) == 1


# =============================================================================
# 4. Conversation Persistence API Tests
# =============================================================================

def test_chat_api_create_and_retrieve():
    """Verify POST /api/chat persists conversation and messages in Neon."""
    client = TestClient(app)

    mock_agent_return = (
        "Total direct manufacturing cost is ₹14,024,712,024.30 across 5,000 batches.",
        [{"step": 1, "tool": "get_cost_summary", "input": {}, "result": {"status": "SUCCESS"}}],
        {"iterations": 2, "data_as_of": "2026-10-31"},
    )

    with patch("app.main.run_agent", return_value=mock_agent_return):
        resp = client.post("/api/chat", json={"message": "What is total cost?"})
        assert resp.status_code == 200
        data = resp.json()
        conv_id = data["conversation_id"]
        assert conv_id is not None
        assert "₹14,024,712,024.30" in data["message"]
        assert len(data["tool_traces"]) == 1

        hist_resp = client.get(f"/api/chat/conversations/{conv_id}")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert len(hist_data["messages"]) == 2
        assert hist_data["messages"][0]["role"] == "user"
        assert hist_data["messages"][1]["role"] == "assistant"
        assert hist_data["messages"][1]["steps"][0]["tool"] == "get_cost_summary"
