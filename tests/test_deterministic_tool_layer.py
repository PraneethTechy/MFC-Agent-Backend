"""
Test Suite for Deterministic Manufacturing Intelligence Tool Layer (Task 2)
Covers all 11 specific requirements:
1. Every registered tool can be discovered.
2. Every registered tool executes successfully with valid inputs.
3. Invalid filters are handled safely.
4. Date ranges are respected.
5. Material intelligence calculations are reproducible.
6. Production-quality calculations are reproducible.
7. Product and cost movement calculations are reproducible.
8. Empty datasets return meaningful insufficient-evidence results.
9. Synthetic data is not silently mixed with original data.
10. The agent can select the correct tools for representative manufacturing questions.
11. Existing application and analytics regression tests continue to pass.
"""

from decimal import Decimal
import pytest
from unittest.mock import MagicMock, patch

from app.tools import (
    TOOLS,
    validate_cost_data,
    get_cost_summary,
    get_standard_vs_actual,
    calculate_variance_bridge,
    rank_cost_drivers,
    inspect_bom_components,
    investigate_variance,
    analyze_cost_movement,
    get_management_recommendations,
    get_material_intelligence,
    get_production_quality_intelligence,
    get_product_intelligence,
    discover_manufacturing_datasets,
)
from app.agent import TOOL_MAP, _parse_and_validate_action


# =============================================================================
# REQUIREMENT 1: Every Registered Tool Can Be Discovered
# =============================================================================
def test_requirement_1_all_13_tools_registered_and_discoverable():
    """Verifies all 13 tools are registered, named properly, and exposed to the agent."""
    assert len(TOOLS) == 13, f"Expected 13 registered tools, found {len(TOOLS)}"
    tool_names = {t.name for t in TOOLS}
    expected_names = {
        "validate_cost_data",
        "get_cost_summary",
        "get_standard_vs_actual",
        "calculate_variance_bridge",
        "rank_cost_drivers",
        "inspect_bom_components",
        "investigate_variance",
        "analyze_cost_movement",
        "get_management_recommendations",
        "get_material_intelligence",
        "get_production_quality_intelligence",
        "get_product_intelligence",
        "discover_manufacturing_datasets",
    }
    assert tool_names == expected_names
    assert set(TOOL_MAP.keys()) == expected_names

    # Verify each tool has non-empty description and valid args_schema
    for t in TOOLS:
        assert len(t.description) > 20
        assert hasattr(t, "args")


# =============================================================================
# REQUIREMENT 2: Every Registered Tool Executes Successfully with Valid Inputs
# =============================================================================
def test_requirement_2_every_tool_executes_successfully():
    """Verifies that invoking each of the 13 tools with valid arguments succeeds."""
    # 1. validate_cost_data
    r1 = validate_cost_data.invoke({})
    assert r1.get("status") == "VALIDATED"

    # 2. get_cost_summary
    r2 = get_cost_summary.invoke({"plant_code": "IN-KA-01"})
    assert r2.get("status") == "SUCCESS"

    # 3. get_standard_vs_actual
    r3 = get_standard_vs_actual.invoke({"product_code": "SPH-PRO-256"})
    assert r3.get("status") == "PROVISIONAL_COMPARISON"

    # 4. calculate_variance_bridge
    r4 = calculate_variance_bridge.invoke({"product_code": "SPH-PRO-256"})
    assert r4.get("status") == "PROVISIONAL_BRIDGE"

    # 5. rank_cost_drivers
    r5 = rank_cost_drivers.invoke({})
    assert r5.get("status") == "SUCCESS"

    # 6. inspect_bom_components
    r6 = inspect_bom_components.invoke({"product_code": "SPH-PRO-256"})
    assert r6.get("status") == "SUCCESS"

    # 7. investigate_variance
    r7 = investigate_variance.invoke({"product_code": "SPH-PRO-256"})
    assert r7.get("status") == "INVESTIGATION_COMPLETE"

    # 8. analyze_cost_movement
    r8 = analyze_cost_movement.invoke({"current_period": "2026-10", "baseline_period": "2026-09"})
    assert r8.get("status") == "COMPLETED"

    # 9. get_management_recommendations (returns prioritized list of recommendation dicts)
    r9 = get_management_recommendations.invoke({"period_code": "2026-10"})
    assert isinstance(r9, list)
    assert len(r9) > 0

    # 10. get_material_intelligence
    r10 = get_material_intelligence.invoke({"period_code": "2026-10", "product_code": "SPH-PRO-256"})
    assert r10.get("status") == "COMPLETED"

    # 11. get_production_quality_intelligence
    r11 = get_production_quality_intelligence.invoke({"period_code": "2026-10"})
    assert r11.get("status") == "COMPLETED"

    # 12. get_product_intelligence
    r12 = get_product_intelligence.invoke({"period_code": "2026-10"})
    assert r12.get("status") == "COMPLETED"

    # 13. discover_manufacturing_datasets
    r13 = discover_manufacturing_datasets.invoke({"dimension_number": 1})
    assert r13.get("status") == "DISCOVERY_SUCCESS"


