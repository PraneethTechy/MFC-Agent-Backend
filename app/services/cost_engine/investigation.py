"""
Variance Investigation Service
Orchestrates scope resolution, validation, deterministic standard vs actual calculation,
variance bridge decomposition, cost driver prioritization, and operational evidence extraction.
"""

from typing import Any
import datetime as dt
from sqlalchemy.orm import Session
from ...models import (
    MaterialPosting,
    LabourPosting,
    MachineEvent,
    EnergyReading,
    QualityEvent,
    OverheadPool,
    SupplierPriceHistory,
    ProductionOrder,
)
from .schemas import (
    AnalyticalScopeRequest,
    VarianceInvestigationResponse,
    VarianceComponent,
)
from .scope import ScopeService
from .validation import CostDataValidator
from .standard_actual import StandardVsActualService
from .variance_bridge import VarianceBridgeService
from .cost_drivers import CostDriverRankingService


class VarianceInvestigationService:
    """Master orchestrator for deterministic manufacturing cost investigations."""

    @staticmethod
    def investigate_variance(db: Session, request: AnalyticalScopeRequest) -> VarianceInvestigationResponse:
        # 1. Scope Resolution
        scope, costing_version, period = ScopeService.resolve_scope(db, request)
        analysis_id = ScopeService.generate_analysis_id()

        # 2. Data Validation Pre-flight
        val_result = CostDataValidator.validate_cost_data(db, scope)
        if not val_result.can_proceed:
            error_msgs = [i["message"] for i in val_result.blocking_issues]
            raise ValueError(f"Investigation cannot proceed due to blocking data issues: {'; '.join(error_msgs)}")

        # 3. Standard vs Actual Calculation
        std_vs_act = StandardVsActualService.get_standard_vs_actual(db, scope)

        # 4. Variance Bridge Decomposition
        bridge = VarianceBridgeService.calculate_variance_bridge(db, scope)

        # 5. Cost Driver Ranking
        drivers_resp = CostDriverRankingService.rank_cost_drivers(db, scope)

        # 6. Operational Evidence Inspection
        order_ids = []
        if scope.get("production_order_id"):
            order_ids = [scope["production_order_id"]]
        else:
            q = db.query(ProductionOrder.id)
            if scope.get("plant_id"):
                q = q.filter(ProductionOrder.plant_id == scope["plant_id"])
            if scope.get("product_id"):
                q = q.filter(ProductionOrder.product_id == scope["product_id"])
            if scope.get("period_id"):
                q = q.filter(ProductionOrder.period_id == scope["period_id"])
            order_ids = [r[0] for r in q.all()]

        evidence_trail: list[dict[str, Any]] = []

        # Evidence: Material price changes
        if scope.get("material_code"):
            from ...models import Material
            mat_rec = db.query(Material).filter_by(code=scope["material_code"]).first()
            if mat_rec:
                price_hist = db.query(SupplierPriceHistory).filter_by(material_id=mat_rec.id).all()
                for ph in price_hist:
                    evidence_trail.append({
                        "evidence_type": "SUPPLIER_PRICE_INCREASE",
                        "source_table": "supplier_price_history",
                        "record_id": ph.id,
                        "date": ph.effective_date.isoformat(),
                        "details": f"Supplier price revised to {ph.currency} {ph.price:.2f} (material {scope['material_code']}).",
                    })

        # Evidence: Overtime Surges
        if order_ids:
            ot_posts = db.query(LabourPosting).filter(
                LabourPosting.production_order_id.in_(order_ids),
                LabourPosting.overtime_hours > 0,
            ).limit(10).all()
            for op in ot_posts:
                evidence_trail.append({
                    "evidence_type": "LABOUR_OVERTIME_SURGE",
                    "source_table": "labour_postings",
                    "record_id": op.id,
                    "date": op.posting_date.isoformat(),
                    "details": f"Shift {op.shift} logged {op.overtime_hours:.1f} OT hours at ₹{op.hourly_rate:.2f}/hr.",
                })

        # Evidence: Machine Downtime
        if order_ids:
            dt_events = db.query(MachineEvent).filter(
                MachineEvent.production_order_id.in_(order_ids),
                MachineEvent.downtime_hours > 0,
            ).limit(10).all()
            for me in dt_events:
                evidence_trail.append({
                    "evidence_type": "UNPLANNED_MACHINE_DOWNTIME",
                    "source_table": "machine_events",
                    "record_id": me.id,
                    "date": me.event_date.isoformat(),
                    "details": f"Machine event logged {me.downtime_hours:.1f} hrs downtime. Reason: {me.downtime_reason or 'Tool wear / breakdown'}.",
                })

        # Evidence: Quality Rejects and Rework
        if order_ids:
            qlt_events = db.query(QualityEvent).filter(
                QualityEvent.production_order_id.in_(order_ids)
            ).limit(10).all()
            for qe in qlt_events:
                evidence_trail.append({
                    "evidence_type": "DEFECT_SCRAP_REWORK",
                    "source_table": "quality_events",
                    "record_id": qe.id,
                    "date": qe.event_date.isoformat(),
                    "details": f"Defect '{qe.defect_code}' ({qe.defect_description}): {qe.scrap_quantity:.1f} scrap units, {qe.rework_hours:.1f} rework hrs (cost: ₹{qe.rework_cost:.2f}).",
                })

        # Evidence: Idle Energy Load Spikes
        if scope.get("plant_id") and scope.get("period_id"):
            idle_nrg = db.query(EnergyReading).filter(
                EnergyReading.plant_id == scope["plant_id"],
                EnergyReading.period_id == scope["period_id"],
                EnergyReading.is_idle_load == True,
            ).all()
            for ie in idle_nrg:
                evidence_trail.append({
                    "evidence_type": "OFF_SHIFT_ENERGY_SPIKE",
                    "source_table": "energy_readings",
                    "record_id": ie.id,
                    "date": str(ie.reading_timestamp)[:10],
                    "details": f"Off-shift furnace/line idle consumption logged: {ie.kwh_consumed:.1f} kWh (cost: ₹{ie.total_energy_cost:.2f}).",
                })

        # Evidence: Overhead Under-absorption
        if scope.get("plant_id") and scope.get("period_id"):
            ovh_pools = db.query(OverheadPool).filter(
                OverheadPool.plant_id == scope["plant_id"],
                OverheadPool.period_id == scope["period_id"],
            ).all()
            for op in ovh_pools:
                if op.under_over_absorption != 0:
                    evidence_trail.append({
                        "evidence_type": "OVERHEAD_CAPACITY_UNDER_ABSORPTION",
                        "source_table": "overhead_pools",
                        "record_id": op.id,
                        "date": period.start_date.isoformat() if period else dt.date.today().isoformat(),
                        "details": f"Pool '{op.pool_name}' planned {op.planned_driver_capacity:.1f} {op.absorption_driver}, actual usage {op.actual_driver_usage:.1f} (under-absorption: ₹{op.under_over_absorption:.2f}).",
                    })

        # Flatten variance components for response schema
        flat_comps: list[VarianceComponent] = []
        for c_list in bridge.components_by_category.values():
            flat_comps.extend(c_list)

        assumptions = [
            "Financial calculations are deterministic SQL/Python sums with zero LLM arithmetic.",
            f"Standard costs evaluated strictly against baseline costing version '{costing_version.code}'.",
            "Allocated energy uses plant run-hour distribution and is tagged as estimated.",
            "Unexplained remainder reflects category variance not captured by discrete source postings.",
        ]

        warnings = [w["message"] for w in val_result.warnings]

        summary = {
            "total_standard_cost": std_vs_act.total_standard_cost,
            "total_actual_cost": std_vs_act.total_actual_cost,
            "total_variance": std_vs_act.total_variance,
            "total_variance_pct": std_vs_act.total_variance_pct,
            "is_unfavourable": std_vs_act.is_unfavourable,
            "total_explained_variance": bridge.total_explained_variance,
            "total_unexplained_variance": bridge.total_unexplained_variance,
            "reconciled": bridge.reconciled,
        }

        return VarianceInvestigationResponse(
            status="SUCCESS",
            analysis_id=analysis_id,
            scope=scope,
            period=scope.get("period_code") or "ALL_PERIODS",
            currency=scope.get("currency") or "INR",
            costing_version=costing_version.code,
            data_as_of=dt.datetime.now(dt.timezone.utc).isoformat(),
            is_synthetic=True,
            data_quality={
                "data_trust_score": val_result.data_trust_score,
                "data_coverage_pct": val_result.data_coverage_pct,
                "missing_information": val_result.missing_information,
            },
            summary=summary,
            category_breakdown=std_vs_act.categories,
            variance_components=flat_comps,
            cost_drivers=drivers_resp.drivers,
            evidence_trail=evidence_trail,
            assumptions=assumptions,
            unexplained_variance=bridge.total_unexplained_variance,
            warnings=warnings,
        )
