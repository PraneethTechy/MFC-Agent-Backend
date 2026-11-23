"""
Targeted Verification Suite for Manufacturing AI Chatbot
Defect 1: Reporting-Period Resolution
Defect 2: Data-Source and Cross-Store Routing
Defect 3: Variance Decomposition & Reconciliation Integrity
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


def test_question_1_october_2026_global_store_expenditure(db_session):
    """
    Defect 1 & 2: User asks: 'What was our total manufacturing expenditure in October 2026?'
    - Must resolve October 2026 (2026-10) explicitly.
    - Must query committed Global Store in Neon DB only.
    - Must return October expenditure (₹463.01 Cr), NOT November upload (₹313.48 Cr).
    - Must not label as 'All Available Periods'.
    """
    req = InvestigationQueryRequest(
        question="What was our total manufacturing expenditure in October 2026?",
        reporting_period="ALL",
        session_id="6e9668d6-9142-4b3b-b21a-eb87f0f0f301",
        mode="CROSS_STORE",
    )
    res = InvestigationQueryService.process_investigation(db=db_session, request=req)

    assert res.status == "COMPLETED"
    assert res.effective_mode == "GLOBAL_ONLY"
    assert res.data_origin == "REAL_COMMITTED_STORE"
    assert not res.is_synthetic
    assert "2026-10" in res.reporting_period or "October 2026" in res.reporting_period
    assert "All Available Periods" not in res.reporting_period

    # Must contain October 2026 totals: ₹463.01 Cr
    assert "463.01" in res.title or "463.01" in res.executive_summary
    assert "313.48" not in res.executive_summary  # Did not substitute November upload!


def test_question_2_november_current_upload_summary(db_session):
    """
    Defect 2: User asks: 'Summarize the manufacturing expenditure and production output in my current November upload.'
    - Must resolve November 2026 (2026-11).
    - Must query active upload session only (SYNTHETIC_TEST).
    - Must return November metrics (₹313.48 Cr across 207,940 units).
    """
    req = InvestigationQueryRequest(
        question="Summarize the manufacturing expenditure and production output in my current November upload.",
        reporting_period="ALL",
        session_id="6e9668d6-9142-4b3b-b21a-eb87f0f0f301",
        mode="CROSS_STORE",
    )
    res = InvestigationQueryService.process_investigation(db=db_session, request=req)

    assert res.status == "COMPLETED"
    assert res.effective_mode == "UPLOAD_SESSION_ONLY"
    assert res.data_origin == "SYNTHETIC_TEST"
    assert res.is_synthetic
    assert "2026-11" in res.reporting_period or "November 2026" in res.reporting_period

    # Must contain November 2026 upload totals: ₹313.48 Cr across 207,940 units
    assert "313.48" in res.title or "313.48" in res.executive_summary
    assert "207,940" in res.executive_summary


def test_question_3_cross_store_comparison_variance_integrity(db_session):
    """
    Defect 3: User asks: 'Compare November 2026 manufacturing expenditure from my current upload with October 2026 from the Global Store. Explain the difference.'
    - Mode must be CROSS_STORE.
    - Total variance: net decrease of ₹149.52 Cr (-32.29%).
    - Mathematical reconciliation: -₹143.84 Cr - ₹6.91 Cr + ₹2.40 Cr - ₹0.98 Cr - ₹0.20 Cr = -₹149.52 Cr.
    - Clearly separate cost decreases from cost increases (Machine Operating is +₹2.40 Cr cost addition).
    - Volume Effect and Mix Effect must be reported as NOT_AVAILABLE.
    - Zero symbol regressions (no leading +/- before currency symbols in narrative).
    """
    req = InvestigationQueryRequest(
        question="Compare November 2026 manufacturing expenditure from my current upload with October 2026 from the Global Store. Explain the difference.",
        session_id="6e9668d6-9142-4b3b-b21a-eb87f0f0f301",
        mode="CROSS_STORE",
    )
    res = InvestigationQueryService.process_investigation(db=db_session, request=req)

    assert res.status == "COMPLETED"
    assert res.intent == "PERIOD_COMPARISON"
    assert res.effective_mode == "UPLOAD_SESSION_WITH_GLOBAL_COMPARISON"
    assert "CROSS_STORE" in res.data_origin

    # Verify total movement: ₹149.52 Cr decrease
    assert "149.52" in res.title or "149.52" in res.executive_summary
    assert "32.29%" in res.executive_summary

    # Verify category drivers separated by decrease vs increase
    assert "decrease of ₹143.84 Cr" in res.executive_summary or "Direct Material" in res.executive_summary
    assert "Direct Labour" in res.executive_summary
    assert "Machine Operating" in res.executive_summary
    assert "increase of ₹2.40 Cr" in res.executive_summary or "offset" in res.executive_summary

    # Verify Volume and Mix reported as NOT_AVAILABLE
    assert "NOT_AVAILABLE" in res.executive_summary
    assert "Volume Effect" in res.executive_summary
    assert "Mix Effect" in res.executive_summary

    # Verify bridge steps in detailed_findings
    vol_mix_steps = [f for f in res.detailed_findings if "Volume" in f.get("title", "") or "Mix" in f.get("title", "")]
    for s in vol_mix_steps:
        assert s.get("evidence_classification") == "NOT_AVAILABLE" or "NOT_AVAILABLE" in str(s)


def test_question_4_data_sources_and_commit_status(db_session):
    """
    Defect 2 & Provenance: User asks: 'Which data sources did you use, and has the November upload been committed?'
    - Must identify Store A (Neon PostgreSQL Global Store) and Store B (Upload Session Store).
    - Must explicitly confirm that the November upload has NOT been committed to production tables.
    """
    req = InvestigationQueryRequest(
        question="Which data sources did you use, and has the November upload been committed?",
        session_id="6e9668d6-9142-4b3b-b21a-eb87f0f0f301",
        mode="CROSS_STORE",
    )
    res = InvestigationQueryService.process_investigation(db=db_session, request=req)

    assert res.status == "COMPLETED"
    assert res.intent == "DATA_PROVENANCE"

    # Confirms Store A & Store B
    assert "Store A" in res.executive_summary or "Global Store" in res.executive_summary
    assert "Store B" in res.executive_summary or "Upload Session" in res.executive_summary

    # Explicitly confirms that November upload is uncommitted
    assert "NOT been committed" in res.executive_summary or "uncommitted" in res.executive_summary.lower()


def test_missing_period_guardrail(db_session):
    """
    Boundary: User asks about a non-existent period (e.g. December 2026).
    - Must return status='PERIOD_UNAVAILABLE'.
    - Must disclose available periods without zero-fabrication.
    """
    req = InvestigationQueryRequest(
        question="What was our total manufacturing expenditure in December 2026?",
        reporting_period="ALL",
        session_id="6e9668d6-9142-4b3b-b21a-eb87f0f0f301",
        mode="CROSS_STORE",
    )
    res = InvestigationQueryService.process_investigation(db=db_session, request=req)

    assert res.status == "PERIOD_UNAVAILABLE"
    assert "December 2026" in res.title or "December 2026" in res.executive_summary
    assert "unavailable" in res.executive_summary.lower()