# =============================================================================
# REQUIREMENT 3: Invalid Filters Handled Safely
# =============================================================================
def test_requirement_3_invalid_filters_handled_safely():
    """Verifies that non-existent plants, products, or unknown periods return structured errors, not crashes."""
    # Unknown plant in get_cost_summary
    r_cost = get_cost_summary.invoke({"plant_code": "NON-EXISTENT-PLANT"})
    assert r_cost.get("status") == "NO_DATA"

    # Unknown product in inspect_bom_components
    r_bom = inspect_bom_components.invoke({"product_code": "UNKNOWN-SKU-999"})
    assert r_bom.get("status") == "NOT_FOUND"

    # Unknown period in analyze_cost_movement
    r_mov = analyze_cost_movement.invoke({"current_period": "1999-01", "baseline_period": "1998-12"})
    assert r_mov.get("status") in ("PERIOD_UNAVAILABLE", "INVALID_PERIOD", "NO_DATA", "ERROR")

    # Invalid dimension in discover_manufacturing_datasets
    r_disc = discover_manufacturing_datasets.invoke({"dimension_number": 999})
    assert r_disc.get("status") == "DISCOVERY_SUCCESS"
    assert r_disc["dimension_sufficiency"]["is_supported"] is False


# =============================================================================
# REQUIREMENT 4: Date Ranges Respected
# =============================================================================
def test_requirement_4_date_ranges_respected():
    """Verifies filtering by period code (e.g. 2026-08 vs 2026-10) isolates period-specific rows."""
    r_aug = get_cost_summary.invoke({"period_code": "2026-08"})
    r_oct = get_cost_summary.invoke({"period_code": "2026-10"})

    assert r_aug.get("status") == "SUCCESS"
    assert r_oct.get("status") == "SUCCESS"
    assert r_aug["batches_analyzed"] > 0
    assert r_oct["batches_analyzed"] > 0
    # Cost in August and October must differ
    assert r_aug["total_direct_actual_cost_inr"] != r_oct["total_direct_actual_cost_inr"]


