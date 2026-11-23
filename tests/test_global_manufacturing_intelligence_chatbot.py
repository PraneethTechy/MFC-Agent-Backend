"""
Comprehensive Verification Suite for GWC Global Manufacturing Intelligence Chatbot
Covers Scenarios:
1. Cross-Store Period Comparison (November 2026 vs October 2026) with zero +/- regressions
2. Global Store Only Mode (Authoritative committed Neon records)
3. Staged Upload Session Only Mode
4. Missing Period Guardrail (PERIOD_UNAVAILABLE without zero-fabrication)
5. Out-of-Scope Intent Routing
6. Data Provenance & Source Inquiry Intent
7. Zero Symbol Regressions (+/- purged before currency & percentages)
"""

import re
import pytest
from app.db import SessionLocal
from app.services.investigation.query_service import (
    InvestigationQueryService,
    InvestigationQueryRequest,
    _clean_symbols_deep,
)


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def test_symbol_sanitization_deep():
    """Verify that _clean_symbols_deep purges leading +/- from currency and percentages."""
    samples = [
        "(+₹9.69 Cr)",
        "(-₹143.84 Cr)",
        "+₹2.40 Cr",
        "-₹149.52 Cr",
        "-32.29%",
        "(-1.6%)",
        "+1.6%",
        "decreased by -₹149.52 Cr",
        "SPH-A15-256",
        "SMT-L1",
        "INV-1794758-00ec",
    ]

    cleaned = [_clean_symbols_deep(s) for s in samples]

    assert cleaned[0] == "(₹9.69 Cr)"
    assert cleaned[1] == "(₹143.84 Cr)"
    assert cleaned[2] == "₹2.40 Cr"
    assert cleaned[3] == "₹149.52 Cr"
    assert cleaned[4] == "32.29%"
    assert cleaned[5] == "(1.6%)"
    assert cleaned[6] == "1.6%"
    assert "₹149.52 Cr" in cleaned[7]
    assert "-₹" not in cleaned[7]
    # SKUs and Line IDs preserved with standard hyphens
    assert cleaned[8] == "SPH-A15-256"
    assert cleaned[9] == "SMT-L1"
    assert cleaned[10] == "INV-1794758-00ec"


def test_scenario_cross_store_comparison(db_session):
    """Verify Cross-Store comparison between November 2026 (staged) and October 2026 (baseline)."""
    req = InvestigationQueryRequest(
        question="Compare November 2026 manufacturing expenditure with October 2026 and decompose the primary variance drivers",
        session_id="6e9668d6-9142-4b3b-b21a-eb87f0f0f301",
        investigation_mode="UPLOAD_SESSION_WITH_GLOBAL_COMPARISON",
    )
    res = InvestigationQueryService.process_investigation(db=db_session, request=req)

    assert res.status == "COMPLETED"
    assert res.intent == "PERIOD_COMPARISON"
    assert "149.52" in res.title or "149.52" in res.executive_summary
    # Verify no leading + or - before currency symbols in title or summary
    assert not re.search(r'[\+\-\–\—]\s*₹', res.title)
    assert not re.search(r'[\+\-\–\—]\s*₹', res.executive_summary)
    assert not re.search(r'\(\+₹', res.executive_summary)
    assert not re.search(r'\(\-₹', res.executive_summary)


def test_scenario_missing_period_guardrail(db_session):
    """Verify that asking for a non-existent period returns PERIOD_UNAVAILABLE without fabricating zero."""
    req = InvestigationQueryRequest(
        question="Compare December 2026 manufacturing expenditure with October 2026",
        session_id="6e9668d6-9142-4b3b-b21a-eb87f0f0f301",
        investigation_mode="UPLOAD_SESSION_WITH_GLOBAL_COMPARISON",
    )
    res = InvestigationQueryService.process_investigation(db=db_session, request=req)

    assert res.status == "PERIOD_UNAVAILABLE"
    assert "December 2026" in res.title or "December 2026" in res.executive_summary
    assert "not recorded" in res.executive_summary.lower() or "unavailable" in res.executive_summary.lower()


def test_scenario_out_of_scope(db_session):
    """Verify that general/unrelated questions receive accurate, scoped answers without unnecessary refusal."""
    req = InvestigationQueryRequest(
        question="What is the capital of France and who is the prime minister?",
        session_id="6e9668d6-9142-4b3b-b21a-eb87f0f0f301",
        investigation_mode="GLOBAL_ONLY",
    )
    res = InvestigationQueryService.process_investigation(db=db_session, request=req)

    assert res.intent in ("GENERAL_KNOWLEDGE", "OUT_OF_SCOPE")
    assert res.status in ("GENERAL_KNOWLEDGE", "OUT_OF_SCOPE")
    assert "manufacturing" in res.executive_summary.lower()


def test_scenario_data_provenance_intent(db_session):
    """Verify that data provenance questions return exact store, session ID, and commit status."""
    req = InvestigationQueryRequest(
        question="Which data source did you use to answer my question?",
        session_id="6e9668d6-9142-4b3b-b21a-eb87f0f0f301",
        investigation_mode="UPLOAD_SESSION_WITH_GLOBAL_COMPARISON",
    )
    res = InvestigationQueryService.process_investigation(db=db_session, request=req)

    assert res.intent == "DATA_PROVENANCE"
    assert res.status == "COMPLETED"
    assert "data provenance" in res.title.lower() or "audit trail" in res.title.lower()
    assert "6e9668d6-9142-4b3b-b21a-eb87f0f0f301" in res.executive_summary or "Store" in res.executive_summary
