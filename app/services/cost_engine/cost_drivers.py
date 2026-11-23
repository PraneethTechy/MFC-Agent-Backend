"""
Cost Driver Ranking Service
Prioritizes variance contributors by absolute financial impact (Pareto analysis),
and classifies analytical confidence without confusing correlation with causation.
"""

from typing import Any
from sqlalchemy.orm import Session
from .schemas import CostDriverRankingResponse, CostDriverRanking
from .scope import ScopeService
from .variance_bridge import VarianceBridgeService


class CostDriverRankingService:
    """Ranks and contextualizes primary cost drivers."""

    @staticmethod
    def rank_cost_drivers(db: Session, scope: dict[str, Any]) -> CostDriverRankingResponse:
        analysis_id = ScopeService.generate_analysis_id()

        bridge = VarianceBridgeService.calculate_variance_bridge(db, scope)
        total_var = bridge.total_variance

        flat_components = []
        for cat_name, comp_list in bridge.components_by_category.items():
            for comp in comp_list:
                if comp.amount != 0.0:
                    flat_components.append(comp)

        # Sort by absolute financial magnitude descending
        sorted_comps = sorted(flat_components, key=lambda c: abs(c.amount), reverse=True)

        total_abs_variance = sum(abs(c.amount) for c in sorted_comps) or 1.0
        total_unfavourable = round(sum(c.amount for c in sorted_comps if c.amount > 0), 4)
        total_favourable = round(sum(c.amount for c in sorted_comps if c.amount < 0), 4)

        drivers: list[CostDriverRanking] = []
        for rank, comp in enumerate(sorted_comps, 1):
            abs_amount = round(abs(comp.amount), 4)
            # 1. Absolute driver magnitude share (Pareto scale)
            abs_contrib_pct = round((abs_amount / total_abs_variance) * 100.0, 1)

            # 2. Net variance contribution percentage
            net_contrib_pct = round((comp.amount / total_var * 100.0), 1) if total_var != 0 else 0.0

            # 3. Categorize impact type
            impact_type = "UNFAVOURABLE" if comp.amount > 0 else "FAVOURABLE"

            # Assign analytical confidence based on accounting proof vs correlation
            if "Purchase Price" in comp.component_name or "Overtime" in comp.component_name:
                confidence = "PROVEN"
                evidence = f"Verified transactional ledger records ({comp.evidence_records_count} postings)."
                data_source = "ERP Invoices & Production Timecards"
            elif "Downtime" in comp.component_name or "Rework" in comp.component_name:
                confidence = "OBSERVED_CORRELATION"
                evidence = f"Logged shop-floor operational events ({comp.evidence_records_count} machine/quality events)."
                data_source = "MES & Quality Event Logs"
            elif "Idle Load" in comp.component_name:
                confidence = "OBSERVED_CORRELATION"
                evidence = "Off-shift meter readings correlate with non-operating production hours."
                data_source = "Energy IoT Sub-meters"
            elif "Volume" in comp.component_name:
                confidence = "PROVEN"
                evidence = "Cost accounting absorption formula applied to actual driver machine hours."
                data_source = "Factory Cost Accounting Ledger"
            elif "Standard Scrap Allowance" in comp.component_name:
                confidence = "PROVEN"
                evidence = "Approved baseline standard costing allowance per completed good unit."
                data_source = "Approved Standard Cost Master (SCI)"
            else:
                confidence = "HYPOTHESIS"
                evidence = f"Mathematical remainder from category variance balance: {comp.formula_used}"
                data_source = "Analytical Variance Engine"

            drivers.append(CostDriverRanking(
                rank=rank,
                driver_name=comp.component_name,
                category=comp.category,
                variance_amount=comp.amount,
                abs_variance_amount=abs_amount,
                contribution_pct=abs_contrib_pct,
                net_variance_contribution_pct=net_contrib_pct,
                impact_type=impact_type,
                direction=impact_type,
                supporting_evidence=evidence,
                data_source=data_source,
                confidence=confidence,
            ))

        return CostDriverRankingResponse(
            status="SUCCESS",
            analysis_id=analysis_id,
            scope=scope,
            total_variance=total_var,
            total_unfavourable_variance=total_unfavourable,
            total_favourable_variance=total_favourable,
            drivers=drivers,
        )

