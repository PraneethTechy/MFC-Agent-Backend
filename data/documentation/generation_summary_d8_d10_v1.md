# Generation Summary - Datasets 8, 9, 10 (v1)
All new data is **synthetic**; existing seven datasets were read only (not rewritten). Run tag `GEN-D8D10-V1-20261120`.

## Files (17 CSV, 35,080 rows)
| File | Rows | Cols | Primary key | Dup PK |
|---|---|---|---|---|
| d8_supplier_master_v1.csv | 15 | 14 | supplier_id | 0 |
| d8_supplier_material_source_list_v1.csv | 19 | 9 | source_list_id | 0 |
| d8_po_header_v1.csv | 260 | 15 | po_id | 0 |
| d8_po_line_v1.csv | 348 | 33 | po_line_id | 0 |
| d8_goods_receipt_v1.csv | 346 | 36 | gr_id | 0 |
| d8_supplier_quality_v1.csv | 346 | 21 | quality_id | 0 |
| d9_equipment_master_v1.csv | 32 | 25 | equipment_id | 0 |
| d9_equipment_event_v1.csv | 2,487 | 20 | event_id | 0 |
| d9_energy_reading_shift_v1.csv | 8,864 | 24 | reading_id | 0 |
| d9_maintenance_event_v1.csv | 429 | 19 | maintenance_id | 0 |
| d9_event_hourly_candidate_link_v1.csv | 262 | 9 | link_id | 0 |
| d10_shift_definition_v1.csv | 3 | 12 | shift_id | 0 |
| d10_employee_master_v1.csv | 248 | 17 | employee_id | 0 |
| d10_shift_assignment_v1.csv | 380 | 10 | shift_assignment_id | 0 |
| d10_line_allocation_v1.csv | 380 | 18 | allocation_id | 0 |
| d10_attendance_v1.csv | 19,557 | 29 | attendance_id | 0 |
| d10_line_shift_labour_daily_v1.csv | 1,104 | 20 | labour_day_id | 0 |

Docs: `data_dictionary_d8_d10_v1.csv` (226 unique columns, field_origin tagged), `key_relationship_spec_d8_d10_v1.csv`, `cross_dataset_audit_d8_d10_v1.xlsx`. Scripts: `generate_d8_d10_v1.py`, `validate_and_document_d8_d10_v1.py`, `build_docs_d8_d10_v1.py`.

## Validation (one run, files re-read from disk)
**161/161 checks PASS.** Duplicate PKs 0, duplicate alternate keys 0, 35 FK checks with 0 invalid references, 0 failed reconciliations.
One validator rule was mis-specified on the first run (productive hours ceiling ignored overtime); I corrected the check, not the data, and re-ran.

## Key reconciliations
- **D8 <-> D7:** all 346 D7 `GOODS_RECEIPT` rows have exactly one D8 GR (txn id, plant, sloc, material, batch, timestamp match). `accepted_qty` = D7 `qty_in` on every row; value diff <= INR 1. Received = accepted + rejected (41,480 units rejected at dock, never in D7). No stock balance is held in D8.
- **D8 PO lines:** totals equal sum of GRs; 30 split deliveries, 32 open lines (due after window); every shortfall is a CLOSED_SHORT with a reason.
- **D9:** 0 overlapping events per equipment; shift energy windows reconcile to event minutes recomputed independently; meter registers continuous; kWh within +/-15% of the rated-power model.
- **D10:** actual hours = punches; actual = regular + OT; absent/leave rows have zero hours/productive hours; 0 rest or assignment conflicts; labour-day summary matches attendance.

## Relationship classes
CONFIRMED 6, CANDIDATE_ONLY 4, UNMATCHED 11 (see `Relationship_Status`). Only identifier-level links (GR->D7, material, plant/line, shift) are CONFIRMED. Equipment events vs hourly downtime (252 events), station mappings and labour-day vs hourly slots are CANDIDATE_ONLY. Employee-to-run attribution, supplier-to-real-source, purchase PO vs production PO, and energy vs cost file are UNMATCHED.

## Headline figures
GR on-time 88.4% (40 late), 54 lots with rejects; equipment unplanned downtime 34,022 min; energy 376,136 kWh / INR 3,046,851; absence+leave 6.74%; OT 4,254 h.

## Unresolved assumptions (full list in workbook `Assumptions`)
1. Supplier, price, FX (88.00), tariff, equipment catalogue and headcount are assumptions; none are real. 2. D7's own supplier status stays UNMATCHED (read-only); the link lives in `d8_goods_receipt`. 3. Equipment downtime is not confirmed against hourly downtime (magnitudes differ; see `Info_CrossScope`). 4. Energy is not reconciled to cost-file energy. 5. 2026-07-31 C-shift hourly slots have no workforce rows; 74 Oct-31 C-shift punches check out on 2026-11-01. 6. Intentional RCA test patterns exist only in `Injected_Anomalies`.
