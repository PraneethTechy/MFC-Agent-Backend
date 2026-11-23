# GWC DATA.AI — Manufacturing Cost RCA Platform
## Dataset Integration, Organization, and Integrity Audit Report

> **Document Status:** Authoritative Dataset Organization & Integration Report  
> **Target Path:** `backend/data/documentation/dataset_integration_report.md`  
> **Execution Date:** November 20, 2026  
> **Scope:** File system organization, dataset inventory, extraction, and cryptographic validation only.  
> **Safety Assurance:** Zero application code, zero frontend components, and zero database records were modified or executed.

---

## 1. EXECUTIVE SUMMARY & SAFETY GUARANTEE

All provided manufacturing datasets—including the four enhanced baseline CSVs and all synthetic extension files contained in ZIP 1 and ZIP 2—have been successfully inspected, cryptographically audited, and organized into the standard `backend/data/` directory hierarchy.

### Safety & Integrity Confirmations:
1. **Raw Baseline Files Preserved:** The original four raw baseline CSVs in `backend/data/raw/` were verified before and after extraction. Their SHA-256 checksums are 100% identical. Zero bytes were overwritten, modified, or moved.
2. **Enhanced CSVs Isolated:** The four enhanced versioned CSV files (`fact_*_enhanced_v1.csv`) are stored separately in `backend/data/enhanced/`.
3. **Six Additional Datasets Extracted:** Datasets 5 through 10 (comprising 22 physical CSV files across production traceability, material consumption, inventory, procurement, equipment/energy, and workforce) are organized under `backend/data/generated/`.
4. **Supporting Documentation Preserved:** All generator audit workbooks (`.xlsx`), data dictionaries (`.csv`), relationship specifications (`.csv`), and generation summaries (`.md`) are preserved in `backend/data/documentation/`.
5. **Python Scripts Preserved Without Execution:** All dataset generation and validation scripts are archived in `backend/data/scripts/` without execution.
6. **Zero Code or DB Modification:** No application code (`backend/app/*`), no frontend files (`ui/*`), and no database records or migrations in Neon PostgreSQL were altered.

---

## 2. ZIP INVENTORY & EXTRACTION LOG

Two source ZIP archives were supplied and inspected prior to extraction:

### ZIP 1: `files.zip` (uploaded as `files.zip` / `files(1).zip`)
- **Archive Size:** 8,461,760 bytes (8.46 MB)
- **Archive SHA-256:** `d8bc6cc3556c81a29367c3fcb2210086ebc60bb7b0b6c69f06abdb46a51d9ecf`
- **Internal File Count:** 12 files (5 data CSVs, 4 documentation files, 3 python scripts)
- **Logical Domains Covered:**
  - Dataset 5: Production Order & Run Traceability (`d5_production_order_v1.csv`, `d5_production_run_v1.csv`, `d5_run_source_link_v1.csv`)
  - Dataset 6: Material Issue & Consumption (`d6_material_issue_consumption_v1.csv`)
  - Dataset 7: Inventory Transactions (`d7_inventory_transactions_v1.csv`)
  - Documentation: `generation_summary_v1.md`, `cross_dataset_reconciliation_audit_v1.xlsx`, `data_dictionary_v1.csv`, `key_relationship_spec_v1.csv`
  - Scripts: `generate_datasets_v1.py`, `validate_v1.py`, `build_docs_v1.py`

### ZIP 2: `files (2).zip` (uploaded as `files_(2).zip` / `files (2)(1).zip`)
- **Archive Size:** 793,550 bytes (793.5 KB)
- **Archive SHA-256:** `559fc1202dfef70e599b1ba5e638efc0fec5f81014a42b10214a1e944bc31d87`
- **Internal File Count:** 24 files (17 data CSVs, 4 documentation files, 3 python scripts)
- **Logical Domains Covered:**
  - Dataset 8: Procurement & Supplier Performance (6 CSV files)
  - Dataset 9: Equipment Downtime & Energy (5 CSV files)
  - Dataset 10: Workforce Attendance & Allocation (6 CSV files)
  - Documentation: `generation_summary_d8_d10_v1.md`, `cross_dataset_audit_d8_d10_v1.xlsx`, `data_dictionary_d8_d10_v1.csv`, `key_relationship_spec_d8_d10_v1.csv`
  - Scripts: `generate_d8_d10_v1.py`, `validate_and_document_d8_d10_v1.py`, `build_docs_d8_d10_v1.py`

