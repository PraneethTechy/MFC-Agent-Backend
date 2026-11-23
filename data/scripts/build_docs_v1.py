import pandas as pd, numpy as np, json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
OUT = '/mnt/user-data/outputs'; SRC = '/mnt/user-data/uploads'
V = json.load(open('/home/claude/validation.json')); G = json.load(open('/home/claude/gen_meta.json'))
rd = lambda f: pd.read_csv(f, low_memory=False)
O = rd(f'{OUT}/d5_production_order_v1.csv'); R = rd(f'{OUT}/d5_production_run_v1.csv'); L = rd(f'{OUT}/d5_run_source_link_v1.csv')
M = rd(f'{OUT}/d6_material_issue_consumption_v1.csv'); I = rd(f'{OUT}/d7_inventory_transactions_v1.csv')
c = rd(f'{SRC}/fact_manufacturing_cost_enhanced_v1.csv'); h = rd(f'{SRC}/fact_hourly_production_enhanced_v1.csv')

# ---------------------------------------------------------------- data dictionary
DD = {}
def d(file, text):
    DD[file] = [tuple(x.strip() for x in l.split('|', 3)) for l in text.strip().splitlines()]
d('d5_production_order_v1.csv', """
production_order_id|string|PK|Generated unique production order key PORD-<plant>-<seq>; NOT the source PO number
order_context_key|string|AK|Natural key source PO|plant|product; unique; basis for order grouping
source_po_number|string|-|Source PO value (PO-000001..450). Reused across plants/lines/products and over time; never a key
plant_id|string|-|Plant from hourly source (IN-TN-01, IN-KA-01)
product_id|string|-|Product from hourly source; must exist in BOM
bom_id|string|-|BOM header for product (REV-C) from BOM source
bom_revision|string|-|BOM revision from source (only REV-C)
planned_qty|int|-|GENERATED RULE: max planned_qty across the order's runs (run plans are sums of source hourly target_qty)
actual_qty|int|-|Actual units of the completion-basis run (FAL run if present, else SMT run)
good_qty|int|-|Good units of the completion-basis run
reject_qty|int|-|Reject units of the completion-basis run (source hourly, not reconciled to inspection)
rework_qty|int|-|Rework units of the completion-basis run (source hourly, not reconciled to inspection)
completion_basis_run_id|string|FK|production_run_id whose quantities populate order actuals
completion_basis|string|-|FAL_RUN or SMT_RUN_ONLY_NO_FAL_OBSERVED
run_count|int|-|Number of runs under the order (1 or 2)
routing_completeness|string|-|FULL_SMT_FAL, SMT_ONLY or FAL_ONLY as observed in hourly source
planned_start_ts|timestamp|-|Earliest planned run start (first source hourly slot start)
planned_end_ts|timestamp|-|Latest planned run end (last source hourly slot start + 1h)
actual_start_ts|timestamp|-|Earliest first producing slot start; null if no output
actual_end_ts|timestamp|-|Latest producing slot start + run_minutes; null if no output
first_production_date|date|-|Earliest source shift_production_date (may be 2026-07-31 for shift C)
last_production_date|date|-|Latest source shift_production_date
calendar_span_days|int|-|Whole days between planned start and planned end
order_status|string|-|COMPLETED / SHORT_CLOSED / NO_OUTPUT (basis run, FULL routing) or PARTIAL_ROUTING_OBSERVED
schedule_ref|string|-|Generated schedule slot reference SCH-<plant>-<line>-<date>-<shift> (non-unique reference)
source_po_traceability_status|string|-|Carried from hourly source: AMBIGUOUS_MULTI_CONTEXT
order_integrity_flag|string|-|NONE or pipe list: SPARSE_MULTI_WEEK_SPAN (>14 days), PARTIAL_ROUTING
record_origin|string|-|GENERATED_SYNTHETIC
generation_version|string|-|Generation run id
""")
d('d5_production_run_v1.csv', """
production_run_id|string|PK|Generated unique run key PRUN-nnnnn
production_order_id|string|FK|Parent order (exactly one) -> d5_production_order_v1
source_production_run_key|string|AK|Hourly source production_run_key PO|plant|line|product; unique
source_po_number|string|-|Source PO value (not unique)
plant_id|string|-|Plant
line_id|string|-|Line (SMT-L1/FAL-L1 at IN-TN-01; SMT-L2/FAL-L2 at IN-KA-01)
line_type|string|-|SMT or FAL from hourly source
product_id|string|-|Product
shift_id_first|string|-|Shift (A/B/C) of the first slot
shift_ids_covered|string|-|Pipe list of all shifts touched
shift_count|int|-|Distinct shifts touched
production_date_first|date|-|Earliest source shift_production_date
production_date_last|date|-|Latest source shift_production_date
planned_qty|int|-|Sum of hourly target_qty of the run's slots
actual_qty|int|-|Sum of hourly actual_qty
good_qty|int|-|Sum of hourly good_qty
reject_qty|int|-|Sum of hourly reject_qty
rework_qty|int|-|Sum of hourly rework_qty
attainment_pct|float|-|actual/planned x100; null if planned=0
planned_start_ts|timestamp|-|First slot start
planned_end_ts|timestamp|-|Last slot start + 1h
actual_start_ts|timestamp|-|First producing slot start; null if NO_OUTPUT
actual_end_ts|timestamp|-|Last producing slot start + run_minutes; null if NO_OUTPUT
slot_count|int|-|Number of hourly rows linked
producing_slot_count|int|-|Linked slots with actual_qty>0
zero_output_slot_count|int|-|Linked slots with actual_qty=0
downtime_min_total|int|-|Sum of hourly downtime_min
calendar_span_hours|int|-|planned_end - planned_start in hours
max_idle_gap_hours|int|-|Largest gap (hours) between consecutive slots of the run
execution_pattern|string|-|SINGLE_SLOT, CONTIGUOUS_SLOTS or SPARSE_NON_CONTIGUOUS
run_status|string|-|COMPLETED (>=95% of plan), SHORT_CLOSED, NO_OUTPUT
schedule_ref|string|-|Generated schedule slot reference (non-unique)
mes_execution_ref|string|-|MES:<first event_id>..<last event_id> source reference range
first_source_event_id|string|FK|First linked hourly event_id
last_source_event_id|string|FK|Last linked hourly event_id
source_suspicious_slot_count|int|-|Linked slots whose source data_quality = SUSPICIOUS
hourly_link_status|string|-|CONFIRMED (lineage only; see link table caveat)
candidate_cost_record_count|int|-|Cost records candidate-linked (CANDIDATE_ONLY) to this run's slots
record_origin|string|-|GENERATED_SYNTHETIC
generation_version|string|-|Generation run id
""")
d('d5_run_source_link_v1.csv', """
link_id|string|PK|Generated link key LNK-nnnnnnn
production_run_id|string|FK|Run -> d5_production_run_v1
production_order_id|string|FK|Order -> d5_production_order_v1
source_table|string|-|Source file the record comes from (hourly or cost)
source_record_id|string|FK|event_id (hourly) or cost_record_id (cost) in the source file
matched_hourly_event_id|string|FK|Hourly event_id of the slot; equals source_record_id for hourly rows
source_slot_ts|timestamp|-|Source event_ts / posting_ts
plant_id|string|-|Source plant
line_id|string|-|Source line
source_po_number|string|-|Source PO value (not unique)
link_rule_id|string|-|R1_HOURLY_FULLKEY or R2_COST_TO_HOURLY_SLOT
link_status|string|-|CONFIRMED / CANDIDATE_ONLY / UNMATCHED
evidence_strength|string|-|Description of attribute agreement
match_slot_plant_line_po|string|-|Y if slot ts+plant+line+PO matched
match_product|string|-|Y/N product agreement
match_qty|string|-|Y/N produced_qty = actual_qty (cost rows); NA for hourly
source_dq_status|string|-|Source data quality label of the linked row
business_validity_caveat|string|-|Why the status is not a business-validated link
record_origin|string|-|GENERATED_SYNTHETIC
generation_version|string|-|Generation run id
""")
d('d6_material_issue_consumption_v1.csv', """
material_issue_id|string|PK|Generated issue line key MI-nnnnnnn
production_order_id|string|FK|Order -> d5_production_order_v1
production_run_id|string|FK|Run -> d5_production_run_v1
source_hourly_event_id|string|FK|Hourly slot the kit supports -> fact_hourly_production event_id
plant_id|string|-|Plant of issue
storage_location_id|string|-|RM-SMT (SMT components) or RM-FAL (final assembly components); assumption
line_id|string|-|Consuming line
product_id|string|-|Product built
material_id|string|FK|Component -> fact_bom_component material_id
bom_id|string|FK|BOM header -> fact_bom_component bom_id
bom_revision|string|-|BOM revision (REV-C) from BOM
material_batch_id|string|-|Generated lot reference (no supplier lot)
transaction_type|string|-|INITIAL_ISSUE (kit for slot target) or TOP_UP_ISSUE (when consumption exceeded kit)
issue_ts|timestamp|-|Issue posting time (15-50 min before slot start; top-up 20-45 min after)
return_ts|timestamp|-|Return posting time; null if nothing returned
return_ts_basis|string|-|NORMAL, PERIOD_END_CLAMP (slot ended after 2026-10-31 23:59:59), NA_NO_RETURN
uom|string|-|EA (BOM has no UOM; qty-per-unit of 1 supports each)
units_started_qty|int|-|Slot actual_qty (units started incl. rejects); basis for theoretical need
bom_component_qty_per_unit|int|-|Theoretical BOM qty per unit (source, unchanged)
bom_scrap_factor|float|-|BOM scrap factor (source, unchanged)
theoretical_bom_qty|float|-|units x BOM qty, allocated pro-rata to consumed_qty if the slot-material has several lines
theoretical_qty_with_scrap|float|-|units x BOM qty x (1+scrap), allocated the same way. THEORETICAL, not actual
issued_qty|int|-|Quantity issued on this line (one batch)
returned_qty|int|-|Unused quantity returned to stock
consumed_qty|int|-|Actual consumption = issued - returned (includes scrapped_qty)
scrapped_qty|int|-|Portion of consumed_qty lost as material scrap/damage
net_consumed_qty|int|-|consumed - scrapped (material that went into units)
variance_vs_theoretical_qty|float|-|consumed_qty - theoretical_qty_with_scrap
variance_pct|float|-|variance / theoretical_qty_with_scrap x100
unit_value_inr|float|-|Generated lot unit value (standard price x lot variance)
consumed_value_inr|float|-|consumed_qty x unit_value_inr
scrapped_value_inr|float|-|scrapped_qty x unit_value_inr
issue_status|string|-|CLOSED_FULLY_CONSUMED / CLOSED_PARTIAL_RETURN / CLOSED_FULL_RETURN
reconciliation_check|string|-|OK if issued = returned + consumed
inventory_issue_txn_id|string|FK|Matching PRODUCTION_ISSUE row in d7
inventory_return_txn_id|string|FK|Matching PRODUCTION_RETURN row in d7; null if no return
order_run_link_status|string|-|CONFIRMED (generated FK)
hourly_slot_link_status|string|-|CONFIRMED (lineage by construction)
bom_link_status|string|-|CONFIRMED product+material pair exists in BOM REV-C
cost_link_status|string|-|CANDIDATE_ONLY if the slot has a cost record, else UNMATCHED
candidate_cost_record_id|string|FK|Candidate cost record for the slot; unvalidated
bom_structure_confirmation_status|string|-|UNCONFIRMED_IDENTICAL_STRUCTURE_ACROSS_PRODUCTS (source limitation carried forward)
stage_assignment_basis|string|-|ASSUMED_SMT_FAL_MAP_NOT_IN_BOM
record_origin|string|-|GENERATED_SYNTHETIC
generation_version|string|-|Generation run id
""")
d('d7_inventory_transactions_v1.csv', """
inventory_txn_id|string|PK|Generated key INV-nnnnnnn
ledger_seq|int|AK|Order of posting within (plant, material); with plant+material unique
plant_id|string|-|Plant
storage_location_id|string|-|RM-SMT or RM-FAL (one per material per plant)
material_id|string|FK|Component -> fact_bom_component material_id
material_batch_id|string|-|Generated lot reference (not a supplier lot)
transaction_ts|timestamp|-|Posting timestamp
transaction_date|date|-|Posting date
transaction_type|string|-|OPENING_BALANCE, GOODS_RECEIPT, PRODUCTION_ISSUE, PRODUCTION_RETURN, INVENTORY_ADJUSTMENT, TRANSFER_OUT, TRANSFER_IN
transaction_subtype|string|-|e.g. GENERATED_OPENING, STANDARD_GENERATED, TO_PRODUCTION_RUN, UNUSED_TO_STOCK, ADJ_GAIN, ADJ_LOSS, INTER_PLANT
reference_doc_type|string|-|Reference document class (MATERIAL_ISSUE, GENERATED_RECEIPT, ...)
reference_id|string|-|material_issue_id for issue/return; generated GR/OB/CC/STO number otherwise
related_material_issue_id|string|FK|D6 line for issue/return rows; null otherwise
related_production_order_id|string|FK|Order for issue/return rows
related_production_run_id|string|FK|Run for issue/return rows
counterpart_inventory_txn_id|string|FK|Paired transfer row (OUT<->IN)
qty_in|int|-|Quantity added to stock
qty_out|int|-|Quantity removed from stock
net_qty|int|-|qty_in - qty_out
uom|string|-|EA
unit_value_inr|float|-|Lot unit value (GENERATED, not actual purchase price)
valuation_basis|string|-|GENERATED_STANDARD_PRICE_x_LOT_VARIANCE
line_value_inr|float|-|net_qty x unit_value_inr
running_balance_batch_qty|int|-|Stock of this batch at plant after the row
running_balance_material_qty|int|-|Stock of this material at plant after the row
transaction_status|string|-|POSTED
negative_stock_flag|string|-|Y if either running balance < 0 (none expected)
traceability_status|string|-|CONFIRMED for issue/return (traced to D6), else NOT_APPLICABLE
supplier_receipt_link_status|string|-|UNMATCHED_SUPPLIER_DATASET_NOT_AVAILABLE for receipts/opening; else NOT_APPLICABLE
record_origin|string|-|GENERATED_OPENING_BALANCE for opening rows, GENERATED_SYNTHETIC otherwise
generation_version|string|-|Generation run id
""")
files = {'d5_production_order_v1.csv': O, 'd5_production_run_v1.csv': R, 'd5_run_source_link_v1.csv': L, 'd6_material_issue_consumption_v1.csv': M, 'd7_inventory_transactions_v1.csv': I}
rows = []
for f, df in files.items():
    assert [x[0] for x in DD[f]] == list(df.columns), f
    for col, typ, key, desc in DD[f]:
        rows.append(dict(file=f, column=col, data_type=typ, key_status={'-': ''}.get(key, key), business_meaning=desc))
