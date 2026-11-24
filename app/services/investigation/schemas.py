"""
Manufacturing Cost Investigation Schemas
Strict Pydantic v2 schemas defining the contract for root-cause investigations,
waterfall variance decomposition, evidence governance, and interactive reports.
"""

from typing import Any, Optional, Union
from pydantic import BaseModel, Field


class ExecutiveFinding(BaseModel):
    cost_movement_type: str = Field(
        ...,
        description="COST_INCREASED, COST_DECREASED, COST_STABLE, NOT_COMPARABLE, or INSUFFICIENT_DATA"
    )
    headline: str = Field(..., description="High-impact executive answer")
    sub_headline: str = Field(..., description="Key contributors summary")
    baseline_period_label: str
    current_period_label: str
    is_increase: bool
    change_pct: float
    change_amount: float


class InvestigationScope(BaseModel):
    baseline_period: Optional[str] = None
    current_period: Optional[str] = None
    reporting_period: Optional[str] = None
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    baseline_min_date: Optional[str] = None
    baseline_max_date: Optional[str] = None
    is_partial_period: bool = False
    partial_period_note: Optional[str] = None
    datasets_analyzed: int = 1
    uploaded_files_count: int = 1
    dataset_types_count: int = 1
    dataset_types: list[str] = Field(default_factory=list)
    records_parsed: int = 0
    records_validated: int = 0
    records_rejected: int = 0
    duplicate_files_detected: list[str] = Field(default_factory=list)
    period_range: str = "Current Upload Scope"
    products_count: int = 0
    plants_count: int = 0
    lines_count: int = 0
    cost_records_count: int = 0
    matched_production_label: str = "Unavailable (production data not uploaded)"
    currency: str = "INR"
    plant_code: Optional[str] = None
    product_code: Optional[str] = None
    line_code: Optional[str] = None
    uploaded_files: list[str] = Field(default_factory=list)
    inspection_id: Optional[str] = None
    files_parsed_count: int = 0
    unsupported_files: list[str] = Field(default_factory=list)
    file_manifest: list[dict[str, Any]] = Field(default_factory=list)
    comparison_mode: Optional[str] = "PREVIOUS_MONTH"
    baseline_months: list[str] = Field(default_factory=list)
    available_historical_months: list[dict[str, Any]] = Field(default_factory=list)
    coverage_summary: Optional[str] = None
    is_unequal_duration: bool = False
    is_aggregate_history: bool = False
    comparison_note: Optional[str] = None


class WaterfallStep(BaseModel):
    name: str
    amount: float
    pct_change: float
    running_total: float
    step_type: str = Field(..., description="START, INCREASE, DECREASE, or END")
    description: Optional[str] = None
    classification: str = Field("PROVEN", description="PROVEN, OBSERVED_CORRELATION, HYPOTHESIS, UNAVAILABLE")


class CostMovementBridge(BaseModel):
    baseline_total: float
    current_total: float
    net_variance: float
    steps: list[WaterfallStep]
    total_explained: float
    unexplained_remainder: float
    reconciled: bool


class RootCauseFinding(BaseModel):
    finding_id: str
    title: str
    evidence_classification: str = Field(..., description="PROVEN, OBSERVED, HYPOTHESIS, or LIMITATION")
    financial_impact_amount: float
    financial_impact_pct: float
    direction: str = Field("UNFAVOURABLE", description="UNFAVOURABLE or FAVOURABLE")
    short_explanation: str
    detailed_explanation: str
    what_happened: str
    scope_affected: str
    data_source: str
    evidence_reliability: str
    supporting_metrics: dict[str, Any] = Field(default_factory=dict)
    price_movement_table: list[dict[str, Any]] = Field(default_factory=list)
    trend_data: list[dict[str, Any]] = Field(default_factory=list)


class CategoryMovement(BaseModel):
    category: str
    baseline_amount: float
    current_amount: float
    change_amount: float
    change_pct: float
    share_of_total_pct: float
    allocation_type: str = "DIRECT"


class ProductCostMovement(BaseModel):
    product_code: str
    product_name: str
    baseline_cost_per_unit: Optional[float] = None
    current_cost_per_unit: Optional[float] = None
    change_amount: Optional[float] = None
    change_pct: Optional[float] = None
    main_driver: str
    baseline_total_cost: float
    current_total_cost: float
    good_units_produced: Optional[float] = None
    availability_reason: Optional[str] = None


class ReliabilityCheck(BaseModel):
    title: str
    status: str = "PASS"
    details: str


class DataReliability(BaseModel):
    score: Optional[float] = None
    grade: Optional[str] = "VERIFIED"
    checks: list[ReliabilityCheck]
    uncosted_runs: Optional[int] = None
    uncosted_volume: Optional[int] = None
    cost_coverage_pct: Optional[float] = None
    total_records_evaluated: Optional[int] = None
    matching_coverage_pct: Optional[float] = None
    rejected_records_count: Optional[int] = 0
    reconciliation_status: Optional[str] = "VERIFIED"


