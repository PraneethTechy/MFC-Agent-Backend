"""
Master Automated Verification Suite for GWC Manufacturing Cost AI Chatbot.
Verifies all 22 required scenarios from the Final Master Prompt:
- Overview questions (1-7)
- Contradictory and follow-up reasoning (8-13)
- Data scope and application context (14-19)
- Suggested questions (20-22)
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domo_llm import DomoTextLLM

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_domo_fast(monkeypatch):
    """Triggers immediate deterministic calculation narrative for instantaneous testing."""
    def _mock_invoke(self, prompt, **kwargs):
        raise RuntimeError("Fast test mock: immediate deterministic synthesis")
    def _mock_call(self, prompt, stop=None, **kwargs):
        raise RuntimeError("Fast test mock: immediate deterministic synthesis")
    monkeypatch.setattr(DomoTextLLM, "invoke", _mock_invoke)
    monkeypatch.setattr(DomoTextLLM, "_call", _mock_call)


def test_scenario_01_cost_increase_assumption_correction():
    """1 & 13: Why did manufacturing cost increase in November? (Politely corrects assumption while explaining unit cost increase)."""
    resp = client.post("/api/investigation/ask", json={
        "question": "Why did manufacturing cost increase in November?",
        "reporting_period": "2026-11",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("COMPLETED", "PROVEN")
    summary = data["executive_summary"].lower()
    # Verified direction: Total expenditure decreased, but unit cost increased
    assert "not increase" in summary or "decreased" in summary
    assert "cost per good unit" in summary or "unit" in summary


def test_scenario_02_cost_decrease_explanation():
    """2: Why did manufacturing cost decrease in November?"""
    resp = client.post("/api/investigation/ask", json={
        "question": "Why did manufacturing cost decrease in November?",
        "reporting_period": "2026-11",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("COMPLETED", "PROVEN")
    summary = data["executive_summary"].lower()
    assert "decreased" in summary
    assert "volume" in summary or "output" in summary


def test_scenario_03_highest_cost_per_good_unit():
    """3: Which month had the highest cost per good unit?"""
    resp = client.post("/api/investigation/ask", json={
        "question": "Which month had the highest cost per good unit?",
        "reporting_period": "ALL",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("COMPLETED", "PROVEN")
    assert "cost per good unit" in data["executive_summary"].lower() or "unit" in data["executive_summary"].lower()


def test_scenario_04_plant_contribution():
    """4: Which plant contributed most to manufacturing cost?"""
    resp = client.post("/api/investigation/ask", json={
        "question": "Which plant contributed most to manufacturing cost?",
        "reporting_period": "ALL",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("COMPLETED", "PROVEN")
    summary = data["executive_summary"].lower()
    assert "plant" in summary or "plt" in summary


def test_scenario_05_compare_november_with_october():
    """5: Compare November with October."""
    resp = client.post("/api/investigation/ask", json={
        "question": "Compare November with October",
        "reporting_period": "2026-11",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("COMPLETED", "PROVEN")
    assert data["intent"] == "PERIOD_COMPARISON"
    assert "november" in data["executive_summary"].lower()
    assert "october" in data["executive_summary"].lower()


def test_scenario_06_material_cost_movement():
    """6: What changed in material cost?"""
    resp = client.post("/api/investigation/ask", json={
        "question": "What changed in material cost?",
        "reporting_period": "2026-11",
        "page_context": "COST_ANALYSIS",
        "data_scope": "GLOBAL_STORE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("COMPLETED", "PROVEN")
    assert "material" in data["executive_summary"].lower()


def test_scenario_07_production_vs_demo_mode():
    """7: What is the difference between Production and Demo mode?"""
    resp = client.post("/api/investigation/ask", json={
        "question": "What is the difference between Production and Demo mode?",
        "reporting_period": "ALL",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("COMPLETED", "PROVEN")
    summary = data["executive_summary"].lower()
    assert "production" in summary and "demo" in summary


def test_scenario_08_contradictory_increase_then_decrease():
    """8: Contradictory reasoning: Ask why cost increased, then why it decreased for same period."""
    # Turn 1: Increase question
    r1 = client.post("/api/investigation/ask", json={
        "question": "Why did manufacturing cost increase in November?",
        "reporting_period": "2026-11",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert r1.status_code == 200
    rep1_id = r1.json()["report_id"]

    # Turn 2: Decrease question with parent_report_id
    r2 = client.post("/api/investigation/ask", json={
        "question": "Why did manufacturing cost decrease in November?",
        "reporting_period": "2026-11",
        "parent_report_id": rep1_id,
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert r2.status_code == 200
    s1 = r1.json()["executive_summary"]
    s2 = r2.json()["executive_summary"]
    # They must not be blindly identical
    assert s1 != s2
    assert "decrease" in s2.lower()


def test_scenario_09_total_spend_down_unit_cost_up():
    """9: Ask why total expenditure decreased but cost per good unit increased."""
    resp = client.post("/api/investigation/ask", json={
        "question": "Why did total expenditure decrease but cost per good unit increase?",
        "reporting_period": "2026-11",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("COMPLETED", "PROVEN")
    summary = data["executive_summary"].lower()
    assert "expenditure" in summary or "total" in summary
    assert "unit" in summary or "good unit" in summary


def test_scenario_10_plant_drilldown_to_line():
    """10: Ask which plant contributed most, then ask which production line within that plant contributed most."""
    r1 = client.post("/api/investigation/ask", json={
        "question": "Which plant contributed most to total manufacturing cost?",
        "reporting_period": "2026-11",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert r1.status_code == 200
    rep1_id = r1.json()["report_id"]

    r2 = client.post("/api/investigation/ask", json={
        "question": "Which production line within that plant contributed most?",
        "reporting_period": "2026-11",
        "parent_report_id": rep1_id,
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["status"] in ("COMPLETED", "PROVEN")
    assert "line" in data2["executive_summary"].lower() or "l1" in data2["executive_summary"].lower() or "l2" in data2["executive_summary"].lower()


def test_scenario_11_material_drilldown_to_supplier():
    """11: Ask about material cost, then ask whether the supplier caused the change."""
    r1 = client.post("/api/investigation/ask", json={
        "question": "What about material cost?",
        "reporting_period": "2026-11",
        "page_context": "COST_ANALYSIS",
        "data_scope": "GLOBAL_STORE",
    })
    assert r1.status_code == 200
    rep1_id = r1.json()["report_id"]

    r2 = client.post("/api/investigation/ask", json={
        "question": "Was it due to the supplier?",
        "reporting_period": "2026-11",
        "parent_report_id": rep1_id,
        "page_context": "COST_ANALYSIS",
        "data_scope": "GLOBAL_STORE",
    })
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["status"] in ("COMPLETED", "PROVEN")
    assert "supplier" in data2["executive_summary"].lower() or "procurement" in data2["executive_summary"].lower() or "vendor" in data2["executive_summary"].lower()


def test_scenario_12_reporting_period_context_update():
    """12: Change reporting period and verify previous-period context updates correctly."""
    r1 = client.post("/api/investigation/ask", json={
        "question": "What was the total manufacturing cost in October?",
        "reporting_period": "2026-10",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert r1.status_code == 200
    assert "october" in r1.json()["executive_summary"].lower() or "2026-10" in str(r1.json())

    r2 = client.post("/api/investigation/ask", json={
        "question": "What about November?",
        "reporting_period": "2026-11",
        "parent_report_id": r1.json()["report_id"],
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert r2.status_code == 200
    assert "november" in r2.json()["executive_summary"].lower() or "2026-11" in str(r2.json())


def test_scenario_14_15_global_store_committed_isolation():
    """14 & 15: Global Store uses committed operational facts."""
    resp = client.post("/api/investigation/ask", json={
        "question": "Summarize total manufacturing cost across all available history",
        "reporting_period": "ALL",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("COMPLETED", "PROVEN")
    assert data["data_origin"] in ("REAL_COMMITTED_STORE", "GLOBAL_STORE")


def test_scenario_16_unavailable_period_handling():
    """16: Verify unavailable periods produce meaningful explanations without crashing."""
    resp = client.post("/api/investigation/ask", json={
        "question": "Compare May 2025 with April 2025",
        "reporting_period": "2025-05",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PERIOD_UNAVAILABLE"
    assert "unavailable" in data["executive_summary"].lower() or "could not" in data["executive_summary"].lower()


def test_scenario_17_synthetic_exclusion_in_production():
    """17: Production responses exclude synthetic demonstration records."""
    resp = client.post("/api/investigation/ask", json={
        "question": "What is our production direct expenditure?",
        "reporting_period": "2026-11",
        "page_context": "OVERVIEW",
        "data_scope": "GLOBAL_STORE",
        "data_mode": "PRODUCTION",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_synthetic"] is False


def test_scenario_18_report_evidence_grounding():
    """18: Verify report questions answer from report evidence."""
    resp = client.post("/api/investigation/ask", json={
        "question": "What are the primary findings in this report?",
        "reporting_period": "2026-11",
        "page_context": "REPORTS",
        "data_scope": "GLOBAL_STORE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("COMPLETED", "PROVEN")
    assert len(data.get("detailed_findings", [])) > 0


def test_scenario_19_general_unrelated_questions():
    """19: General questions receive natural answers without SQL errors."""
    general_queries = [
        "What is the capital of France?",
        "Tell me a joke",
        "What is Generative AI?",
        "Explain neural networks",
        "What is machine learning?",
        "Explain SQL joins",
    ]
    for q in general_queries:
        resp = client.post("/api/investigation/ask", json={
            "question": q,
            "reporting_period": "ALL",
            "page_context": "HOME",
            "data_scope": "GLOBAL_STORE",
        })
        assert resp.status_code == 200, f"Failed on {q}"
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert len(data["executive_summary"]) > 10


def test_scenario_20_21_22_suggested_overview_questions():
    """20, 21, 22: Every suggested Overview question must execute to 200."""
    overview_suggestions = [
        "Why did manufacturing cost increase in November?",
        "Which month had the highest cost per good unit?",
        "Which plant contributes most to total manufacturing cost?",
        "What is the difference between Production and Demo mode?",
    ]
    for q in overview_suggestions:
        resp = client.post("/api/investigation/ask", json={
            "question": q,
            "reporting_period": "2026-11",
            "page_context": "OVERVIEW",
            "data_scope": "GLOBAL_STORE",
        })
        assert resp.status_code == 200, f"Suggested question failed: {q}"
        data = resp.json()
        assert data["status"] in ("COMPLETED", "PROVEN")
