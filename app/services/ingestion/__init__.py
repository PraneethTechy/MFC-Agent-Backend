"""
Manufacturing Cost Agent - Ingestion Subsystem Package
Aggregates file streaming, SHA-256 verification, staging, validation,
transformation, and promotion for manufacturing data.
"""

from .config import (
    EXPECTED_CHECKSUMS,
    EXPECTED_ROW_COUNTS,
    EXPECTED_COST_TOTALS,
    EXPECTED_PRODUCTION_METRICS,
    EXPECTED_QUALITY_METRICS,
    MAX_FILE_SIZE_BYTES,
    CHUNK_SIZE_ROWS,
)
from .checksum import ChecksumVerifier
from .csv_reader import CsvReader
from .staging_loader import StagingLoader
from .validator import DataValidator
from .transformer import DataTransformer
from .promotion_service import PromotionService
from .import_manager import ImportManager
from .legacy import (
    DATASET_SCHEMAS,
    IngestionService,
    ingestion_service,
)

__all__ = [
    "EXPECTED_CHECKSUMS",
    "EXPECTED_ROW_COUNTS",
    "EXPECTED_COST_TOTALS",
    "EXPECTED_PRODUCTION_METRICS",
    "EXPECTED_QUALITY_METRICS",
    "MAX_FILE_SIZE_BYTES",
    "CHUNK_SIZE_ROWS",
    "ChecksumVerifier",
    "CsvReader",
    "StagingLoader",
    "DataValidator",
    "DataTransformer",
    "PromotionService",
    "ImportManager",
    "DATASET_SCHEMAS",
    "IngestionService",
    "ingestion_service",
]

