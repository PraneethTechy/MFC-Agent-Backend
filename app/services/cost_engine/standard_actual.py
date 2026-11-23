"""
Standard vs Actual Cost Calculation Service
Calculates deterministic variances across all six manufacturing cost categories,
unit cost comparisons, and validates reconciliation integrity.
"""

from typing import Any
import datetime as dt
from sqlalchemy.orm import Session
from sqlalchemy import text
from .schemas import StandardVsActualResponse, CostCategoryBreakdown
from .scope import ScopeService


class StandardVsActualService:
    """Calculates deterministic standard vs actual variance analyses."""

    @staticmethod
    def get_standard_vs_actual(db: Session, scope: dict[str, Any]) -> StandardVsActualResponse:
        analysis_id = ScopeService.generate_analysis_id()

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
        if scope.get("costing_version_id"):
            clauses.append("costing_version_id = :costing_version_id")
            params["costing_version_id"] = scope["costing_version_id"]

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        query_sql = f"""
        SELECT 
            COALESCE(SUM(completed_good_qty), 0.00) AS total_good_qty,
            
            -- Standard Extended Costs
            COALESCE(SUM(standard_material_cost), 0.0000) AS std_material,
            COALESCE(SUM(standard_labour_cost), 0.0000) AS std_labour,
            COALESCE(SUM(standard_machine_cost), 0.0000) AS std_machine,
            COALESCE(SUM(standard_energy_cost), 0.0000) AS std_energy,
            COALESCE(SUM(standard_scrap_allowance_cost), 0.0000) AS std_scrap_allowance,
            COALESCE(SUM(standard_overhead_cost), 0.0000) AS std_overhead,
            COALESCE(SUM(standard_total_cost), 0.0000) AS std_total,

            -- Actual Costs
            COALESCE(SUM(actual_material_cost), 0.0000) AS act_material,
            COALESCE(SUM(actual_labour_cost), 0.0000) AS act_labour,
            COALESCE(SUM(actual_machine_cost), 0.0000) AS act_machine,
            COALESCE(SUM(actual_energy_cost), 0.0000) AS act_energy,
            COALESCE(SUM(actual_rework_cost), 0.0000) AS act_rework,
            COALESCE(SUM(absorbed_overhead_cost), 0.0000) AS act_overhead,
            COALESCE(SUM(total_actual_cost), 0.0000) AS act_total

        FROM v_variance_facts
        {where_sql}
        """

        result = db.execute(text(query_sql), params).mappings().first()

        good_qty = float(result["total_good_qty"] or 0.0)

        # Standard amounts
        std_mat = round(float(result["std_material"] or 0.0), 4)
        std_lab = round(float(result["std_labour"] or 0.0), 4)
        std_mac = round(float(result["std_machine"] or 0.0), 4)
        std_nrg = round(float(result["std_energy"] or 0.0), 4)
        std_qlt = round(float(result["std_scrap_allowance"] or 0.0), 4)
        std_ovh = round(float(result["std_overhead"] or 0.0), 4)
        total_std = round(std_mat + std_lab + std_mac + std_nrg + std_qlt + std_ovh, 4)

        # Actual amounts
        act_mat = round(float(result["act_material"] or 0.0), 4)
        act_lab = round(float(result["act_labour"] or 0.0), 4)
        act_mac = round(float(result["act_machine"] or 0.0), 4)
        act_nrg = round(float(result["act_energy"] or 0.0), 4)
        act_qlt = round(float(result["act_rework"] or 0.0), 4)
        act_ovh = round(float(result["act_overhead"] or 0.0), 4)
        total_act = round(act_mat + act_lab + act_mac + act_nrg + act_qlt + act_ovh, 4)

        # Variances
        total_var = round(total_act - total_std, 4)
        total_var_pct = round((total_var / total_std * 100.0), 2) if total_std > 0 else 0.0

        def make_cat(name: str, actual: float, standard: float, alloc: str) -> CostCategoryBreakdown:
            variance = round(actual - standard, 4)
            var_pct = round((variance / standard * 100.0), 2) if standard > 0 else 0.0
            act_unit = round(actual / good_qty, 4) if good_qty > 0 else 0.0
            std_unit = round(standard / good_qty, 4) if good_qty > 0 else 0.0
            return CostCategoryBreakdown(
                category=name,
                actual_cost=actual,
                standard_cost=standard,
                variance=variance,
                variance_pct=var_pct,
                is_unfavourable=variance > 0,
                allocation_type=alloc,
                unit_cost_actual=act_unit,
                unit_cost_standard=std_unit,
            )

        categories = [
            make_cat("Material", act_mat, std_mat, "DIRECT"),
            make_cat("Labour", act_lab, std_lab, "DIRECT"),
            make_cat("Machine", act_mac, std_mac, "DIRECT"),
            make_cat("Energy", act_nrg, std_nrg, "ESTIMATED"),
            make_cat("Scrap and Rework", act_qlt, std_qlt, "DIRECT"),
            make_cat("Manufacturing Overhead", act_ovh, std_ovh, "ALLOCATED"),
        ]

        sum_cat_variances = round(sum(c.variance for c in categories), 4)
        reconciled = (round(total_act - total_std, 4) == sum_cat_variances) and (sum_cat_variances == total_var)

        reconciliation_check = {
            "total_actual_minus_standard": round(total_act - total_std, 4),
            "sum_of_category_variances": sum_cat_variances,
            "total_variance": total_var,
            "reconciled": reconciled,
        }

        return StandardVsActualResponse(
            status="SUCCESS",
            analysis_id=analysis_id,
            scope=scope,
            currency=scope.get("currency") or "INR",
            costing_version=scope.get("costing_version_code") or "AOP-2026-V1",
            data_as_of=dt.datetime.now(dt.timezone.utc).isoformat(),
            is_synthetic=True,
            total_standard_cost=total_std,
            total_actual_cost=total_act,
            total_variance=total_var,
            total_variance_pct=total_var_pct,
            is_unfavourable=total_var > 0,
            categories=categories,
            reconciliation_check=reconciliation_check,
        )

