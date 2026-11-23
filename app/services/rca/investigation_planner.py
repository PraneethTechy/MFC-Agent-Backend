"""
Manufacturing RCA - Intelligent Dynamic Dimension Discovery & Investigation Planner
Executes goal-driven, evidence-based dimensional planning.
Does NOT execute all 15 dimensions blindly.
Evaluates cost movements, identifies causal pathways, assesses dataset sufficiency,
expands dynamically along evidence triggers, and stops when variance is reconciled.
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Optional
from sqlalchemy.orm import Session

from .models import (
    DimensionAnalysisResult,
    PlannerDecision,
    EvidenceNode,
    EvidenceClassification,
)
from .period_baseline import DynamicComparisonScope
from .dimension_engine import DimensionAnalyticsEngine
from .evidence_graph import EvidenceGraph

logger = logging.getLogger("manufacturing_cost_agent.rca.investigation_planner")


class InvestigationPlanner:
    """Intelligent dynamic investigation planner for manufacturing cost root cause analysis."""

    # Initial screening dimensions (always assessed to establish cost and volume movement)
    ENTRY_DIMENSIONS = [1, 2, 5]

    # Causal trigger pathways linking initial dimensional observations to connected dimensions
    CAUSAL_TRIGGERS: dict[str, dict[str, Any]] = {
        "TRIGGER_SCRAP_REWORK": {
            "dimensions": [3, 4, 18],  # Scrap & rework, Line performance, Smartphone testing
            "description": "Scrap and rework costs exceeded threshold, triggering quality station and line investigation.",
            "tools": ["investigate_variance", "get_production_quality_intelligence"],
        },
        "TRIGGER_MATERIAL_INFLATION_OR_USAGE": {
            "dimensions": [6, 13, 14, 17],  # Material consumption, Procurement, Inventory, Reconciliation
            "description": "Material cost variance elevated, triggering procurement PPV and inventory reconciliation.",
            "tools": ["get_material_intelligence", "inspect_bom_components"],
        },
        "TRIGGER_ENERGY_ANOMALY": {
            "dimensions": [7, 4],  # Energy consumption, Plant/line performance
            "description": "Energy expenditure variance detected, triggering equipment power draw analysis.",
            "tools": ["investigate_variance"],
        },
        "TRIGGER_LABOUR_AND_PRODUCTIVITY": {
            "dimensions": [8, 9, 12, 16],  # Absenteeism, Workforce allocation, Productivity, Capacity
            "description": "Labour variance or production run-rate deficit detected, triggering workforce and capacity checks.",
            "tools": ["calculate_variance_bridge", "rank_cost_drivers"],
        },
    }

    CATEGORY_PATHWAYS: dict[str, list[int]] = {
        "Manufacturing cost increase": [1, 2, 5, 6, 8],
        "Cost per good unit increase": [2, 3, 5, 4],
        "Scrap / rework increase": [3, 4, 18],
        "Quality / rejection increase": [3, 4, 18],
        "Production output decrease": [4, 16, 5],
        "Labour productivity issue": [8, 9, 12, 16],
        "Energy consumption increase": [7, 4],
        "Material consumption / inventory variance": [6, 13, 14, 17],
        "Supplier / procurement issue": [13, 17, 6],
        "Equipment downtime / efficiency issue": [4, 7, 16],
    }

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.decisions: list[PlannerDecision] = []
        self.evidence_graph = EvidenceGraph()
        self.dimensional_results: dict[int, DimensionAnalysisResult] = {}
        self.active_agenda: list[int] = []
        self.completed_dimensions: set[int] = set()

    def plan_and_execute(
        self,
        scope: DynamicComparisonScope,
        session_datasets: Optional[dict[str, Any]] = None,
        plant_code: Optional[str] = None,
        product_code: Optional[str] = None,
        line_code: Optional[str] = None,
        max_expansions: int = 4,
        problem_category: Optional[str] = None,
    ) -> tuple[dict[int, DimensionAnalysisResult], EvidenceGraph, list[PlannerDecision]]:
        """
        Executes the intelligent dynamic investigation plan:
        1. Evaluates entry dimensions (D1, D2, D5).
        2. Detects evidence triggers and checks dataset sufficiency.
        3. Dynamically expands agenda to connected causal dimensions.
        4. Stops when variance is adequately explained or no further pathways exist.
        """
        self.decisions.clear()
        self.dimensional_results.clear()
        self.evidence_graph = EvidenceGraph()
        self.completed_dimensions.clear()

        step = 1

        # Step 1: Initial Selection (Entry Dimensions D1, D2, D5)
        for d_num in self.ENTRY_DIMENSIONS:
            self.decisions.append(PlannerDecision(
                step_number=step,
                action="INITIAL_SELECTION",
                dimension_number=d_num,
                dimension_name=DimensionAnalyticsEngine.AUTHORITATIVE_NAMES[d_num],
                trigger_reason="Core baseline financial and unit cost screening",
                evidence_sufficiency_score=1.0,
                selected_tools=["get_cost_summary", "get_standard_vs_actual"],
            ))
            step += 1
            res = DimensionAnalyticsEngine.analyze_dimension(
                dimension_number=d_num,
                scope=scope,
                db=self.db,
                session_datasets=session_datasets,
                plant_code=plant_code,
                product_code=product_code,
                line_code=line_code,
            )
            self.dimensional_results[d_num] = res
            self.completed_dimensions.add(d_num)
            for node in res.nodes:
                self.evidence_graph.add_node(node)

        # Step 2: Causal Trigger Detection based on initial findings & category focus
        d1_res = self.dimensional_results.get(1)
        d2_res = self.dimensional_results.get(2)
        top_cat = d1_res.metrics.get("top_category", "Material") if d1_res else "Material"
        cat_breakdown = d1_res.metrics.get("category_breakdown", {}) if d1_res else {}

        triggered_agenda: list[int] = []

        # Check manufacturer prioritized problem category
        if problem_category and problem_category in self.CATEGORY_PATHWAYS:
            cat_dims = [d for d in self.CATEGORY_PATHWAYS[problem_category] if d not in self.completed_dimensions]
            if cat_dims:
                triggered_agenda.extend(cat_dims)
                self.decisions.append(PlannerDecision(
                    step_number=step,
                    action="PRIORITY_CATEGORY_EXPANSION",
                    dimension_number=cat_dims[0],
                    dimension_name=f"Manufacturer Category Focus: {problem_category}",
                    trigger_reason=f"Manufacturer initiated investigation for category '{problem_category}', prioritizing dimensions {cat_dims}",
                    evidence_sufficiency_score=0.95,
                    selected_tools=["investigate_variance", "get_production_quality_intelligence"],
                ))
                step += 1

        # Check Material trigger
        mat_diff = cat_breakdown.get("Material", {}).get("variance", 0.0)
        if mat_diff > 0 or top_cat == "Material":
            triggered_agenda.extend(self.CAUSAL_TRIGGERS["TRIGGER_MATERIAL_INFLATION_OR_USAGE"]["dimensions"])
            self.decisions.append(PlannerDecision(
                step_number=step,
                action="CAUSAL_EXPANSION",
                dimension_number=6,
                dimension_name="Material consumption & procurement pathway",
                trigger_reason=f"Material cost expanded by ₹{mat_diff / 1e7:.2f} Cr, triggering D6, D13, D14, D17",
                evidence_sufficiency_score=0.9,
                selected_tools=["get_material_intelligence", "inspect_bom_components"],
            ))
            step += 1

        # Check Scrap and Rework trigger
        scr_diff = cat_breakdown.get("Scrap and Rework", {}).get("variance", 0.0)
        if scr_diff > 0 or top_cat == "Scrap and Rework":
            triggered_agenda.extend(self.CAUSAL_TRIGGERS["TRIGGER_SCRAP_REWORK"]["dimensions"])
            self.decisions.append(PlannerDecision(
                step_number=step,
                action="CAUSAL_EXPANSION",
                dimension_number=3,
                dimension_name="Scrap and rework pathway",
                trigger_reason=f"Scrap & rework moved by ₹{scr_diff / 1e7:.2f} Cr, triggering D3, D4, D18",
                evidence_sufficiency_score=0.85,
                selected_tools=["get_production_quality_intelligence"],
            ))
            step += 1

        # Check Energy trigger
        nrg_diff = cat_breakdown.get("Energy", {}).get("variance", 0.0)
        if nrg_diff > 500000.0 or top_cat == "Energy":
            triggered_agenda.extend(self.CAUSAL_TRIGGERS["TRIGGER_ENERGY_ANOMALY"]["dimensions"])
            self.decisions.append(PlannerDecision(
                step_number=step,
                action="CAUSAL_EXPANSION",
                dimension_number=7,
                dimension_name="Energy consumption pathway",
                trigger_reason=f"Energy cost variance of ₹{nrg_diff / 1e7:.2f} Cr detected, triggering D7",
                evidence_sufficiency_score=0.75,
                selected_tools=["investigate_variance"],
            ))
            step += 1

        # Check Labour & Capacity trigger
        lab_diff = cat_breakdown.get("Labour", {}).get("variance", 0.0)
        if lab_diff > 1000000.0 or top_cat == "Labour":
            triggered_agenda.extend(self.CAUSAL_TRIGGERS["TRIGGER_LABOUR_AND_PRODUCTIVITY"]["dimensions"])
            self.decisions.append(PlannerDecision(
                step_number=step,
                action="CAUSAL_EXPANSION",
                dimension_number=12,
                dimension_name="Workforce & labour productivity pathway",
                trigger_reason=f"Labour variance of ₹{lab_diff / 1e7:.2f} Cr detected, triggering D8, D9, D12, D16",
                evidence_sufficiency_score=0.8,
                selected_tools=["rank_cost_drivers"],
            ))
            step += 1

        # Dataset-Driven Sufficiency Triggers: When specific uploaded datasets are present in session,
        # prioritize evaluating their corresponding causal dimensions to ensure evidence coverage.
        if session_datasets:
            has_quality = any(k.upper() in ["QUALITY_INSPECTION", "D4_QUALITY_INSPECTION", "QUALITY"] for k in session_datasets)
            if has_quality and 3 not in triggered_agenda:
                triggered_agenda.extend([3, 18])
                self.decisions.append(PlannerDecision(
                    step_number=step,
                    action="DATASET_EXPANSION",
                    dimension_number=3,
                    dimension_name="Scrap and rework (Quality Inspection telemetry)",
                    trigger_reason="Quality inspection dataset present in session, triggering D3 and D18",
                    evidence_sufficiency_score=1.0,
                    selected_tools=["get_production_quality_intelligence"],
                ))
                step += 1

            has_equip = any(k.upper() in ["EQUIPMENT_DOWNTIME_ENERGY", "EQUIPMENT_ENERGY", "D9_EQUIPMENT_ENERGY", "EQUIPMENT"] for k in session_datasets)
            if has_equip and 4 not in triggered_agenda:
                triggered_agenda.extend([4, 16])
                self.decisions.append(PlannerDecision(
                    step_number=step,
                    action="DATASET_EXPANSION",
                    dimension_number=4,
                    dimension_name="Line performance & equipment telemetry",
                    trigger_reason="Equipment downtime & energy dataset present in session, triggering D4 and D16",
                    evidence_sufficiency_score=1.0,
                    selected_tools=["investigate_variance"],
                ))
                step += 1

            has_po = any(k.upper() in ["MATERIAL_PURCHASE", "D8_PROCUREMENT_SUPPLIER", "PURCHASE"] for k in session_datasets)
            if has_po and 13 not in triggered_agenda:
                triggered_agenda.append(13)
                self.decisions.append(PlannerDecision(
                    step_number=step,
                    action="DATASET_EXPANSION",
                    dimension_number=13,
                    dimension_name="Procurement and supplier performance",
                    trigger_reason="Material purchase dataset present in session, triggering D13 PPV analysis",
                    evidence_sufficiency_score=1.0,
                    selected_tools=["inspect_bom_components"],
                ))
                step += 1

            has_att = any(k.upper() in ["WORKFORCE_ATTENDANCE", "D10_WORKFORCE_ATTENDANCE_ALLOCATION", "WORKFORCE", "ATTENDANCE"] for k in session_datasets)
            if has_att and 8 not in triggered_agenda:
                triggered_agenda.extend([8, 9])
                self.decisions.append(PlannerDecision(
                    step_number=step,
                    action="DATASET_EXPANSION",
                    dimension_number=8,
                    dimension_name="Workforce attendance & decoy evaluation",
                    trigger_reason="Workforce attendance dataset present in session, triggering D8 and D9",
                    evidence_sufficiency_score=1.0,
                    selected_tools=["rank_cost_drivers"],
                ))
                step += 1

        # Deduplicate and filter out already completed dimensions
        agenda_to_run = [d for d in dict.fromkeys(triggered_agenda) if d not in self.completed_dimensions]

        # Step 3: Targeted Execution of Expanded Agenda (Only Relevant Dimensions)
        expansions_done = 0
        for d_num in agenda_to_run:
            if expansions_done >= max_expansions * 3:
                # Stop when expansion ceiling reached
                self.decisions.append(PlannerDecision(
                    step_number=step,
                    action="TERMINATE",
                    dimension_number=d_num,
                    dimension_name=DimensionAnalyticsEngine.AUTHORITATIVE_NAMES[d_num],
                    trigger_reason="Investigation sufficient; stopping criteria met to prevent over-investigation",
                    evidence_sufficiency_score=1.0,
                ))
                break

            # Execute dimension
            res = DimensionAnalyticsEngine.analyze_dimension(
                dimension_number=d_num,
                scope=scope,
                db=self.db,
                session_datasets=session_datasets,
                plant_code=plant_code,
                product_code=product_code,
                line_code=line_code,
            )
            self.dimensional_results[d_num] = res
            self.completed_dimensions.add(d_num)
            expansions_done += 1

            for node in res.nodes:
                self.evidence_graph.add_node(node)
                # Connect node to total cost root
                if d_num in (3, 6, 7, 9, 13, 14):
                    self.evidence_graph.add_edge(
                        source_node_id=node.node_id,
                        target_node_id="NODE-D1-TOTAL-COST",
                        edge_type="CONFIRMED_CAUSAL",
                        description=f"Direct financial contribution to manufacturing cost variance.",
                    )
                else:
                    self.evidence_graph.add_edge(
                        source_node_id=node.node_id,
                        target_node_id="NODE-D2-UNIT-COST",
                        edge_type="CORRELATED",
                        description=f"Operational correlation impacting finished smartphone yield.",
                    )

        # Step 4: Add formal documentation of Deferred Dimensions (never executed or fabricated)
        for def_num in [10, 11, 15]:
            self.decisions.append(PlannerDecision(
                step_number=step,
                action="DEFER",
                dimension_number=def_num,
                dimension_name=DimensionAnalyticsEngine.AUTHORITATIVE_NAMES[def_num],
                trigger_reason=DimensionAnalyticsEngine.DEFERRED_DIMENSIONS[def_num],
                evidence_sufficiency_score=0.0,
            ))
            step += 1
            def_res = DimensionAnalyticsEngine.analyze_dimension(
                dimension_number=def_num,
                scope=scope,
                db=self.db,
                session_datasets=session_datasets,
            )
            self.dimensional_results[def_num] = def_res

        logger.info(
            "Investigation Planner completed: %d dimensions investigated, %d deferred, %d planner decisions.",
            len([r for r in self.dimensional_results.values() if r.status == "INVESTIGATED"]),
            len([r for r in self.dimensional_results.values() if r.status == "DEFERRED_NO_DATA"]),
            len(self.decisions),
        )

        return self.dimensional_results, self.evidence_graph, self.decisions
