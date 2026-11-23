"""
Comprehensive Test Suite for Manufacturing Dataset Registry & Dynamic Data Discovery Layer
Covers all 10 specific architectural test requirements:
1. All 10 logical datasets discoverable.
2. Multiple physical files belonging to one logical dataset.
3. Different date ranges across datasets.
4. Hourly, daily, transaction, shift, and static spec granularities.
5. Partial date coverage detection.
6. Missing date columns handled (e.g. static reference BOM).
7. Missing or ambiguous identifiers handled (candidate vs confirmed keys).
8. Synthetic versus original provenance distinction.
9. Candidate versus verified relationships filtering.
10. Unsupported investigation dimensions (10, 11, 15 correctly flagged as deferred).
"""

import datetime as dt
import pytest
from app.services.dataset_registry import (
    ManufacturingDatasetRegistry,
    DatasetDiscoveryService,
    TimePeriodResolver,
    GranularityType,
    ProvenanceTier,
    RelationshipStatus,
    LogicalDatasetDefinition,
    PhysicalSourceReference,
    ColumnMetadata,
)


@pytest.fixture
def registry():
    return ManufacturingDatasetRegistry.get_instance()


@pytest.fixture
def discovery_service(registry):
    return DatasetDiscoveryService(registry)


# =============================================================================
# REQUIREMENT 1: All 10 Logical Datasets Discoverable
# =============================================================================
def test_requirement_1_all_10_logical_datasets_discoverable(discovery_service):
    """Verifies that all 10 logical manufacturing datasets (D1-D10) are registered and discoverable."""
    datasets = discovery_service.list_available_datasets(include_synthetic=True)
    assert len(datasets) == 10, f"Expected 10 logical datasets, found {len(datasets)}"

    expected_domains = {f"D{i}" for i in range(1, 11)}
    found_domains = {d.domain_code for d in datasets}
    assert found_domains == expected_domains, f"Missing domains: {expected_domains - found_domains}"

    # Verify each dataset has required fields populated
    for ds in datasets:
        assert ds.dataset_id.startswith("d")
        assert len(ds.name) > 0
        assert len(ds.business_description) > 20
        assert len(ds.physical_sources) >= 1
        assert len(ds.columns) > 0
        assert ds.is_active is True


# =============================================================================
# REQUIREMENT 2: Multiple Physical Files Belonging to One Logical Dataset
# =============================================================================
def test_requirement_2_multiple_physical_files_per_logical_dataset(discovery_service):
    """Verifies that logical datasets accurately map to multiple physical files (raw, enhanced, generated)."""
    # D1 has raw CSV + enhanced CSV + DB table
    d1 = discovery_service.get_dataset("d1")
    assert d1 is not None
    assert len(d1.physical_sources) >= 2
    sources_d1 = [s.location for s in d1.physical_sources]
    assert any("raw" in s for s in sources_d1)
    assert any("enhanced" in s for s in sources_d1)

    # D5 has 3 physical CSVs (orders, runs, links)
    d5 = discovery_service.get_dataset("d5")
    assert d5 is not None
    assert len(d5.physical_sources) >= 3
    sources_d5 = [s.location for s in d5.physical_sources]
    assert any("d5_production_order_v1.csv" in s for s in sources_d5)
    assert any("d5_production_run_v1.csv" in s for s in sources_d5)
    assert any("d5_run_source_link_v1.csv" in s for s in sources_d5)

    # D8 has 5 physical CSVs (POs, lines, receipts, receipts lines, invoice matches) + DB table
    d8 = discovery_service.get_dataset("d8")
    assert d8 is not None
    assert len(d8.physical_sources) >= 5

    # D9 has 5 physical CSVs (energy readings, meter master, equipment logs, downtime events, candidate links)
    d9 = discovery_service.get_dataset("d9")
    assert d9 is not None
    assert len(d9.physical_sources) >= 4

    # D10 has 4 physical CSVs (worker master, shift roster, shift attendance, station assignment)
    d10 = discovery_service.get_dataset("d10")
    assert d10 is not None
    assert len(d10.physical_sources) >= 4


