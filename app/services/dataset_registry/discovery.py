"""
Manufacturing Dataset Registry - Dynamic Data Discovery Layer
Provides intelligence, search, and referential governance services across all
10 logical manufacturing datasets and their physical sources.
Answers:
- Which datasets are available and what do they contain?
- Which datasets contain evidence for an investigation question or dimension?
- Which datasets cover a requested temporal period or date range?
- What are the confirmed vs candidate relationships between datasets?
- How should synthetic vs ground-truth data be isolated?
- Is there sufficient evidence to answer a specific dimension's hypothesis?
"""

import datetime as dt
from dataclasses import dataclass, field, asdict
import logging
import re
from typing import Any, Optional

from .models import (
    LogicalDatasetDefinition,
    GranularityType,
    ProvenanceTier,
    RelationshipStatus,
)
from .registry import ManufacturingDatasetRegistry
from .time_period import TimePeriodResolver, ResolvedPeriodScope, CoverageAssessment

logger = logging.getLogger("manufacturing_cost_agent.dataset_discovery")


@dataclass
class DimensionSupportStatus:
    """Evaluation of evidence sufficiency for an authoritative manufacturing dimension."""
    dimension_number: int
    dimension_name: str
    status: str  # 'SUPPORTED', 'PARTIAL_SUPPORT', 'DEFERRED_NO_DATA'
    is_supported: bool
    is_deferred: bool
    primary_dataset_ids: list[str] = field(default_factory=list)
    secondary_dataset_ids: list[str] = field(default_factory=list)
    evidence_sufficiency_score: float = 0.0
    notes: str = ""
    deferral_reason: Optional[str] = None

    def dict(self) -> dict[str, Any]:
        return asdict(self)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QuestionDatasetMatch:
    """Discovery result linking a natural-language investigation question to dataset evidence."""
    question_text: str
    detected_intents: list[str] = field(default_factory=list)
    relevant_dimensions: list[int] = field(default_factory=list)
    primary_datasets: list[str] = field(default_factory=list)
    context_datasets: list[str] = field(default_factory=list)
    recommended_join_pathways: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    confidence: str = "HIGH"

    def dict(self) -> dict[str, Any]:
        return asdict(self)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class DatasetDiscoveryService:
    """Dynamic discovery and evidence routing engine for manufacturing root-cause analysis."""

    DATASET_ALIASES: dict[str, str] = {
        "d1": "d1_hourly_production",
        "d1_hourly": "d1_hourly_production",
        "d1_hourly_production": "d1_hourly_production",
        "d2": "d2_manufacturing_cost",
        "d2_cost": "d2_manufacturing_cost",
        "d2_manufacturing_cost": "d2_manufacturing_cost",
        "d3": "d3_bom_components",
        "d3_bom": "d3_bom_components",
        "d3_bom_components": "d3_bom_components",
        "d4": "d4_quality_inspection",
        "d4_quality": "d4_quality_inspection",
        "d4_quality_inspection": "d4_quality_inspection",
        "d5": "d5_production_traceability",
        "d5_traceability": "d5_production_traceability",
        "d5_production_traceability": "d5_production_traceability",
        "d6": "d6_material_consumption",
        "d6_consumption": "d6_material_consumption",
        "d6_material_consumption": "d6_material_consumption",
        "d7": "d7_inventory_transactions",
        "d7_inventory": "d7_inventory_transactions",
        "d7_inventory_transactions": "d7_inventory_transactions",
        "d8": "d8_procurement_supplier",
        "d8_procurement": "d8_procurement_supplier",
        "d8_procurement_supplier": "d8_procurement_supplier",
        "d9": "d9_equipment_energy",
        "d9_energy": "d9_equipment_energy",
        "d9_equipment_energy": "d9_equipment_energy",
        "d10": "d10_workforce_attendance_allocation",
        "d10_workforce": "d10_workforce_attendance_allocation",
        "d10_workforce_attendance_allocation": "d10_workforce_attendance_allocation",
    }

    # Authoritative 18-dimension definitions aligned with the Manufacturing Cost RCA Master Architecture
    AUTHORITATIVE_DIMENSIONS: dict[int, dict[str, Any]] = {
        1: {
            "name": "Total manufacturing cost",
            "status": "SUPPORTED",
            "primary": ["d2_manufacturing_cost"],
            "secondary": ["d1_hourly_production"],
            "notes": "Total manufacturing expenditure reconciliation, ledger batch postings, and cost category breakdowns (Material, Labour, Machine, Energy, Scrap).",
        },
        2: {
            "name": "Cost per good unit",
            "status": "SUPPORTED",
            "primary": ["d2_manufacturing_cost", "d1_hourly_production"],
            "secondary": ["d4_quality_inspection"],
            "notes": "Direct manufacturing cost per good finished smartphone, strictly excluding uncosted operational runs from unit denominator.",
        },
        3: {
            "name": "Scrap and rework",
            "status": "SUPPORTED",
            "primary": ["d4_quality_inspection", "d2_manufacturing_cost"],
            "secondary": ["d3_bom_components", "d6_material_consumption"],
            "notes": "Serialized testing station fallout, rework station looping, component replacement costs, and scrap absorption.",
        },
        4: {
            "name": "Plant and production-line performance",
            "status": "SUPPORTED",
            "primary": ["d1_hourly_production", "d2_manufacturing_cost"],
            "secondary": ["d4_quality_inspection"],
            "notes": "Line-level throughput, OEE, downtime losses, target vs actual run rate across plants IN-KA-01 and IN-TN-01.",
        },
        5: {
            "name": "Product-wise manufacturing cost",
            "status": "SUPPORTED",
            "primary": ["d2_manufacturing_cost", "d3_bom_components"],
            "secondary": ["d1_hourly_production"],
            "notes": "Product SKU unit economics across SPH-PRO-256, SPH-A15-128, and SPH-LITE-64, accounting for distinct engineering BOM baselines.",
        },
        6: {
            "name": "Material consumption and machine efficiency",
            "status": "SUPPORTED",
            "primary": ["d6_material_consumption", "d1_hourly_production"],
            "secondary": ["d3_bom_components", "d9_equipment_energy"],
            "notes": "Pick-and-place component issues, feeder dispense scrap, machine operational hours, and downtime efficiency.",
        },
        7: {
            "name": "Energy consumption",
            "status": "SUPPORTED",
            "primary": ["d9_equipment_energy"],
            "secondary": ["d1_hourly_production", "d2_manufacturing_cost"],
            "notes": "Sub-meter kWh power telemetry, reflow oven heater draw, peak demand surges, and electricity tariff variance.",
        },
        8: {
            "name": "Employee absenteeism",
            "status": "SUPPORTED",
            "primary": ["d10_workforce_attendance_allocation"],
            "secondary": ["d1_hourly_production", "d2_manufacturing_cost"],
            "notes": "Daily shift operator attendance logs, unscheduled absence rate, and line pacing impacts.",
        },
        9: {
            "name": "Workforce allocation",
            "status": "SUPPORTED",
            "primary": ["d10_workforce_attendance_allocation", "d1_hourly_production"],
            "secondary": ["d2_manufacturing_cost"],
            "notes": "Shift line assignments, operator deployment, overtime hours, and headcount variance vs standard staffing.",
        },
        10: {
            "name": "Employee skill gaps",
            "status": "DEFERRED_NO_DATA",
            "primary": [],
            "secondary": ["d10_workforce_attendance_allocation"],
            "notes": "DEFERRED: Requires granular station-level operator competency matrix and individual certification records not captured in current MES.",
            "deferral_reason": "No station-level skill matrix or operator certification logs present in committed datasets.",
        },
        11: {
            "name": "Training effectiveness",
            "status": "DEFERRED_NO_DATA",
            "primary": [],
            "secondary": ["d10_workforce_attendance_allocation"],
            "notes": "DEFERRED: Requires HR learning management system (LMS) completion dates and post-training ramp rates.",
            "deferral_reason": "LMS training milestones and new-hire ramp logs are absent from factory telemetry.",
        },
        12: {
            "name": "Labour productivity",
            "status": "SUPPORTED",
            "primary": ["d1_hourly_production", "d10_workforce_attendance_allocation"],
            "secondary": ["d2_manufacturing_cost"],
            "notes": "Good units produced per operator labor hour, standard labor hours vs actual labor hours, and shift productivity trends.",
        },
        13: {
            "name": "Procurement and supplier performance",
            "status": "SUPPORTED",
            "primary": ["d8_procurement_supplier"],
            "secondary": ["d7_inventory_transactions", "d3_bom_components"],
            "notes": "Purchase price variance (PPV) against standard cost, supplier delivery on-time-in-full (OTIF), and lot defect rates.",
        },
        14: {
            "name": "Inventory management",
            "status": "SUPPORTED",
            "primary": ["d7_inventory_transactions"],
            "secondary": ["d6_material_consumption", "d8_procurement_supplier"],
            "notes": "Raw material warehouse receipts, issues, safety stock breaches, stockouts, and carrying costs.",
        },
        15: {
            "name": "Management and organizational decisions",
            "status": "DEFERRED_NO_DATA",
            "primary": [],
            "secondary": ["d5_production_traceability"],
            "notes": "DEFERRED: Requires executive change-order logs and ERP manual planning override tracking.",
            "deferral_reason": "Manual production reschedule override records not captured in automated telemetry.",
        },
        16: {
            "name": "Production capacity and capacity utilization",
            "status": "SUPPORTED",
            "primary": ["d1_hourly_production"],
            "secondary": ["d2_manufacturing_cost"],
            "notes": "Installed line design capacity, actual throughput utilization percentage, bottleneck line starvation, and planned downtime.",
        },
        17: {
            "name": "Material consumption and inventory reconciliation",
            "status": "SUPPORTED",
            "primary": ["d6_material_consumption", "d7_inventory_transactions"],
            "secondary": ["d3_bom_components"],
            "notes": "Reconciliation of physical component warehouse issues vs line consumption vs theoretical engineering BOM requirements.",
        },
        18: {
            "name": "Smartphone testing and inspection efficiency",
            "status": "SUPPORTED",
            "primary": ["d4_quality_inspection"],
            "secondary": ["d1_hourly_production", "d5_production_traceability"],
            "notes": "Serialized testing station pass/fail throughput across S01 to S06, First Pass Yield (FPY), re-test cycling, and defect Pareto analysis.",
        },
    }

    def __init__(self, registry: Optional[ManufacturingDatasetRegistry] = None):
        self.registry = registry or ManufacturingDatasetRegistry.get_instance()

    def list_available_datasets(
        self,
        include_synthetic: bool = True,
        include_staged: bool = False,
    ) -> list[LogicalDatasetDefinition]:
        """
        Returns all registered logical datasets, optionally filtering out synthetic extensions.
        """
        all_datasets = self.registry.list_datasets(active_only=True)
        results = []
        for ds in all_datasets:
            if not include_synthetic and ds.provenance_tier == ProvenanceTier.SYNTHETIC_EXTENSION:
                continue
            results.append(ds)
        return results

    def get_dataset(self, dataset_id: str) -> Optional[LogicalDatasetDefinition]:
        """Retrieves a single logical dataset definition by ID, alias, or domain code."""
        norm_key = dataset_id.strip().lower()
        if norm_key in self.DATASET_ALIASES:
            norm_key = self.DATASET_ALIASES[norm_key]

        ds = self.registry.get_dataset(norm_key)
        if ds:
            return ds

        # Check domain code match (e.g. 'D1', 'D5')
        norm_upper = dataset_id.strip().upper()
        for candidate in self.registry.list_datasets(active_only=False):
            if candidate.domain_code.upper() == norm_upper:
                return candidate
            if candidate.dataset_id.lower() == norm_key:
                return candidate
            if norm_key.startswith(candidate.domain_code.lower() + "_"):
                return candidate

        return None

    def find_datasets_for_dimension(self, dimension_number: int) -> list[LogicalDatasetDefinition]:
        """Returns all logical datasets that provide primary or secondary evidence for a dimension."""
        matching = []
        for ds in self.registry.list_datasets(active_only=True):
            if dimension_number in ds.supported_dimensions:
                matching.append(ds)
        return matching

    def check_evidence_sufficiency(
        self,
        dimension_number: int,
        period_str: Optional[str] = None,
    ) -> DimensionSupportStatus:
        """
        Evaluates whether sufficient evidence exists in available datasets to investigate a dimension.
        Explicitly identifies DEFERRED dimensions (10, 11, 15) and highlights missing data.
        """
        dim_info = self.AUTHORITATIVE_DIMENSIONS.get(dimension_number)
        if not dim_info:
            return DimensionSupportStatus(
                dimension_number=dimension_number,
                dimension_name=f"Unknown Dimension {dimension_number}",
                status="DEFERRED_NO_DATA",
                is_supported=False,
                is_deferred=True,
                notes=f"Dimension {dimension_number} is not defined in the 18-dimension manufacturing RCA taxonomy.",
                deferral_reason="Undefined dimension index",
            )

        is_deferred = dim_info["status"] == "DEFERRED_NO_DATA"
        primary_ids = dim_info.get("primary", [])
        secondary_ids = dim_info.get("secondary", [])

        if is_deferred:
            return DimensionSupportStatus(
                dimension_number=dimension_number,
                dimension_name=dim_info["name"],
                status="DEFERRED_NO_DATA",
                is_supported=False,
                is_deferred=True,
                primary_dataset_ids=primary_ids,
                secondary_dataset_ids=secondary_ids,
                evidence_sufficiency_score=0.0,
                notes=dim_info["notes"],
                deferral_reason=dim_info.get("deferral_reason"),
            )

        # Dimension is technically supported. Check if backing datasets exist in registry.
        available_primary = [pid for pid in primary_ids if self.registry.get_dataset(pid) is not None]
        available_secondary = [sid for sid in secondary_ids if self.registry.get_dataset(sid) is not None]

        score = (len(available_primary) / max(len(primary_ids), 1)) * 0.7 + \
                (len(available_secondary) / max(len(secondary_ids), 1)) * 0.3

        # If period specified, check coverage
        period_warning = ""
        if period_str:
            resolved = TimePeriodResolver.resolve_period(period_str)
            for pid in available_primary:
                ds = self.registry.get_dataset(pid)
                if ds:
                    assessment = TimePeriodResolver.assess_dataset_coverage(ds, resolved)
                    if assessment.coverage_status in ("PARTIAL_COVERAGE", "OUT_OF_BOUNDS"):
                        period_warning = f" (Warning: {ds.name} has {assessment.coverage_status})"
                        score *= 0.85

        status_str = "SUPPORTED" if score >= 0.7 else "PARTIAL_SUPPORT"
        return DimensionSupportStatus(
            dimension_number=dimension_number,
            dimension_name=dim_info["name"],
            status=status_str,
            is_supported=True,
            is_deferred=False,
            primary_dataset_ids=available_primary,
            secondary_dataset_ids=available_secondary,
            evidence_sufficiency_score=round(score, 2),
            notes=dim_info["notes"] + period_warning,
        )

    def find_datasets_for_question(self, question_text: str) -> QuestionDatasetMatch:
        """
        Analyzes natural-language investigation question to identify manufacturing concepts,
        relevant dimensions, primary datasets, and recommended join pathways.
        """
        q = question_text.lower()
        intents = []
        dimensions: list[int] = []
        primary_ds: set[str] = set()
        context_ds: set[str] = set()
        pathways: list[str] = []
        caveats: list[str] = []

        # Intent & Keyword Mapping
        # 1. Purchase Price Variance / Supplier / Procurement
        if any(w in q for w in ["ppv", "purchase price", "vendor cost", "procurement", "po price", "contract price", "supplier cost", "supplier"]):
            intents.extend(["PROCUREMENT_AND_SUPPLIER_PERFORMANCE", "PURCHASE_PRICE_VARIANCE"])
            dimensions.extend([13, 1])
            primary_ds.update(["d8_procurement_supplier", "d2_manufacturing_cost"])
            context_ds.update(["d7_inventory_transactions", "d3_bom_components"])
            pathways.append("d8_procurement_supplier (po_number, material_id) -> d7_inventory_transactions -> d2_manufacturing_cost")

        # 2. Yield Loss / Rejection / Quality Testing / Defect
        if any(w in q for w in ["yield", "fpy", "rejection", "scrap", "defect", "fail", "station", "testing", "camera fail", "display void", "inspection"]):
            intents.extend(["FIRST_PASS_YIELD_LOSS", "SMARTPHONE_TESTING_AND_INSPECTION"])
            dimensions.extend([3, 18])
            primary_ds.update(["d4_quality_inspection", "d2_manufacturing_cost"])
            context_ds.update(["d1_hourly_production", "d5_production_traceability"])
            pathways.append("d4_quality_inspection (tested_at_hour, line_id) [CANDIDATE] -> d1_hourly_production")
            caveats.append("Quality inspection records are serialized per handset; join to hourly production is candidate-only by plant+line+hour.")

        # 3. Dispense Creep / Consumption / BOM Over-use
        if any(w in q for w in ["dispense", "bom creep", "over-consumption", "paste", "glue", "underfill", "usage variance", "consumption"]):
            intents.append("MATERIAL_CONSUMPTION_VARIANCE")
            dimensions.extend([6, 17])
            primary_ds.update(["d6_material_consumption", "d3_bom_components"])
            context_ds.update(["d2_manufacturing_cost", "d7_inventory_transactions"])
            pathways.append("d6_material_consumption (material_id) [CONFIRMED] -> d3_bom_components (material_id)")

        # 4. Machine Stoppage / Downtime / OEE / Equipment
        if any(w in q for w in ["downtime", "stoppage", "oee", "breakdown", "starvation", "jam", "nozzle", "feeder", "capacity", "utilization"]):
            intents.append("PLANT_LINE_PERFORMANCE_AND_CAPACITY")
            dimensions.extend([4, 16])
            primary_ds.update(["d1_hourly_production", "d9_equipment_energy"])
            context_ds.update(["d2_manufacturing_cost", "d5_production_traceability"])
            pathways.append("d9_equipment_energy (plant_id, line_id, shift_date) [CANDIDATE] -> d1_hourly_production")

        # 5. Labor Overtime / Absenteeism / Workforce
        if any(w in q for w in ["overtime", "labor", "labour", "absenteeism", "operator", "headcount", "shift attendance", "attendance"]):
            intents.append("WORKFORCE_ABSENTEEISM_AND_ALLOCATION")
            dimensions.extend([8, 9, 12])
            primary_ds.update(["d10_workforce_attendance_allocation", "d1_hourly_production"])
            context_ds.update(["d2_manufacturing_cost"])
            pathways.append("d10_workforce_attendance_allocation (plant_id, line_id, date, shift) [CANDIDATE] -> d1_hourly_production")
            caveats.append("Workforce records are line-shift aggregated; individual operator badge numbers are not mapped to specific serial numbers.")

        # 6. Energy / Power / Electricity
        if any(w in q for w in ["energy", "power", "kwh", "electricity", "oven heater", "surge"]):
            intents.append("ENERGY_CONSUMPTION")
            dimensions.append(7)
            primary_ds.update(["d9_equipment_energy"])
            context_ds.update(["d1_hourly_production", "d2_manufacturing_cost"])
            caveats.append("Energy kWh telemetry is recorded at shift/line level and has not been reconciled to ERP accounting ledgers.")

        # 7. SKU Mix / Product Shift (Analytical technique across Dimensions 1, 2, 5)
        if any(w in q for w in ["mix", "sku", "product mix", "flagship", "volume share", "product-wise"]):
            intents.append("PRODUCT_WISE_COST_AND_MIX")
            dimensions.extend([1, 2, 5])
            primary_ds.update(["d2_manufacturing_cost", "d3_bom_components"])
            context_ds.update(["d1_hourly_production", "d5_production_traceability"])
            caveats.append("Product mix is an analytical decomposition technique mapping to Dimensions 1, 2, and 5; SKU cost divergence reflects engineered BOM differences.")

        # 8. Inventory / Stockout / Warehouse
        if any(w in q for w in ["inventory", "stockout", "warehouse", "safety stock", "stock", "holding cost"]):
            intents.append("INVENTORY_MANAGEMENT")
            dimensions.extend([14, 17])
            primary_ds.update(["d7_inventory_transactions"])
            context_ds.update(["d6_material_consumption", "d8_procurement_supplier"])

        # 9. Unrecorded/Deferred Dimensions Checks
        if any(w in q for w in ["skill", "competency", "training effectiveness", "management override"]):
            if "skill" in q or "competency" in q:
                dimensions.append(10)
                caveats.append("Operator skill gaps (Dimension 10) are DEFERRED: no station-level competency matrix in current datasets.")
            if "training" in q:
                dimensions.append(11)
                caveats.append("Training effectiveness (Dimension 11) is DEFERRED: LMS training records are not integrated.")
            if "management override" in q:
                dimensions.append(15)
                caveats.append("Management override (Dimension 15) is DEFERRED: manual override change orders are not logged.")

        # Default fallback if general cost query
        if not intents and any(w in q for w in ["cost", "variance", "expensive", "margin", "budget"]):
            intents.append("GENERAL_COST_INVESTIGATION")
            dimensions.extend([1, 2, 4, 5])
            primary_ds.update(["d2_manufacturing_cost", "d1_hourly_production"])
            context_ds.update(["d8_procurement_supplier", "d4_quality_inspection"])
            pathways.append("d2_manufacturing_cost (plant_id, line_id, date) [CANDIDATE] -> d1_hourly_production")

        # Deduplicate dimensions
        unique_dims = sorted(list(set(dimensions)))

        return QuestionDatasetMatch(
            question_text=question_text,
            detected_intents=intents,
            relevant_dimensions=unique_dims,
            primary_datasets=sorted(list(primary_ds)),
            context_datasets=sorted(list(context_ds)),
            recommended_join_pathways=pathways,
            caveats=caveats,
            confidence="HIGH" if len(primary_ds) > 0 else "LOW",
        )

    def find_datasets_for_period(self, period_str: str) -> dict[str, Any]:
        """
        Evaluates temporal coverage of all active manufacturing datasets for a given query period.
        """
        resolved = TimePeriodResolver.resolve_period(period_str)
        assessments: dict[str, Any] = {}

        for ds in self.registry.list_datasets(active_only=True):
            assessment = TimePeriodResolver.assess_dataset_coverage(ds, resolved)
            assessments[ds.dataset_id] = assessment.dict()

        return {
            "resolved_scope": resolved.dict(),
            "coverage_assessments": assessments,
        }

    def get_verified_relationships(
        self,
        dataset_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Returns only CONFIRMED referential linkages, strictly excluding candidate or unmatched joins.
        """
        confirmed_links = []
        datasets_to_check = (
            [self.registry.get_dataset(dataset_id)]
            if dataset_id and self.registry.get_dataset(dataset_id)
            else self.registry.list_datasets(active_only=True)
        )

        for ds in datasets_to_check:
            if not ds:
                continue
            for rel in ds.relationships:
                if rel.status == RelationshipStatus.CONFIRMED:
                    confirmed_links.append({
                        "source_dataset_id": ds.dataset_id,
                        "source_name": ds.name,
                        "local_key": rel.local_key,
                        "target_dataset_id": rel.target_dataset_id,
                        "target_key": rel.target_key,
                        "relationship_type": rel.relationship_type,
                        "status": rel.status.value,
                        "caveat": rel.caveat,
                    })
        return confirmed_links

    def get_synthetic_isolation_rules(self) -> dict[str, Any]:
        """
        Returns governance and isolation rules ensuring synthetic data is never
        mingled into audited financial ground truth without explicit user authorization.
        """
        return {
            "isolation_policy": "STRICT_SEPARATION",
            "enforcement_rules": [
                "Synthetic extension datasets (D5-D10 CSVs, simulated batches) MUST carry provenance_tier='SYNTHETIC_EXTENSION'.",
                "Queries against financial truth (D2 manufacturing cost, D8 actual procurement) default to include_synthetic=False.",
                "When synthetic extensions are queried, all result rows and analytical charts must display 'SIMULATED / TEST' provenance badge.",
                "Synthetic data files are stored under backend/data/generated/ and must not overwrite backend/data/raw/ baseline files.",
                "Referential joins between ground-truth and synthetic datasets are marked CANDIDATE_ONLY and require caveat disclosure.",
            ],
            "synthetic_datasets": [
                ds.dataset_id for ds in self.registry.list_datasets(active_only=False)
                if ds.provenance_tier == ProvenanceTier.SYNTHETIC_EXTENSION
            ],
            "baseline_datasets": [
                ds.dataset_id for ds in self.registry.list_datasets(active_only=False)
                if ds.provenance_tier in (ProvenanceTier.RAW_BASELINE, ProvenanceTier.ENHANCED_BASELINE)
            ],
        }