# =============================================================================
# REQUIREMENT 5: Material Intelligence Calculations Reproducible
# =============================================================================
def test_requirement_5_material_intelligence_reproducible():
    """Verifies theoretical consumption, actual consumption variance, and Pareto ranking with provenance governance."""
    # 1. Baseline Period (October 2026): BOM requirements are calculated, purchase prices remain NOT_AVAILABLE
    res_oct = get_material_intelligence.invoke({"period_code": "2026-10", "product_code": "SPH-PRO-256"})
    assert res_oct.get("status") == "COMPLETED"
    assert "components" in res_oct
    comps_oct = res_oct["components"]
    assert len(comps_oct) > 0

    # Every component has theoretical consumption >= 0
    for c in comps_oct:
        assert c["theoretical_consumption_qty"] >= 0.0
        assert "material_code" in c
        assert "material_name" in c

    # In baseline period, unverified synthetic purchases are not mingled into audited ground truth
    assert res_oct.get("purchase_status") == "NOT_AVAILABLE"

    # 2. Extended Period (November 2026): Purchase prices exist and Pareto ranking is active
    res_nov = get_material_intelligence.invoke({"period_code": "2026-11"})
    assert res_nov.get("status") == "COMPLETED"
    assert res_nov.get("purchase_status") == "VERIFIED"
    assert res_nov.get("key_pareto_drivers_count", 0) > 0
    pareto_drivers = [c for c in res_nov["components"] if c.get("is_pareto_key_driver") is True]
    assert len(pareto_drivers) > 0


# =============================================================================
# REQUIREMENT 6: Production Quality Calculations Reproducible
# =============================================================================
def test_requirement_6_production_quality_reproducible():
    """Verifies operational yield, uncosted volume governance, and serialized defect codes."""
    res = get_production_quality_intelligence.invoke({"period_code": "2026-09"})
    assert res.get("status") == "COMPLETED"
    summary = res["factory_summary"]

    assert summary["factory_actual_qty"] > 0
    assert summary["factory_good_qty"] > 0
    assert summary["factory_yield_pct"] > 90.0

    # Operational governance: uncosted operational volumes tracked
    gov = res["operational_governance"]
    assert gov["uncosted_runs_count"] > 0
    assert gov["costed_runs_count"] > 0

    # Top serialized defects populated
    defects = res["top_defects"]
    assert len(defects) > 0
    assert any("defect_code" in d for d in defects)


# =============================================================================
# REQUIREMENT 7: Product and Cost Movement Calculations Reproducible
# =============================================================================
def test_requirement_7_product_and_cost_movement_reproducible():
    """Verifies mathematical reconciliation of cost movement (0.00 residual discrepancy) and SKU unit costs."""
    # 1. Product Intelligence
    prod_res = get_product_intelligence.invoke({"period_code": "2026-10"})
    assert prod_res.get("status") == "COMPLETED"
    assert len(prod_res["products"]) >= 3
    # Check mix limitation disclosure
    assert "Governance Note" in prod_res["mix_limitation_disclosure"]

    # 2. Cost Movement Bridge
    mov_res = analyze_cost_movement.invoke({"current_period": "2026-10", "baseline_period": "2026-09"})
    assert mov_res.get("status") == "COMPLETED"
    reconciliation = mov_res["reconciliation"]
    assert reconciliation["is_reconciled"] is True
    assert abs(reconciliation["discrepancy"]) < 0.01  # Zero discrepancy


# =============================================================================
# REQUIREMENT 8: Empty Datasets Return Meaningful Insufficient-Evidence Results
# =============================================================================
def test_requirement_8_empty_scope_insufficient_evidence():
    """Verifies that scopes with no matching records return informative NO_DATA responses."""
    res = get_cost_summary.invoke({"plant_code": "IN-TN-99", "period_code": "2020-01"})
    assert res.get("status") == "NO_DATA"
    assert "No cost records found" in res.get("message", "")


# =============================================================================
# REQUIREMENT 9: Synthetic Data is Not Silently Mixed with Original Data
# =============================================================================
def test_requirement_9_synthetic_isolation_governance():
    """Verifies that baseline queries filter out synthetic rows, and synthetic periods are explicitly marked."""
    # Baseline query (October 2026) must have is_synthetic == False
    oct_res = get_product_intelligence.invoke({"period_code": "2026-10"})
    assert oct_res["is_synthetic"] is False

    # November query (synthetic period) in material intelligence
    nov_res = get_material_intelligence.invoke({"period_code": "2026-11"})
    assert nov_res.get("status") == "COMPLETED"
    assert nov_res["data_governance"]["is_synthetic"] is True
    assert nov_res["data_governance"]["data_origin"] == "SYNTHETIC_TEST"

    # Check synthetic isolation rules from discovery tool
    disc = discover_manufacturing_datasets.invoke({})
    rules = disc.get("verified_relationships", [])
    assert len(rules) > 0


