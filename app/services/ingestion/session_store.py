"""
Session Data Store for Manufacturing Upload Sessions.
Provides durable, isolated file-based storage for uncommitted upload packages.
Guarantees that uploaded test datasets (e.g. November 2026 Claude-generated datasets)
are preserved on disk, retrievable across server restarts, and completely isolated
from Neon PostgreSQL production fact tables.
"""

import json
import logging
import os
import shutil
import time
from typing import Any, Optional

logger = logging.getLogger("manufacturing_cost_agent.ingestion.session_store")

SESSIONS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "sessions")
)
BENCHMARK_CSV_DIR = r"C:\Users\gwc\Downloads\manufacturing-agent-test-dataset\manufacturing-agent-test-dataset\csv"


class SessionDataStore:
    """Manages session-scoped dataset packages on local filesystem with in-memory caching."""

    _cache: dict[str, dict[str, Any]] = {}
    _active_session_id: Optional[str] = None

    @classmethod
    def _ensure_dir(cls) -> str:
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        return SESSIONS_DIR

    @classmethod
    def save_session(
        cls,
        session_id: str,
        datasets: dict[str, Any],
        data_origin: str = "SYNTHETIC_TEST",
        metadata: Optional[dict[str, Any]] = None,
        set_as_active: bool = True,
    ) -> str:
        """
        Durably saves a multi-dataset upload session to disk.
        Each dataset is serialized to a separate JSON file in data/sessions/{session_id}/.
        """
        cls._ensure_dir()
        session_path = os.path.join(SESSIONS_DIR, session_id)
        os.makedirs(session_path, exist_ok=True)

        manifest = {
            "session_id": session_id,
            "created_at": time.time(),
            "data_origin": data_origin,
            "dataset_count": len(datasets),
            "datasets": list(datasets.keys()),
            "metadata": metadata or {},
        }

        # Write each dataset to disk
        for dataset_key, dataset_val in datasets.items():
            fn = f"{dataset_key}.json"
            fp = os.path.join(session_path, fn)
            try:
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(dataset_val, f, ensure_ascii=False)
            except Exception as e:
                logger.error("Failed saving dataset %s for session %s: %s", dataset_key, session_id, e)

        # Write manifest
        manifest_fp = os.path.join(session_path, "manifest.json")
        with open(manifest_fp, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        # Update latest active session pointer if requested
        if set_as_active:
            latest_fp = os.path.join(SESSIONS_DIR, "latest_session.json")
            with open(latest_fp, "w", encoding="utf-8") as f:
                json.dump({"active_session_id": session_id, "updated_at": time.time()}, f, indent=2)
            cls._active_session_id = session_id

        cls._cache[session_id] = datasets
        logger.info("Saved upload session [%s] with %d datasets to %s", session_id, len(datasets), session_path)
        return session_id

    @classmethod
    def get_session(cls, session_id: str) -> Optional[dict[str, Any]]:
        """Retrieves all parsed datasets for a given session ID."""
        if session_id in cls._cache:
            return cls._cache[session_id]

        cls._ensure_dir()
        session_path = os.path.join(SESSIONS_DIR, session_id)
        if not os.path.exists(session_path):
            return None

        manifest_fp = os.path.join(session_path, "manifest.json")
        if not os.path.exists(manifest_fp):
            return None

        try:
            with open(manifest_fp, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            logger.error("Failed reading manifest for session %s: %s", session_id, e)
            return None

        datasets = {}
        for dk in manifest.get("datasets", []):
            dfp = os.path.join(session_path, f"{dk}.json")
            if os.path.exists(dfp):
                try:
                    with open(dfp, "r", encoding="utf-8") as f:
                        datasets[dk] = json.load(f)
                except Exception as e:
                    logger.error("Failed loading dataset %s for session %s: %s", dk, session_id, e)

        if datasets:
            cls._cache[session_id] = datasets
            cls._active_session_id = session_id
            return datasets

        return None

    @classmethod
    def reset_in_memory_state(cls) -> None:
        """
        Simulates backend restart or reinitialization by clearing in-memory caches
        and active session pointers. Persisted files on disk are completely untouched.
        """
        cls._cache.clear()
        cls._active_session_id = None
        logger.info("SessionDataStore in-memory cache and state reset.")

    @classmethod
    def get_active_session_id(cls) -> Optional[str]:
        """Returns the ID of the latest active upload session."""
        if cls._active_session_id:
            # Verify session still exists on disk
            cls._ensure_dir()
            if os.path.exists(os.path.join(SESSIONS_DIR, cls._active_session_id)):
                return cls._active_session_id
            cls._active_session_id = None

        cls._ensure_dir()
        latest_fp = os.path.join(SESSIONS_DIR, "latest_session.json")
        if os.path.exists(latest_fp):
            try:
                with open(latest_fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sid = data.get("active_session_id")
                    if sid and os.path.exists(os.path.join(SESSIONS_DIR, sid)):
                        cls._active_session_id = sid
                        return cls._active_session_id
            except Exception:
                pass

        # Do not automatically seed or fall back to synthetic benchmark
        return None

    @classmethod
    def set_active_session_id(cls, session_id: str) -> bool:
        """Explicitly sets the active upload session ID."""
        cls._ensure_dir()
        if not os.path.exists(os.path.join(SESSIONS_DIR, session_id)):
            return False
        latest_fp = os.path.join(SESSIONS_DIR, "latest_session.json")
        try:
            with open(latest_fp, "w", encoding="utf-8") as f:
                json.dump({"active_session_id": session_id, "updated_at": time.time()}, f, indent=2)
            cls._active_session_id = session_id
            return True
        except Exception as e:
            logger.error("Could not write latest_session.json: %s", e)
            return False

    @classmethod
    def get_active_session(cls) -> Optional[tuple[str, dict[str, Any]]]:
        """Returns tuple (session_id, datasets_dict) for active session."""
        sid = cls.get_active_session_id()
        if not sid:
            return None
        data = cls.get_session(sid)
        if not data:
            return None
        return sid, data

    @classmethod
    def get_session_info(cls, session_id: str) -> Optional[dict[str, Any]]:
        """Returns metadata, dataset counts, and validation summary for a given session."""
        cls._ensure_dir()
        spath = os.path.join(SESSIONS_DIR, session_id)
        mfp = os.path.join(spath, "manifest.json")
        if not (os.path.isdir(spath) and os.path.exists(mfp)):
            return None
        try:
            with open(mfp, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            datasets = cls.get_session(session_id) or {}
            row_counts = {
                k: (v.get("total_rows") or len(v.get("rows", [])) or len(v.get("raw_rows", [])))
                if isinstance(v, dict)
                else (len(v) if isinstance(v, list) else 0)
                for k, v in datasets.items()
            }
            meta = manifest.get("metadata", {})
            total_rows = sum(row_counts.values()) or meta.get("total_rows", 0)
            return {
                "session_id": session_id,
                "created_at": manifest.get("created_at"),
                "data_origin": manifest.get("data_origin", "SYNTHETIC_TEST"),
                "dataset_count": len(datasets),
                "datasets": list(datasets.keys()),
                "row_counts": row_counts,
                "total_rows": total_rows,
                "metadata": meta,
                "files": meta.get("uploaded_files", [f"{k.lower()}.csv" for k in datasets.keys()]),
                "is_valid": len(datasets) > 0 or meta.get("status") == "PROCESSING",
                "status": meta.get("status", "VALIDATED" if len(datasets) >= 6 else "PARTIAL"),
            }
        except Exception as e:
            logger.error("Error reading session info for %s: %s", session_id, e)
            return None

    @classmethod
    def list_sessions(cls) -> list[dict[str, Any]]:
        """Lists metadata of all available sessions on disk."""
        cls._ensure_dir()
        sessions = []
        for name in os.listdir(SESSIONS_DIR):
            spath = os.path.join(SESSIONS_DIR, name)
            mfp = os.path.join(spath, "manifest.json")
            if os.path.isdir(spath) and os.path.exists(mfp):
                try:
                    with open(mfp, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        sessions.append(meta)
                except Exception:
                    pass
        sessions.sort(key=lambda s: s.get("created_at", 0), reverse=True)
        return sessions

    @classmethod
    def get_or_create_default_benchmark_session(cls) -> Optional[str]:
        """
        Seeds the default November 2026 benchmark session from test CSV directory
        if it hasn't been seeded yet.
        """
        benchmark_id = "session_nov_2026_test"
        existing = cls.get_session(benchmark_id)
        if existing:
            return benchmark_id

        if not os.path.exists(BENCHMARK_CSV_DIR):
            logger.warning("Benchmark CSV directory not found at: %s", BENCHMARK_CSV_DIR)
            return None

        try:
            import csv
            datasets = {}
            mapping_rules = {
                "test_fact_manufacturing_cost.csv": "MANUFACTURING_COST",
                "test_fact_hourly_production.csv": "HOURLY_PRODUCTION",
                "test_fact_bom_component.csv": "BOM_COMPONENT",
                "test_fact_material_purchase.csv": "MATERIAL_PURCHASE",
                "test_fact_material_consumption.csv": "MATERIAL_CONSUMPTION",
                "test_fact_quality_inspection.csv": "QUALITY_INSPECTION",
                "test_fact_quality_rework_events.csv": "QUALITY_REWORK_EVENTS",
            }

            for fn, dtype in mapping_rules.items():
                fp = os.path.join(BENCHMARK_CSV_DIR, fn)
                if not os.path.exists(fp):
                    continue
                with open(fp, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    headers = reader.fieldnames or []
                    rows = list(reader)
                    datasets[dtype] = {
                        "filename": fn,
                        "dataset_type": dtype,
                        "headers": list(headers),
                        "column_mapping": {h: h for h in headers},
                        "rows": rows,
                        "raw_rows": rows,
                        "valid_count": len(rows),
                        "total_rows": len(rows),
                    }

            if datasets:
                cls.save_session(
                    session_id=benchmark_id,
                    datasets=datasets,
                    data_origin="SYNTHETIC_TEST",
                    metadata={
                        "title": "November 2026 Benchmark Test Package",
                        "source": "Claude-generated November 2026 test datasets",
                        "file_count": len(datasets),
                        "total_rows": sum(d.get("total_rows", 0) for d in datasets.values()),
                    },
                )
                logger.info("Successfully initialized default benchmark session [%s]", benchmark_id)
                return benchmark_id
        except Exception as e:
            logger.error("Failed creating benchmark session: %s", e)

        return None
