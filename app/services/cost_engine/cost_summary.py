"""
Cost Summary Calculation Service
Calculates deterministic actual manufacturing expenditures across all six categories,
unit costs, and manufacturing quantities.
"""

from typing import Any
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from sqlalchemy import text
from .schemas import CostSummaryResponse, CostCategoryBreakdown
from .scope import ScopeService


class CostSummaryService:
    """Calculates deterministic cost summaries from database facts."""

    @staticmethod
    def get_cost_summary(db: Session, scope: dict[str, Any]) -> CostSummaryResponse:
        analysis_id = ScopeService.generate_analysis_id()

        # Build dynamic SQL query over v_cost_facts to aggregate actual costs
        clauses = []
        params = {}

        if scope.get("plant_id"):
            clauses.append("plant_id = :plant_id")
            params["plant_id"] = scope["plant_id"]
        if scope.get("product_id"):
            clauses.append("product_id = :product_id")
            params["product_id"] = scope["product_id"]
        if scope.get("period_id"):
            clauses.append("period_id = :period_id")
            params["period_id"] = scope["period_id"]
        if scope.get("production_order_id"):
            clauses.append("production_order_id = :production_order_id")
            params["production_order_id"] = scope["production_order_id"]

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        query_sql = f"""
        SELECT 
            COALESCE(SUM(planned_qty), 0.00) AS total_planned_qty,
            COALESCE(SUM(completed_good_qty), 0.00) AS total_good_qty,
            COALESCE(SUM(actual_scrap_qty), 0.00) AS total_scrap_qty,
            COALESCE(SUM(actual_rework_qty), 0.00) AS total_rework_qty,
            COALESCE(SUM(actual_material_cost), 0.0000) AS total_material_cost,
            COALESCE(SUM(actual_labour_cost), 0.0000) AS total_labour_cost,
            COALESCE(SUM(actual_machine_cost), 0.0000) AS total_machine_cost,
            COALESCE(SUM(actual_energy_cost), 0.0000) AS total_energy_cost,
            COALESCE(SUM(actual_rework_cost), 0.0000) AS total_rework_cost,
            COALESCE(SUM(absorbed_overhead_cost), 0.0000) AS total_absorbed_overhead,
            COALESCE(SUM(total_actual_cost), 0.0000) AS total_actual_cost,
            MAX(is_energy_estimated::int) AS is_energy_estimated,
            MAX(currency) AS currency
        FROM v_cost_facts
        {where_sql}
        """

        result = db.execute(text(query_sql), params).mappings().first()

        total_planned_qty = float(result["total_planned_qty"] or 0.0)
        total_good_qty = float(result["total_good_qty"] or 0.0)
        total_scrap_qty = float(result["total_scrap_qty"] or 0.0)
        total_rework_qty = float(result["total_rework_qty"] or 0.0)

        mat_cost = round(float(result["total_material_cost"] or 0.0), 4)
        lab_cost = round(float(result["total_labour_cost"] or 0.0), 4)
        mac_cost = round(float(result["total_machine_cost"] or 0.0), 4)
        nrg_cost = round(float(result["total_energy_cost"] or 0.0), 4)
        qlt_cost = round(float(result["total_rework_cost"] or 0.0), 4)
        ovh_cost = round(float(result["total_absorbed_overhead"] or 0.0), 4)

        # Total actual manufacturing cost is the deterministic sum of the 6 categories
        total_actual = round(mat_cost + lab_cost + mac_cost + nrg_cost + qlt_cost + ovh_cost, 4)

        # Actual Unit Cost based on completed good units
        actual_unit_cost = round(total_actual / total_good_qty, 4) if total_good_qty > 0 else 0.0

        warnings = []
        if total_good_qty == 0:
            warnings.append("Total good quantity produced is zero; actual unit cost cannot be calculated.")

        # Unit costs per category
        def calc_cat_unit(val: float) -> float:
            return round(val / total_good_qty, 4) if total_good_qty > 0 else 0.0

        categories = [
            CostCategoryBreakdown(
                category="Material",
                actual_cost=mat_cost,
                standard_cost=0.0,
                variance=mat_cost,
                variance_pct=0.0,
                is_unfavourable=False,
                allocation_type="DIRECT",
                unit_cost_actual=calc_cat_unit(mat_cost),
                unit_cost_standard=0.0,
            ),
            CostCategoryBreakdown(
                category="Labour",
                actual_cost=lab_cost,
                standard_cost=0.0,
                variance=lab_cost,
                variance_pct=0.0,
                is_unfavourable=False,
                allocation_type="DIRECT",
                unit_cost_actual=calc_cat_unit(lab_cost),
                unit_cost_standard=0.0,
            ),
            CostCategoryBreakdown(
                category="Machine",
                actual_cost=mac_cost,
                standard_cost=0.0,
                variance=mac_cost,
                variance_pct=0.0,
                is_unfavourable=False,
                allocation_type="DIRECT",
                unit_cost_actual=calc_cat_unit(mac_cost),
                unit_cost_standard=0.0,
            ),
            CostCategoryBreakdown(
                category="Energy",
                actual_cost=nrg_cost,
                standard_cost=0.0,
                variance=nrg_cost,
                variance_pct=0.0,
                is_unfavourable=False,
                allocation_type="ESTIMATED",
                unit_cost_actual=calc_cat_unit(nrg_cost),
                unit_cost_standard=0.0,
            ),
            CostCategoryBreakdown(
                category="Scrap and Rework",
                actual_cost=qlt_cost,
                standard_cost=0.0,
                variance=qlt_cost,
                variance_pct=0.0,
                is_unfavourable=False,
                allocation_type="DIRECT",
                unit_cost_actual=calc_cat_unit(qlt_cost),
                unit_cost_standard=0.0,
            ),
            CostCategoryBreakdown(
                category="Manufacturing Overhead",
                actual_cost=ovh_cost,
                standard_cost=0.0,
                variance=ovh_cost,
                variance_pct=0.0,
                is_unfavourable=False,
                allocation_type="ALLOCATED",
                unit_cost_actual=calc_cat_unit(ovh_cost),
                unit_cost_standard=0.0,
            ),
        ]

        import datetime as dt
        return CostSummaryResponse(
            status="SUCCESS",
            analysis_id=analysis_id,
            scope=scope,
            currency=scope.get("currency") or "INR",
            costing_version=scope.get("costing_version_code") or "ACTUAL_ONLY",
            data_as_of=dt.datetime.now(dt.timezone.utc).isoformat(),
            is_synthetic=True,
            total_actual_cost=total_actual,
            actual_unit_cost=actual_unit_cost,
            total_planned_qty=total_planned_qty,
            total_good_qty=total_good_qty,
            total_scrap_qty=total_scrap_qty,
            total_rework_qty=total_rework_qty,
            categories=categories,
            warnings=warnings,
        )

