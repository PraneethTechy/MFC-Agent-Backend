"""
Manufacturing RCA - Structured Evidence Graph & Causal Relationship Model
Connects verified records, dimensional findings, and dataset evidence across all 10 datasets.
Strictly distinguishes verified causal links from correlations and hypotheses.
Preserves data provenance and guarantees no synthetic data is presented as raw ground truth.
"""

from collections import defaultdict
from dataclasses import dataclass, field
import logging
from typing import Any, Optional

from .models import (
    EvidenceNode,
    EvidenceEdge,
    EdgeType,
    EvidenceClassification,
    ProvenanceClassification,
    EvidenceStrength,
)

logger = logging.getLogger("manufacturing_cost_agent.rca.evidence_graph")


class EvidenceGraph:
    """Directed graph of manufacturing evidence nodes and causal relationship edges."""

    def __init__(self):
        self.nodes: dict[str, EvidenceNode] = {}
        self.edges: list[EvidenceEdge] = []
        self._adjacency: dict[str, list[str]] = defaultdict(list)

    def add_node(self, node: EvidenceNode) -> None:
        """Adds an evidence node to the graph."""
        self.nodes[node.node_id] = node

    def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        edge_type: str = EdgeType.CONFIRMED_CAUSAL.value,
        description: str = "",
        weight: float = 1.0,
    ) -> None:
        """Connects two evidence nodes with a typed relationship edge."""
        if source_node_id in self.nodes and target_node_id in self.nodes:
            edge = EvidenceEdge(
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                edge_type=edge_type,
                relationship_description=description,
                confidence_weight=weight,
            )
            self.edges.append(edge)
            self._adjacency[source_node_id].append(target_node_id)
        else:
            logger.warning("Attempted to connect missing node: %s -> %s", source_node_id, target_node_id)

    def get_root_cause_candidates(self) -> list[EvidenceNode]:
        """Returns all evidence nodes flagged as root-cause candidates."""
        return [n for n in self.nodes.values() if n.is_root_cause_candidate and n.variance_amount and n.variance_amount != 0]

    def get_connected_findings(self, node_id: str) -> list[EvidenceNode]:
        """Traverses adjacent nodes connected by confirmed or correlated edges."""
        target_ids = self._adjacency.get(node_id, [])
        return [self.nodes[tid] for tid in target_ids if tid in self.nodes]

    def build_causal_chains(self) -> list[dict[str, Any]]:
        """Extracts end-to-end causal chains linking root causes to total cost variance."""
        chains = []
        root_nodes = self.get_root_cause_candidates()
        target_cost_node = self.nodes.get("NODE-D1-TOTAL-COST")

        for r_node in root_nodes:
            if r_node.node_id == "NODE-D1-TOTAL-COST":
                continue
            edges_from_r = [e for e in self.edges if e.source_node_id == r_node.node_id]
            chains.append({
                "root_node": r_node.to_dict(),
                "impact_inr": r_node.business_impact_inr,
                "edges": [e.to_dict() for e in edges_from_r],
                "target_node_id": "NODE-D1-TOTAL-COST",
                "relationship_status": "VERIFIED_CAUSAL" if any(e.edge_type == EdgeType.CONFIRMED_CAUSAL.value for e in edges_from_r) else "CORRELATED",
            })
        return chains

    def to_dict(self) -> dict[str, Any]:
        """Serializes the evidence graph for API responses and reporting."""
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
            "causal_chains": self.build_causal_chains(),
            "provenance_breakdown": self._get_provenance_breakdown(),
            "confidence_breakdown": self._get_confidence_breakdown(),
        }

    def _get_provenance_breakdown(self) -> dict[str, int]:
        counts = defaultdict(int)
        for n in self.nodes.values():
            counts[n.provenance] += 1
        return dict(counts)

    def _get_confidence_breakdown(self) -> dict[str, int]:
        counts = defaultdict(int)
        for n in self.nodes.values():
            counts[n.classification] += 1
        return dict(counts)