DDF = pd.DataFrame(rows); DDF.to_csv(f'{OUT}/data_dictionary_v1.csv', index=False)

KS = pd.DataFrame([
 ('PK', 'd5_production_order_v1', 'production_order_id', '', '', 'Unique generated key'),
 ('AK', 'd5_production_order_v1', 'order_context_key', '', '', 'Natural key source_po|plant|product, unique'),
 ('PK', 'd5_production_run_v1', 'production_run_id', '', '', 'Unique generated key'),
 ('AK', 'd5_production_run_v1', 'source_production_run_key', '', '', 'Equals hourly production_run_key, unique'),
 ('FK', 'd5_production_run_v1', 'production_order_id', 'd5_production_order_v1', 'production_order_id', 'Many runs : 1 order (mandatory)'),
 ('FK', 'd5_production_order_v1', 'completion_basis_run_id', 'd5_production_run_v1', 'production_run_id', 'Run supplying order actuals'),
 ('PK', 'd5_run_source_link_v1', 'link_id', '', '', 'Unique generated key'),
 ('FK', 'd5_run_source_link_v1', 'production_run_id', 'd5_production_run_v1', 'production_run_id', 'Many links : 1 run'),
 ('FK', 'd5_run_source_link_v1', 'production_order_id', 'd5_production_order_v1', 'production_order_id', ''),
 ('FK (external)', 'd5_run_source_link_v1', 'source_record_id', 'fact_hourly_production_enhanced_v1.event_id / fact_manufacturing_cost_enhanced_v1.cost_record_id', '', 'Chosen by source_table; hourly CONFIRMED lineage, cost CANDIDATE_ONLY'),
 ('FK (external)', 'd5_run_source_link_v1', 'matched_hourly_event_id', 'fact_hourly_production_enhanced_v1', 'event_id', ''),
 ('FK (external)', 'd5_production_run_v1', 'first_source_event_id, last_source_event_id', 'fact_hourly_production_enhanced_v1', 'event_id', 'Source reference range'),
 ('PK', 'd6_material_issue_consumption_v1', 'material_issue_id', '', '', 'Unique generated key'),
 ('FK', 'd6_material_issue_consumption_v1', 'production_order_id', 'd5_production_order_v1', 'production_order_id', ''),
 ('FK', 'd6_material_issue_consumption_v1', 'production_run_id', 'd5_production_run_v1', 'production_run_id', 'Run belongs to the stated order (validated)'),
 ('FK (external)', 'd6_material_issue_consumption_v1', 'source_hourly_event_id', 'fact_hourly_production_enhanced_v1', 'event_id', ''),
 ('FK (external)', 'd6_material_issue_consumption_v1', 'material_id', 'fact_bom_component_enhanced_v1', 'material_id', 'Also (product_id, material_id) pair valid in BOM'),
 ('FK (external)', 'd6_material_issue_consumption_v1', 'bom_id', 'fact_bom_component_enhanced_v1', 'bom_id', ''),
 ('FK (external, candidate)', 'd6_material_issue_consumption_v1', 'candidate_cost_record_id', 'fact_manufacturing_cost_enhanced_v1', 'cost_record_id', 'CANDIDATE_ONLY'),
 ('FK', 'd6_material_issue_consumption_v1', 'inventory_issue_txn_id', 'd7_inventory_transactions_v1', 'inventory_txn_id', '1:1'),
 ('FK', 'd6_material_issue_consumption_v1', 'inventory_return_txn_id', 'd7_inventory_transactions_v1', 'inventory_txn_id', '1:0..1'),
 ('AK', 'd6_material_issue_consumption_v1', 'production_run_id+source_hourly_event_id+material_id+material_batch_id+transaction_type', '', '', 'Business key, unique'),
 ('PK', 'd7_inventory_transactions_v1', 'inventory_txn_id', '', '', 'Unique generated key'),
 ('AK', 'd7_inventory_transactions_v1', 'plant_id+material_id+ledger_seq', '', '', 'Posting order; reproducible balance'),
 ('FK (external)', 'd7_inventory_transactions_v1', 'material_id', 'fact_bom_component_enhanced_v1', 'material_id', ''),
 ('FK', 'd7_inventory_transactions_v1', 'related_material_issue_id', 'd6_material_issue_consumption_v1', 'material_issue_id', 'Issue/return rows only'),
 ('FK', 'd7_inventory_transactions_v1', 'related_production_run_id', 'd5_production_run_v1', 'production_run_id', 'Issue/return rows only'),
 ('FK', 'd7_inventory_transactions_v1', 'related_production_order_id', 'd5_production_order_v1', 'production_order_id', 'Issue/return rows only'),
 ('FK (self)', 'd7_inventory_transactions_v1', 'counterpart_inventory_txn_id', 'd7_inventory_transactions_v1', 'inventory_txn_id', 'Transfer OUT<->IN'),
], columns=['key_type', 'table', 'column(s)', 'references_table', 'references_column', 'note'])
KS.to_csv(f'{OUT}/key_relationship_spec_v1.csv', index=False)

