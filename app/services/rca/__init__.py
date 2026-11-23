"""
Manufacturing Root Cause Analysis (RCA) Intelligence Engine Package.
Authoritative implementation of Task 4:
- Dynamic Dataset & Period Discovery
- 15-Dimension Analytical Engine
- Intelligent Investigation Planner (Dynamic Causal Expansion)
- Structured Evidence Graph & Provenance Isolation
- Root-Cause Prioritization & Mathematical Reconciliation
- Evidence-Grounded Corrective Recommendation Engine
- Master RCA Orchestrator
"""

from .models import (
    EvidenceClassification,
    ProvenanceClassification,
    EvidenceStrength,
    EdgeType,
    EvidenceNode,
    EvidenceEdge,
    DimensionAnalysisResult,
    PlannerDecision,
    PrioritizedRootCause,
    CorrectiveRecommendation,
)
from .period_baseline import DynamicBaselineResolver, DynamicComparisonScope
from .dimension_engine import DimensionAnalyticsEngine
from .evidence_graph import EvidenceGraph
from .investigation_planner import InvestigationPlanner
from .root_cause_prioritizer import RootCausePrioritizer
from .recommendation_engine import CorrectiveRecommendationEngine
from .orchestrator import RCAOrchestrator

__all__ = [
    "EvidenceClassification",
    "ProvenanceClassification",
    "EvidenceStrength",
    "EdgeType",
    "EvidenceNode",
    "EvidenceEdge",
    "DimensionAnalysisResult",
    "PlannerDecision",
    "PrioritizedRootCause",
    "CorrectiveRecommendation",
    "DynamicBaselineResolver",
    "DynamicComparisonScope",
    "DimensionAnalyticsEngine",
    "EvidenceGraph",
    "InvestigationPlanner",
    "RootCausePrioritizer",
    "CorrectiveRecommendationEngine",
    "RCAOrchestrator",
]