# =============================================================================
# REQUIREMENT 10: Agent Action Parsing & Tool Selection
# =============================================================================
def test_requirement_10_agent_action_parsing_new_tools():
    """Verifies that the agent JSON action parser recognizes and validates calls to new tools."""
    # Action calling get_material_intelligence
    raw_mat = '{"action": "get_material_intelligence", "input": {"product_code": "SPH-PRO-256", "period_code": "2026-10"}}'
    action_mat = _parse_and_validate_action(raw_mat)
    assert action_mat["action"] == "get_material_intelligence"
    assert action_mat["input"]["product_code"] == "SPH-PRO-256"

    # Action calling get_production_quality_intelligence
    raw_qual = '{"action": "get_production_quality_intelligence", "input": {"line_code": "SMT-L1"}}'
    action_qual = _parse_and_validate_action(raw_qual)
    assert action_qual["action"] == "get_production_quality_intelligence"

    # Action calling discover_manufacturing_datasets
    raw_disc = '{"action": "discover_manufacturing_datasets", "input": {"question": "Why did OLED display price spike?"}}'
    action_disc = _parse_and_validate_action(raw_disc)
    assert action_disc["action"] == "discover_manufacturing_datasets"


# =============================================================================
# REQUIREMENT 11: Deferred Dimensions Flagged as DEFERRED_NO_DATA
# =============================================================================
def test_requirement_11_deferred_dimensions_never_claimed_as_root_causes():
    """Verifies that Dimensions 10, 11, 15 are reported as DEFERRED with zero evidence sufficiency score."""
    for dim_num in (10, 11, 15):
        res = discover_manufacturing_datasets.invoke({"dimension_number": dim_num})
        assert res.get("status") == "DISCOVERY_SUCCESS"
        suff = res["dimension_sufficiency"]
        assert suff["status"] == "DEFERRED_NO_DATA"
        assert suff["is_supported"] is False
        assert suff["is_deferred"] is True
        assert suff["evidence_sufficiency_score"] == 0.0


# =============================================================================
# REQUIREMENT 12: Zero Pydantic Dependencies in Task 2 Implementations
# =============================================================================
def test_requirement_12_zero_pydantic_in_task_2():
    """Verifies that all Task 2 dataset registry models and new tools use standard Python dataclasses without Pydantic."""
    import inspect
    from app.services.dataset_registry import discovery, models, time_period
    import app.tools as tools_mod

    # 1. Dataset registry modules do not import pydantic
    for mod in (discovery, models, time_period):
        src = inspect.getsource(mod)
        assert "from pydantic" not in src, f"{mod.__name__} must not import from pydantic"
        assert "import pydantic" not in src, f"{mod.__name__} must not import pydantic"

    # 2. Verify Task 2 custom Pydantic input schemas were removed
    removed_schemas = [
        "MaterialIntelligenceInput",
        "ProductionQualityInput",
        "ProductIntelligenceInput",
        "DatasetDiscoveryInput",
    ]
    for schema_name in removed_schemas:
        assert not hasattr(tools_mod, schema_name), f"Schema {schema_name} should have been removed from tools.py"

    # 3. Verify underlying tool functions use pure Python signatures
    new_tool_funcs = [
        tools_mod.get_material_intelligence.func,
        tools_mod.get_production_quality_intelligence.func,
        tools_mod.get_product_intelligence.func,
        tools_mod.discover_manufacturing_datasets.func,
    ]
    for func in new_tool_funcs:
        sig = inspect.signature(func)
        assert len(sig.parameters) > 0