class RecommendedStep(BaseModel):
    step_number: int
    action: Optional[str] = None
    rationale: Optional[str] = None
    priority: str = "HIGH"

    # Rich Evidence-Driven Fields for Manufacturing Cost Improvement Plan
    recommendation_id: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = "Material Cost"  # Material Cost, Labour, Machine, Energy, Quality, Scrap & Rework, Operational Efficiency
    problem_statement: Optional[str] = None
    short_summary: Optional[str] = None
    observed_evidence: Optional[Union[list[dict[str, Any]], dict[str, Any]]] = None
    key_evidence: Optional[list[dict[str, Any]]] = None
    root_cause_status: Optional[str] = "PROVEN"  # PROVEN, OBSERVED_CORRELATION, POTENTIAL_CONTRIBUTING_FACTOR, UNVERIFIED
    root_cause_explanation: Optional[str] = None
    affected_scope: Optional[dict[str, Any]] = None  # products, components, plants, lines, time_period
    recommended_action: Optional[str] = None
    implementation_steps: list[str] = Field(default_factory=list)
    playbook_steps: list[str] = Field(default_factory=list)
    expected_benefit: Optional[Union[dict[str, Any], str]] = None
    estimated_savings_amount: Optional[float] = None
    estimated_savings_display: Optional[str] = None  # e.g. "₹22.39 Cr" or "Not Quantified"
    unit_cost_impact_display: Optional[str] = None  # e.g. "↓ ~7.1%"
    implementation_timeframe: Optional[str] = None  # e.g. "2 - 4 Weeks"
    owner: Optional[str] = None
    target_kpi: Optional[str] = None
    current_measured_value: Optional[str] = None
    proposed_target: Optional[str] = None
    verification_method: Optional[str] = None
    savings_calculation: Optional[dict[str, Any]] = None  # methodology, formula, assumptions
    confidence: Optional[str] = "Verified (PROVEN)"
    data_limitations: Optional[Union[list[str], str]] = None
    supporting_record_references: list[str] = Field(default_factory=list)


class MonthlyTrendPoint(BaseModel):
    period: str
    month_label: str
    total_cost: float
    cost_per_good_unit: Optional[float] = None
    good_output: Optional[float] = None


class CostCompositionSlice(BaseModel):
    name: str
    amount: float
    pct: float
    color: str


class InvestigationReport(BaseModel):
    report_id: str
    inspection_id: Optional[str] = None
    staged_batch_id: Optional[str] = None
    uploaded_files: list[str] = Field(default_factory=list)
    schema_version: str = "1.0.0"
    data_origin: str = "REAL"
    generated_at: str
    computation_ms: int

    executive_finding: ExecutiveFinding
    scope: InvestigationScope

    baseline_total_cost: float
    current_total_cost: float
    cost_change_amount: float
    cost_change_pct: float
    is_unequal_duration: bool = False
    is_aggregate_history: bool = False
    raw_baseline_total_cost: Optional[float] = None
    normalized_baseline_total_cost: Optional[float] = None
    normalized_daily_cost: Optional[float] = None
    normalized_baseline_daily_cost: Optional[float] = None
    run_rate_variance_pct: Optional[float] = None

    baseline_cost_per_good_unit: Optional[float] = None
    current_cost_per_good_unit: Optional[float] = None
    unit_cost_change_pct: Optional[float] = None

    # Denominators and produced unit cost movement
    baseline_cost_per_produced_unit: Optional[float] = None
    current_cost_per_produced_unit: Optional[float] = None
    produced_unit_cost_change_pct: Optional[float] = None
    baseline_produced_qty: Optional[float] = None
    current_produced_qty: Optional[float] = None
    baseline_good_qty: Optional[float] = None
    current_good_qty: Optional[float] = None

    bridge: CostMovementBridge
    findings: list[RootCauseFinding]
    category_breakdown: list[CategoryMovement]
    product_comparison: list[ProductCostMovement]
    data_reliability: DataReliability
    monthly_trend: list[MonthlyTrendPoint]
    cost_composition: list[CostCompositionSlice]

    # Dynamic period metadata and granular trend series
    reporting_period_label: Optional[str] = None
    comparison_period_label: Optional[str] = None
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    baseline_min_date: Optional[str] = None
    baseline_max_date: Optional[str] = None
    is_partial_period: bool = False
    partial_period_note: Optional[str] = None
    daily_cost_trend: list[dict[str, Any]] = Field(default_factory=list)
    weekly_cost_trend: list[dict[str, Any]] = Field(default_factory=list)
    available_granularities: list[str] = Field(default_factory=lambda: ["Daily", "Weekly"])
    default_granularity: str = "Daily"
    reporting_context: dict[str, Any] = Field(default_factory=dict)

    limitations: list[str]
    recommended_steps: list[RecommendedStep]
    cost_improvement_plan: Optional[dict[str, Any]] = None
    calculation_details: dict[str, Any] = Field(default_factory=dict)
    ai_narrative: Optional[str] = None
    status: Optional[str] = None
    consolidation_status: Optional[str] = None


class InvestigationHistoryItem(BaseModel):
    report_id: str
    inspection_id: Optional[str] = None
    title: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    uploaded_file_count: int = 1
    uploaded_files: list[str] = Field(default_factory=list)
    dataset_types: list[str] = Field(default_factory=list)
    reporting_period: Optional[str] = None
    executive_finding: Optional[str] = None
    data_origin: str = "REAL"
    is_synthetic: bool = False