# ---------------------------------------------------------------- analytics for workbook
Mi = M.copy(); Ii = I.copy()
# material recon per plant/material
rec = []
for (p, m), x in Ii.groupby(['plant_id', 'material_id']):
    t = x.groupby('transaction_type')[['qty_in', 'qty_out']].sum()
    g = lambda ty, k: int(t.loc[ty, k]) if ty in t.index else 0
    rec.append(dict(plant_id=p, material_id=m, storage_location_id=x.storage_location_id.iloc[0], opening=g('OPENING_BALANCE', 'qty_in'), receipts=g('GOODS_RECEIPT', 'qty_in'),
        transfer_in=g('TRANSFER_IN', 'qty_in'), returns=g('PRODUCTION_RETURN', 'qty_in'), issues=g('PRODUCTION_ISSUE', 'qty_out'), transfer_out=g('TRANSFER_OUT', 'qty_out'),
        adj_in=int(x[(x.transaction_type == 'INVENTORY_ADJUSTMENT')].qty_in.sum()), adj_out=int(x[(x.transaction_type == 'INVENTORY_ADJUSTMENT')].qty_out.sum()),
        closing_ledger=int(x.sort_values('ledger_seq').running_balance_material_qty.iloc[-1]),
        d6_issued=int(M[(M.plant_id == p) & (M.material_id == m)].issued_qty.sum()), d6_returned=int(M[(M.plant_id == p) & (M.material_id == m)].returned_qty.sum()),
        d6_consumed=int(M[(M.plant_id == p) & (M.material_id == m)].consumed_qty.sum())))
