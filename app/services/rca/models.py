"""
Manufacturing Root Cause Analysis (RCA) - Domain Models
Lightweight, standard Python dataclasses for evidence nodes, dimensional results,
planner decisions, prioritized root causes, and corrective recommendations.
Strictly zero-Pydantic domain models conforming to project guidelines.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class EvidenceClassification(str, Enum):
    """Authoritative classification of evidence certainty."""
    PROVEN = "PROVEN"
    OBSERVED_CORRELATION = "OBSERVED_CORRELATION"
    HYPOTHESIS = "HYPOTHESIS"
    UNAVAILABLE = "UNAVAILABLE"


class ProvenanceClassification(str, Enum):
    """Authoritative classification of data source origin."""
    RAW_BASELINE = "RAW_BASELINE"
    ENHANCED_BASELINE = "ENHANCED_BASELINE"
    SYNTHETIC_GENERATED = "SYNTHETIC_GENERATED"
    MIXED = "MIXED"


class EvidenceStrength(str, Enum):
    """Evaluation of evidence volume and statistical robustness."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class EdgeType(str, Enum):
    """Causal relationship types in the evidence graph."""
    CONFIRMED_CAUSAL = "CONFIRMED_CAUSAL"  # Mathematically or referentially verified link
    CORRELATED = "CORRELATED"              # Observed statistical co-movement without record-level trace
    EXPLORATORY = "EXPLORATORY"            # Plausible hypothesis requiring further data collection


@dataclass
class EvidenceNode:
    """A discrete verifiable evidence point in the RCA evidence graph."""
    node_id: str
    dimension_number: int
    dimension_name: str
    metric_name: str
    baseline_value: Optional[float] = None
    actual_value: Optional[float] = None
    variance_amount: Optional[float] = None
    variance_pct: Optional[float] = None
    direction: str = "NEUTRAL"  # UNFAVOURABLE, FAVOURABLE, NEUTRAL
    classification: str = "PROVEN"  # PROVEN, OBSERVED_CORRELATION, HYPOTHESIS, UNAVAILABLE
    provenance: str = "RAW_BASELINE"  # RAW_BASELINE, ENHANCED_BASELINE, SYNTHETIC_GENERATED
    evidence_strength: str = "HIGH"
    supporting_dataset_ids: list[str] = field(default_factory=list)
    supporting_records_count: int = 0
    records_sample: list[dict[str, Any]] = field(default_factory=list)
    description: str = ""
    business_impact_inr: float = 0.0
    is_root_cause_candidate: bool = False
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceEdge:
    """Directed connection linking evidence nodes across datasets."""
    source_node_id: str
    target_node_id: str
    edge_type: str = "CONFIRMED_CAUSAL"
    relationship_description: str = ""
    confidence_weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DimensionAnalysisResult:
    """Complete analytical outcome for an individual manufacturing dimension."""
    dimension_number: int
    dimension_name: str
    status: str  # 'INVESTIGATED', 'SKIPPED_INSUFFICIENT_DATA', 'DEFERRED_NO_DATA', 'NO_VARIANCE'
    is_supported: bool = True
    is_deferred: bool = False
    deferral_reason: Optional[str] = None
    primary_dataset_ids: list[str] = field(default_factory=list)
    baseline_value: Optional[float] = None
    actual_value: Optional[float] = None
    variance_amount: Optional[float] = None
    variance_pct: Optional[float] = None
    direction: str = "NEUTRAL"
    evidence_classification: str = "PROVEN"
    provenance: str = "RAW_BASELINE"
    evidence_strength: str = "HIGH"
    financial_impact_inr: float = 0.0
    summary_explanation: str = ""
    detailed_findings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    nodes: list[EvidenceNode] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["nodes"] = [n.to_dict() if isinstance(n, EvidenceNode) else n for n in self.nodes]
        return d


@dataclass
class PlannerDecision:
    """Audit entry documenting dynamic investigation agenda selection or expansion."""
    step_number: int
    action: str  # 'INITIAL_SELECTION', 'CAUSAL_EXPANSION', 'SKIP', 'DEFER', 'TERMINATE'
    dimension_number: int
    dimension_name: str
    trigger_reason: str
    evidence_sufficiency_score: float
    selected_tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PrioritizedRootCause:
    """A quantified and evidence-ranked root cause explaining manufacturing cost movement."""
    rank: int
    finding_id: str
    dimension_number: int
    dimension_name: str
    title: str
    observed_issue: str
    financial_impact_inr: float
    financial_impact_pct: float
    reconciled_share_pct: float
    direction: str = "UNFAVOURABLE"
    evidence_classification: str = "PROVEN"
    evidence_strength: str = "HIGH"
    provenance: str = "RAW_BASELINE"
    supporting_datasets: list[str] = field(default_factory=list)
    what_happened: str = ""
    operational_cause: str = ""
    supporting_metrics: dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 1.0
    is_primary_driver: bool = False
    related_findings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CorrectiveRecommendation:
    """Actionable operational playbook recommendation tied directly to a verified root cause."""
    recommendation_id: str
    title: str
    dimension_number: int
    category: str
    problem_statement: str
    recommended_action: str
    responsible_function: str
    expected_operational_outcome: str
    estimated_savings_amount: Optional[float] = None
    estimated_savings_display: str = "Not Quantified"
    priority: str = "HIGH"
    measurement_kpi: str = ""
    verification_timeframe: str = "2 - 4 Weeks"
    target_kpi: str = ""
    current_measured_value: str = ""
    proposed_target: str = ""
    verification_method: str = ""
    root_cause_finding_id: Optional[str] = None
    confidence: str = "Verified (PROVEN)"
    implementation_steps: list[str] = field(default_factory=list)
    supporting_evidence_summary: str = ""
    key_evidence: list[dict[str, Any]] = field(default_factory=list)
    affected_scope: dict[str, Any] = field(default_factory=dict)
    unit_cost_impact_display: str = ""
    unit_cost_impact_inr: Optional[float] = None
    savings_calculation: dict[str, Any] = field(default_factory=dict)
    financial_breakdown: dict[str, Any] = field(default_factory=dict)
    data_limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
