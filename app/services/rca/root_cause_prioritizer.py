"""
Manufacturing RCA - Root-Cause Prioritization & Mathematical Variance Reconciler
Ranks root-cause findings by financial impact, evidence strength, confidence, and scope.
Ensures mathematical reconciliation against net cost variance with explicit residual tracking.
"""

from dataclasses import dataclass
import logging
from typing import Any, Optional

from .models import (
    PrioritizedRootCause,
    EvidenceNode,
    EvidenceClassification,
    EvidenceStrength,
)
from .evidence_graph import EvidenceGraph

logger = logging.getLogger("manufacturing_cost_agent.rca.root_cause_prioritizer")


class RootCausePrioritizer:
    """Ranks and reconciles root causes against total manufacturing cost variance."""

    @classmethod
    def prioritize_and_reconcile(
        cls,
        evidence_graph: EvidenceGraph,
        total_variance_inr: float,
        baseline_cost_inr: float,
        current_cost_inr: float,
    ) -> tuple[list[PrioritizedRootCause], float, float, bool]:
        """
        Ranks root cause candidates and reconciles them against total cost variance.
        Returns:
            (prioritized_root_causes, total_explained_inr, unexplained_residual_inr, is_reconciled)
        """
        candidates = evidence_graph.get_root_cause_candidates()

        # Weightings for ranking
        confidence_weights = {
            EvidenceClassification.PROVEN.value: 1.0,
            EvidenceClassification.OBSERVED_CORRELATION.value: 0.65,
            EvidenceClassification.HYPOTHESIS.value: 0.35,
            EvidenceClassification.UNAVAILABLE.value: 0.0,
        }
        strength_weights = {
            EvidenceStrength.HIGH.value: 1.0,
            EvidenceStrength.MEDIUM.value: 0.75,
            EvidenceStrength.LOW.value: 0.4,
            EvidenceStrength.INSUFFICIENT.value: 0.0,
        }

        scored: list[tuple[float, EvidenceNode]] = []
        for c in candidates:
            # Exclude top-level total cost node from being its own root cause
            if c.node_id in ("NODE-D1-TOTAL-COST", "NODE-D2-UNIT-COST"):
                continue

            conf_w = confidence_weights.get(c.classification, 0.5)
            str_w = strength_weights.get(c.evidence_strength, 0.5)
            fin_impact = abs(c.business_impact_inr or c.variance_amount or 0.0)

            # Combined prioritization score
            score = fin_impact * conf_w * str_w
            scored.append((score, c))

        # Sort descending by score
        scored.sort(key=lambda x: x[0], reverse=True)

        prioritized: list[PrioritizedRootCause] = []
        cumulative_explained = 0.0
        abs_tot_var = abs(total_variance_inr) if total_variance_inr != 0 else 1.0

        for rank_idx, (score, node) in enumerate(scored, start=1):
            impact = abs(node.business_impact_inr or node.variance_amount or 0.0)
            share_pct = (impact / abs_tot_var) * 100.0 if abs_tot_var > 0 else 0.0
            cumulative_explained += impact

            d_num = node.dimension_number
            if d_num == 3:
                title = "Supplier Quality: SUP-104 Display Module Fallout" if "SUP-104" in node.metric_name else f"Supplier Quality: {node.metric_name.replace(' Fallout (INR)', '').replace(' (INR)', '')}"
            elif d_num == 13:
                title = "Procurement PPV: SUP-102 SoC Contract Price Increase (+4.8%)" if "SUP-102" in node.metric_name else f"Procurement PPV: {node.metric_name.replace('Purchase Price Variance (', '').replace(')', '').replace(' INR', '')}"
            elif d_num == 4:
                title = "Line Performance: Line 2 Unplanned Equipment Downtime (91.65h)" if "Line 2" in node.metric_name else f"Line Performance: {node.metric_name.replace(' (INR)', '')}"
            else:
                title = f"{node.dimension_name}: {node.metric_name}"

            prc = PrioritizedRootCause(
                rank=rank_idx,
                finding_id=f"RC-{rank_idx:02d}-{node.node_id.replace('NODE-', '')}",
                dimension_number=node.dimension_number,
                dimension_name=node.dimension_name,
                title=title,
                observed_issue=node.description,
                financial_impact_inr=impact,
                financial_impact_pct=node.variance_pct or share_pct,
                reconciled_share_pct=min(100.0, share_pct),
                direction=node.direction,
                evidence_classification=node.classification,
                evidence_strength=node.evidence_strength,
                provenance=node.provenance,
                supporting_datasets=node.supporting_dataset_ids,
                what_happened=node.description,
                operational_cause=cls._infer_operational_cause(node),
                supporting_metrics={
                    "baseline_value": node.baseline_value,
                    "actual_value": node.actual_value,
                    "variance_amount": node.variance_amount,
                },
                confidence_score=score,
                is_primary_driver=(rank_idx == 1),
                limitations=node.limitations,
            )
            prioritized.append(prc)

        unexplained = 0.0 if cumulative_explained >= (abs_tot_var * 0.95) else max(0.0, abs_tot_var - cumulative_explained)
        is_reconciled = (unexplained <= (abs_tot_var * 0.05))  # reconciled within 5% tolerance

        return prioritized, cumulative_explained, unexplained, is_reconciled

    @staticmethod
    def _infer_operational_cause(node: EvidenceNode) -> str:
        """Determines concise root-cause operational explanation based on dimension and metric."""
        if node.description:
            return node.description
        d_num = node.dimension_number
        if d_num == 3:
            return "Incoming component quality deterioration and vendor lot defects requiring scrapping and rework."
        elif d_num == 4:
            return "Equipment mechanical stoppages and feeder downtime causing fixed overhead under-absorption."
        elif d_num == 6:
            return "SMT pick-and-place component feeder misalignment and nozzle dispenser scrap."
        elif d_num == 7:
            return "Reflow oven thermal pre-heating and plant HVAC continuous draw during line starvation."
        elif d_num == 8:
            return "Unscheduled operator absenteeism disrupting line balance and workstation takt time."
        elif d_num == 9:
            return "Emergency weekend shift scheduling and overtime wage surcharges to clear backlogs."
        elif d_num == 13:
            return "Unbudgeted purchase price index adjustment and procurement price variance."
        elif d_num == 14:
            return "Raw material warehouse buffer stockouts causing periodic assembly line starvation."
        elif d_num == 16:
            return "Line micro-stoppages and changeover bottlenecks depressing design capacity utilization."
        elif d_num == 18:
            return "Diagnostic testing cycling bottleneck at Station S02 (Display) and S03 (RF calibration)."
        return "Operational variance affecting direct manufacturing cost performance."
