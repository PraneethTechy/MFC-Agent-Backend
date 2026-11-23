"""
Manufacturing Dataset Registry - Data Models
Defines domain models for logical datasets, physical source references,
granularities, provenance tiers, and relationship statuses.
Pure standard Python using dataclasses (Zero Pydantic dependency).
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class GranularityType(str, Enum):
    """Temporal and operational granularity of a manufacturing dataset."""
    HOURLY = "HOURLY"
    BATCH_SLOT = "BATCH_SLOT"
    TRANSACTION = "TRANSACTION"
    SHIFT = "SHIFT"
    DAILY = "DAILY"
    STATIC_SPEC = "STATIC_SPEC"


class ProvenanceTier(str, Enum):
    """Data provenance classification ensuring strict evidence governance."""
    RAW_BASELINE = "RAW_BASELINE"
    ENHANCED_BASELINE = "ENHANCED_BASELINE"
    SYNTHETIC_EXTENSION = "SYNTHETIC_EXTENSION"
    USER_UPLOADED = "USER_UPLOADED"


class RelationshipStatus(str, Enum):
    """Referential linkage certainty between datasets."""
    CONFIRMED = "CONFIRMED"          # Formally validated referential integrity (e.g. D8 GR -> D7 Goods Receipt)
    CANDIDATE_ONLY = "CANDIDATE_ONLY"# Plausible join key, but unverified accounting or campaign continuity
    UNMATCHED = "UNMATCHED"          # Known missing linkage (e.g. employee badge to phone serial number)


@dataclass
class ColumnMetadata:
    """Metadata describing an individual column in a manufacturing dataset."""
    name: str
    data_type: str
    business_meaning: str
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_date_column: bool = False
    is_nullable: bool = True

    def dict(self) -> dict[str, Any]:
        return asdict(self)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PhysicalSourceReference:
    """Reference to a physical CSV file or database table backing a logical dataset."""
    source_type: str
    location: str
    row_count: int = 0
    column_count: int = 0
    date_column: Optional[str] = None
    available_date_range: Optional[str] = None
    sha256_checksum: Optional[str] = None
    is_synthetic: bool = False
    data_origin: Optional[str] = None

    def dict(self) -> dict[str, Any]:
        return asdict(self)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetRelationship:
    """Specification of referential or candidate linkage between two logical datasets."""
    target_dataset_id: str
    local_key: str
    target_key: str
    relationship_type: str
    status: RelationshipStatus
    caveat: Optional[str] = None

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        if isinstance(self.status, RelationshipStatus):
            d["status"] = self.status.value
        return d

    def model_dump(self) -> dict[str, Any]:
        return self.dict()


@dataclass
class LogicalDatasetDefinition:
    """Authoritative metadata specification of one of the 10 logical manufacturing datasets."""
    dataset_id: str
    domain_code: str
    name: str
    category: str
    business_description: str
    default_granularity: GranularityType
    primary_identifier: str
    provenance_tier: ProvenanceTier
    supported_dimensions: list[int] = field(default_factory=list)
    date_columns: list[str] = field(default_factory=list)
    physical_sources: list[PhysicalSourceReference] = field(default_factory=list)
    columns: list[ColumnMetadata] = field(default_factory=list)
    relationships: list[DatasetRelationship] = field(default_factory=list)
    known_limitations: list[str] = field(default_factory=list)
    is_active: bool = True

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["default_granularity"] = self.default_granularity.value if hasattr(self.default_granularity, "value") else str(self.default_granularity)
        d["provenance_tier"] = self.provenance_tier.value if hasattr(self.provenance_tier, "value") else str(self.provenance_tier)
        d["physical_sources"] = [s.dict() if hasattr(s, "dict") else asdict(s) for s in self.physical_sources]
        d["columns"] = [c.dict() if hasattr(c, "dict") else asdict(c) for c in self.columns]
        d["relationships"] = [r.dict() if hasattr(r, "dict") else asdict(r) for r in self.relationships]
        return d

    def model_dump(self) -> dict[str, Any]:
        return self.dict()