### Overlap & Collision Check
- **Filename Collision between ZIP 1 and ZIP 2:** **0 files.** The set intersection between ZIP 1 and ZIP 2 file lists is empty (`set()`). Zero files collided or overwrote each other.

---

## 3. MAPPING OF ALL 10 LOGICAL DATASETS TO PHYSICAL CSV FILES

The platform's data foundation comprises **30 physical CSV files** mapped across the 10 authoritative logical domains:

```
+----------------------------------------------------------------------------------------------------+
|                                    10-DATASET LOGICAL DOMAIN MAPPING                               |
+----+------------------------------------+----------------+-----------------------------------------+
| #  | Logical Manufacturing Dataset      | Domain Code    | Physical CSV Files                      |
+----+------------------------------------+----------------+-----------------------------------------+
| 1  | Hourly Production                  | D1             | - raw/fact_hourly_production.csv        |
|    |                                    |                | - enhanced/fact_hourly_production_...   |
+----+------------------------------------+----------------+-----------------------------------------+
| 2  | Manufacturing Cost                 | D2             | - raw/fact_manufacturing_cost.csv       |
|    |                                    |                | - enhanced/fact_manufacturing_cost_...  |
+----+------------------------------------+----------------+-----------------------------------------+
| 3  | BOM Components                     | D3             | - raw/fact_bom_component.csv            |
|    |                                    |                | - enhanced/fact_bom_component_enh...    |
+----+------------------------------------+----------------+-----------------------------------------+
| 4  | Quality Inspection                 | D4             | - raw/fact_quality_inspection.csv       |
|    |                                    |                | - enhanced/fact_quality_inspection_...  |
+----+------------------------------------+----------------+-----------------------------------------+
| 5  | Production Order & Run Traceability| D5             | - generated/production_traceability/    |
|    |                                    |                |   * d5_production_order_v1.csv          |
|    |                                    |                |   * d5_production_run_v1.csv            |
|    |                                    |                |   * d5_run_source_link_v1.csv           |
+----+------------------------------------+----------------+-----------------------------------------+
| 6  | Material Issue & Consumption       | D6             | - generated/material_consumption/       |
|    |                                    |                |   * d6_material_issue_consumption_v1.csv|
+----+------------------------------------+----------------+-----------------------------------------+
| 7  | Inventory Transactions             | D7             | - generated/inventory/                  |
|    |                                    |                |   * d7_inventory_transactions_v1.csv    |
+----+------------------------------------+----------------+-----------------------------------------+
| 8  | Procurement & Supplier Performance | D8             | - generated/procurement/                |
|    |                                    |                |   * d8_supplier_master_v1.csv           |
|    |                                    |                |   * d8_supplier_material_source_list_...|
|    |                                    |                |   * d8_po_header_v1.csv                 |
|    |                                    |                |   * d8_po_line_v1.csv                   |
|    |                                    |                |   * d8_goods_receipt_v1.csv             |
|    |                                    |                |   * d8_supplier_quality_v1.csv          |
+----+------------------------------------+----------------+-----------------------------------------+
| 9  | Equipment Downtime & Energy        | D9             | - generated/equipment_energy/           |
|    |                                    |                |   * d9_equipment_master_v1.csv          |
|    |                                    |                |   * d9_equipment_event_v1.csv           |
|    |                                    |                |   * d9_energy_reading_shift_v1.csv      |
|    |                                    |                |   * d9_maintenance_event_v1.csv         |
|    |                                    |                |   * d9_event_hourly_candidate_link_...  |
+----+------------------------------------+----------------+-----------------------------------------+
| 10 | Workforce Attendance & Allocation  | D10            | - generated/workforce/                  |
|    |                                    |                |   * d10_shift_definition_v1.csv         |
|    |                                    |                |   * d10_employee_master_v1.csv          |
|    |                                    |                |   * d10_shift_assignment_v1.csv         |
|    |                                    |                |   * d10_line_allocation_v1.csv          |
|    |                                    |                |   * d10_attendance_v1.csv               |
|    |                                    |                |   * d10_line_shift_labour_daily_v1.csv  |
+----+------------------------------------+----------------+-----------------------------------------+
```

---

## 4. FINAL FOLDER STRUCTURE IN THE PROJECT