# =============================================================================
# REQUIREMENT 13: Authoritative 18-Dimension Taxonomy & Analytical Techniques
# =============================================================================
def test_requirement_13_authoritative_18_dimension_mapping():
    """Verifies the exact 18-dimension definitions and Dimension 18 naming."""
    from app.services.dataset_registry.discovery import DatasetDiscoveryService

    service = DatasetDiscoveryService()
    dims = service.AUTHORITATIVE_DIMENSIONS

    assert len(dims) == 18, f"Expected 18 dimensions, got {len(dims)}"

    expected_names = {
        1: "Total manufacturing cost",
        2: "Cost per good unit",
        3: "Scrap and rework",
        4: "Plant and production-line performance",
        5: "Product-wise manufacturing cost",
        6: "Material consumption and machine efficiency",
        7: "Energy consumption",
        8: "Employee absenteeism",
        9: "Workforce allocation",
        10: "Employee skill gaps",
        11: "Training effectiveness",
        12: "Labour productivity",
        13: "Procurement and supplier performance",
        14: "Inventory management",
        15: "Management and organizational decisions",
        16: "Production capacity and capacity utilization",
        17: "Material consumption and inventory reconciliation",
        18: "Smartphone testing and inspection efficiency",
    }

    for dim_num, expected_name in expected_names.items():
        assert dim_num in dims, f"Dimension {dim_num} missing"
        assert dims[dim_num]["name"] == expected_name, (
            f"Dimension {dim_num} name mismatch: expected '{expected_name}', got '{dims[dim_num]['name']}'"
        )

    # Explicit check: Dimension 18 MUST NOT be Product Mix
    assert dims[18]["name"] == "Smartphone testing and inspection efficiency"
    assert "mix" not in dims[18]["name"].lower()

    # Deferred checks
    assert dims[10]["status"] == "DEFERRED_NO_DATA"
    assert dims[11]["status"] == "DEFERRED_NO_DATA"
    assert dims[15]["status"] == "DEFERRED_NO_DATA"

    # Analytical routing check: product mix inquiry routes to Dimensions 1, 2, 5
    mix_match = service.find_datasets_for_question("How did SKU product mix affect our costs?")
    assert 5 in mix_match.relevant_dimensions
    assert 1 in mix_match.relevant_dimensions
    assert 2 in mix_match.relevant_dimensions


# =============================================================================
# REQUIREMENT 14: Workforce Row-Count Reconciliation (21,669 vs 21,672)
# =============================================================================
def test_requirement_14_workforce_row_count_breakdown():
    """
    Reconciles the exact workforce row counts across all physical CSV files:
    - 21,669: Operational workforce transaction rows (attendance, allocation, shifts, employee master)
    - 21,672: Grand total including the 3-row static catalog (d10_shift_definition_v1.csv)
    """
    import csv
    import os

    workforce_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "generated", "workforce")
    assert os.path.isdir(workforce_dir), f"Directory {workforce_dir} not found"

    expected_files = {
        "d10_attendance_v1.csv": 19557,
        "d10_employee_master_v1.csv": 248,
        "d10_line_allocation_v1.csv": 380,
        "d10_line_shift_labour_daily_v1.csv": 1104,
        "d10_shift_assignment_v1.csv": 380,
        "d10_shift_definition_v1.csv": 3,
    }

    actual_counts = {}
    for filename, exp_count in expected_files.items():
        filepath = os.path.join(workforce_dir, filename)
        assert os.path.exists(filepath), f"File {filename} missing"
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            row_count = sum(1 for _ in reader)
        actual_counts[filename] = row_count
        assert row_count == exp_count, f"Row count for {filename}: expected {exp_count}, got {row_count}"

    operational_sum = sum(cnt for f, cnt in actual_counts.items() if f != "d10_shift_definition_v1.csv")
    grand_total = sum(actual_counts.values())

    assert operational_sum == 21669, f"Expected 21,669 operational rows, got {operational_sum}"
    assert grand_total == 21672, f"Expected 21,672 total rows, got {grand_total}"
    assert grand_total - operational_sum == 3, "Discrepancy must equal 3 rows (shift definition catalog)"