REC = pd.DataFrame(rec)
# min balances
minbal = Ii.groupby(['plant_id', 'material_id']).running_balance_material_qty.min().rename('min_balance').reset_index()
REC = REC.merge(minbal, on=['plant_id', 'material_id'])
# variance by material
VAR = M.groupby('material_id').agg(lines=('material_issue_id', 'size'), issued=('issued_qty', 'sum'), returned=('returned_qty', 'sum'), consumed=('consumed_qty', 'sum'),
    scrapped=('scrapped_qty', 'sum'), theoretical_with_scrap=('theoretical_qty_with_scrap', 'sum'), variance_qty=('variance_vs_theoretical_qty', 'sum'), scrapped_value_inr=('scrapped_value_inr', 'sum')).reset_index()
VAR['variance_pct'] = (VAR.variance_qty / VAR.theoretical_with_scrap * 100).round(3)
# anomaly detection check
an = pd.DataFrame(G['anomalies'])
lot = M.groupby(['plant_id', 'material_id', 'material_batch_id']).agg(consumed=('consumed_qty', 'sum'), scrapped=('scrapped_qty', 'sum')).reset_index()
lot['scrap_rate_pct'] = (lot.scrapped / lot.consumed * 100).round(3)
lot['material_median_pct'] = lot.groupby(['plant_id', 'material_id']).scrap_rate_pct.transform('median')
an = an.merge(lot, left_on=['plant_id', 'material_id', 'batch_id'], right_on=['plant_id', 'material_id', 'material_batch_id'], how='left')[['material_id', 'plant_id', 'batch_id', 'waste_multiplier', 'consumed', 'scrapped', 'scrap_rate_pct', 'material_median_pct']]
# cost cross-check
cc = c.merge(h[['event_id', 'event_ts', 'plant_id', 'line_id', 'production_order_id']], left_on=['posting_ts', 'plant_id', 'line_id', 'production_order_id'], right_on=['event_ts', 'plant_id', 'line_id', 'production_order_id'])
mv = M.groupby('source_hourly_event_id').consumed_value_inr.sum()
cc['d6_consumed_value'] = cc.event_id.map(mv).fillna(0)
cx = cc.groupby(['line_type', 'product_id']).agg(cost_rows=('cost_record_id', 'size'), units=('produced_qty', 'sum'), source_material_cost_inr=('material_cost_inr', 'sum'), d6_consumed_value_inr=('d6_consumed_value', 'sum')).reset_index()
cx['source_material_cost_per_unit'] = (cx.source_material_cost_inr / cx.units).round(2); cx['d6_value_per_unit'] = (cx.d6_consumed_value_inr / cx.units).round(2)
# status distributions
dist = []
for nm, s in [('order_status', O.order_status), ('routing_completeness', O.routing_completeness), ('order_integrity_flag', O.order_integrity_flag), ('run_status', R.run_status), ('execution_pattern', R.execution_pattern), ('run line_type', R.line_type), ('link_status by source', L.source_table + ' : ' + L.link_status), ('D6 transaction_type', M.transaction_type), ('D6 issue_status', M.issue_status), ('D7 transaction_type', I.transaction_type)]:
    for k, v in s.value_counts().items(): dist.append((nm, k, int(v)))
