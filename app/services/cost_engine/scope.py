"""
Analytical Scope Resolution and Validation Service
Ensures analytical parameters are consistent, valid, and non-ambiguous before financial analysis.
"""

import uuid
import datetime as dt
from typing import Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from ...models import Plant, Product, CalendarPeriod, CostingVersion, ProductionOrder
from .schemas import AnalyticalScopeRequest


class ScopeResolutionError(ValueError):
    """Raised when the requested analytical scope is invalid or contradictory."""
    pass


class ScopeService:
    """Validates and resolves analytical boundaries."""

    @staticmethod
    def resolve_scope(db: Session, request: AnalyticalScopeRequest) -> Tuple[dict[str, Any], CostingVersion, CalendarPeriod | None]:
        """
        Resolves scope identifiers into verified entities.
        Ensures costing versions match period validity dates.
        """
        scope_data: dict[str, Any] = {
            "plant_code": request.plant_code,
            "production_order_number": request.production_order_number,
            "product_code": request.product_code,
            "material_code": request.material_code,
            "period_code": request.period_code,
            "currency": request.currency or "INR",
        }

        # 1. Resolve Plant if specified
        plant = None
        if request.plant_code:
            plant = db.query(Plant).filter(Plant.code == request.plant_code.strip().upper()).first()
            if not plant:
                raise ScopeResolutionError(f"Plant with code '{request.plant_code}' does not exist.")
            scope_data["plant_id"] = plant.id
            scope_data["plant_name"] = plant.name

        # 2. Resolve Production Order if specified
        order = None
        if request.production_order_number:
            order = db.query(ProductionOrder).filter(ProductionOrder.order_number == request.production_order_number.strip().upper()).first()
            if not order:
                raise ScopeResolutionError(f"Production Work Order '{request.production_order_number}' not found.")
            scope_data["production_order_id"] = order.id
            scope_data["plant_id"] = order.plant_id
            scope_data["product_id"] = order.product_id
            scope_data["period_id"] = order.period_id

        # 3. Resolve Product if specified
        product = None
        if request.product_code:
            product = db.query(Product).filter(Product.code == request.product_code.strip().upper()).first()
            if not product:
                raise ScopeResolutionError(f"Product SKU '{request.product_code}' does not exist.")
        elif order and order.product_id:
            product = db.query(Product).filter(Product.id == order.product_id).first()

        if product:
            scope_data["product_id"] = product.id
            scope_data["product_code"] = product.code
            scope_data["product_name"] = product.name

        # 4. Resolve Calendar Period
        period = None
        if request.period_code:
            period = db.query(CalendarPeriod).filter(CalendarPeriod.code == request.period_code.strip().upper()).first()
            if not period:
                raise ScopeResolutionError(f"Calendar period '{request.period_code}' does not exist in master periods.")
        elif order and order.period_id:
            period = db.query(CalendarPeriod).filter(CalendarPeriod.id == order.period_id).first()

        if period:
            scope_data["period_id"] = period.id
            scope_data["period_code"] = period.code
            scope_data["start_date"] = period.start_date.isoformat()
            scope_data["end_date"] = period.end_date.isoformat()

        # 5. Resolve & Validate Costing Version
        costing_version = None
        if request.costing_version_code:
            costing_version = db.query(CostingVersion).filter(
                CostingVersion.code == request.costing_version_code.strip().upper()
            ).first()
            if not costing_version:
                raise ScopeResolutionError(f"Requested standard costing version '{request.costing_version_code}' not found.")
        else:
            # Look for active approved version valid for the period
            query = db.query(CostingVersion).filter(CostingVersion.is_active == True, CostingVersion.status == "APPROVED")
            if period:
                query = query.filter(CostingVersion.valid_from <= period.end_date, CostingVersion.valid_to >= period.start_date)
            versions = query.all()
            if not versions:
                # Fallback to any active costing version
                versions = db.query(CostingVersion).filter(CostingVersion.is_active == True).all()

            if len(versions) == 1:
                costing_version = versions[0]
            elif len(versions) > 1:
                costing_version = versions[0] # Deterministically take primary active baseline
            else:
                raise ScopeResolutionError("No active standard costing version found in database.")

        # Validate period / costing version date compatibility
        if period and costing_version:
            if period.end_date < costing_version.valid_from or period.start_date > costing_version.valid_to:
                raise ScopeResolutionError(
                    f"Selected costing version '{costing_version.code}' (valid {costing_version.valid_from} to {costing_version.valid_to}) "
                    f"is not valid for period '{period.code}' ({period.start_date} to {period.end_date})."
                )

        scope_data["costing_version_id"] = costing_version.id
        scope_data["costing_version_code"] = costing_version.code
        scope_data["costing_version_name"] = costing_version.name

        return scope_data, costing_version, period

    @staticmethod
    def generate_analysis_id() -> str:
        """Generates a standard formatted analysis identifier."""
        return f"ANL-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

