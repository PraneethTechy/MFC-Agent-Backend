"""
Investigation Report In-Memory Cache and Neon PostgreSQL Permanent Store.
Guarantees fast retrieval of investigation reports while persisting every report
durably to Neon PostgreSQL to survive backend restarts.
"""

import datetime as dt
import hashlib
import json
import logging
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.agent_records import InvestigationReportRecord
from .schemas import InvestigationReport, InvestigationHistoryItem

logger = logging.getLogger("manufacturing_cost_agent.investigation.report_cache")

_REPORT_CACHE: dict[str, InvestigationReport] = {}


def generate_cache_key(
    baseline_period: str,
    current_period: str,
    plant_code: Optional[str] = None,
    product_code: Optional[str] = None,
    line_code: Optional[str] = None,
) -> str:
    raw = f"{baseline_period}|{current_period}|{plant_code or ''}|{product_code or ''}|{line_code or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def get_cached_report(key: str, db: Optional[Session] = None) -> Optional[InvestigationReport]:
    """
    Retrieves investigation report from in-memory cache first,
    falling back to Neon PostgreSQL if not present (e.g. after backend restart).
    """
    if key in _REPORT_CACHE:
        return _REPORT_CACHE[key]

    if db is not None:
        try:
            rec = (
                db.query(InvestigationReportRecord)
                .filter(
                    (InvestigationReportRecord.report_id == key)
                    | (InvestigationReportRecord.inspection_id == key)
                )
                .first()
            )
            if rec and rec.report_json:
                rep = InvestigationReport.model_validate(rec.report_json)
                set_cached_report(rep.report_id, rep)
                return rep
        except Exception as exc:
            logger.warning("Failed to query investigation report from database by key [%s]: %s", key, exc)

    return None


def set_cached_report(key: str, report: InvestigationReport) -> None:
    """Populates the in-memory fast retrieval cache."""
    _REPORT_CACHE[key] = report
    if getattr(report, "report_id", None):
        _REPORT_CACHE[report.report_id] = report
    if getattr(report, "inspection_id", None):
        _REPORT_CACHE[report.inspection_id] = report
    if getattr(report, "staged_batch_id", None):
        _REPORT_CACHE[report.staged_batch_id] = report


def persist_investigation_report(
    db: Session,
    report: InvestigationReport,
    inspection_id: Optional[str] = None,
    staged_batch_id: Optional[str] = None,
    title: Optional[str] = None,
    status: str = "COMPLETED",
) -> None:
    """
    Persists complete investigation report into Neon PostgreSQL.
    Idempotent on retries: updates existing record if report_id exists.
    """
    report_dict = report.model_dump()
    report_dict["investigation_type"] = "DATA_UPLOAD_INVESTIGATION"
    report_dict["report_type"] = "DATA_UPLOAD_INVESTIGATION"
    insp_id = inspection_id or report.inspection_id
    rep_title = title or report.executive_finding.headline or "Manufacturing Cost Investigation"

    scope_dict = report.scope.model_dump() if hasattr(report.scope, "model_dump") else (report.scope or {})
    if isinstance(scope_dict, dict):
        scope_dict["investigation_type"] = "DATA_UPLOAD_INVESTIGATION"
        scope_dict["report_type"] = "DATA_UPLOAD_INVESTIGATION"

    # Also keep in-memory cache hot
    set_cached_report(report.report_id, report)
    if insp_id:
        set_cached_report(insp_id, report)

    try:
        existing = (
            db.query(InvestigationReportRecord)
            .filter_by(report_id=report.report_id)
            .first()
        )
        if existing:
            clean_files = list(dict.fromkeys(report.uploaded_files or []))
            clean_types = getattr(report.scope, "dataset_types", None) or ["MANUFACTURING_COST"]

            existing.inspection_id = insp_id
            existing.title = rep_title
            existing.status = status
            existing.data_origin = report.data_origin
            existing.uploaded_files = clean_files
            existing.dataset_types = clean_types
            existing.source_batch_id = staged_batch_id or report.staged_batch_id
            existing.data_scope = scope_dict
            existing.executive_summary = report.executive_finding.headline
            existing.findings = [f.model_dump() for f in report.findings]
            existing.details = report.calculation_details or {}
            existing.report_json = report_dict
            existing.completed_at = dt.datetime.now(dt.timezone.utc)
            db.commit()
            logger.info("Updated existing investigation report record [%s] in Neon DB", report.report_id)
        else:
            clean_files = list(dict.fromkeys(report.uploaded_files or []))
            clean_types = getattr(report.scope, "dataset_types", None) or ["MANUFACTURING_COST"]

            rec = InvestigationReportRecord(
                report_id=report.report_id,
                inspection_id=insp_id,
                title=rep_title,
                status=status,
                data_origin=report.data_origin,
                is_synthetic=(report.data_origin == "SYNTHETIC_TEST"),
                uploaded_files=clean_files,
                dataset_types=clean_types,
                source_batch_id=staged_batch_id or report.staged_batch_id,
                data_scope=scope_dict,
                executive_summary=report.executive_finding.headline,
                findings=[f.model_dump() for f in report.findings],
                details=report.calculation_details or {},
                report_json=report_dict,
                completed_at=dt.datetime.now(dt.timezone.utc),
            )
            db.add(rec)
            db.commit()
            logger.info("Successfully persisted new investigation report [%s] to Neon DB", report.report_id)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist investigation report [%s] to database: %s", report.report_id, exc)