DIST = pd.DataFrame(dist, columns=['attribute', 'value', 'count'])
R2 = R[R.slot_count > 1]
span = dict(sparse_runs=int((R.execution_pattern == 'SPARSE_NON_CONTIGUOUS').sum()), single=int((R.execution_pattern == 'SINGLE_SLOT').sum()), contiguous=int((R.execution_pattern == 'CONTIGUOUS_SLOTS').sum()),
            median_span_days_multislot=float(R2.calendar_span_hours.median() / 24), orders_span_gt14=int((O.calendar_span_days > 14).sum()))

ASSUME = [
 ('A1', 'Production run = source production_run_key group (PO|plant|line|product)', 'Hourly source has no contiguous runs: PO/product changes almost every hour (8,823 contiguous blocks in 8,832 rows). Key groups are the only run definition the source supports.', 'Runs are sparse (median ~40 day span for multi-slot runs). Flagged by execution_pattern/max_idle_gap_hours. NOT repaired.'),
 ('A2', 'Production order = source PO + plant + product', 'PO alone is reused across plants, lines and products; 2,607 distinct PO|plant|product contexts. An order routes through SMT and FAL lines of one plant.', 'Orders can span weeks (order_integrity_flag). Likely PO-number reuse over time in source.'),
 ('A3', 'Run planned qty/timestamps from hourly target_qty / slot times; actuals from producing slots', 'Hourly target_qty is the only plan evidence.', 'No independent MES order plan exists.'),
 ('A4', 'Order planned_qty = max of run plans; order actuals = final-stage run (FAL else SMT)', 'Phones pass SMT then FAL; line-level quantities differ in source.', 'Generated rule; SMT_ONLY / FAL_ONLY orders flagged PARTIAL_ROUTING_OBSERVED.'),
 ('A5', 'SMT components = SOC, MEM, NAND, PCB, CON; all other components consumed at FAL', 'BOM has no stage attribute; needed to avoid double-counting consumption on both lines.', 'ASSUMPTION; every D6 row carries stage_assignment_basis. Confirm with process engineering.'),
 ('A6', 'UOM = EA for all components', 'BOM has no UOM; every BOM qty is integer 1 per phone, supporting discrete units.', 'No reel/tray/weight units are supported by source.'),
 ('A7', 'Material issued per hourly slot (line-feeding kit = slot target x BOM qty x (1+scrap), rounded up to 10); consumption from slot actual_qty', 'Source gives hourly grain only; per-run issue would hold stock at line for weeks because slots are sparse.', 'Returns are frequent because source attainment averages ~83% of target (over-issue pattern is a genuine RCA signal in this synthetic data).'),
 ('A8', 'Actual consumption = units started x BOM qty + generated material scrap (Poisson around BOM scrap_factor x component multiplier x lot factor; x3 for SMT slots with FEEDER_JAM)', 'Needed to distinguish actual from theoretical.', 'Synthetic. Scrap is NOT reconciled to hourly reject/rework or inspection (source cannot support it).'),
 ('A9', 'Unit valuation: standard price per component calibrated so sum(price x (1+scrap)) = observed mean material cost per unit in cost file (INR %.2f), split by assumed component weights; lot variance lognormal ~1.2%%' % G['target_unit_mat_cost'], 'Source has no component prices.', 'Generated valuation, not purchase prices; row-level reconciliation to cost file is not claimed.'),
 ('A10', 'Opening balances at 2026-08-01T00:00:00 (TN 10 days of demand, KA 16 days) in two lots per plant/material', 'No historical stock source.', 'GENERATED_OPENING_BALANCE; supplier receipt link UNMATCHED.'),
 ('A11', 'Goods receipts generated by reorder-point policy (ROP 5 days demand, lot 8 days, lead 36-72h), no supplier information', 'Receipts are needed for a closed-loop ledger; supplier deliveries belong to a future dataset.', 'GENERATED; reference GR-GEN-*.'),
 ('A12', 'Inter-plant transfers (OUT then IN 24-36h later), monthly cycle-count adjustments (~-0.1%% mean)', 'Optional types shown consistently.', 'GENERATED.'),
 ('A13', 'Zero-output hourly slots receive no material issue', 'No units started.', '155 slots / 24 runs have no D6 rows.'),
 ('A14', 'Slot-level material cost issue: cost file books ~full BOM material cost per unit on BOTH SMT and FAL lines', 'Observed in cost data (see Cost_CrossCheck).', 'Not reconcilable with the stage split; reported, not repaired.'),
]
INJ = an

