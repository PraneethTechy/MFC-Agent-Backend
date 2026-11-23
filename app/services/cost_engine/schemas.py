"""
Manufacturing Cost Intelligence Engine - Data Schemas & Models
Strict typing, Pydantic validation, and transparent financial result structures.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


class AnalyticalScopeRequest(BaseModel):
    """Explicit analytical boundaries requested for cost calculation."""
    plant_code: Optional[str] = Field(None, description="Plant / Facility identifier (e.g. PLANT-PUN)")
    production_order_number: Optional[str] = Field(None, description="Specific Production Work Order (e.g. PO-2026-M04-01)")
    product_code: Optional[str] = Field(None, description="Finished product SKU (e.g. PRD-MOTOR-01)")
    material_code: Optional[str] = Field(None, description="Raw material code (e.g. MAT-STEEL-01)")
    period_code: Optional[str] = Field(None, description="Fiscal calendar period (e.g. 2026-M04)")
    costing_version_code: Optional[str] = Field(None, description="Approved standard costing version (e.g. AOP-2026-V1)")
    currency: Optional[str] = Field("INR", description="Base reporting currency")


class DataValidationResult(BaseModel):
    """Data quality and integrity audit results for the requested scope."""
    is_valid: bool = Field(..., description="Whether data meets minimal integrity requirements to proceed")
    can_proceed: bool = Field(..., description="True if no blocking financial issues exist")
    blocking_issues: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    data_trust_score: float = Field(..., description="Composite 6-dimension trust score (0-100)")
    data_coverage_pct: float = Field(..., description="Percentage of required cost categories with active postings")
    missing_information: list[str] = Field(default_factory=list)


class CostCategoryBreakdown(BaseModel):
    """Detailed financial breakdown for one of the six manufacturing cost categories."""
    category: str = Field(..., description="Material, Labour, Machine, Energy, Scrap and Rework, or Manufacturing Overhead")
    actual_cost: float = Field(..., description="Actual expenditure incurred")
    standard_cost: float = Field(..., description="Standard allowed expenditure for completed good units")
    variance: float = Field(..., description="Actual minus Standard (positive is unfavourable)")
    variance_pct: float = Field(..., description="Percentage variance relative to standard")
    is_unfavourable: bool = Field(..., description="True if variance represents an unfavourable cost increase")
    allocation_type: str = Field(..., description="DIRECT, ALLOCATED, or ESTIMATED")
    unit_cost_actual: float = Field(0.0, description="Actual cost per good unit produced")
    unit_cost_standard: float = Field(0.0, description="Standard cost per good unit produced")


class CostSummaryResponse(BaseModel):
    """Aggregate actual cost summary and manufacturing output quantities."""
    status: str = "SUCCESS"
    analysis_id: str
    scope: dict[str, Any]
    currency: str
    costing_version: str
    data_as_of: str
    is_synthetic: bool = False
    total_actual_cost: float
    actual_unit_cost: float
    total_planned_qty: float
    total_good_qty: float
    total_scrap_qty: float
    total_rework_qty: float
    categories: list[CostCategoryBreakdown]
    warnings: list[str] = Field(default_factory=list)


class StandardVsActualResponse(BaseModel):
    """Comparison of standard baseline costs against actual manufacturing costs."""
    status: str = "SUCCESS"
    analysis_id: str
    scope: dict[str, Any]
    currency: str
    costing_version: str
    data_as_of: str
    is_synthetic: bool = False
    total_standard_cost: float
    total_actual_cost: float
    total_variance: float
    total_variance_pct: float
    is_unfavourable: bool
    categories: list[CostCategoryBreakdown]
    reconciliation_check: dict[str, Any]


class VarianceComponent(BaseModel):
    """Specific mathematical decomposition of a cost category variance."""
    category: str
    component_name: str
    amount: float
    variance_direction: str = Field(..., description="FAVOURABLE, UNFAVOURABLE, or NEUTRAL")
    formula_used: str
    source_data_available: bool = True
    evidence_records_count: int = 0


class VarianceBridgeResponse(BaseModel):
    """Deterministic step-by-step variance bridge from Standard to Actual."""
    status: str = "SUCCESS"
    analysis_id: str
    scope: dict[str, Any]
    currency: str
    costing_version: str
    data_as_of: str
    is_synthetic: bool = False
    standard_total_cost: float
    actual_total_cost: float
    total_variance: float
    components_by_category: dict[str, list[VarianceComponent]]
    category_unexplained: dict[str, float]
    total_explained_variance: float
    total_unexplained_variance: float
    reconciled: bool


class CostDriverRanking(BaseModel):
    """Ranked financial contributor to overall cost variance."""
    rank: int
    driver_name: str
    category: str
    variance_amount: float
    abs_variance_amount: float
    contribution_pct: float
    net_variance_contribution_pct: float = Field(0.0, description="Directional contribution to net variance (amount / net_total_variance * 100)")
    impact_type: str = Field("UNFAVOURABLE", description="UNFAVOURABLE (cost increase) or FAVOURABLE (cost saving)")
    direction: str = Field(..., description="FAVOURABLE or UNFAVOURABLE")
    supporting_evidence: str
    data_source: str
    confidence: str = Field(..., description="PROVEN, OBSERVED_CORRELATION, or HYPOTHESIS")


class CostDriverRankingResponse(BaseModel):
    """Prioritized Pareto ranking of variance contributors."""
    status: str = "SUCCESS"
    analysis_id: str
    scope: dict[str, Any]
    total_variance: float
    total_unfavourable_variance: float = 0.0
    total_favourable_variance: float = 0.0
    drivers: list[CostDriverRanking]


class VarianceInvestigationResponse(BaseModel):
    """Comprehensive evidence-backed manufacturing cost investigation result."""
    status: str = "SUCCESS"
    analysis_id: str
    scope: dict[str, Any]
    period: str
    currency: str
    costing_version: str
    data_as_of: str
    is_synthetic: bool = False
    data_quality: dict[str, Any]
    summary: dict[str, Any]
    category_breakdown: list[CostCategoryBreakdown]
    variance_components: list[VarianceComponent]
    cost_drivers: list[CostDriverRanking]
    evidence_trail: list[dict[str, Any]]
    assumptions: list[str]
    unexplained_variance: float
    warnings: list[str]