# =============================================================================
# REQUIREMENT 3: Different Date Ranges Across Datasets
# =============================================================================
def test_requirement_3_different_date_ranges_across_datasets(discovery_service):
    """Verifies datasets can have different temporal coverage boundaries without hardcoding August-October."""
    d1 = discovery_service.get_dataset("d1")
    d3 = discovery_service.get_dataset("d3")
    d10 = discovery_service.get_dataset("d10")

    # D1 has operational timestamps
    assert len(d1.date_columns) > 0
    # D3 is static engineering spec
    assert d3.default_granularity == GranularityType.STATIC_SPEC

    # Test dynamic coverage assessment with custom query windows
    # Window A: Within D1's physical CSV span (2026-08-01 to 2026-08-21)
    assessment_aug = TimePeriodResolver.assess_dataset_coverage(
        d1, TimePeriodResolver.resolve_period("2026-08-01 to 2026-08-21")
    )
    assert assessment_aug.coverage_status == "FULL_COVERAGE"
    assert assessment_aug.coverage_percentage == 100.0

    # Window B: Custom single month outside baseline
    assessment_nov = TimePeriodResolver.assess_dataset_coverage(
        d1, TimePeriodResolver.resolve_period("2026-11")
    )
    assert assessment_nov.coverage_status == "OUT_OF_BOUNDS"
    assert assessment_nov.coverage_percentage == 0.0


# =============================================================================
# REQUIREMENT 4: Hourly, Daily, Transaction, Shift, and Static Spec Granularity
# =============================================================================
def test_requirement_4_granularities_hourly_daily_transaction_shift(discovery_service):
    """Verifies all required temporal and operational granularities are represented."""
    d1 = discovery_service.get_dataset("d1")
    d2 = discovery_service.get_dataset("d2")
    d3 = discovery_service.get_dataset("d3")
    d4 = discovery_service.get_dataset("d4")
    d9 = discovery_service.get_dataset("d9")
    d10 = discovery_service.get_dataset("d10")

    assert d1.default_granularity == GranularityType.HOURLY
    assert d2.default_granularity == GranularityType.BATCH_SLOT
    assert d3.default_granularity == GranularityType.STATIC_SPEC
    assert d4.default_granularity == GranularityType.TRANSACTION
    assert d9.default_granularity == GranularityType.SHIFT
    assert d10.default_granularity == GranularityType.DAILY

    # Verify granularity compatibility resolver
    assert TimePeriodResolver.validate_granularity_compatibility(GranularityType.HOURLY, "MONTH")["compatible"] is True
    assert TimePeriodResolver.validate_granularity_compatibility(GranularityType.DAILY, "SINGLE_DAY")["compatible"] is True
    # Querying hourly resolution on a daily dataset requires aggregation warning
    hourly_on_daily = TimePeriodResolver.validate_granularity_compatibility(GranularityType.DAILY, "HOURLY")
    assert hourly_on_daily["compatible"] is False


# =============================================================================
# REQUIREMENT 5: Partial Date Coverage Detection
# =============================================================================
def test_requirement_5_partial_date_coverage_detection(discovery_service):
    """Verifies partial date coverage is detected when query window extends beyond available data."""
    d1 = discovery_service.get_dataset("d1")

    # D1 covers 2026-08-01 to 2026-08-21. Query spans 2026-08-15 to 2026-08-31 (7 days within, 10 days out)
    resolved = TimePeriodResolver.resolve_period("2026-08-15 to 2026-08-31")
    assessment = TimePeriodResolver.assess_dataset_coverage(d1, resolved)

    assert assessment.coverage_status == "PARTIAL_COVERAGE"
    assert assessment.missing_lag_days > 0
    assert 0.0 < assessment.coverage_percentage < 100.0
    assert "Partial coverage" in assessment.diagnostic_message or "Dataset covers" in assessment.diagnostic_message