# ---------------------------------------------------------------- workbook
wb = Workbook(); HF = Font(name='Arial', bold=True, color='FFFFFF'); HFill = PatternFill('solid', fgColor='1F3864'); AF = Font(name='Arial', size=10)
def sheet(name, df, widths=None, note=None):
    ws = wb.create_sheet(name); r0 = 1
    if note: ws.cell(1, 1, note).font = Font(name='Arial', italic=True, size=10); r0 = 3
    for j, col in enumerate(df.columns, 1):
        cell = ws.cell(r0, j, col); cell.font = HF; cell.fill = HFill; cell.alignment = Alignment(wrap_text=True, vertical='center')
    for i, row in enumerate(df.itertuples(index=False), r0 + 1):
        for j, v in enumerate(row, 1):
            if isinstance(v, (np.integer,)): v = int(v)
            elif isinstance(v, (np.floating,)): v = None if np.isnan(v) else float(v)
            ws.cell(i, j, v).font = AF
    for j, col in enumerate(df.columns, 1):
        mx = max([len(str(col))] + [len(str(x)) for x in df.iloc[:200, j - 1]]); ws.column_dimensions[get_column_letter(j)].width = min(max(10, mx + 2), 70 if not widths else widths.get(col, 70))
    ws.freeze_panes = ws.cell(r0 + 1, 1); return ws, r0
