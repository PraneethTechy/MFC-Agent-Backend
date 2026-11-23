"""
Data Validation Service for Manufacturing Cost Engine
Evaluates data completeness, referential integrity, and flags blocking issues before financial calculation.
"""

from typing import Any
from sqlalchemy.orm import Session
from ...models import (
    StandardCostItem,
    ProductionOrder,
    MaterialPosting,
    LabourPosting,
    MachineEvent,
    EnergyReading,
    OverheadPool,
    DataQualityIssue,
)
from .schemas import DataValidationResult


class CostDataValidator:
    """Pre-flight financial validation ensuring calculations run only on reliable data."""

    @staticmethod
    def validate_cost_data(db: Session, scope: dict[str, Any]) -> DataValidationResult:
        blocking_issues: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        missing_info: list[str] = []

        plant_id = scope.get("plant_id")
        product_id = scope.get("product_id")
        period_id = scope.get("period_id")
        costing_version_id = scope.get("costing_version_id")
        order_id = scope.get("production_order_id")

        # 1. Check Standard Cost Item existence
        sci_query = db.query(StandardCostItem).filter(
            StandardCostItem.costing_version_id == costing_version_id
        )
        if plant_id:
            sci_query = sci_query.filter(StandardCostItem.plant_id == plant_id)
        if product_id:
            sci_query = sci_query.filter(StandardCostItem.product_id == product_id)

        standard_cost_items = sci_query.all()
        if not standard_cost_items:
            blocking_issues.append({
                "rule": "ERR_MISSING_STANDARD_COST",
                "severity": "BLOCKING",
                "message": f"No standard cost items found for costing version {scope.get('costing_version_code')} within requested scope.",
            })
            missing_info.append("Standard Cost Baseline (standard_cost_items)")

        # 2. Check Production Orders
        order_query = db.query(ProductionOrder)
        if order_id:
            order_query = order_query.filter(ProductionOrder.id == order_id)
        if plant_id:
            order_query = order_query.filter(ProductionOrder.plant_id == plant_id)
        if product_id:
            order_query = order_query.filter(ProductionOrder.product_id == product_id)
        if period_id:
            order_query = order_query.filter(ProductionOrder.period_id == period_id)

        orders = order_query.all()
        if not orders:
            blocking_issues.append({
                "rule": "ERR_NO_PRODUCTION_ORDERS",
                "severity": "BLOCKING",
                "message": "No production orders match the requested scope.",
            })
            missing_info.append("Production Orders (production_orders)")

        # 3. Check Order Quantity Integrity
        order_ids = [o.id for o in orders]
        for ord_rec in orders:
            if ord_rec.actual_qty < 0:
                blocking_issues.append({
                    "rule": "ERR_NEGATIVE_GOOD_QTY",
                    "severity": "BLOCKING",
                    "order_number": ord_rec.order_number,
                    "message": f"Order {ord_rec.order_number} has negative good quantity: {ord_rec.actual_qty}",
                })
            if ord_rec.scrap_qty < 0:
                blocking_issues.append({
                    "rule": "ERR_NEGATIVE_SCRAP_QTY",
                    "severity": "BLOCKING",
                    "order_number": ord_rec.order_number,
                    "message": f"Order {ord_rec.order_number} has negative scrap quantity: {ord_rec.scrap_qty}",
                })
            if ord_rec.planned_qty > 0 and (ord_rec.actual_qty + ord_rec.scrap_qty) == 0:
                warnings.append({
                    "rule": "WARN_ZERO_OUTPUT",
                    "severity": "WARNING",
                    "order_number": ord_rec.order_number,
                    "message": f"Order {ord_rec.order_number} has zero completed output recorded.",
                })

        # 4. Coverage across the six cost categories
        category_coverage = {
            "Material": False,
            "Labour": False,
            "Machine": False,
            "Energy": False,
            "Overhead": False,
        }

        if order_ids:
            mat_count = db.query(MaterialPosting).filter(MaterialPosting.production_order_id.in_(order_ids)).count()
            category_coverage["Material"] = mat_count > 0

            lab_count = db.query(LabourPosting).filter(LabourPosting.production_order_id.in_(order_ids)).count()
            category_coverage["Labour"] = lab_count > 0

            mac_count = db.query(MachineEvent).filter(MachineEvent.production_order_id.in_(order_ids)).count()
            category_coverage["Machine"] = mac_count > 0

        if plant_id and period_id:
            nrg_count = db.query(EnergyReading).filter(
                EnergyReading.plant_id == plant_id, EnergyReading.period_id == period_id
            ).count()
            category_coverage["Energy"] = nrg_count > 0

            ovh_count = db.query(OverheadPool).filter(
                OverheadPool.plant_id == plant_id, OverheadPool.period_id == period_id
            ).count()
            category_coverage["Overhead"] = ovh_count > 0
        else:
            # Check global presence
            category_coverage["Energy"] = db.query(EnergyReading).count() > 0
            category_coverage["Overhead"] = db.query(OverheadPool).count() > 0

        for cat, covered in category_coverage.items():
            if not covered:
                warnings.append({
                    "rule": f"WARN_MISSING_{cat.upper()}_POSTINGS",
                    "severity": "WARNING",
                    "message": f"No actual {cat} postings found in requested scope; category will default to 0.00.",
                })
                missing_info.append(f"Actual {cat} Postings")

        # 5. Check recorded Ingestion Issues
        recorded_issues = db.query(DataQualityIssue).all()
        for issue in recorded_issues:
            if issue.severity == "ERROR":
                warnings.append({
                    "rule": issue.rule_code,
                    "severity": "WARNING",
                    "message": f"Unresolved ingestion issue in {issue.field_name or 'record'}: {issue.message}",
                })

        # Calculate Coverage Percentage
        covered_count = sum(1 for v in category_coverage.values() if v)
        coverage_pct = round((covered_count / len(category_coverage)) * 100.0, 1)

        # Calculate Data Trust Score for the scope
        trust_score = 100.0
        trust_score -= len(blocking_issues) * 25.0
        trust_score -= len(warnings) * 4.0
        trust_score = max(0.0, min(100.0, round(trust_score, 1)))

        can_proceed = len(blocking_issues) == 0

        return DataValidationResult(
            is_valid=can_proceed,
            can_proceed=can_proceed,
            blocking_issues=blocking_issues,
            warnings=warnings,
            data_trust_score=trust_score,
            data_coverage_pct=coverage_pct,
            missing_information=missing_info,
        )