# =============================================================================
# REQUIREMENT 6: Missing Date Columns Handled (Static Reference)
# =============================================================================
def test_requirement_6_missing_date_columns_handled(discovery_service):
    """Verifies that static reference datasets like BOM Specs are handled safely as reference masters."""
    d3 = discovery_service.get_dataset("d3")
    assert d3 is not None
    assert d3.default_granularity == GranularityType.STATIC_SPEC

    # Should evaluate to STATIC_SPEC with 100% coverage
    resolved = TimePeriodResolver.resolve_period("2026-09")
    assessment = TimePeriodResolver.assess_dataset_coverage(d3, resolved)
    assert assessment.coverage_status == "STATIC_SPEC"
    assert assessment.coverage_percentage == 100.0
    assert "reference" in assessment.diagnostic_message.lower() or "static" in assessment.diagnostic_message.lower()


# =============================================================================
# REQUIREMENT 7: Missing or Ambiguous Identifiers Handled
# =============================================================================
def test_requirement_7_missing_or_ambiguous_identifiers(discovery_service):
    """Verifies candidate vs confirmed joins, handling ambiguous keys and missing linkages."""
    d1 = discovery_service.get_dataset("d1")
    d4 = discovery_service.get_dataset("d4")
    d10 = discovery_service.get_dataset("d10")

    # D4 serial inspection to D1 hourly log is candidate only (no serial number in hourly aggregate)
    d4_to_d1 = next((r for r in d4.relationships if "d1" in r.target_dataset_id), None)
    assert d4_to_d1 is not None
    assert d4_to_d1.status == RelationshipStatus.CANDIDATE_ONLY
    assert "minute" in d4_to_d1.caveat.lower() or "candidate" in d4_to_d1.caveat.lower()

    # D10 workforce to D1 hourly log is candidate only (line+shift level, no individual badge linkage)
    d10_to_d1 = next((r for r in d10.relationships if "d1" in r.target_dataset_id), None)
    assert d10_to_d1 is not None
    assert d10_to_d1.status == RelationshipStatus.CANDIDATE_ONLY
    assert len(d10.known_limitations) > 0


# =============================================================================
# REQUIREMENT 8: Synthetic versus Original Provenance Distinction
# =============================================================================
def test_requirement_8_synthetic_vs_original_provenance(discovery_service):
    """Verifies strict separation between raw/enhanced baselines and synthetic extension datasets."""
    d1 = discovery_service.get_dataset("d1")
    d2 = discovery_service.get_dataset("d2")
    d5 = discovery_service.get_dataset("d5")
    d9 = discovery_service.get_dataset("d9")

    assert d1.provenance_tier == ProvenanceTier.RAW_BASELINE
    assert d2.provenance_tier == ProvenanceTier.RAW_BASELINE
    assert d5.provenance_tier == ProvenanceTier.SYNTHETIC_EXTENSION
    assert d9.provenance_tier == ProvenanceTier.SYNTHETIC_EXTENSION

    # Filtering by synthetic
    natural_only = discovery_service.list_available_datasets(include_synthetic=False)
    assert len(natural_only) == 4  # D1, D2, D3, D4
    assert all(d.provenance_tier != ProvenanceTier.SYNTHETIC_EXTENSION for d in natural_only)

    # Check isolation rules
    rules = discovery_service.get_synthetic_isolation_rules()
    assert rules["isolation_policy"] == "STRICT_SEPARATION"
    assert len(rules["synthetic_datasets"]) == 6  # D5-D10
    assert len(rules["baseline_datasets"]) == 4   # D1-D4