wb.remove(wb.active)
# File profile
prof = []
for f, p in V['profile'].items():
    prof.append(dict(filename=f, row_count=p['rows'], column_count=p['cols'], primary_key=p['pk'], foreign_keys=p['fks'], date_column=p['date_col'], date_min=p['dmin'], date_max=p['dmax'],
                     total_null_cells=p['null_total'], columns_with_nulls=', '.join(f'{k}={v}' for k, v in p['null_cols'].items()) or 'none', duplicate_pk_count=p['dup_pk'], invalid_reference_count=V['fk_invalid_by_file'][f]))
PROF = pd.DataFrame(prof)
sheet('File_Profile', PROF, note='Profile of the five generated CSVs (re-read from disk). Null counts are structural (e.g. return_ts empty when nothing returned) unless noted in the dictionary.')
RES = pd.DataFrame(V['res']); sheet('Validation_Results', RES, widths={'detail': 90, 'check': 95}, note='Automated checks executed against files re-read from disk. 89 checks; results below are actual outputs of validate_v1.py.')
RELD = pd.DataFrame(V['rel'], columns=['relationship', 'classification', 'record_count', 'basis_and_caveat']); sheet('Relationship_Report', RELD, widths={'basis_and_caveat': 110, 'relationship': 55}, note='Classification: CONFIRMED / CANDIDATE_ONLY / UNMATCHED / NOT_APPLICABLE. Candidate links were NOT promoted to confirmed.')
sheet('Distributions', DIST)
# Material recon with formulas
ws, r0 = sheet('Stock_Recon', REC, note='Per plant/material: closing recomputed by formula = opening + receipts + transfer_in + returns + adj_in - issues - transfer_out - adj_out; diff vs ledger closing must be 0. D6 issued/returned tie to D7 issues/returns.')
n = len(REC); cols = list(REC.columns); ci = {k: get_column_letter(i + 1) for i, k in enumerate(cols)}
base = len(cols)
extra = ['closing_by_formula', 'diff_vs_ledger', 'issues_vs_D6_issued_diff', 'returns_vs_D6_returned_diff', 'min_balance_check']
for k, e in enumerate(extra):
    cell = ws.cell(r0, base + 1 + k, e); cell.font = HF; cell.fill = HFill
for i in range(r0 + 1, r0 + 1 + n):
    r = i
    ws.cell(r, base + 1, f"={ci['opening']}{r}+{ci['receipts']}{r}+{ci['transfer_in']}{r}+{ci['returns']}{r}+{ci['adj_in']}{r}-{ci['issues']}{r}-{ci['transfer_out']}{r}-{ci['adj_out']}{r}")
    ws.cell(r, base + 2, f"={get_column_letter(base + 1)}{r}-{ci['closing_ledger']}{r}")
    ws.cell(r, base + 3, f"={ci['issues']}{r}-{ci['d6_issued']}{r}")
    ws.cell(r, base + 4, f"={ci['returns']}{r}-{ci['d6_returned']}{r}")
    ws.cell(r, base + 5, f'=IF({ci["min_balance"]}{r}>=0,"OK","NEGATIVE")')
    for k in range(1, 6): ws.cell(r, base + k).font = AF