def persist_failed_investigation(
    db: Session,
    inspection_id: str,
    error_message: str,
    uploaded_files: list[str],
) -> None:
    """Records a failed inspection attempt in database to preserve audit trail."""
    try:
        report_id = f"FAILED-{inspection_id}"
        existing = db.query(InvestigationReportRecord).filter_by(report_id=report_id).first()
        if not existing:
            rec = InvestigationReportRecord(
                report_id=report_id,
                inspection_id=inspection_id,
                title=f"Failed Investigation ({inspection_id})",
                status="FAILED",
                data_origin="REAL",
                is_synthetic=False,
                uploaded_files=uploaded_files,
                dataset_types=[],
                data_scope={},
                executive_summary=error_message,
                findings=[],
                details={"error": error_message},
                report_json={"error": error_message, "status": "FAILED"},
                completed_at=dt.datetime.now(dt.timezone.utc),
            )
            db.add(rec)
            db.commit()
            logger.info("Recorded failed investigation [%s] in Neon DB", inspection_id)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to record failed investigation in database: %s", exc)


def list_investigation_history(
    db: Session,
    limit: int = 50,
    offset: int = 0,
) -> list[InvestigationHistoryItem]:
    """Retrieves paginated investigation reports history, newest first."""
    try:
        records = (
            db.query(InvestigationReportRecord)
            .order_by(InvestigationReportRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        from app.services.reports_service import extract_period_label
        items = []
        for r in records:
            uploaded = r.uploaded_files or []
            scope = r.data_scope or {}
            dt_obj = r.created_at or dt.datetime.now(dt.timezone.utc)
            period_label = extract_period_label(r.title, scope, dt_obj)

            items.append(
                InvestigationHistoryItem(
                    report_id=r.report_id,
                    inspection_id=r.inspection_id,
                    title=r.title,
                    status=r.status,
                    created_at=r.created_at.isoformat() if r.created_at else dt.datetime.now(dt.timezone.utc).isoformat(),
                    completed_at=r.completed_at.isoformat() if r.completed_at else None,
                    uploaded_file_count=len(uploaded) if uploaded else 1,
                    uploaded_files=uploaded,
                    dataset_types=r.dataset_types or ["MANUFACTURING_COST"],
                    reporting_period=period_label,
                    executive_finding=r.executive_summary,
                    data_origin=r.data_origin or "REAL",
                    is_synthetic=bool(r.is_synthetic),
                )
            )
        return items
    except Exception as exc:
        logger.error("Failed to list investigation history from Neon DB: %s", exc)
        return []


def clear_report_cache() -> None:
    _REPORT_CACHE.clear()


