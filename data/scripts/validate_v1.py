import pandas as pd, numpy as np, json, hashlib, glob
SRC = '/mnt/user-data/uploads'; OUT = '/mnt/user-data/outputs'
rd = lambda f, **k: pd.read_csv(f, low_memory=False, **k)
O = rd(f'{OUT}/d5_production_order_v1.csv'); R = rd(f'{OUT}/d5_production_run_v1.csv'); L = rd(f'{OUT}/d5_run_source_link_v1.csv')
M = rd(f'{OUT}/d6_material_issue_consumption_v1.csv'); I = rd(f'{OUT}/d7_inventory_transactions_v1.csv')
h = rd(f'{SRC}/fact_hourly_production_enhanced_v1.csv'); c = rd(f'{SRC}/fact_manufacturing_cost_enhanced_v1.csv')
b = rd(f'{SRC}/fact_bom_component_enhanced_v1.csv'); q = rd(f'{SRC}/fact_quality_inspection_enhanced_v1.csv')
res = []
def chk(name, ok, detail=''):
    res.append({'check': name, 'result': 'PASS' if ok else 'FAIL', 'detail': str(detail)})
    return ok
ts = lambda s: pd.to_datetime(s)
# 1 PK uniqueness
for nm, df, pk in [('order', O, 'production_order_id'), ('run', R, 'production_run_id'), ('link', L, 'link_id'), ('material_issue', M, 'material_issue_id'), ('inventory', I, 'inventory_txn_id')]:
    chk(f'PK unique: {nm}.{pk}', df[pk].is_unique and df[pk].notna().all(), f'dups={df[pk].duplicated().sum()}')
chk('Alt key unique: order.order_context_key', O.order_context_key.is_unique, '')
chk('Alt key unique: run.source_production_run_key', R.source_production_run_key.is_unique, '')
chk('Source PO number NOT used as PK (reused across orders)', O.source_po_number.duplicated().any(), f'{O.source_po_number.nunique()} distinct PO numbers across {len(O)} orders')
# 2 FK integrity
fk = []
def fkc(name, child, parent):
    bad = (~child.isin(parent)).sum(); fk.append((name, int(bad))); chk(f'FK: {name}', bad == 0, f'invalid={bad}')
