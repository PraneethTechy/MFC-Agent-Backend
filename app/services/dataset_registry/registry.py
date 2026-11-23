"""
Manufacturing Dataset Registry - Central Authoritative Catalog
Maintains complete definitions, physical references, column schemas, relationships,
and provenance tiers for all 10 logical manufacturing datasets in smartphone RCA.
Allows dynamic registration of future user-uploaded and staged datasets.
"""

import logging
from typing import Optional
from .models import (
    LogicalDatasetDefinition,
    PhysicalSourceReference,
    ColumnMetadata,
    DatasetRelationship,
    GranularityType,
    ProvenanceTier,
    RelationshipStatus,
)

logger = logging.getLogger("manufacturing_cost_agent.dataset_registry")


class ManufacturingDatasetRegistry:
    """Singleton repository of logical manufacturing datasets and physical sources."""

    _instance: Optional["ManufacturingDatasetRegistry"] = None

    def __init__(self):
        self._datasets: dict[str, LogicalDatasetDefinition] = {}
        self._bootstrap_registry()

    @classmethod
    def get_instance(cls) -> "ManufacturingDatasetRegistry":
        if cls._instance is None:
            cls._instance = ManufacturingDatasetRegistry()
        return cls._instance

    def get_dataset(self, dataset_id: str) -> Optional[LogicalDatasetDefinition]:
        return self._datasets.get(dataset_id)

    def list_datasets(self, active_only: bool = True) -> list[LogicalDatasetDefinition]:
        datasets = list(self._datasets.values())
        if active_only:
            return [d for d in datasets if d.is_active]
        return datasets

    def register_dataset(self, dataset: LogicalDatasetDefinition) -> None:
        """Dynamically registers or updates a dataset definition (e.g. for user uploads)."""
        self._datasets[dataset.dataset_id] = dataset
        logger.info("Registered dataset %s (%s)", dataset.dataset_id, dataset.name)

    def _bootstrap_registry(self) -> None:
        """Populates the 10 authoritative logical manufacturing datasets."""

        # =====================================================================
        # DATASET 1: HOURLY PRODUCTION
        # =====================================================================
        d1 = LogicalDatasetDefinition(
            dataset_id="d1_hourly_production",
            domain_code="D1",
            name="Hourly Production Telemetry",
            category="Production & Throughput",
            business_description=(
                "MES hourly machine and assembly line production logs. Records line output, "
                "good units, rejects, rework volume, and machine downtime minutes across plants and shifts."
            ),
            supported_dimensions=[1, 2, 4, 12, 16],
            default_granularity=GranularityType.HOURLY,
            primary_identifier="event_id",
            date_columns=["event_ts", "event_date"],
            provenance_tier=ProvenanceTier.RAW_BASELINE,
            physical_sources=[
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/raw/fact_hourly_production.csv",
                    row_count=8832,
                    column_count=23,
                    date_column="event_date",
                    available_date_range="2026-08-01 to 2026-08-21",
                    sha256_checksum="cdd5e0b3444132886b688fe51416db8111bc24e33bbab1decee2810b6b31b370",
                    is_synthetic=False,
                    data_origin="FACTORY_MES",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/enhanced/fact_hourly_production_enhanced_v1.csv",
                    row_count=8832,
                    column_count=41,
                    date_column="event_date",
                    available_date_range="2026-08-01 to 2026-08-21",
                    sha256_checksum="b5f6c67f64be967c82e7c1ca12eb109ddcdfcf45a60115559292b369e8a1b5ce",
                    is_synthetic=False,
                    data_origin="FACTORY_MES_ENHANCED",
                ),
                PhysicalSourceReference(
                    source_type="DB_TABLE",
                    location="hourly_production_logs",
                    row_count=13332,
                    column_count=26,
                    date_column="event_date",
                    available_date_range="2026-08-01 to 2026-12-25",
                    is_synthetic=False,
                    data_origin="POSTGRES_OPERATIONAL",
                ),
            ],
            columns=[
                ColumnMetadata(name="event_id", data_type="string", business_meaning="Unique production event identifier", is_primary_key=True),
                ColumnMetadata(name="event_ts", data_type="datetime", business_meaning="Timestamp of hourly production block", is_date_column=True),
                ColumnMetadata(name="event_date", data_type="date", business_meaning="Calendar date of production", is_date_column=True),
                ColumnMetadata(name="plant_code", data_type="string", business_meaning="Manufacturing facility code (e.g. IN-KA-01, IN-TN-01)"),
                ColumnMetadata(name="line_code", data_type="string", business_meaning="Production line (SMT-L1, FAL-L1, etc.)"),
                ColumnMetadata(name="shift_id", data_type="string", business_meaning="Operational shift identifier (SHIFT-A, SHIFT-B, SHIFT-C)"),
                ColumnMetadata(name="product_code", data_type="string", business_meaning="Smartphone SKU (SPH-A15-128, SPH-PRO-256)"),
                ColumnMetadata(name="target_qty", data_type="integer", business_meaning="Engineering target units for the hour"),
                ColumnMetadata(name="actual_qty", data_type="integer", business_meaning="Total physical units produced"),
                ColumnMetadata(name="good_qty", data_type="integer", business_meaning="Successfully produced first-pass good units"),
                ColumnMetadata(name="reject_qty", data_type="integer", business_meaning="Scrapped units failing quality gates"),
                ColumnMetadata(name="rework_qty", data_type="integer", business_meaning="Units routed to off-line rework stations"),
                ColumnMetadata(name="downtime_min", data_type="float", business_meaning="Line stoppages in minutes during the hour"),
                ColumnMetadata(name="downtime_reason", data_type="string", business_meaning="Primary reason code for machine downtime"),
                ColumnMetadata(name="operator_team", data_type="string", business_meaning="Assigned assembly/SMT shift crew"),
            ],
            relationships=[
                DatasetRelationship(
                    target_dataset_id="d2_manufacturing_cost",
                    local_key="event_ts|plant_code|line_code|product_code",
                    target_key="posting_ts|plant_code|line_code|product_code",
                    relationship_type="1:1",
                    status=RelationshipStatus.CANDIDATE_ONLY,
                    caveat="Cost batches match hourly slots on attributes; statutory ERP ledger linkage unverified.",
                ),
                DatasetRelationship(
                    target_dataset_id="d5_production_traceability",
                    local_key="event_id",
                    target_key="hourly_slot_id",
                    relationship_type="1:1",
                    status=RelationshipStatus.CONFIRMED,
                    caveat="Lineage verified via d5_run_source_link_v1.csv.",
                ),
            ],
            known_limitations=[
                "Source hourly feed assigns PO/product per hour; no contiguous physical campaign exists in raw logs.",
                "3,832 hourly slots have no corresponding cost records (UNCOSTED_OPERATIONAL_RUN).",
            ],
        )
        self._datasets[d1.dataset_id] = d1

        # =====================================================================
        # DATASET 2: MANUFACTURING COST
        # =====================================================================
        d2 = LogicalDatasetDefinition(
            dataset_id="d2_manufacturing_cost",
            domain_code="D2",
            name="Manufacturing Cost Ledger",
            category="Cost Accounting",
            business_description=(
                "Direct manufacturing cost ledger postings per production batch. "
                "Disaggregates expenditures into Material, Labour, Machine, Energy, and Scrap & Rework."
            ),
            supported_dimensions=[1, 2, 5],
            default_granularity=GranularityType.BATCH_SLOT,
            primary_identifier="cost_record_id",
            date_columns=["posting_ts"],
            provenance_tier=ProvenanceTier.RAW_BASELINE,
            physical_sources=[
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/raw/fact_manufacturing_cost.csv",
                    row_count=5000,
                    column_count=15,
                    date_column="posting_ts",
                    available_date_range="2026-08-01 to 2026-10-31",
                    sha256_checksum="444212efe15a93952bda90889e51b3d0e3fffe8a56ede5c71735de9665671cbc",
                    is_synthetic=False,
                    data_origin="FACTORY_FINANCE",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/enhanced/fact_manufacturing_cost_enhanced_v1.csv",
                    row_count=5000,
                    column_count=36,
                    date_column="posting_ts",
                    available_date_range="2026-08-01 to 2026-10-31",
                    sha256_checksum="86159dcca1f8bdd1824bb2ae34ec66866b6d3b1d5963fa9a7b74d82d2733c1bf",
                    is_synthetic=False,
                    data_origin="FACTORY_FINANCE_ENHANCED",
                ),
                PhysicalSourceReference(
                    source_type="DB_TABLE",
                    location="line_cost_batches",
                    row_count=9503,
                    column_count=24,
                    date_column="posting_ts",
                    available_date_range="2026-08-01 to 2026-12-25",
                    is_synthetic=False,
                    data_origin="POSTGRES_OPERATIONAL",
                ),
            ],
            columns=[
                ColumnMetadata(name="cost_record_id", data_type="string", business_meaning="Unique cost ledger posting ID", is_primary_key=True),
                ColumnMetadata(name="posting_ts", data_type="datetime", business_meaning="Financial settlement timestamp", is_date_column=True),
                ColumnMetadata(name="plant_code", data_type="string", business_meaning="Plant identifier"),
                ColumnMetadata(name="line_code", data_type="string", business_meaning="Assembly/SMT Line identifier"),
                ColumnMetadata(name="product_code", data_type="string", business_meaning="Smartphone SKU"),
                ColumnMetadata(name="produced_qty", data_type="float", business_meaning="Batch output volume in units"),
                ColumnMetadata(name="material_cost_inr", data_type="float", business_meaning="Direct component material expenditure (INR)"),
                ColumnMetadata(name="labour_cost_inr", data_type="float", business_meaning="Direct operator wage allocation (INR)"),
                ColumnMetadata(name="machine_cost_inr", data_type="float", business_meaning="Machine depreciation and tooling cost (INR)"),
                ColumnMetadata(name="energy_cost_inr", data_type="float", business_meaning="Line power and electricity cost (INR)"),
                ColumnMetadata(name="scrap_rework_cost_inr", data_type="float", business_meaning="Quality defect loss expenditure (INR)"),
                ColumnMetadata(name="total_direct_cost_inr", data_type="float", business_meaning="Total direct batch cost (INR)"),
            ],
            relationships=[
                DatasetRelationship(
                    target_dataset_id="d1_hourly_production",
                    local_key="posting_ts|plant_code|line_code|product_code",
                    target_key="event_ts|plant_code|line_code|product_code",
                    relationship_type="1:1",
                    status=RelationshipStatus.CANDIDATE_ONLY,
                    caveat="Direct costed runs cover only 5,000 batches.",
                )
            ],
            known_limitations=[
                "Books ~INR 9.7k material cost per unit on both SMT and FAL lines (not stage-differentiated in source).",
                "Factory overhead is completely UNAVAILABLE.",
            ],
        )
        self._datasets[d2.dataset_id] = d2

        # =====================================================================
        # DATASET 3: BOM COMPONENTS
        # =====================================================================
        d3 = LogicalDatasetDefinition(
            dataset_id="d3_bom_components",
            domain_code="D3",
            name="Bill of Materials Specification",
            category="Engineering & Master Data",
            business_description=(
                "Engineering standard Bill of Materials specifying nominal component quantities, "
                "engineering scrap factors, and active revisions for each smartphone SKU."
            ),
            supported_dimensions=[5, 6],
            default_granularity=GranularityType.STATIC_SPEC,
            primary_identifier="bom_component_key",
            date_columns=["effective_from", "effective_to"],
            provenance_tier=ProvenanceTier.RAW_BASELINE,
            physical_sources=[
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/raw/fact_bom_component.csv",
                    row_count=48,
                    column_count=8,
                    date_column="effective_from",
                    available_date_range="2026-07-01 to 2027-12-31",
                    sha256_checksum="aa7849e2b5c466d07ee12682a58ffcf79324a0b9dc67d9d2183c01313c26847d",
                    is_synthetic=False,
                    data_origin="ENGINEERING_PLM",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/enhanced/fact_bom_component_enhanced_v1.csv",
                    row_count=48,
                    column_count=23,
                    date_column="effective_from",
                    available_date_range="2026-07-01 to 2027-12-31",
                    sha256_checksum="d1ec3459766e02ad7bfe1ffc7cf347d130b70b4bb268a99bb583174e16d07510",
                    is_synthetic=False,
                    data_origin="ENGINEERING_PLM_ENHANCED",
                ),
                PhysicalSourceReference(
                    source_type="DB_TABLE",
                    location="bom_component_records",
                    row_count=246,
                    column_count=15,
                    date_column="effective_from",
                    available_date_range="Static Engineering Spec",
                    is_synthetic=False,
                    data_origin="POSTGRES_OPERATIONAL",
                ),
            ],
            columns=[
                ColumnMetadata(name="bom_id", data_type="string", business_meaning="BOM header identifier (e.g. BOM-SPH-A15-128-REV-C)"),
                ColumnMetadata(name="product_code", data_type="string", business_meaning="Target smartphone product SKU"),
                ColumnMetadata(name="material_code", data_type="string", business_meaning="Component part number (e.g. MAT-SOC-001, MAT-DSP-005)"),
                ColumnMetadata(name="component_qty", data_type="float", business_meaning="Nominal engineering required quantity per phone"),
                ColumnMetadata(name="scrap_factor", data_type="float", business_meaning="Engineering scrap allowance factor (e.g. 0.005)"),
                ColumnMetadata(name="revision", data_type="string", business_meaning="Engineering change revision code (REV-C)"),
            ],
            relationships=[
                DatasetRelationship(
                    target_dataset_id="d6_material_consumption",
                    local_key="material_code|product_code",
                    target_key="material_code|product_code",
                    relationship_type="1:MANY",
                    status=RelationshipStatus.CONFIRMED,
                    caveat="Theoretical consumption derived as target_qty * component_qty * (1 + scrap).",
                )
            ],
            known_limitations=[
                "Contains no unit purchase prices; prices must come from procurement datasets.",
                "BOM components are identical across all 3 phone products in baseline (provisional).",
            ],
        )
        self._datasets[d3.dataset_id] = d3

        # =====================================================================
        # DATASET 4: QUALITY INSPECTION
        # =====================================================================
        d4 = LogicalDatasetDefinition(
            dataset_id="d4_quality_inspection",
            domain_code="D4",
            name="Serialized Quality Inspection",
            category="Quality & Testing",
            business_description=(
                "Individual serialized test station inspection events from AOI, Functional Test, "
                "Acoustic Test, and Final Packing gates. Captures defect codes, severity, and disposition."
            ),
            supported_dimensions=[3, 18],
            default_granularity=GranularityType.TRANSACTION,
            primary_identifier="inspection_id",
            date_columns=["inspection_ts"],
            provenance_tier=ProvenanceTier.RAW_BASELINE,
            physical_sources=[
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/raw/fact_quality_inspection.csv",
                    row_count=16000,
                    column_count=19,
                    date_column="inspection_ts",
                    available_date_range="2026-08-01 to 2026-10-31",
                    sha256_checksum="cf137596cce7b76eb4aa29916349094172c6bf14c6e1b34eaf1720a1f3ae22d1",
                    is_synthetic=False,
                    data_origin="FACTORY_QMS",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/enhanced/fact_quality_inspection_enhanced_v1.csv",
                    row_count=16000,
                    column_count=42,
                    date_column="inspection_ts",
                    available_date_range="2026-08-01 to 2026-10-31",
                    sha256_checksum="4faa12f7c8a6783bba44cc467b8b7856284256e90fe4bd72a19875eb76098245",
                    is_synthetic=False,
                    data_origin="FACTORY_QMS_ENHANCED",
                ),
                PhysicalSourceReference(
                    source_type="DB_TABLE",
                    location="serialized_quality_inspections",
                    row_count=25562,
                    column_count=27,
                    date_column="inspection_ts",
                    available_date_range="2026-08-01 to 2026-12-25",
                    is_synthetic=False,
                    data_origin="POSTGRES_OPERATIONAL",
                ),
            ],
            columns=[
                ColumnMetadata(name="inspection_id", data_type="string", business_meaning="Unique serialized test record ID", is_primary_key=True),
                ColumnMetadata(name="inspection_ts", data_type="datetime", business_meaning="Test execution timestamp", is_date_column=True),
                ColumnMetadata(name="station_id", data_type="string", business_meaning="Inspection station code (S01 to S06)"),
                ColumnMetadata(name="serial_number", data_type="string", business_meaning="Unique smartphone handset serial number"),
                ColumnMetadata(name="defect_code", data_type="string", business_meaning="Engineering defect code (e.g. DEF-001 Solder Bridging)"),
                ColumnMetadata(name="result", data_type="string", business_meaning="PASS or FAIL"),
                ColumnMetadata(name="disposition", data_type="string", business_meaning="RELEASE, REWORK, HOLD, or SCRAP"),
            ],
            relationships=[
                DatasetRelationship(
                    target_dataset_id="d1_hourly_production",
                    local_key="plant_code|line_code|inspection_ts",
                    target_key="plant_code|line_code|event_ts",
                    relationship_type="MANY:1",
                    status=RelationshipStatus.CANDIDATE_ONLY,
                    caveat="Minute-level inspection timestamps match hourly slot windows within 15 minutes.",
                )
            ],
            known_limitations=[
                "Defect count is NOT unique failed smartphone count; a phone may fail 2 stations.",
                "Quality defect records are not directly joined to cost ledger batches.",
            ],
        )
        self._datasets[d4.dataset_id] = d4

        # =====================================================================
        # DATASET 5: PRODUCTION ORDER & RUN TRACEABILITY
        # =====================================================================
        d5 = LogicalDatasetDefinition(
            dataset_id="d5_production_traceability",
            domain_code="D5",
            name="Production Order & Run Traceability",
            category="Manufacturing Operations",
            business_description=(
                "Synthesized manufacturing orders and multi-line runs linking SMT and FAL operations. "
                "Provides order-level scheduled vs actual output and hourly slot link lineage."
            ),
            supported_dimensions=[4, 16],
            default_granularity=GranularityType.BATCH_SLOT,
            primary_identifier="production_order_id",
            date_columns=["order_created_ts", "scheduled_start_date"],
            provenance_tier=ProvenanceTier.SYNTHETIC_EXTENSION,
            physical_sources=[
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/production_traceability/d5_production_order_v1.csv",
                    row_count=2607,
                    column_count=29,
                    date_column="order_created_ts",
                    available_date_range="2026-08-01 to 2026-09-07",
                    sha256_checksum="365c71a3c61793466ae36cf287ef6fa53ec865d4bb316135eecad0d41334c9c7",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/production_traceability/d5_production_run_v1.csv",
                    row_count=4318,
                    column_count=40,
                    date_column="run_start_ts",
                    available_date_range="2026-07-31 to 2026-08-26",
                    sha256_checksum="9be85a15a81caec2a8cbf4a72d733158c3db47bb1f0217983ea1cbf5cf2eb9df",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/production_traceability/d5_run_source_link_v1.csv",
                    row_count=13832,
                    column_count=20,
                    date_column="slot_ts",
                    available_date_range="2026-08-01 to 2026-08-21",
                    sha256_checksum="4c8d5750d402ff1b4c3e8a1b55909d85449557002b8d00ea4f67c4273dfc0678",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
            ],
            columns=[
                ColumnMetadata(name="production_order_id", data_type="string", business_meaning="Synthesized order identifier", is_primary_key=True),
                ColumnMetadata(name="planned_qty", data_type="integer", business_meaning="Order scheduled batch size"),
                ColumnMetadata(name="actual_qty", data_type="integer", business_meaning="Cumulative units manufactured"),
            ],
            relationships=[
                DatasetRelationship(
                    target_dataset_id="d1_hourly_production",
                    local_key="production_order_id",
                    target_key="production_order_id",
                    relationship_type="1:MANY",
                    status=RelationshipStatus.CONFIRMED,
                    caveat="All 8,832 hourly rows linked via d5_run_source_link_v1.csv.",
                )
            ],
            known_limitations=[
                "Orders/runs are label groupings constructed from sparse hourly slots, not continuous campaigns.",
                "2,056 orders have multi-week spans (SPARSE_MULTI_WEEK_SPAN).",
            ],
        )
        self._datasets[d5.dataset_id] = d5

        # =====================================================================
        # DATASET 6: MATERIAL ISSUE & CONSUMPTION
        # =====================================================================
        d6 = LogicalDatasetDefinition(
            dataset_id="d6_material_consumption",
            domain_code="D6",
            name="Material Issue & Consumption",
            category="Supply Chain & Material Tracking",
            business_description=(
                "Shopfloor lot-by-lot component issues, returns, net consumption, and scrap quantities "
                "generated per hourly production slot and BOM kit. Governed by issued = returned + consumed."
            ),
            supported_dimensions=[3, 6, 17],
            default_granularity=GranularityType.TRANSACTION,
            primary_identifier="material_issue_id",
            date_columns=["slot_ts", "issue_ts"],
            provenance_tier=ProvenanceTier.SYNTHETIC_EXTENSION,
            physical_sources=[
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/material_consumption/d6_material_issue_consumption_v1.csv",
                    row_count=72897,
                    column_count=45,
                    date_column="issue_ts",
                    available_date_range="2026-08-01 to 2026-08-03",
                    sha256_checksum="9f6333333337a7fead7208d24cb34d1933ba1fc332402fe38bfbc0ff16aa0ee2",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="DB_TABLE",
                    location="material_consumption_records",
                    row_count=73350,
                    column_count=27,
                    date_column="production_date",
                    available_date_range="2026-10-01 to 2026-12-25",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_TEST",
                ),
            ],
            columns=[
                ColumnMetadata(name="material_issue_id", data_type="string", business_meaning="Unique material kit issue ID", is_primary_key=True),
                ColumnMetadata(name="material_code", data_type="string", business_meaning="BOM component part code"),
                ColumnMetadata(name="issued_quantity", data_type="float", business_meaning="Units issued to line kit"),
                ColumnMetadata(name="returned_quantity", data_type="float", business_meaning="Unused surplus units returned to inventory"),
                ColumnMetadata(name="net_consumed_quantity", data_type="float", business_meaning="Physical units assembled or lost"),
                ColumnMetadata(name="bom_allowed_quantity", data_type="float", business_meaning="Theoretical allowed engineering consumption"),
                ColumnMetadata(name="scrap_quantity", data_type="float", business_meaning="Component scrap/wastage units"),
                ColumnMetadata(name="landed_unit_cost", data_type="float", business_meaning="Standard unit cost applied (INR)"),
            ],
            relationships=[
                DatasetRelationship(
                    target_dataset_id="d7_inventory_transactions",
                    local_key="material_issue_id",
                    target_key="source_doc_id",
                    relationship_type="1:1",
                    status=RelationshipStatus.CONFIRMED,
                    caveat="All D6 issues and returns post 1:1 to D7 ledger.",
                )
            ],
            known_limitations=[
                "Component waste is calculated from BOM scrap factor and feeder jam simulations; not reconciled to quality inspections.",
                "Material prices are calibrated to average batch cost (~INR 9,752), not raw vendor invoices.",
            ],
        )
        self._datasets[d6.dataset_id] = d6

        # =====================================================================
        # DATASET 7: INVENTORY TRANSACTIONS
        # =====================================================================
        d7 = LogicalDatasetDefinition(
            dataset_id="d7_inventory_transactions",
            domain_code="D7",
            name="Warehouse Inventory Transactions & Ledger",
            category="Inventory Management",
            business_description=(
                "Complete inventory movement ledger. Posts opening balances, goods receipts from suppliers, "
                "shopfloor kit issues, returns, inter-plant transfers, and cycle-count adjustments with zero negative stock."
            ),
            supported_dimensions=[14, 17],
            default_granularity=GranularityType.TRANSACTION,
            primary_identifier="inventory_txn_id",
            date_columns=["txn_ts"],
            provenance_tier=ProvenanceTier.SYNTHETIC_EXTENSION,
            physical_sources=[
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/inventory/d7_inventory_transactions_v1.csv",
                    row_count=142508,
                    column_count=31,
                    date_column="txn_ts",
                    available_date_range="2026-08-01 to 2026-08-02",
                    sha256_checksum="ba33c5e0dc3f837651a70cb3c584b4242636eb3907720973a6e60b1387d8df93",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
            ],
            columns=[
                ColumnMetadata(name="inventory_txn_id", data_type="string", business_meaning="Unique inventory ledger entry ID", is_primary_key=True),
                ColumnMetadata(name="txn_ts", data_type="datetime", business_meaning="Timestamp of warehouse movement", is_date_column=True),
                ColumnMetadata(name="txn_type", data_type="string", business_meaning="ISSUE, RETURN, GOODS_RECEIPT, TRANSFER, ADJUSTMENT"),
                ColumnMetadata(name="plant_code", data_type="string", business_meaning="Plant identifier"),
                ColumnMetadata(name="material_code", data_type="string", business_meaning="Material code"),
                ColumnMetadata(name="qty_movement", data_type="float", business_meaning="Positive (in) or negative (out) quantity"),
                ColumnMetadata(name="balance_after", data_type="float", business_meaning="Running stock balance (strictly >= 0)"),
            ],
            relationships=[
                DatasetRelationship(
                    target_dataset_id="d8_procurement_supplier",
                    local_key="inventory_txn_id",
                    target_key="inventory_txn_id",
                    relationship_type="1:1",
                    status=RelationshipStatus.CONFIRMED,
                    caveat="All 346 GOODS_RECEIPT rows reconcile with d8_goods_receipt_v1.csv.",
                )
            ],
            known_limitations=[
                "Inventory movements were generated to match D6 issue/return volume; supplier metadata lives in D8.",
            ],
        )
        self._datasets[d7.dataset_id] = d7

        # =====================================================================
        # DATASET 8: PROCUREMENT & SUPPLIER PERFORMANCE
        # =====================================================================
        d8 = LogicalDatasetDefinition(
            dataset_id="d8_procurement_supplier",
            domain_code="D8",
            name="Procurement, Purchase Orders & Supplier Quality",
            category="Procurement & SCM",
            business_description=(
                "Supplier master records, purchase orders, delivery lines, goods receipts, and receiving "
                "dock quality inspections. Tracks contract prices, landed unit costs, on-time delivery, and vendor rejection rates."
            ),
            supported_dimensions=[13, 14],
            default_granularity=GranularityType.TRANSACTION,
            primary_identifier="po_id",
            date_columns=["po_date", "doc_date", "delivery_due_date", "gr_ts", "gr_date", "inspection_ts"],
            provenance_tier=ProvenanceTier.SYNTHETIC_EXTENSION,
            physical_sources=[
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/procurement/d8_supplier_master_v1.csv",
                    row_count=15,
                    column_count=14,
                    sha256_checksum="13217b1fb9706346bc7fc7387e07fc5fbb9a44ca76f092305389658f8b86d99e",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/procurement/d8_po_header_v1.csv",
                    row_count=260,
                    column_count=15,
                    date_column="po_date",
                    available_date_range="2026-06-22 to 2026-10-26",
                    sha256_checksum="2ffc9bc60b378c3c6f62f83193e25b128509c15d48721bf920c81d830b13cf17",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/procurement/d8_po_line_v1.csv",
                    row_count=348,
                    column_count=33,
                    date_column="delivery_due_date",
                    available_date_range="2026-08-03 to 2026-12-07",
                    sha256_checksum="a5fce4847e09cfeb534e8913926f866b1a7d6537b83f3e1b730f2f3e82fa087f",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/procurement/d8_goods_receipt_v1.csv",
                    row_count=346,
                    column_count=36,
                    date_column="gr_ts",
                    available_date_range="2026-08-07 to 2026-10-30",
                    sha256_checksum="764aa5bc608f0a0d95d1d6a6954a65df19965faef048fa56012674f260fc456d",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/procurement/d8_supplier_quality_v1.csv",
                    row_count=346,
                    column_count=21,
                    date_column="inspection_ts",
                    available_date_range="2026-08-07 to 2026-10-30",
                    sha256_checksum="7995186b5105d15a999cb59c73efd806509f7a7596d66e746535560b435ee10f",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="DB_TABLE",
                    location="material_purchase_records",
                    row_count=996,
                    column_count=24,
                    date_column="receipt_date",
                    available_date_range="2026-10-02 to 2026-12-23",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_TEST",
                ),
            ],
            columns=[
                ColumnMetadata(name="po_id", data_type="string", business_meaning="Purchase order header number", is_primary_key=True),
                ColumnMetadata(name="supplier_code", data_type="string", business_meaning="Supplier identifier (SUP-001 to SUP-015)"),
                ColumnMetadata(name="material_code", data_type="string", business_meaning="Procured component code"),
                ColumnMetadata(name="ordered_qty", data_type="float", business_meaning="PO contracted order quantity"),
                ColumnMetadata(name="received_qty", data_type="float", business_meaning="Physical quantity delivered at dock"),
                ColumnMetadata(name="accepted_qty", data_type="float", business_meaning="Quantity passing receiving inspection"),
                ColumnMetadata(name="rejected_qty", data_type="float", business_meaning="Quantity failed and quarantined at receiving"),
                ColumnMetadata(name="unit_price_contract", data_type="float", business_meaning="Contractual PO purchase price (INR)"),
                ColumnMetadata(name="landed_unit_cost", data_type="float", business_meaning="Fully landed cost including freight/duty (INR)"),
            ],
            relationships=[
                DatasetRelationship(
                    target_dataset_id="d7_inventory_transactions",
                    local_key="gr_id",
                    target_key="inventory_txn_id",
                    relationship_type="1:1",
                    status=RelationshipStatus.CONFIRMED,
                    caveat="All 346 receipts match D7 exactly.",
                )
            ],
            known_limitations=[
                "Supplier pricing, FX rates (88.00 INR/USD), and vendor master catalogs are synthetic test assumptions.",
            ],
        )
        self._datasets[d8.dataset_id] = d8

        # =====================================================================
        # DATASET 9: EQUIPMENT DOWNTIME & ENERGY
        # =====================================================================
        d9 = LogicalDatasetDefinition(
            dataset_id="d9_equipment_energy",
            domain_code="D9",
            name="Equipment Downtime, Maintenance & Shift Energy",
            category="Asset Management & Utilities",
            business_description=(
                "Machine assets catalogue, unplanned equipment downtime events, shift energy meter readings (kWh), "
                "and scheduled maintenance records across SMT placement machines, reflow ovens, and FAL test fixtures."
            ),
            supported_dimensions=[4, 6, 7],
            default_granularity=GranularityType.SHIFT,
            primary_identifier="equipment_id",
            date_columns=["start_ts", "end_ts", "shift_date", "window_start_ts", "scheduled_date"],
            provenance_tier=ProvenanceTier.SYNTHETIC_EXTENSION,
            physical_sources=[
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/equipment_energy/d9_equipment_master_v1.csv",
                    row_count=32,
                    column_count=25,
                    sha256_checksum="15e57d1ae3b3925585090ef8cfb993e39ce6f50b86a8ff35df68ba0990a4279b",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/equipment_energy/d9_equipment_event_v1.csv",
                    row_count=2487,
                    column_count=20,
                    date_column="start_ts",
                    available_date_range="2026-08-01 to 2026-10-31",
                    sha256_checksum="b345f4ec28da8490a1eb9738f6b21644f1c9fc6368d50b4ec701d0a5116788b6",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/equipment_energy/d9_energy_reading_shift_v1.csv",
                    row_count=8864,
                    column_count=24,
                    date_column="shift_date",
                    available_date_range="2026-07-31 to 2026-10-31",
                    sha256_checksum="bb4a7f0e748b64e03d4040da5b22557173e13eb1947eebca44fc6f92dd2e6fa6",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/equipment_energy/d9_maintenance_event_v1.csv",
                    row_count=429,
                    column_count=19,
                    date_column="scheduled_date",
                    available_date_range="2026-08-04 to 2026-10-28",
                    sha256_checksum="5f0ce1dfa1d1ca93d83768f7d98ee67d8d47fa189622d104593e8e225914619b",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/equipment_energy/d9_event_hourly_candidate_link_v1.csv",
                    row_count=262,
                    column_count=9,
                    date_column="candidate_slot_ts",
                    sha256_checksum="c9735d64ffc97ebc1c7ae9883bf44bc4c92ee0fcf0bf41e06cbeee4ce21efaa2",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
            ],
            columns=[
                ColumnMetadata(name="equipment_id", data_type="string", business_meaning="Physical machine identifier", is_primary_key=True),
                ColumnMetadata(name="equipment_name", data_type="string", business_meaning="Machine name (SMT Pick-and-Place, Reflow Oven)"),
                ColumnMetadata(name="kwh_consumed", data_type="float", business_meaning="Shift kilowatt-hour consumption"),
                ColumnMetadata(name="downtime_minutes", data_type="float", business_meaning="Unplanned machine stoppage minutes"),
                ColumnMetadata(name="energy_cost_inr", data_type="float", business_meaning="Energy expenditure (tariff model applied)"),
            ],
            relationships=[
                DatasetRelationship(
                    target_dataset_id="d1_hourly_production",
                    local_key="equipment_id|timestamp_window",
                    target_key="line_code|event_ts",
                    relationship_type="MANY:MANY",
                    status=RelationshipStatus.CANDIDATE_ONLY,
                    caveat="Equipment downtime does not reconcile automatically to hourly line downtime; magnitudes differ.",
                )
            ],
            known_limitations=[
                "Energy readings are generated from a rated-power equipment model and are not reconciled to cost ledger energy.",
            ],
        )
        self._datasets[d9.dataset_id] = d9

        # =====================================================================
        # DATASET 10: WORKFORCE ATTENDANCE & ALLOCATION
        # =====================================================================
        d10 = LogicalDatasetDefinition(
            dataset_id="d10_workforce_attendance_allocation",
            domain_code="D10",
            name="Workforce Attendance, Rosters & Line Labour",
            category="Workforce & Operations",
            business_description=(
                "Worker rosters, shift definitions, daily badge attendance punches, regular and overtime hours, "
                "absenteeism tracking (6.74%), and line-shift aggregated daily direct labour expenditure."
            ),
            supported_dimensions=[8, 9, 12],
            default_granularity=GranularityType.DAILY,
            primary_identifier="employee_id",
            date_columns=["hire_date", "effective_from_date", "effective_to_date", "work_date", "punch_in_ts"],
            provenance_tier=ProvenanceTier.SYNTHETIC_EXTENSION,
            physical_sources=[
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/workforce/d10_shift_definition_v1.csv",
                    row_count=3,
                    column_count=12,
                    sha256_checksum="5e8fcfe76dd4ca9441f92e3a893cb6fb026d304910cfcb42cbbe835368a5c378",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/workforce/d10_employee_master_v1.csv",
                    row_count=248,
                    column_count=17,
                    date_column="hire_date",
                    available_date_range="2019-01-02 to 2026-07-22",
                    sha256_checksum="8f07aa03f75e218ce0e1f7d4b4a3c2005ef96e838b0051e5ea0aa61c5651586a",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/workforce/d10_attendance_v1.csv",
                    row_count=19557,
                    column_count=29,
                    date_column="work_date",
                    available_date_range="2026-08-01 to 2026-08-10",
                    sha256_checksum="954f9a35e76a6cf47e8f5c35cf8db652bc5dae8d356c9a2c3ea0cfba64506869",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
                PhysicalSourceReference(
                    source_type="CSV_FILE",
                    location="backend/data/generated/workforce/d10_line_shift_labour_daily_v1.csv",
                    row_count=1104,
                    column_count=20,
                    date_column="work_date",
                    available_date_range="2026-08-01 to 2026-10-31",
                    sha256_checksum="c04e28080f08a5433d3cbe76cbdfc9b83b6329433e53613a37ba7620a2333b20",
                    is_synthetic=True,
                    data_origin="SYNTHETIC_EXTENSION",
                ),
            ],
            columns=[
                ColumnMetadata(name="employee_id", data_type="string", business_meaning="Worker badge identifier", is_primary_key=True),
                ColumnMetadata(name="regular_hours", data_type="float", business_meaning="Standard shift working hours"),
                ColumnMetadata(name="overtime_hours", data_type="float", business_meaning="Overtime hours worked"),
                ColumnMetadata(name="attendance_status", data_type="string", business_meaning="PRESENT, ABSENT, LEAVE"),
                ColumnMetadata(name="daily_labour_cost_inr", data_type="float", business_meaning="Direct line labour cost per day (INR)"),
            ],
            relationships=[
                DatasetRelationship(
                    target_dataset_id="d1_hourly_production",
                    local_key="line_code|shift_id|work_date",
                    target_key="line_code|shift_id|event_date",
                    relationship_type="1:MANY",
                    status=RelationshipStatus.CANDIDATE_ONLY,
                    caveat="Individual workers are not attributed to specific handset serial numbers or production runs.",
                )
            ],
            known_limitations=[
                "Individual operator skill matrices and training certifications are UNAVAILABLE (Dimensions 10 & 11 Deferred).",
            ],
        )
        self._datasets[d10.dataset_id] = d10