```
backend/data/
├── raw/                                      <-- PRESERVED ORIGINAL BASELINE (4 FILES, UNTOUCHED)
│   ├── fact_bom_component.csv
│   ├── fact_hourly_production.csv
│   ├── fact_manufacturing_cost.csv
│   └── fact_quality_inspection.csv
│
├── enhanced/                                 <-- SEPARATE VERSIONED ENHANCED BASELINE (4 FILES)
│   ├── fact_bom_component_enhanced_v1.csv
│   ├── fact_hourly_production_enhanced_v1.csv
│   ├── fact_manufacturing_cost_enhanced_v1.csv
│   └── fact_quality_inspection_enhanced_v1.csv
│
├── generated/                                <-- 6 ADDITIONAL LOGICAL DOMAINS (22 FILES)
│   ├── production_traceability/              (Dataset 5: Orders, Runs, Source Links)
│   │   ├── d5_production_order_v1.csv
│   │   ├── d5_production_run_v1.csv
│   │   └── d5_run_source_link_v1.csv
│   │
│   ├── material_consumption/                 (Dataset 6: Lot-level Consumption & Kits)
│   │   └── d6_material_issue_consumption_v1.csv
│   │
│   ├── inventory/                            (Dataset 7: Balances, Issues, Returns, Receipts)
│   │   └── d7_inventory_transactions_v1.csv
│   │
│   ├── procurement/                          (Dataset 8: POs, Lines, GRs, Vendor Quality)
│   │   ├── d8_supplier_master_v1.csv
│   │   ├── d8_supplier_material_source_list_v1.csv
│   │   ├── d8_po_header_v1.csv
│   │   ├── d8_po_line_v1.csv
│   │   ├── d8_goods_receipt_v1.csv
│   │   └── d8_supplier_quality_v1.csv
│   │
│   ├── equipment_energy/                     (Dataset 9: Assets, Events, Shift Meters, Maintenance)
│   │   ├── d9_equipment_master_v1.csv
│   │   ├── d9_equipment_event_v1.csv
│   │   ├── d9_energy_reading_shift_v1.csv
│   │   ├── d9_maintenance_event_v1.csv
│   │   └── d9_event_hourly_candidate_link_v1.csv
│   │
│   └── workforce/                            (Dataset 10: Employees, Shifts, Rosters, Attendance)
│       ├── d10_shift_definition_v1.csv
│       ├── d10_employee_master_v1.csv
│       ├── d10_shift_assignment_v1.csv
│       ├── d10_line_allocation_v1.csv
│       ├── d10_attendance_v1.csv
│       └── d10_line_shift_labour_daily_v1.csv
│
├── documentation/                            <-- PRESERVED AUDIT WORKBOOKS & DATA DICTIONARIES
│   ├── generation_summary_v1.md
│   ├── generation_summary_d8_d10_v1.md
│   ├── cross_dataset_reconciliation_audit_v1.xlsx
│   ├── cross_dataset_audit_d8_d10_v1.xlsx
│   ├── data_dictionary_v1.csv
│   ├── data_dictionary_d8_d10_v1.csv
│   ├── key_relationship_spec_v1.csv
│   ├── key_relationship_spec_d8_d10_v1.csv
│   └── dataset_integration_report.md         (This authoritative report)
│
└── scripts/                                  <-- ARCHIVED REPRODUCIBLE GENERATION & VALIDATION CODE
    ├── generate_datasets_v1.py
    ├── validate_v1.py
    ├── build_docs_v1.py
    ├── generate_d8_d10_v1.py
    ├── validate_and_document_d8_d10_v1.py
    └── build_docs_d8_d10_v1.py
```

---

## 5. STATISTICAL VALIDATION TABLE ACROSS ALL 30 CSV FILES

Every single file was scanned directly from disk to compute exact row counts, column counts, column names, date ranges, null cell counts, primary key duplicates, and cryptographic SHA-256 digests:

| Domain | Relative Path & Filename | Row Count | Col Count | Primary Identifier | Duplicate Keys | Total Nulls | Date Columns & Sampled Range | Provenance | SHA-256 Checksum |
|---|---|---|---|---|---|---|---|---|---|
| **D1** | `raw/fact_hourly_production.csv` | 8,832 | 23 | `event_id` | 0 | 5,252 | `event_ts`, `event_date` (2026-08-01 to 2026-08-21) | Raw Baseline | `cdd5e0b3444132886b688fe51416db8111bc24e33bbab1decee2810b6b31b370` |
| **D1** | `enhanced/fact_hourly_production_enhanced_v1.csv` | 8,832 | 41 | `event_id` | 0 | 19,471 | `event_ts`, `event_date` (2026-08-01 to 2026-08-21) | Enhanced Baseline | `b5f6c67f64be967c82e7c1ca12eb109ddcdfcf45a60115559292b369e8a1b5ce` |
| **D2** | `raw/fact_manufacturing_cost.csv` | 5,000 | 15 | `cost_record_id` | 0 | 0 | `posting_ts` (2026-08-01 to 2026-10-31) | Raw Baseline | `444212efe15a93952bda90889e51b3d0e3fffe8a56ede5c71735de9665671cbc` |
| **D2** | `enhanced/fact_manufacturing_cost_enhanced_v1.csv` | 5,000 | 36 | `cost_record_id` | 0 | 5,454 | `posting_ts` (2026-08-01 to 2026-10-31) | Enhanced Baseline | `86159dcca1f8bdd1824bb2ae34ec66866b6d3b1d5963fa9a7b74d82d2733c1bf` |
| **D3** | `raw/fact_bom_component.csv` | 48 | 8 | `bom_id` | 45* | 0 | `effective_from`, `effective_to` (2026-07-01 to 2026-07-01) | Raw Baseline | `aa7849e2b5c466d07ee12682a58ffcf79324a0b9dc67d9d2183c01313c26847d` |
| **D3** | `enhanced/fact_bom_component_enhanced_v1.csv` | 48 | 23 | `bom_id` | 45* | 42 | `effective_from`, `effective_to` (2026-07-01 to 2026-07-01) | Enhanced Baseline | `d1ec3459766e02ad7bfe1ffc7cf347d130b70b4bb268a99bb583174e16d07510` |
| **D4** | `raw/fact_quality_inspection.csv` | 16,000 | 19 | `inspection_id` | 0 | 30,878 | `inspection_ts` (2026-08-01 to 2026-10-31) | Raw Baseline | `cf137596cce7b76eb4aa29916349094172c6bf14c6e1b34eaf1720a1f3ae22d1` |
| **D4** | `enhanced/fact_quality_inspection_enhanced_v1.csv` | 16,000 | 42 | `inspection_id` | 0 | 63,605 | `inspection_ts` (2026-08-01 to 2026-10-31) | Enhanced Baseline | `4faa12f7c8a6783bba44cc467b8b7856284256e90fe4bd72a19875eb76098245` |
| **D5** | `generated/production_traceability/d5_production_order_v1.csv` | 2,607 | 29 | `production_order_id` | 0 | 126 | `order_created_ts`, `scheduled_start_date` (2026-08-01 to 2026-09-07) | Synthetic Extension | `365c71a3c61793466ae36cf287ef6fa53ec865d4bb316135eecad0d41334c9c7` |
| **D5** | `generated/production_traceability/d5_production_run_v1.csv` | 4,318 | 40 | `production_run_id` | 0 | 48 | `run_start_ts`, `run_end_ts` (2026-07-31 to 2026-08-26) | Synthetic Extension | `9be85a15a81caec2a8cbf4a72d733158c3db47bb1f0217983ea1cbf5cf2eb9df` |
| **D5** | `generated/production_traceability/d5_run_source_link_v1.csv` | 13,832 | 20 | `link_id` | 0 | 0 | `slot_ts` (2026-08-01 to 2026-08-21) | Synthetic Extension | `4c8d5750d402ff1b4c3e8a1b55909d85449557002b8d00ea4f67c4273dfc0678` |
| **D6** | `generated/material_consumption/d6_material_issue_consumption_v1.csv` | 72,897 | 45 | `material_issue_id` | 0 | 39,067 | `slot_ts`, `issue_ts` (2026-08-01 to 2026-08-03) | Synthetic Extension | `9f6333333337a7fead7208d24cb34d1933ba1fc332402fe38bfbc0ff16aa0ee2` |
| **D7** | `generated/inventory/d7_inventory_transactions_v1.csv` | 142,508 | 31 | `inventory_txn_id` | 0 | 144,066 | `txn_ts` (2026-08-01 to 2026-08-02) | Synthetic Extension | `ba33c5e0dc3f837651a70cb3c584b4242636eb3907720973a6e60b1387d8df93` |
| **D8** | `generated/procurement/d8_supplier_master_v1.csv` | 15 | 14 | `supplier_id` | 0 | 0 | `audit_date` (Static master catalog) | Synthetic Extension | `13217b1fb9706346bc7fc7387e07fc5fbb9a44ca76f092305389658f8b86d99e` |
| **D8** | `generated/procurement/d8_supplier_material_source_list_v1.csv` | 19 | 9 | `source_list_id` | 0 | 0 | `valid_from`, `valid_to` (Static sourcing list) | Synthetic Extension | `a3ad30c1be5a04a08ecb0e2714c77c01b965f3f2277c22e4313f86e3f56ec8df` |
| **D8** | `generated/procurement/d8_po_header_v1.csv` | 260 | 15 | `po_id` | 0 | 0 | `po_date`, `doc_date` (2026-06-22 to 2026-10-26) | Synthetic Extension | `2ffc9bc60b378c3c6f62f83193e25b128509c15d48721bf920c81d830b13cf17` |
| **D8** | `generated/procurement/d8_po_line_v1.csv` | 348 | 33 | `po_line_id` | 0 | 481 | `delivery_due_date` (2026-08-03 to 2026-12-07) | Synthetic Extension | `a5fce4847e09cfeb534e8913926f866b1a7d6537b83f3e1b730f2f3e82fa087f` |
| **D8** | `generated/procurement/d8_goods_receipt_v1.csv` | 346 | 36 | `gr_id` | 0 | 0 | `gr_ts`, `gr_date` (2026-08-07 to 2026-10-30) | Synthetic Extension | `764aa5bc608f0a0d95d1d6a6954a65df19965faef048fa56012674f260fc456d` |
| **D8** | `generated/procurement/d8_supplier_quality_v1.csv` | 346 | 21 | `quality_id` | 0 | 804 | `inspection_ts` (2026-08-07 to 2026-10-30) | Synthetic Extension | `7995186b5105d15a999cb59c73efd806509f7a7596d66e746535560b435ee10f` |
| **D9** | `generated/equipment_energy/d9_equipment_master_v1.csv` | 32 | 25 | `equipment_id` | 0 | 4 | `commission_date`, `warranty_expiry` (Static assets) | Synthetic Extension | `15e57d1ae3b3925585090ef8cfb993e39ce6f50b86a8ff35df68ba0990a4279b` |
| **D9** | `generated/equipment_energy/d9_equipment_event_v1.csv` | 2,487 | 20 | `event_id` | 0 | 2,512 | `start_ts`, `end_ts` (2026-08-01 to 2026-10-31) | Synthetic Extension | `b345f4ec28da8490a1eb9738f6b21644f1c9fc6368d50b4ec701d0a5116788b6` |
| **D9** | `generated/equipment_energy/d9_energy_reading_shift_v1.csv` | 8,864 | 24 | `reading_id` | 0 | 0 | `shift_date`, `window_start_ts` (2026-07-31 to 2026-10-31) | Synthetic Extension | `bb4a7f0e748b64e03d4040da5b22557173e13eb1947eebca44fc6f92dd2e6fa6` |
| **D9** | `generated/equipment_energy/d9_maintenance_event_v1.csv` | 429 | 19 | `maintenance_id` | 0 | 437 | `scheduled_date`, `actual_start_ts` (2026-08-04 to 2026-10-28) | Synthetic Extension | `5f0ce1dfa1d1ca93d83768f7d98ee67d8d47fa189622d104593e8e225914619b` |
| **D9** | `generated/equipment_energy/d9_event_hourly_candidate_link_v1.csv` | 262 | 9 | `link_id` | 0 | 0 | `candidate_slot_ts` (Candidate cross-link table) | Synthetic Extension | `c9735d64ffc97ebc1c7ae9883bf44bc4c92ee0fcf0bf41e06cbeee4ce21efaa2` |
| **D10**| `generated/workforce/d10_shift_definition_v1.csv` | 3 | 12 | `shift_id` | 0 | 0 | `start_time`, `end_time` (Static shift definitions) | Synthetic Extension | `5e8fcfe76dd4ca9441f92e3a893cb6fb026d304910cfcb42cbbe835368a5c378` |
| **D10**| `generated/workforce/d10_employee_master_v1.csv` | 248 | 17 | `employee_id` | 0 | 2 | `hire_date` (2019-01-02 to 2026-07-22) | Synthetic Extension | `8f07aa03f75e218ce0e1f7d4b4a3c2005ef96e838b0051e5ea0aa61c5651586a` |
| **D10**| `generated/workforce/d10_shift_assignment_v1.csv` | 380 | 10 | `shift_assignment_id` | 0 | 0 | `effective_from_date`, `effective_to_date` (2026-08-01 to 2026-10-01)| Synthetic Extension | `11d8820f4c3a3ff67bb2d97c7ce377755a5bf989ae1c39062eb1bf3c99026da6` |
| **D10**| `generated/workforce/d10_line_allocation_v1.csv` | 380 | 18 | `allocation_id` | 0 | 140 | `effective_from_date`, `effective_to_date` (2026-08-01 to 2026-10-01)| Synthetic Extension | `aa241f9d51e70774641ef6fe9ec1334c4f826354897f2277d33b5c777e5e320d` |
| **D10**| `generated/workforce/d10_attendance_v1.csv` | 19,557 | 29 | `attendance_id` | 0 | 39,712 | `work_date`, `punch_in_ts`, `punch_out_ts` (2026-08-01 to 2026-08-10)| Synthetic Extension | `954f9a35e76a6cf47e8f5c35cf8db652bc5dae8d356c9a2c3ea0cfba64506869` |
| **D10**| `generated/workforce/d10_line_shift_labour_daily_v1.csv` | 1,104 | 20 | `labour_day_id` | 0 | 0 | `work_date` (2026-08-01 to 2026-10-31) | Synthetic Extension | `c04e28080f08a5433d3cbe76cbdfc9b83b6329433e53613a37ba7620a2333b20` |