# =============================================================================
# REQUIREMENT 9: Candidate versus Verified Relationships Filtering
# =============================================================================
def test_requirement_9_candidate_vs_verified_relationships(discovery_service):
    """Verifies that get_verified_relationships filters strictly for CONFIRMED linkages."""
    verified = discovery_service.get_verified_relationships()
    assert len(verified) > 0

    # Every item returned must have status == 'CONFIRMED'
    for rel in verified:
        assert rel["status"] == "CONFIRMED"
        assert rel["local_key"] is not None
        assert rel["target_key"] is not None

    # Verify D8 -> D7 Goods Receipt link is verified
    d8_d7 = [r for r in verified if "d8" in r["source_dataset_id"] and "d7" in r["target_dataset_id"]]
    assert len(d8_d7) > 0
    assert d8_d7[0]["local_key"] == "gr_id"

    # Verify D3 -> D6 BOM link is verified
    d3_d6 = [r for r in verified if "d3" in r["source_dataset_id"] and "d6" in r["target_dataset_id"]]
    assert len(d3_d6) > 0


# =============================================================================
# REQUIREMENT 10: Unsupported Investigation Dimensions (10, 11, 15)
# =============================================================================
def test_requirement_10_unsupported_investigation_dimensions(discovery_service):
    """Verifies Dimensions 10, 11, 15 are correctly marked as DEFERRED with zero evidence and clear reasons."""
    # Test Dimension 10 (Operator Skill Gaps)
    dim10 = discovery_service.check_evidence_sufficiency(10)
    assert dim10.status == "DEFERRED_NO_DATA"
    assert dim10.is_supported is False
    assert dim10.is_deferred is True
    assert dim10.evidence_sufficiency_score == 0.0
    assert "competency matrix" in dim10.deferral_reason.lower() or "skill" in dim10.deferral_reason.lower()

    # Test Dimension 11 (Shift Training Effectiveness)
    dim11 = discovery_service.check_evidence_sufficiency(11)
    assert dim11.status == "DEFERRED_NO_DATA"
    assert dim11.is_supported is False
    assert dim11.is_deferred is True
    assert dim11.evidence_sufficiency_score == 0.0
    assert "training" in dim11.deferral_reason.lower() or "lms" in dim11.deferral_reason.lower()

    # Test Dimension 15 (Management Override)
    dim15 = discovery_service.check_evidence_sufficiency(15)
    assert dim15.status == "DEFERRED_NO_DATA"
    assert dim15.is_supported is False
    assert dim15.is_deferred is True
    assert dim15.evidence_sufficiency_score == 0.0
    assert "override" in dim15.deferral_reason.lower()

    # Test an actively supported dimension (Dimension 1 - PPV)
    dim1 = discovery_service.check_evidence_sufficiency(1)
    assert dim1.status == "SUPPORTED"
    assert dim1.is_supported is True
    assert dim1.is_deferred is False
    assert dim1.evidence_sufficiency_score >= 0.7
    assert len(dim1.primary_dataset_ids) >= 1


# =============================================================================
# QUESTION-BASED DISCOVERY TESTS
# =============================================================================
def test_question_based_discovery_routing(discovery_service):
    """Verifies natural-language question discovery routes to correct datasets and dimensions."""
    # Test PPV query
    res_ppv = discovery_service.find_datasets_for_question("Why did OLED purchase price increase above contract in September?")
    assert "PURCHASE_PRICE_VARIANCE" in res_ppv.detected_intents
    assert 1 in res_ppv.relevant_dimensions
    assert any("d8" in p for p in res_ppv.primary_datasets)

    # Test Yield / Defect query
    res_yield = discovery_service.find_datasets_for_question("What caused the sudden drop in first pass yield on SMT Line 1?")
    assert "FIRST_PASS_YIELD_LOSS" in res_yield.detected_intents
    assert 3 in res_yield.relevant_dimensions
    assert any("d4" in p for p in res_yield.primary_datasets)

    # Test Skill Gap query (deferred dimension detection)
    res_skill = discovery_service.find_datasets_for_question("Are operator skill gaps causing assembly defects?")
    assert 10 in res_skill.relevant_dimensions
    assert any("DEFERRED" in c for c in res_skill.caveats)
