# Manufacturing Cost RCA Agent — Datasets 5, 6, 7 (v1) — Generation Summary

Generation id `GEN-V1-20261120`, seed 20261120. All records are **synthetic extensions** (`record_origin`). The four source CSVs were opened read-only; their MD5 checksums were identical before and after (validated).

## Deliverables
| File | Rows | Cols | PK |
|---|---|---|---|
| d5_production_order_v1.csv | 2,607 | 29 | production_order_id |
| d5_production_run_v1.csv | 4,318 | 40 | production_run_id |
| d5_run_source_link_v1.csv | 13,832 | 20 | link_id |
| d6_material_issue_consumption_v1.csv | 72,897 | 45 | material_issue_id |
| d7_inventory_transactions_v1.csv | 142,508 | 31 | inventory_txn_id |
| data_dictionary_v1.csv, key_relationship_spec_v1.csv | — | — | every column / key documented |
| cross_dataset_reconciliation_audit_v1.xlsx | 12 sheets | | file profile, 89 validation results, relationship report, stock recon (live formulas), variance, anomalies, cost cross-check, assumptions |
| generate_datasets_v1.py, validate_v1.py, build_docs_v1.py | | | reproducible build |

## Most important source finding
The hourly feed assigns a different PO/product on almost every hour (8,823 contiguous blocks in 8,832 rows). **No real contiguous production run exists in the source.** I did not repair this. Runs are the source's own `PO|plant|line|product` groups, so they are sparse: 1,713 single-slot, 2,603 sparse non-contiguous (median ~40-day span for multi-slot runs), 2 contiguous. 2,056 of 2,607 orders carry `SPARSE_MULTI_WEEK_SPAN`. Treat run/order timing as a label grouping, not a physical campaign.

## Design
- **Order** = source PO + plant + product (2,607); **run** = order + line (4,318, 1–2 per order, SMT and FAL). Source PO is kept only as `source_po_number`; it is never a key.
- **Order→Run** 1:many, enforced and validated. 896 orders show only one line (`PARTIAL_ROUTING_OBSERVED`); 8 have no output.
- **Run→Hourly**: all 8,832 rows linked once (rule R1, full-key lineage) = `CONFIRMED`, with a caveat column stating this validates lineage, not the source PO's business meaning. Run quantities equal the sum of linked hourly rows (validated).
- **Run→Cost**: all 5,000 cost rows match one hourly slot on timestamp, plant, line, PO, product and qty (1:1), yet kept `CANDIDATE_ONLY` because the source relationship is unvalidated. 3,832 hourly slots have no cost row.
- **Quality**: not used to build anything. 6,491 inspections share a run key (`CANDIDATE_ONLY`), 9,509 have none (`UNMATCHED`).
- **D6** issue lines are per hourly slot, component and lot: kit = slot target × BOM qty × (1+scrap) rounded up to 10, with top-ups (2,570) when consumption exceeds the kit. Rule: `issued = returned + consumed`; `consumed` includes `scrapped`; actual and theoretical are separate columns.
- **D7** posts every D6 issue (72,897) and return (69,085) 1:1, plus 64 generated opening balances, 346 generated receipts (no supplier fields), 96 cycle-count adjustments and 10 inter-plant transfer pairs. Balances are stored per batch and per plant-material and recomputed independently from the file.

## Why these row counts
Volumes are driven by the source grain, not chosen: 8,677 producing hourly slots × 5 SMT or 11 FAL components ≈ 72.9k issue lines; D7 follows 1:1 from D6 because over-issue vs. ~83% source attainment makes most kits partially returned. Receipts (346) are about 8 days of demand per lot per plant/material.

## Validation (actually run, `validate_v1.py`, files re-read from disk)
89 checks, 89 PASS: PK uniqueness; 20 FK checks with 0 invalid; BOM product/material/qty/revision unchanged; run/order structure and quantity sums; timestamp windows; issue/return arithmetic; D6↔D7 two-way reconciliation; running balances reproduced from cumulative sums; **0 negative-stock rows**; transfer pairs; duplicate detection (0); relationship classes; source checksums.
The first validation run **failed 3 checks** (D6 carried the source PO number instead of the new order ID, a generator column-name collision). I fixed the generator, regenerated, and re-ran: all pass. The delivered files are the regenerated ones.

## Assumptions to confirm (full list in the workbook)
1. SMT components = SOC, MEM, NAND, PCB, CON; the rest at FAL (BOM has no stage; flagged on every D6 row).
2. UOM = EA everywhere (BOM has no UOM).
3. Scrap/waste is generated (BOM scrap factor × component multiplier × lot factor; ×3 on SMT feeder-jam slots) and is **not** reconciled to hourly reject/rework or inspection.
4. Unit values are generated standard prices calibrated to the cost file's mean material cost/unit (~INR 9,752); they are not purchase prices.
5. Opening stock, receipts, transfers and adjustments are generated; supplier linkage is `UNMATCHED` pending the future supplier dataset.

## Findings worth knowing
- The cost file books ~INR 9.7k material cost per unit on **both** SMT and FAL lines, versus ~4.7–5.0k per unit when D6 values only the stage-assigned components. This is reported in `Cost_CrossCheck` and not reconciled.
- Four waste-spike lots (CAM-007 TN, GLS-010 KA, BAT-006 TN, SOC-001 KA) were injected as RCA test signals (scrap 1.5–3.8% vs ~0.5–0.9% median). Ground truth is only in the workbook sheet `Injected_Anomalies`, not in the CSVs.
- BOM identical across three products remains unconfirmed and is flagged on every D6 row.