*(Note on `fact_bom_component.csv`: The primary key is composite `(bom_id, material_id)`. The column `bom_id` repeats across the 16 components of each product SKU, explaining the 45 non-unique rows on column 1; the composite key is 100% unique.)*

---

## 6. BASELINE CRYPTOGRAPHIC VERIFICATION (PRE VS. POST INTEGRATION)

The four raw baseline CSV files were hashed prior to any file operations and re-hashed immediately following the complete directory build.

| Raw Baseline Filename | File Size | Pre-Integration SHA-256 | Post-Integration SHA-256 | Verification Result |
|---|---|---|---|---|
| `fact_bom_component.csv` | 4,033 B | `aa7849e2b5c466d07ee12682a58ffcf79324a0b9dc67d9d2183c01313c26847d` | `aa7849e2b5c466d07ee12682a58ffcf79324a0b9dc67d9d2183c01313c26847d` | **IDENTICAL (100% PASS)** |
| `fact_hourly_production.csv`| 1,270,687 B | `cdd5e0b3444132886b688fe51416db8111bc24e33bbab1decee2810b6b31b370` | `cdd5e0b3444132886b688fe51416db8111bc24e33bbab1decee2810b6b31b370` | **IDENTICAL (100% PASS)** |
| `fact_manufacturing_cost.csv`| 709,183 B | `444212efe15a93952bda90889e51b3d0e3fffe8a56ede5c71735de9665671cbc` | `444212efe15a93952bda90889e51b3d0e3fffe8a56ede5c71735de9665671cbc` | **IDENTICAL (100% PASS)** |
| `fact_quality_inspection.csv`| 2,676,938 B | `cf137596cce7b76eb4aa29916349094172c6bf14c6e1b34eaf1720a1f3ae22d1` | `cf137596cce7b76eb4aa29916349094172c6bf14c6e1b34eaf1720a1f3ae22d1` | **IDENTICAL (100% PASS)** |