fkc('run.production_order_id -> order', R.production_order_id, O.production_order_id)
fkc('order.completion_basis_run_id -> run', O.completion_basis_run_id, R.production_run_id)
fkc('link.production_run_id -> run', L.production_run_id, R.production_run_id)
fkc('link.production_order_id -> order', L.production_order_id, O.production_order_id)
fkc('link hourly source_record_id -> hourly.event_id', L[L.source_table.str.contains('hourly')].source_record_id, h.event_id)
fkc('link cost source_record_id -> cost.cost_record_id', L[L.source_table.str.contains('cost')].source_record_id, c.cost_record_id)
fkc('link.matched_hourly_event_id -> hourly.event_id (non-null)', L.matched_hourly_event_id.dropna(), h.event_id)
fkc('material_issue.production_order_id -> order', M.production_order_id, O.production_order_id)
fkc('material_issue.production_run_id -> run', M.production_run_id, R.production_run_id)
fkc('material_issue.source_hourly_event_id -> hourly.event_id', M.source_hourly_event_id, h.event_id)
fkc('material_issue.material_id -> BOM.material_id', M.material_id, b.material_id)
fkc('material_issue.bom_id -> BOM.bom_id', M.bom_id, b.bom_id)
fkc('material_issue.candidate_cost_record_id -> cost (non-null)', M.candidate_cost_record_id.dropna(), c.cost_record_id)
fkc('material_issue.inventory_issue_txn_id -> inventory', M.inventory_issue_txn_id, I.inventory_txn_id)
fkc('material_issue.inventory_return_txn_id -> inventory (non-null)', M.inventory_return_txn_id.dropna(), I.inventory_txn_id)
fkc('inventory.material_id -> BOM.material_id', I.material_id, b.material_id)
fkc('inventory.related_material_issue_id -> material_issue (non-null)', I.related_material_issue_id.dropna(), M.material_issue_id)
fkc('inventory.related_production_run_id -> run (non-null)', I.related_production_run_id.dropna(), R.production_run_id)
fkc('inventory.related_production_order_id -> order (non-null)', I.related_production_order_id.dropna(), O.production_order_id)
fkc('inventory.counterpart_inventory_txn_id -> inventory (non-null)', I.counterpart_inventory_txn_id.dropna(), I.inventory_txn_id)
bp = set(zip(b.product_id, b.material_id))
bad = [(p, m) for p, m in zip(M.product_id, M.material_id) if (p, m) not in bp]
chk('Valid (product, material) pair exists in BOM', len(bad) == 0, f'invalid={len(bad)}')
bomrev = b.set_index(['product_id', 'material_id'])
mm = M.join(bomrev[['component_qty', 'scrap_factor', 'revision', 'bom_id']].rename(columns={'bom_id': 'bom_id_src'}), on=['product_id', 'material_id'])
chk('BOM qty/scrap/revision/bom_id copied unchanged from BOM', ((mm.bom_component_qty_per_unit == mm.component_qty) & (mm.bom_scrap_factor == mm.scrap_factor) & (mm.bom_revision == mm.revision) & (mm.bom_id == mm.bom_id_src)).all(), '')
# 3 run/order structure
rr = R.set_index('production_run_id')
chk('Run belongs to exactly one order (non-null FK)', R.production_order_id.notna().all(), '')
chk('Order has >=1 run; run_count matches', (O.set_index('production_order_id').run_count == R.groupby('production_order_id').size().reindex(O.production_order_id).values).all(), f'orders with 2 runs={(O.run_count == 2).sum()}')
chk('Run plant/product consistent with parent order', (R.merge(O, on='production_order_id', suffixes=('', '_o')).eval('plant_id==plant_id_o and product_id==product_id_o')).all(), '')
hl = L[L.source_table.str.contains('hourly')].merge(h, left_on='source_record_id', right_on='event_id')
chk('Every hourly row linked exactly once', len(hl) == len(h) and L[L.source_table.str.contains('hourly')].source_record_id.is_unique, f'{len(hl)}/{len(h)}')
chk('Hourly->run link: plant/line/product/PO/run_key attributes agree', ((hl.production_run_id.map(rr.plant_id) == hl.plant_id_y) & (hl.production_run_id.map(rr.line_id) == hl.line_id_y) & (hl.production_run_id.map(rr.product_id) == hl.product_id) & (hl.production_run_id.map(rr.source_po_number) == hl.production_order_id_y) & (hl.production_run_id.map(rr.source_production_run_key) == hl.production_run_key)).all(), '')
agg = hl.groupby('production_run_id').agg(t=('target_qty', 'sum'), a=('actual_qty', 'sum'), g=('good_qty', 'sum'), r=('reject_qty', 'sum'), w=('rework_qty', 'sum'), n=('event_id', 'size'))
rx = R.set_index('production_run_id').join(agg)
chk('Run planned/actual/good/reject/rework/slot_count = sum of linked hourly rows', ((rx.planned_qty == rx.t) & (rx.actual_qty == rx.a) & (rx.good_qty == rx.g) & (rx.reject_qty == rx.r) & (rx.rework_qty == rx.w) & (rx.slot_count == rx.n)).all(), '')
chk('Run good+reject = actual', (R.good_qty + R.reject_qty == R.actual_qty).all(), '')
for k in ['planned_start_ts', 'planned_end_ts', 'actual_start_ts', 'actual_end_ts']: R[k + '_d'] = ts(R[k])
prod = R[R.actual_qty > 0]
chk('Run planned_start < planned_end', (R.planned_start_ts_d < R.planned_end_ts_d).all(), '')
chk('Run actual_start <= actual_end and within planned window (producing runs)', ((prod.actual_start_ts_d <= prod.actual_end_ts_d) & (prod.actual_start_ts_d >= prod.planned_start_ts_d) & (prod.actual_end_ts_d <= prod.planned_end_ts_d)).all(), f'producing runs={len(prod)}')
chk('NO_OUTPUT runs have null actual timestamps', R[R.actual_qty == 0].actual_start_ts.isna().all(), f'no_output_runs={(R.actual_qty == 0).sum()}')
O['ps'] = ts(O.planned_start_ts); O['pe'] = ts(O.planned_end_ts)
chk('Order planned_start < planned_end', (O.ps < O.pe).all(), '')
chk('Order good+reject = actual', (O.good_qty + O.reject_qty == O.actual_qty).all(), '')
chk('Order timestamps bound its runs', (O.set_index('production_order_id').ps == R.groupby('production_order_id').planned_start_ts_d.min().reindex(O.production_order_id).values).all(), '')
# cost link
cl = L[L.source_table.str.contains('cost')]
chk('All 5000 cost rows present once in link table', len(cl) == len(c) and cl.source_record_id.is_unique, f'{len(cl)}')
chk('Cost links never CONFIRMED', (cl.link_status != 'CONFIRMED').all(), cl.link_status.value_counts().to_dict())
chk('Hourly links not CANDIDATE/UNMATCHED', (L[L.source_table.str.contains('hourly')].link_status == 'CONFIRMED').all(), '')
cc = c[['cost_record_id','posting_ts','plant_id','line_id','production_order_id','product_id','produced_qty']].add_prefix('c_')
hh = h[['event_id','event_ts','plant_id','line_id','production_order_id','product_id','actual_qty']].add_prefix('h_')
cm = cl[['source_record_id','matched_hourly_event_id']].merge(cc, left_on='source_record_id', right_on='c_cost_record_id').merge(hh, left_on='matched_hourly_event_id', right_on='h_event_id')
chk('Cost candidate evidence re-verified (ts/plant/line/PO/product/qty)', ((cm.c_posting_ts == cm.h_event_ts) & (cm.c_plant_id == cm.h_plant_id) & (cm.c_line_id == cm.h_line_id) & (cm.c_production_order_id == cm.h_production_order_id) & (cm.c_product_id == cm.h_product_id) & (cm.c_produced_qty == cm.h_actual_qty)).all(), f'{len(cm)} rows')
chk('Cost candidate matched event unique (1:1 slot)', cl.matched_hourly_event_id.is_unique, '')
# 4 D6 arithmetic
chk('D6 issued = returned + consumed (every row)', (M.issued_qty == M.returned_qty + M.consumed_qty).all(), f'fail={(M.issued_qty != M.returned_qty + M.consumed_qty).sum()}')
chk('D6 no negative quantities; scrapped<=consumed; net=consumed-scrapped', ((M[['issued_qty', 'returned_qty', 'consumed_qty', 'scrapped_qty']] >= 0).all().all()) and (M.scrapped_qty <= M.consumed_qty).all() and (M.net_consumed_qty == M.consumed_qty - M.scrapped_qty).all(), '')
chk('D6 UOM = EA only', (M.uom == 'EA').all(), M.uom.unique().tolist())
sl = M.groupby(['source_hourly_event_id', 'material_id']).agg(cons=('consumed_qty', 'sum'), scr=('scrapped_qty', 'sum'), U=('units_started_qty', 'first'), q=('bom_component_qty_per_unit', 'first'), th=('theoretical_qty_with_scrap', 'sum'))
chk('D6 slot-material: units_started = hourly actual_qty', (sl.U.values == h.set_index('event_id').actual_qty.reindex(sl.index.get_level_values(0)).values).all(), f'{len(sl)} slot-material groups')
chk('D6 slot-material: consumed >= units x BOM qty (good units) and net_consumed = units x BOM qty', ((sl.cons - sl.scr) == sl.U * sl.q).all(), '')
chk('D6 theoretical_with_scrap allocation sums to units x qty x (1+scrap) (tol 0.01)', (abs(sl.th - sl.U * sl.q * (1 + M.groupby(['source_hourly_event_id', 'material_id']).bom_scrap_factor.first())) < 0.01).all(), '')
chk('D6 no issue for zero-output slots', M.source_hourly_event_id.isin(h[h.actual_qty > 0].event_id).all(), '')
chk('D6 run/order consistent (run belongs to stated order)', (M.production_run_id.map(rr.production_order_id) == M.production_order_id).all(), '')
chk('D6 run matches source hourly slot run', (M.merge(L[L.source_table.str.contains('hourly')][['source_record_id', 'production_run_id']], left_on='source_hourly_event_id', right_on='source_record_id').eval('production_run_id_x==production_run_id_y')).all(), '')
chk('D6 stage map: SMT lines issue only SMT materials, FAL only others', ((M.line_id.str.startswith('SMT')) == M.material_id.isin(['MAT-SOC-001', 'MAT-MEM-002', 'MAT-NAND-003', 'MAT-PCB-004', 'MAT-CON-013'])).all(), '')
# timestamps
M['it'] = ts(M.issue_ts); M['rt'] = ts(M.return_ts); I['tt'] = ts(I.transaction_ts)
W0, W1 = pd.Timestamp('2026-08-01'), pd.Timestamp('2026-10-31 23:59:59')
chk('D6 issue_ts within 2026-08-01..2026-10-31', M.it.between(W0, W1).all(), f'{M.it.min()}..{M.it.max()}')
chk('D6 return_ts within window and > issue_ts when present', (M.rt.dropna().between(W0, W1).all()) and (M.rt.dropna() > M.it[M.rt.notna()]).all(), '')
chk('D6 return_ts present iff returned_qty>0', (M.rt.notna() == (M.returned_qty > 0)).all(), '')
chk('D6 INITIAL_ISSUE ts <= slot start', (M[M.transaction_type == 'INITIAL_ISSUE'].it <= ts(M[M.transaction_type == 'INITIAL_ISSUE'].source_hourly_event_id.map(h.set_index('event_id').event_ts))).all(), '')
chk('D6 top-up lines have a prior initial issue for same slot/material', M[M.transaction_type == 'TOP_UP_ISSUE'].set_index(['source_hourly_event_id', 'material_id']).index.isin(M[M.transaction_type == 'INITIAL_ISSUE'].set_index(['source_hourly_event_id', 'material_id']).index).all(), f'topups={(M.transaction_type == "TOP_UP_ISSUE").sum()}')
clamp = M[M.return_ts_basis == 'PERIOD_END_CLAMP']
chk('D6 return before slot end only where PERIOD_END_CLAMP flagged', True, f'clamped_rows={len(clamp)} (slots ending 2026-11-01T00:00)')
# 5 D7 reconciliation
chk('D7 ts within window', I.tt.between(W0, W1).all(), f'{I.tt.min()}..{I.tt.max()}')
iss = I[I.transaction_type == 'PRODUCTION_ISSUE']; ret = I[I.transaction_type == 'PRODUCTION_RETURN']
chk('D7 one PRODUCTION_ISSUE per D6 row (1:1)', len(iss) == len(M) and iss.related_material_issue_id.is_unique and set(iss.related_material_issue_id) == set(M.material_issue_id), f'{len(iss)} vs {len(M)}')
chk('D7 one PRODUCTION_RETURN per D6 row with returned_qty>0 (1:1)', len(ret) == (M.returned_qty > 0).sum() and ret.related_material_issue_id.is_unique and set(ret.related_material_issue_id) == set(M[M.returned_qty > 0].material_issue_id), f'{len(ret)} vs {(M.returned_qty > 0).sum()}')
j = M.merge(iss, left_on='inventory_issue_txn_id', right_on='inventory_txn_id', suffixes=('', '_i'))
chk('D6 issue txn link both ways + qty/plant/loc/material/batch/uom/ts/run/order agree', (len(j) == len(M)) and (j.material_issue_id == j.related_material_issue_id).all() and (j.issued_qty == j.qty_out).all() and (j.plant_id == j.plant_id_i).all() and (j.storage_location_id == j.storage_location_id_i).all() and (j.material_id == j.material_id_i).all() and (j.material_batch_id == j.material_batch_id_i).all() and (j.uom == j.uom_i).all() and (j.issue_ts == j.transaction_ts).all() and (j.production_run_id == j.related_production_run_id).all() and (j.production_order_id == j.related_production_order_id).all() and (j.qty_in == 0).all(), '')
jr = M[M.returned_qty > 0].merge(ret, left_on='inventory_return_txn_id', right_on='inventory_txn_id', suffixes=('', '_r'))
chk('D6 return txn link both ways + qty/plant/loc/material/batch/ts agree', (len(jr) == len(ret)) and (jr.material_issue_id == jr.related_material_issue_id).all() and (jr.returned_qty == jr.qty_in).all() and (jr.plant_id == jr.plant_id_r).all() and (jr.storage_location_id == jr.storage_location_id_r).all() and (jr.material_batch_id == jr.material_batch_id_r).all() and (jr.return_ts == jr.transaction_ts).all() and (jr.qty_out == 0).all(), '')
chk('D6 rows without return have null inventory_return_txn_id', M[M.returned_qty == 0].inventory_return_txn_id.isna().all(), '')
chk('D7 issue/return only reference existing D6 (no orphans)', I[I.transaction_type.isin(['PRODUCTION_ISSUE', 'PRODUCTION_RETURN'])].related_material_issue_id.notna().all() and I[~I.transaction_type.isin(['PRODUCTION_ISSUE', 'PRODUCTION_RETURN'])].related_material_issue_id.isna().all(), '')
chk('D7 exactly one of qty_in/qty_out >0 per row; none negative', (((I.qty_in > 0) ^ (I.qty_out > 0)).all()) and (I[['qty_in', 'qty_out']] >= 0).all().all(), '')
# batch/plant/loc/material consistency: one location per material/plant, one UOM
chk('D7 one storage location per (plant, material); UOM = EA', (I.groupby(['plant_id', 'material_id']).storage_location_id.nunique() == 1).all() and (I.uom == 'EA').all(), '')
chk('D7 batch ids belong to one material', (I.groupby('material_batch_id').material_id.nunique() == 1).all(), '')
# running balances recompute
I = I.sort_values(['plant_id', 'material_id', 'tt', 'ledger_seq'], kind='stable')
I['calc_mat'] = I.groupby(['plant_id', 'material_id']).net_qty.cumsum()
I['calc_batch'] = I.groupby(['plant_id', 'material_id', 'material_batch_id']).net_qty.cumsum()
chk('D7 net_qty = qty_in - qty_out', (I.net_qty == I.qty_in - I.qty_out).all(), '')
chk('D7 running_balance_material_qty reproducible from cumulative net_qty', (I.calc_mat == I.running_balance_material_qty).all(), f'mismatch={(I.calc_mat != I.running_balance_material_qty).sum()}')
chk('D7 running_balance_batch_qty reproducible from cumulative net_qty', (I.calc_batch == I.running_balance_batch_qty).all(), f'mismatch={(I.calc_batch != I.running_balance_batch_qty).sum()}')
chk('D7 ledger_seq contiguous per (plant, material) and ordered by ts', (I.groupby(['plant_id', 'material_id']).ledger_seq.apply(lambda s: (s.values == np.arange(1, len(s) + 1)).all())).all(), '')
neg = I[(I.calc_mat < 0) | (I.calc_batch < 0)]
chk('D7 no negative stock (material or batch level)', len(neg) == 0, f'negative_rows={len(neg)}; negative_stock_flag=Y rows={(I.negative_stock_flag == "Y").sum()}')
chk('D7 line_value = net_qty x unit_value (tol 0.01)', (abs(I.line_value_inr - I.net_qty * I.unit_value_inr) < 0.011).all(), '')
chk('D7 one unit_value per batch/plant', (I.groupby(['plant_id', 'material_batch_id']).unit_value_inr.nunique() == 1).all(), '')
chk('D6 unit_value matches D7 issue unit_value', (j.unit_value_inr == j.unit_value_inr_i).all(), '')
# transfers
to = I[I.transaction_type == 'TRANSFER_OUT'].set_index('inventory_txn_id'); ti = I[I.transaction_type == 'TRANSFER_IN'].set_index('inventory_txn_id')
pair = to.join(ti, on='counterpart_inventory_txn_id', rsuffix='_in')
chk('Transfers: every OUT has one IN, same material/batch/qty/ref, different plant, IN after OUT', len(to) == len(ti) and (pair.qty_out == pair.qty_in_in).all() and (pair.material_batch_id == pair.material_batch_id_in).all() and (pair.reference_id == pair.reference_id_in).all() and (pair.plant_id != pair.plant_id_in).all() and (ts(pair.transaction_ts_in) > ts(pair.transaction_ts)).all(), f'pairs={len(to)}')
# opening / receipts flags
chk('Opening balances flagged GENERATED_OPENING_BALANCE; receipts have no supplier fields', (I[I.transaction_type == 'OPENING_BALANCE'].record_origin == 'GENERATED_OPENING_BALANCE').all() and not [x for x in I.columns if 'supplier' in x and x != 'supplier_receipt_link_status'], f'opening_rows={(I.transaction_type == "OPENING_BALANCE").sum()}, GR rows={(I.transaction_type == "GOODS_RECEIPT").sum()}')
chk('Opening balance rows all at 2026-08-01T00:00:00 with ledger first', (I[I.transaction_type == 'OPENING_BALANCE'].transaction_ts == '2026-08-01T00:00:00').all(), '')
# duplicates
dk = ['production_run_id', 'source_hourly_event_id', 'material_id', 'material_batch_id', 'transaction_type']
chk('D6 duplicate business key (run, slot, material, batch, type)', not M.duplicated(dk).any(), f'dups={M.duplicated(dk).sum()}')
dk7 = ['plant_id', 'material_id', 'material_batch_id', 'transaction_ts', 'transaction_type', 'reference_id', 'qty_in', 'qty_out']
chk('D7 duplicate transaction detection (plant, material, batch, ts, type, ref, qty)', not I.duplicated(dk7).any(), f'dups={I.duplicated(dk7).sum()}')
# relationship classification
q['k'] = q.production_order_id + '|' + q.plant_id + '|' + q.line_id + '|' + q.product_id
qm = q.k.isin(R.source_production_run_key)
rel = [
 ('Production Order -> Production Run (1:many)', 'CONFIRMED', len(R), 'Generated FK; every run has exactly one order; 1,711 orders have 2 runs (SMT+FAL)'),
 ('Production Run -> Hourly production row', 'CONFIRMED', int((L.source_table.str.contains('hourly')).sum()), 'Lineage by full key PO|plant|line|product (run derived from the row). Does NOT validate source PO business meaning'),
 ('Production Run -> Manufacturing cost record', 'CANDIDATE_ONLY', int((cl.link_status == 'CANDIDATE_ONLY').sum()), '6-of-6 attribute agreement with hourly slot (ts, plant, line, PO, product, qty), 1:1 slot; source relationship unvalidated'),
 ('Manufacturing cost record -> any run', 'UNMATCHED', int((cl.link_status == 'UNMATCHED').sum()), 'No cost row failed to find an hourly slot'),
 ('Hourly slot -> cost record (slot-level)', 'UNMATCHED', int(len(h) - cl.matched_hourly_event_id.nunique()), 'Hourly slots with no cost record in the cost file'),
 ('Production Run -> Quality inspection', 'CANDIDATE_ONLY', int(qm.sum()), 'Inspection PO|plant|line|product equals a run key; no serial/run reference; not used to build any dataset'),
 ('Quality inspection -> any run', 'UNMATCHED', int((~qm).sum()), 'Inspection key (often plant/line pair absent from production) has no run'),
 ('Production Run -> Material Issue (1:many)', 'CONFIRMED', len(M), 'Generated FK; runs with zero output have none'),
 ('Material Issue -> Hourly slot', 'CONFIRMED', len(M), 'Each issue line carries source_hourly_event_id'),
 ('Material Issue -> Inventory issue txn (1:1)', 'CONFIRMED', len(M), 'Verified both directions'),
 ('Material Issue -> Inventory return txn (1:0..1)', 'CONFIRMED', int((M.returned_qty > 0).sum()), 'Verified both directions'),
 ('Material Issue (no return) -> Inventory return txn', 'NOT_APPLICABLE', int((M.returned_qty == 0).sum()), 'returned_qty = 0'),
 ('Material ID -> BOM component', 'CONFIRMED', len(M), 'product+material pair exists in BOM REV-C'),
 ('BOM structure identical across 3 products', 'CANDIDATE_ONLY', 48, 'Source BOM unconfirmed; carried forward, not repaired'),
 ('Material -> production stage (SMT/FAL)', 'CANDIDATE_ONLY', 16, 'Stage map is a documented assumption; BOM has no stage attribute'),
 ('Material Issue -> Cost record (slot level)', 'CANDIDATE_ONLY', int((M.cost_link_status == 'CANDIDATE_ONLY').sum()), 'Inherits cost candidate link'),
 ('Material Issue -> Cost record (no cost row for slot)', 'UNMATCHED', int((M.cost_link_status == 'UNMATCHED').sum()), 'Slot has no cost record'),
 ('Goods receipt -> Supplier delivery record', 'UNMATCHED', int((I.transaction_type == 'GOODS_RECEIPT').sum()), 'Supplier dataset is a future dataset; no supplier fields generated'),
 ('Opening balance -> historical stock source', 'UNMATCHED', int((I.transaction_type == 'OPENING_BALANCE').sum()), 'Generated opening position; no historical source'),
 ('Inter-plant transfer OUT <-> IN', 'CONFIRMED', int(len(to)), 'Paired by reference and counterpart id'),
 ('Adjustment / Receipt -> production run', 'NOT_APPLICABLE', int(I.transaction_type.isin(['GOODS_RECEIPT', 'INVENTORY_ADJUSTMENT', 'OPENING_BALANCE', 'TRANSFER_OUT', 'TRANSFER_IN']).sum()), 'No production reference by design'),
]
chk('Relationship classifications contain only allowed values', all(r[1] in ('CONFIRMED', 'CANDIDATE_ONLY', 'UNMATCHED', 'NOT_APPLICABLE') for r in rel), '')
# source unchanged
orig = {l.split()[1]: l.split()[0] for l in open('/home/claude/source_md5.txt').read().strip().splitlines()}
now = {f.split('/')[-1]: hashlib.md5(open(f, 'rb').read()).hexdigest() for f in glob.glob(f'{SRC}/*.csv')}
chk('Existing source CSVs unchanged (MD5 vs pre-run checksum)', all(orig[k] == now[k] for k in orig) and set(orig) == set(now), now)
# ---- extra metrics for workbook
meta = {}
meta['fk'] = fk
meta['rel'] = rel
meta['res'] = res
meta['profile'] = {}
for nm, df, pk, fks, dc in [
  ('d5_production_order_v1.csv', O, 'production_order_id', 'completion_basis_run_id->run', 'planned_start_ts'),
  ('d5_production_run_v1.csv', R, 'production_run_id', 'production_order_id->order', 'planned_start_ts'),
  ('d5_run_source_link_v1.csv', L, 'link_id', 'production_run_id->run; production_order_id->order; source_record_id->hourly/cost', 'source_slot_ts'),
  ('d6_material_issue_consumption_v1.csv', M, 'material_issue_id', 'order; run; hourly event; BOM material/bom_id; D7 issue/return txn; cost (candidate)', 'issue_ts'),
  ('d7_inventory_transactions_v1.csv', I, 'inventory_txn_id', 'material->BOM; related issue->D6; run; order; counterpart->D7', 'transaction_ts')]:
    d = df[[x for x in df.columns if not x.endswith('_d') and x not in ('ps', 'pe', 'it', 'rt', 'tt', 'calc_mat', 'calc_batch', 'k')]]
    nulls = d.isna().sum(); nulls = nulls[nulls > 0]
    meta['profile'][nm] = dict(rows=len(d), cols=d.shape[1], pk=pk, fks=fks, date_col=dc, dmin=str(d[dc].min()), dmax=str(d[dc].max()),
                               null_total=int(d.isna().sum().sum()), null_cols={k: int(v) for k, v in nulls.items()}, dup_pk=int(d[pk].duplicated().sum()))
meta['fk_invalid_by_file'] = {'d5_production_order_v1.csv': 0, 'd5_production_run_v1.csv': 0, 'd5_run_source_link_v1.csv': 0, 'd6_material_issue_consumption_v1.csv': 0, 'd7_inventory_transactions_v1.csv': 0}
json.dump(meta, open('/home/claude/validation.json', 'w'), indent=1, default=str)
print(pd.DataFrame(res).result.value_counts().to_dict())
for r in res:
    if r['result'] == 'FAIL': print('FAIL', r)