tr = r0 + n + 1
ws.cell(tr, 1, 'TOTAL / CHECK').font = Font(name='Arial', bold=True)
for k in ['opening', 'receipts', 'transfer_in', 'returns', 'issues', 'transfer_out', 'adj_in', 'adj_out', 'closing_ledger', 'd6_issued', 'd6_returned', 'd6_consumed']:
    ws[f"{ci[k]}{tr}"] = f"=SUM({ci[k]}{r0 + 1}:{ci[k]}{r0 + n})"; ws[f"{ci[k]}{tr}"].font = Font(name='Arial', bold=True)
for k in range(2, 5):
    L_ = get_column_letter(base + k); ws[f"{L_}{tr}"] = f"=SUMPRODUCT(ABS({L_}{r0 + 1}:{L_}{r0 + n}))"; ws[f"{L_}{tr}"].font = Font(name='Arial', bold=True)
ws[f"{get_column_letter(base + 5)}{tr}"] = f'=COUNTIF({get_column_letter(base + 5)}{r0 + 1}:{get_column_letter(base + 5)}{r0 + n},"NEGATIVE")'
ws.cell(tr + 1, 1, 'Identity check (D7 transfer_in/out): consumed = issued - returned').font = AF
ws[f"{ci['d6_consumed']}{tr + 1}"] = f"={ci['d6_issued']}{tr}-{ci['d6_returned']}{tr}-{ci['d6_consumed']}{tr}"
for col in range(1, base + 6):
    for row in range(r0 + 1, tr + 2):
        cell = ws.cell(row, col)
        if isinstance(cell.value, (int, float)) or (isinstance(cell.value, str) and cell.value.startswith('=')): cell.number_format = '#,##0;(#,##0);-'
sheet('Material_Variance', VAR, note='Actual consumption vs THEORETICAL BOM requirement (with scrap factor), all D6 lines. Positive variance = consumed more than theoretical.')
sheet('Injected_Anomalies', INJ, note='GROUND TRUTH of synthetic waste-spike lots (generator setting). Kept out of the CSVs so RCA testing is blind. scrap_rate vs the material/plant median shows detectability.')
sheet('Cost_CrossCheck', cx, note='INFORMATIONAL, candidate-linked slots only. Cost file books ~full BOM material cost per unit on both SMT and FAL lines; D6 values only the stage-assigned components. Not reconciled and not repaired.')
sheet('Assumptions', pd.DataFrame(ASSUME, columns=['id', 'assumption_or_rule', 'reason', 'limitation_or_flag']), widths={'assumption_or_rule': 80, 'reason': 80, 'limitation_or_flag': 80})
sheet('Source_Limitations', pd.DataFrame([
 ('PO reuse', 'PO values reused across 2 plants, 4 lines, 3 products (and across time)', 'Order/run keys use PO|plant|(line)|product; PO never a key'),
 ('Hourly feed', 'PO/product assignment changes almost every hour; no contiguous runs', 'Runs flagged SPARSE_NON_CONTIGUOUS / SINGLE_SLOT; not repaired'),
 ('Cost vs hourly', 'All 5,000 cost rows match an hourly slot on ts/plant/line/PO/product/qty (1:1) but relationship is unvalidated', 'CANDIDATE_ONLY'),
 ('BOM', '3 products x 16 identical components, REV-C only, quantities theoretical', 'Carried forward; flagged UNCONFIRMED on every D6 row'),
 ('Quality', 'No run/serial-to-run relationship; fail events != rejected units', 'Not used to build D5-D7; classified CANDIDATE_ONLY / UNMATCHED in report'),
 ('Shift C production date', 'Aug 1 00:00-05:00 slots carry shift_production_date 2026-07-31', 'Kept as source (production_date_first can be 2026-07-31)'),
 ('Hourly dq', '1,956 hourly rows SUSPICIOUS (rework>reject, downtime reason mismatch)', 'Carried in link.source_dq_status and run.source_suspicious_slot_count; not corrected'),
], columns=['area', 'observation', 'handling']), widths={'observation': 100, 'handling': 90})
sheet('Data_Dictionary', DDF, widths={'business_meaning': 110})
sheet('Key_Spec', KS, widths={'references_table': 70, 'column(s)': 70})
wb.save(f'{OUT}/cross_dataset_reconciliation_audit_v1.xlsx')
json.dump({'span': span, 'cx': cx.to_dict('records'), 'dist': DIST.to_dict('records'), 'an': an.to_dict('records')}, open('/home/claude/extra.json', 'w'), default=str, indent=1)
print('ok', span); print(an.to_string()); print(cx.to_string())