**Conclusion:** Zero corruption, zero modification, zero drift.

---

## 7. CRITICAL FINDINGS FROM GENERATION AUDIT DOCUMENTATION

The generation documentation preserved in `backend/data/documentation/` (`generation_summary_v1.md`, `generation_summary_d8_d10_v1.md`, and the accompanying Excel reconciliation workbooks) reveals vital operational boundaries that the AI Agent and future database ingestion pipelines must respect:

### 1. Production Orders & Runs are Synthetic Groupings, Not Physical Campaigns
- The raw hourly production feed assigns a different PO/product code on almost every hour (8,823 contiguous blocks across 8,832 rows).
- In reality, **no continuous physical campaign exists in the raw data**. Production orders (`d5_production_order_v1.csv`) and runs (`d5_production_run_v1.csv`) are synthetic label groupings constructed by pooling `PO + plant + line + product`. 2,056 of the 2,607 orders carry the explicit flag `SPARSE_MULTI_WEEK_SPAN`.
- *Governance Directive:* The agent must never treat order start/end dates as physical shopfloor continuous run boundaries.

### 2. Hourly Production to Cost Batch Linkage is `CANDIDATE_ONLY`
- All 5,000 cost batches match an hourly production slot on `timestamp + plant + line + PO + product + qty`.
- However, 3,832 hourly slots have no corresponding cost batch (`UNCOSTED_OPERATIONAL_RUN`).
- The link is formally classified in the audit workbook as `CANDIDATE_ONLY` because statutory ERP accounting settlement linkage is unverified.

### 3. Material Consumption (D6) vs. Inventory Transactions (D7)
- D6 posts 72,897 material issue lines generated per hourly slot and component kit.
- D7 posts 142,508 inventory movements: every D6 issue and partial return (69,085 lines), plus 64 opening balances, 346 goods receipts, 96 cycle-count adjustments, and 10 inter-plant transfer pairs.
- *Strict Accounting Rule:* `issued = returned + consumed`. Actual consumption and theoretical consumption are maintained in separate columns.

### 4. Supplier Goods Receipts (D8) Reconcile with Inventory (D7)
- All 346 D7 `GOODS_RECEIPT` movements reconcile 1:1 with `d8_goods_receipt_v1.csv` on `txn_id + plant + material + lot + timestamp`.
- Value discrepancy is $\le \text{INR } 1.00$.
- In addition, 41,480 units were rejected at receiving inspection dock (`d8_supplier_quality_v1.csv`) and were correctly excluded from inventory.

### 5. Equipment Downtime & Energy (D9) Discrepancies
- Equipment events (2,487 events, 34,022 unplanned downtime minutes) do NOT reconcile directly to hourly production log downtime. The two feeds capture different failure granularities.
- Energy consumption (8,864 shift readings, 376,136 kWh, INR 3,046,851) is based on a rated-power equipment model and is **not reconciled** with the energy cost line in `fact_manufacturing_cost.csv`.

### 6. Workforce Attendance (D10) Attribution Limits
- Attendance (19,557 records, 248 employees) captures punches, regular hours, overtime (4,254 hours), and absenteeism (6.74%).
- However, **individual workers are not attributed to specific smartphone units or serial numbers**. Linkage to hourly production is at the aggregate line-shift-day level (`d10_line_shift_labour_daily_v1.csv`).

### 7. Injected RCA Anomaly Signals (Testing Ground-Truth)
- The documentation explicitly notes that several anomalies were intentionally injected as test signals for root-cause analysis:
  - Four material waste-spike lots: `MAT-CAM-007` (Plant TN), `MAT-GLS-010` (Plant KA), `MAT-BAT-006` (Plant TN), `MAT-SOC-001` (Plant KA) with scrap rates between 1.5% and 3.8% (vs. ~0.5%–0.9% normal).
  - 54 supplier receipt lots with elevated rejection rates.
  - SMT feeder-jam slots with 3x nominal component waste.
- *Governance Directive:* These test anomalies must be evaluated as synthetic validation scenarios, not represented as historical factory defects.

---

## 8. SUMMARY CHECKLIST & COMPLETION STATUS

- [x] All 10 logical manufacturing datasets are fully organized in the project.
- [x] All 30 physical CSV files are extracted, validated, and mapped.
- [x] Original four raw baseline CSV files remain 100% untouched and cryptographically verified.
- [x] Four enhanced versioned CSV files are cleanly isolated in `backend/data/enhanced/`.
- [x] All 22 extension CSV files are cleanly organized under `backend/data/generated/`.
- [x] All audit workbooks, data dictionaries, and specs are preserved in `backend/data/documentation/`.
- [x] All dataset generation and validation scripts are preserved in `backend/data/scripts/` without execution.
- [x] Comprehensive statistical table (rows, cols, dates, nulls, checksums) generated.
- [x] Zero application source files, zero frontend components, and zero database records were modified.

**Task Status:** **COMPLETE.** Ready for user review and approval before proceeding to AI Agent implementation.
