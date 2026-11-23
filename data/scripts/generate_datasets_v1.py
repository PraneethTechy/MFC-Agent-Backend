"""Generate Dataset 5 (order/run traceability), Dataset 6 (material issue/consumption),
Dataset 7 (inventory transactions) as versioned NEW files. Source CSVs are read-only."""
import pandas as pd, numpy as np, math, heapq, json, os
SRC = '/mnt/user-data/uploads'; OUT = '/mnt/user-data/outputs'
os.makedirs(OUT, exist_ok=True)
SEED = 20261120
GEN = 'GEN-V1-20261120'
P_END = pd.Timestamp('2026-10-31 23:59:59'); P_START = pd.Timestamp('2026-08-01 00:00:00')
F = '%Y-%m-%dT%H:%M:%S'
fmt = lambda s: s.dt.strftime(F)

h = pd.read_csv(f'{SRC}/fact_hourly_production_enhanced_v1.csv')
c = pd.read_csv(f'{SRC}/fact_manufacturing_cost_enhanced_v1.csv')
b = pd.read_csv(f'{SRC}/fact_bom_component_enhanced_v1.csv')
h['ts'] = pd.to_datetime(h.event_ts)
h = h.sort_values(['ts', 'plant_id', 'line_id'], kind='stable').reset_index(drop=True)
PC = {'IN-TN-01': 'TN', 'IN-KA-01': 'KA'}
h['producing'] = h.actual_qty > 0
h['act_end'] = h.ts + pd.to_timedelta(np.where(h.run_minutes > 0, h.run_minutes, 60), unit='m')
g = h.groupby('production_run_key', sort=False)
h['idle_gap_h'] = g.ts.diff().dt.total_seconds() / 3600 - 1

# ------------------------------------------------------------------ D5 runs
R = g.agg(source_po_number=('production_order_id', 'first'), plant_id=('plant_id', 'first'),
          line_id=('line_id', 'first'), line_type=('line_type', 'first'), product_id=('product_id', 'first'),
          slot_count=('event_id', 'size'), producing_slot_count=('producing', 'sum'),
          planned_qty=('target_qty', 'sum'), actual_qty=('actual_qty', 'sum'), good_qty=('good_qty', 'sum'),
          reject_qty=('reject_qty', 'sum'), rework_qty=('rework_qty', 'sum'),
          downtime_min_total=('downtime_min', 'sum'), first_ts=('ts', 'min'), last_ts=('ts', 'max'),
          production_date_first=('shift_production_date', 'min'), production_date_last=('shift_production_date', 'max'),
          shift_id_first=('shift_id', 'first'), first_source_event_id=('event_id', 'first'),
          last_source_event_id=('event_id', 'last'), max_idle_gap_hours=('idle_gap_h', 'max'),
          source_suspicious_slot_count=('data_quality', lambda s: int((s == 'SUSPICIOUS').sum()))).reset_index()
R['shift_ids_covered'] = R.production_run_key.map(g.shift_id.agg(lambda s: '|'.join(sorted(set(s)))))
R['shift_count'] = R.shift_ids_covered.str.count(r'\|') + 1
pr = h[h.producing].groupby('production_run_key').agg(a0=('ts', 'min'), a1=('act_end', 'max'))
R = R.merge(pr, left_on='production_run_key', right_index=True, how='left')
R['zero_output_slot_count'] = R.slot_count - R.producing_slot_count
R['max_idle_gap_hours'] = R.max_idle_gap_hours.fillna(0).astype(int)
R['planned_start_ts'] = R.first_ts; R['planned_end_ts'] = R.last_ts + pd.Timedelta(hours=1)
R['actual_start_ts'] = R.a0; R['actual_end_ts'] = R.a1
R['calendar_span_hours'] = ((R.planned_end_ts - R.planned_start_ts).dt.total_seconds() / 3600).astype(int)
R['execution_pattern'] = np.where(R.slot_count == 1, 'SINGLE_SLOT', np.where(R.max_idle_gap_hours == 0, 'CONTIGUOUS_SLOTS', 'SPARSE_NON_CONTIGUOUS'))
R['attainment_pct'] = np.where(R.planned_qty > 0, (R.actual_qty / R.planned_qty * 100).round(2), np.nan)
R['run_status'] = np.where(R.actual_qty == 0, 'NO_OUTPUT', np.where(R.actual_qty >= 0.95 * R.planned_qty, 'COMPLETED', 'SHORT_CLOSED'))
R = R.sort_values(['first_ts', 'plant_id', 'line_id']).reset_index(drop=True)
R['production_run_id'] = ['PRUN-%05d' % (i + 1) for i in range(len(R))]
R['schedule_ref'] = ('SCH-' + R.plant_id.map(PC) + '-' + R.line_id + '-' + R.production_date_first.str.replace('-', '') + '-' + R.shift_id_first)
R['mes_execution_ref'] = 'MES:' + R.first_source_event_id + '..' + R.last_source_event_id
R['order_context_key'] = R.source_po_number + '|' + R.plant_id + '|' + R.product_id

# ------------------------------------------------------------------ D5 orders
bomp = b.groupby('product_id').agg(bom_id=('bom_id', 'first'), bom_revision=('revision', 'first'))
O = R.groupby('order_context_key', sort=False).agg(
    source_po_number=('source_po_number', 'first'), plant_id=('plant_id', 'first'), product_id=('product_id', 'first'),
    run_count=('production_run_id', 'size'), planned_qty=('planned_qty', 'max'),
    planned_start_ts=('planned_start_ts', 'min'), planned_end_ts=('planned_end_ts', 'max'),
    actual_start_ts=('actual_start_ts', 'min'), actual_end_ts=('actual_end_ts', 'max'),
    first_production_date=('production_date_first', 'min'), last_production_date=('production_date_last', 'max'),
    line_types=('line_type', lambda s: '|'.join(sorted(set(s)))), schedule_ref=('schedule_ref', 'first')).reset_index()
O['routing_completeness'] = O.line_types.map({'FAL|SMT': 'FULL_SMT_FAL', 'SMT': 'SMT_ONLY', 'FAL': 'FAL_ONLY'})
basis = R.assign(pri=(R.line_type == 'FAL').astype(int)).sort_values('pri').groupby('order_context_key').tail(1).set_index('order_context_key')
O['completion_basis_run_id'] = O.order_context_key.map(basis.production_run_id)
O['completion_basis'] = O.order_context_key.map(basis.line_type).map({'FAL': 'FAL_RUN', 'SMT': 'SMT_RUN_ONLY_NO_FAL_OBSERVED'})
for k in ['actual_qty', 'good_qty', 'reject_qty', 'rework_qty']:
    O[k] = O.order_context_key.map(basis[k])
bst = O.order_context_key.map(basis.run_status)
O['order_status'] = np.where(O.routing_completeness == 'FULL_SMT_FAL', bst, 'PARTIAL_ROUTING_OBSERVED')
O['calendar_span_days'] = (O.planned_end_ts - O.planned_start_ts).dt.days
O['bom_id'] = O.product_id.map(bomp.bom_id); O['bom_revision'] = O.product_id.map(bomp.bom_revision)
O['source_po_traceability_status'] = 'AMBIGUOUS_MULTI_CONTEXT'
fl = []
for sp, rc in zip(O.calendar_span_days, O.routing_completeness):
    f = []
    if sp > 14: f.append('SPARSE_MULTI_WEEK_SPAN')
    if rc != 'FULL_SMT_FAL': f.append('PARTIAL_ROUTING')
    fl.append('|'.join(f) if f else 'NONE')
O['order_integrity_flag'] = fl
O = O.sort_values(['planned_start_ts', 'plant_id', 'product_id']).reset_index(drop=True)
O['production_order_id'] = ['PORD-%s-%05d' % (PC[p], i + 1) for i, p in enumerate(O.plant_id)]
# per-plant sequence
O['production_order_id'] = O.groupby('plant_id').cumcount().add(1).astype(str).str.zfill(5).radd('PORD-' + O.plant_id.map(PC) + '-')
R['production_order_id'] = R.order_context_key.map(O.set_index('order_context_key').production_order_id)

# ------------------------------------------------------------------ D5 bridge (hourly + cost)
rk2run = R.set_index('production_run_key')[['production_run_id', 'production_order_id']].rename(columns={'production_run_id': 'run_id_', 'production_order_id': 'order_id_'})
hb = h[['event_id', 'event_ts', 'plant_id', 'line_id', 'production_order_id', 'production_run_key', 'data_quality']].join(rk2run, on='production_run_key')
HL = pd.DataFrame({'production_run_id': hb.run_id_, 'production_order_id': hb.order_id_,
    'source_table': 'fact_hourly_production_enhanced_v1', 'source_record_id': hb.event_id, 'matched_hourly_event_id': hb.event_id,
    'source_slot_ts': hb.event_ts, 'plant_id': hb.plant_id, 'line_id': hb.line_id, 'source_po_number': hb.production_order_id,
    'link_rule_id': 'R1_HOURLY_FULLKEY', 'link_status': 'CONFIRMED', 'evidence_strength': 'EXACT_FULL_KEY_DERIVATION',
    'match_slot_plant_line_po': 'Y', 'match_product': 'Y', 'match_qty': 'NA', 'source_dq_status': hb.data_quality,
    'business_validity_caveat': 'LINEAGE_ONLY: run is a generated construct from source key PO|plant|line|product; source PO number remains AMBIGUOUS_MULTI_CONTEXT and run window is sparse'})
HL = HL.sort_values('source_slot_ts', kind='stable')
cm = c.merge(h[['event_id', 'event_ts', 'plant_id', 'line_id', 'production_order_id', 'product_id', 'actual_qty', 'production_run_key']],
             left_on=['posting_ts', 'plant_id', 'line_id', 'production_order_id'],
             right_on=['event_ts', 'plant_id', 'line_id', 'production_order_id'], how='left', suffixes=('', '_h'))
cm = cm.join(rk2run, on='production_run_key')
CL = pd.DataFrame({'production_run_id': cm.run_id_, 'production_order_id': cm.order_id_, 'source_table': 'fact_manufacturing_cost_enhanced_v1',
    'source_record_id': cm.cost_record_id, 'matched_hourly_event_id': cm.event_id, 'source_slot_ts': cm.posting_ts,
    'plant_id': cm.plant_id, 'line_id': cm.line_id, 'source_po_number': cm.production_order_id,
    'link_rule_id': 'R2_COST_TO_HOURLY_SLOT', 'link_status': np.where(cm.event_id.notna(), 'CANDIDATE_ONLY', 'UNMATCHED'),
    'evidence_strength': np.where(cm.event_id.notna(), 'STRONG_6_OF_6', 'NONE'),
    'match_slot_plant_line_po': np.where(cm.event_id.notna(), 'Y', 'N'),
    'match_product': np.where(cm.product_id == cm.product_id_h, 'Y', 'N'),
    'match_qty': np.where(cm.produced_qty == cm.actual_qty, 'Y', 'N'), 'source_dq_status': cm.data_quality_v1,
    'business_validity_caveat': 'CANDIDATE_ONLY: source cost-to-hourly relationship is unvalidated (PO ambiguous across plants/lines/products); strong attribute agreement does not confirm a business link'})
BR = pd.concat([HL, CL], ignore_index=True)
BR['link_id'] = ['LNK-%07d' % (i + 1) for i in range(len(BR))]
BR['record_origin'] = 'GENERATED_SYNTHETIC'; BR['generation_version'] = GEN
BR = BR[['link_id', 'production_run_id', 'production_order_id', 'source_table', 'source_record_id', 'matched_hourly_event_id',
         'source_slot_ts', 'plant_id', 'line_id', 'source_po_number', 'link_rule_id', 'link_status', 'evidence_strength',
         'match_slot_plant_line_po', 'match_product', 'match_qty', 'source_dq_status', 'business_validity_caveat',
         'record_origin', 'generation_version']]
cost_by_event = CL[CL.matched_hourly_event_id.notna()].set_index('matched_hourly_event_id').source_record_id
R['candidate_cost_record_count'] = R.production_run_id.map(CL[CL.link_status == 'CANDIDATE_ONLY'].groupby('production_run_id').size()).fillna(0).astype(int)

# ------------------------------------------------------------------ D6/D7 simulation
mats = list(b.material_id.drop_duplicates())
BOMd = {(r.product_id, r.material_id): (int(r.component_qty), float(r.scrap_factor), r.bom_id, r.revision) for r in b.itertuples()}
SMT_MATS = {'MAT-SOC-001', 'MAT-MEM-002', 'MAT-NAND-003', 'MAT-PCB-004', 'MAT-CON-013'}
LOC = lambda m: 'RM-SMT' if m in SMT_MATS else 'RM-FAL'
WEIGHT = {'MAT-SOC-001': 22, 'MAT-MEM-002': 7, 'MAT-NAND-003': 8, 'MAT-PCB-004': 5, 'MAT-DSP-005': 15, 'MAT-BAT-006': 4,
          'MAT-CAM-007': 9, 'MAT-CAM-008': 4, 'MAT-HSG-009': 5, 'MAT-GLS-010': 3.5, 'MAT-SPK-011': 1.5, 'MAT-ANT-012': 1.5,
          'MAT-CON-013': 2, 'MAT-BOX-014': 1.5, 'MAT-CBL-015': 1, 'MAT-SCR-016': 0.5}
MULT = {'MAT-SOC-001': .8, 'MAT-MEM-002': .7, 'MAT-NAND-003': .7, 'MAT-PCB-004': 1.2, 'MAT-DSP-005': 1.5, 'MAT-BAT-006': 1.0,
        'MAT-CAM-007': 1.4, 'MAT-CAM-008': 1.3, 'MAT-HSG-009': 1.2, 'MAT-GLS-010': 1.8, 'MAT-SPK-011': .9, 'MAT-ANT-012': .9,
        'MAT-CON-013': 1.1, 'MAT-BOX-014': 1.0, 'MAT-CBL-015': .8, 'MAT-SCR-016': 1.6}
ANOM = {('MAT-CAM-007', 'IN-TN-01', 4): 4.0, ('MAT-GLS-010', 'IN-KA-01', 3): 3.5, ('MAT-BAT-006', 'IN-TN-01', 5): 3.0, ('MAT-SOC-001', 'IN-KA-01', 6): 3.0}
TARGET_UNIT_MAT_COST = float(c.material_cost_inr.sum() / c.produced_qty.sum())
wsum = sum(WEIGHT.values())
PRICE = {m: round(TARGET_UNIT_MAT_COST * WEIGHT[m] / wsum / (1 + BOMd[(b.product_id.iloc[0], m)][1]), 2) for m in mats}
ceil_to = lambda x, k: int(math.ceil(x / k) * k)

S = h[h.producing].copy().rename(columns={'production_order_id': 'source_po_number'})
S = S.join(rk2run, on='production_run_key').rename(columns={'run_id_':'production_run_id','order_id_':'production_order_id'})
S['cost_rec'] = S.event_id.map(cost_by_event)
S['rets'] = list(zip(S.index, S.ts))
slots = S.reset_index(drop=True)

def alloc(total, weights):
    w = np.array(weights, float)
    if total == 0 or w.sum() == 0: return [0] * len(w)
    raw = total * w / w.sum(); fl = np.floor(raw).astype(int); rem = int(total - fl.sum())
    for i in np.argsort(-(raw - fl))[:rem]: fl[i] += 1
    return fl.tolist()

d6_rows, d7_rows, anomaly_log, stats = [], [], [], {'expedited_gr': 0, 'transfers': 0, 'adjustments': 0, 'topups': 0, 'return_clamped': 0}
uidc = [0]
def uid(prefix): uidc[0] += 1; return f'{prefix}{uidc[0]}'

for mi, m in enumerate(mats):
    rng = np.random.default_rng([SEED, mi])
    stage = 'SMT' if m in SMT_MATS else 'FAL'
    sm = slots[slots.line_type == stage]
    plants = sorted(PC)
    qtyb = {p: 0 for p in plants}
    dem = {}
    for p in plants:
        x = sm[sm.plant_id == p]
        dem[p] = float((x.actual_qty * x.product_id.map(lambda pr: BOMd[(pr, m)][0])).sum()) / 92.0
    ROP = {p: 5 * dem[p] for p in plants}; LOT = {p: ceil_to(8 * dem[p], 100) for p in plants}
    st = {p: {'batches': {}, 'order': [], 'pending': 0, 'bseq': 0, 'ledger': 0} for p in plants}
    heap = []; seqc = [0]
    def push(ts, prio, kind, pay):
        seqc[0] += 1; heapq.heappush(heap, (ts, prio, seqc[0], kind, pay))
    def total(p): return sum(bt['qty'] for bt in st[p]['batches'].values())
    def new_batch(p, ts, opening=False, idx=None):
        s = st[p]; s['bseq'] += 1
        short = m.replace('MAT-', '').replace('-', '')
        bid = f"LOT-{short}-{'OPEN' if opening else ts.strftime('%y%m%d')}-{PC[p]}{s['bseq']:02d}"
        fac = float(rng.lognormal(0, 0.15)) * ANOM.get((m, p, s['bseq']), 1.0)
        if (m, p, s['bseq']) in ANOM: anomaly_log.append({'material_id': m, 'plant_id': p, 'batch_id': bid, 'waste_multiplier': ANOM[(m, p, s['bseq'])]})
        cost = round(PRICE[m] * float(rng.lognormal(0, 0.012)), 2)
        s['batches'][bid] = {'qty': 0, 'cost': cost, 'factor': fac, 'rec': ts}; s['order'].append(bid)
        return bid
    def post(p, ts, ttype, sub, refdoc, refid, bid, qin, qout, rel=None, origin='GENERATED_SYNTHETIC', extra=None):
        s = st[p]; bt = s['batches'][bid]
        bt['qty'] += qin - qout; assert bt['qty'] >= 0, (m, p, bid, ttype)
        s['ledger'] += 1; u = uid('I')
        d7_rows.append(dict(_uid=u, ledger_seq=s['ledger'], plant_id=p, storage_location_id=LOC(m), material_id=m, material_batch_id=bid,
            transaction_ts=ts, transaction_type=ttype, transaction_subtype=sub, reference_doc_type=refdoc, reference_id=refid,
            _rel=rel, qty_in=qin, qty_out=qout, unit_value_inr=bt['cost'], record_origin=origin,
            running_balance_batch_qty=bt['qty'], running_balance_material_qty=total(p), **(extra or {})))
        return u
    def alloc_fifo(p, need):
        out = []
        for bid in st[p]['order']:
            if need == 0: break
            q = st[p]['batches'][bid]['qty']
            if q > 0:
                t = min(q, need); out.append((bid, t)); need -= t
        assert need == 0
        return out
    def gr(p, ts, sub='STANDARD_GENERATED'):
        bid = new_batch(p, ts); q = LOT[p] if sub == 'STANDARD_GENERATED' else None
        return bid
    grn = [0]; sto = [0]; adj = [0]
    def do_receipt(p, ts, qty, sub):
        bid = new_batch(p, ts); grn[0] += 1
        post(p, ts, 'GOODS_RECEIPT', sub, 'GENERATED_RECEIPT', f'GR-GEN-{mi + 1:02d}-{grn[0]:04d}', bid, qty, 0)
    def reorder(p, ts):
        s = st[p]
        if s['pending'] > 0 or total(p) > ROP[p]: return
        o = [q for q in plants if q != p][0]
        qt = int(math.floor(0.35 * LOT[p] / 100) * 100)
        big = max(st[o]['batches'].items(), key=lambda kv: kv[1]['qty'])
        if ts < pd.Timestamp('2026-10-27') and rng.random() < 0.35 and total(o) - qt >= 1.0 * ROP[o] and big[1]['qty'] >= qt and qt > 0:
            sto[0] += 1; ref = f'STO-GEN-{mi + 1:02d}-{sto[0]:03d}'; bid = big[0]; bt = big[1]
            uo = post(o, ts, 'TRANSFER_OUT', 'INTER_PLANT', 'GENERATED_STO', ref, bid, 0, qt)
            arr = ts + pd.Timedelta(hours=int(rng.integers(24, 37)), minutes=int(rng.integers(0, 60)))
            s['pending'] += qt; push(arr, 1, 'TIN', dict(p=p, bid=bid, qty=qt, cost=bt['cost'], fac=bt['factor'], ref=ref, out_uid=uo))
            stats['transfers'] += 1
        else:
            arr = ts + pd.Timedelta(hours=int(rng.integers(36, 73)), minutes=int(rng.integers(0, 60)))
            s['pending'] += LOT[p]
            if arr <= P_END: push(arr, 1, 'GR', dict(p=p, qty=LOT[p]))
    # opening balances
    for p in plants:
        n1 = ceil_to((6 if p == 'IN-TN-01' else 10) * dem[p], 100); n2 = ceil_to((4 if p == 'IN-TN-01' else 6) * dem[p], 100)
        for q in (n1, n2):
            bid = new_batch(p, P_START, opening=True)
            post(p, P_START, 'OPENING_BALANCE', 'GENERATED_OPENING', 'GENERATED_OPENING_LOAD', f'OB-GEN-{PC[p]}-{m}', bid, q, 0, origin='GENERATED_OPENING_BALANCE')
    # schedule slot issues
    for i, r in sm.iterrows():
        lead = int(rng.integers(15, 51))
        its = max(P_START, r.ts - pd.Timedelta(minutes=lead))
        push(its, 5, 'ISSUE', dict(i=i))
    for p in plants:
        for mo in (8, 9, 10):
            push(pd.Timestamp(2026, mo, 15, 10, mi, 0), 3, 'ADJ', dict(p=p))
    while heap:
        ts, prio, _, kind, pay = heapq.heappop(heap)
        if kind == 'GR':
            p = pay['p']; st[p]['pending'] = max(0, st[p]['pending'] - pay['qty']); do_receipt(p, ts, pay['qty'], 'STANDARD_GENERATED')
        elif kind == 'TIN':
            p = pay['p']; s = st[p]; s['pending'] = max(0, s['pending'] - pay['qty'])
            if pay['bid'] not in s['batches']:
                s['batches'][pay['bid']] = {'qty': 0, 'cost': pay['cost'], 'factor': pay['fac'], 'rec': ts}; s['order'].append(pay['bid'])
            ui = post(p, ts, 'TRANSFER_IN', 'INTER_PLANT', 'GENERATED_STO', pay['ref'], pay['bid'], pay['qty'], 0, extra={'_cp': pay['out_uid']})
            for r_ in d7_rows:
                if r_['_uid'] == pay['out_uid']: r_['_cp'] = ui; break
        elif kind == 'ADJ':
            p = pay['p']; s = st[p]
            bid, bt = max(s['batches'].items(), key=lambda kv: kv[1]['qty'])
            delta = int(round(rng.normal(-0.001, 0.003) * bt['qty']))
            if delta == 0: continue
            adj[0] += 1; stats['adjustments'] += 1
            ref = f'CC-GEN-{mi + 1:02d}-{adj[0]:03d}'
            if delta < 0: post(p, ts, 'INVENTORY_ADJUSTMENT', 'ADJ_LOSS', 'GENERATED_CYCLE_COUNT', ref, bid, 0, min(-delta, bt['qty']))
            else: post(p, ts, 'INVENTORY_ADJUSTMENT', 'ADJ_GAIN', 'GENERATED_CYCLE_COUNT', ref, bid, delta, 0)
            reorder(p, ts)
        elif kind == 'RET':
            L = pay['line']; p = L['plant_id']
            ui = post(p, ts, 'PRODUCTION_RETURN', 'UNUSED_TO_STOCK', 'MATERIAL_ISSUE', L['_uid'], L['material_batch_id'], L['returned_qty'], 0, rel=L['_uid'])
            L['_ret_uid'] = ui
        elif kind in ('ISSUE', 'TOPUP'):
            if kind == 'ISSUE':
                r = slots.loc[pay['i']]; p = r.plant_id; U = int(r.actual_qty)
                qb, sf, bomid, rev = BOMd[(r.product_id, m)]
                I = ceil_to(r.target_qty * qb * (1 + sf), 10); need = I
            else:
                r = pay['r']; p = r.plant_id; U = int(r.actual_qty); qb, sf, bomid, rev = pay['bom']; need = pay['T']
            if total(p) < need:
                do_receipt(p, ts, ceil_to(need - total(p) + 0.25 * LOT[p], 100), 'EXPEDITED_GENERATED'); stats['expedited_gr'] += 1
            draws = alloc_fifo(p, need)
            if kind == 'ISSUE':
                bf = st[p]['batches'][draws[0][0]]['factor']
                rate = sf * MULT[m] * bf * (3.0 if (stage == 'SMT' and r.downtime_reason == 'FEEDER_JAM') else 1.0)
                G = U * qb; W = int(rng.poisson(G * rate)); C = G + W
                theo = U * qb * (1 + sf)
                cons_init = min(C, I)
                cons_alloc = []; rem = cons_init
                for bid, q in draws: t = min(q, rem); cons_alloc.append(t); rem -= t
                scr_init_total = int(round(W * cons_init / C)) if C else 0
                scr_alloc = alloc(scr_init_total, cons_alloc)
                lines = []
                for (bid, q), cq, sq in zip(draws, cons_alloc, scr_alloc):
                    lines.append(dict(draw=(bid, q), cons=cq, scr=sq))
                info = dict(r=r, U=U, qb=qb, sf=sf, bomid=bomid, rev=rev, G=G, W=W, C=C, theo=theo, topup=0)
                ttype = 'INITIAL_ISSUE'
                if C > I:
                    T = ceil_to(C - I, 10); info['topup'] = T
                    tts = r.ts + pd.Timedelta(minutes=int(rng.integers(20, 46)))
                    push(tts, 5, 'TOPUP', dict(r=r, bom=(qb, sf, bomid, rev), T=T, C=C, I=I, W=W, scr_rem=W - scr_init_total, theo=theo,
                                               G=G, ret_base=r.act_end))
                    stats['topups'] += 1
            else:
                info = None; ttype = 'TOP_UP_ISSUE'
                cons_rem = pay['C'] - pay['I']; cons_alloc = []
                for bid, q in draws: t = min(q, cons_rem); cons_alloc.append(t); cons_rem -= t
                scr_alloc = alloc(pay['scr_rem'], cons_alloc)
                lines = [dict(draw=d, cons=cq, scr=sq) for d, cq, sq in zip(draws, cons_alloc, scr_alloc)]
                G = pay['G']; C = pay['C']; theo = pay['theo']; W = pay['W']
            for L in lines:
                bid, q = L['draw']
                u = uid('M'); retq = q - L['cons']
                base_ret = (r.act_end if kind == 'ISSUE' else max(pay['ret_base'], ts + pd.Timedelta(minutes=5)))
                rts = base_ret + pd.Timedelta(minutes=int(rng.integers(10, 61)))
                basis_ = 'NORMAL'
                if rts > P_END: rts = P_END; basis_ = 'PERIOD_END_CLAMP'
                bt = st[p]['batches'][bid]
                theo_l = round(theo * (L['cons'] / C), 4) if C else 0.0
                row = dict(_uid=u, plant_id=p, storage_location_id=LOC(m), line_id=r.line_id, product_id=r.product_id, material_id=m,
                    bom_id=bomid, bom_revision=rev, material_batch_id=bid, transaction_type=ttype, issue_ts=ts,
                    return_ts=(rts if retq > 0 else pd.NaT), return_ts_basis=(basis_ if retq > 0 else 'NA_NO_RETURN'), uom='EA',
                    source_hourly_event_id=r.event_id, production_run_id=r.production_run_id, production_order_id=r.production_order_id,
                    units_started_qty=U, bom_component_qty_per_unit=qb, bom_scrap_factor=sf,
                    theoretical_bom_qty=round(G * (L['cons'] / C), 4) if C else 0.0, theoretical_qty_with_scrap=theo_l,
                    issued_qty=q, returned_qty=retq, consumed_qty=L['cons'], scrapped_qty=L['scr'], net_consumed_qty=L['cons'] - L['scr'],
                    variance_vs_theoretical_qty=round(L['cons'] - theo_l, 4),
                    unit_value_inr=bt['cost'], consumed_value_inr=round(L['cons'] * bt['cost'], 2), scrapped_value_inr=round(L['scr'] * bt['cost'], 2),
                    candidate_cost_record_id=r.cost_rec)
                issue_uid = post(p, ts, 'PRODUCTION_ISSUE', 'TO_PRODUCTION_RUN', 'MATERIAL_ISSUE', u, bid, 0, q, rel=u)
                row['_iss_uid'] = issue_uid; row['_ret_uid'] = None
                d6_rows.append(row)
                if retq > 0: push(rts, 2, 'RET', dict(line=row))
                row['_ret_basis'] = basis_
            reorder(p, ts)
    stats.setdefault('mat_end', {})[m] = {p: total(p) for p in plants}

# ------------------------------------------------------------------ finalize D6
D6 = pd.DataFrame(d6_rows)
D6 = D6.sort_values(['issue_ts', 'material_id', 'plant_id', 'production_run_id', 'transaction_type', 'material_batch_id']).reset_index(drop=True)
D6['material_issue_id'] = ['MI-%07d' % (i + 1) for i in range(len(D6))]
mi_map = dict(zip(D6._uid, D6.material_issue_id))
D7 = pd.DataFrame(d7_rows)
D7 = D7.sort_values(['transaction_ts', 'plant_id', 'material_id', 'ledger_seq']).reset_index(drop=True)
D7['inventory_txn_id'] = ['INV-%07d' % (i + 1) for i in range(len(D7))]
inv_map = dict(zip(D7._uid, D7.inventory_txn_id))
D6['inventory_issue_txn_id'] = D6._iss_uid.map(inv_map); D6['inventory_return_txn_id'] = D6._ret_uid.map(inv_map)
D7['related_material_issue_id'] = D7._rel.map(mi_map)
D7['counterpart_inventory_txn_id'] = D7['_cp'].map(inv_map) if '_cp' in D7 else None
# reference_id for issue/return = material_issue_id
isr = D7.transaction_type.isin(['PRODUCTION_ISSUE', 'PRODUCTION_RETURN'])
D7.loc[isr, 'reference_id'] = D7.loc[isr, 'related_material_issue_id']
rr = R.set_index('production_run_id'); mm = D6.set_index('material_issue_id')
D7['related_production_run_id'] = D7.related_material_issue_id.map(mm.production_run_id)
D7['related_production_order_id'] = D7.related_material_issue_id.map(mm.production_order_id)
D7['transaction_date'] = D7.transaction_ts.dt.strftime('%Y-%m-%d')
D7['net_qty'] = D7.qty_in - D7.qty_out
D7['line_value_inr'] = (D7.net_qty * D7.unit_value_inr).round(2)
D7['valuation_basis'] = 'GENERATED_STANDARD_PRICE_x_LOT_VARIANCE'
D7['transaction_status'] = 'POSTED'
D7['negative_stock_flag'] = np.where((D7.running_balance_batch_qty < 0) | (D7.running_balance_material_qty < 0), 'Y', 'N')
D7['traceability_status'] = np.where(isr, 'CONFIRMED', 'NOT_APPLICABLE')
D7['supplier_receipt_link_status'] = np.where(D7.transaction_type.isin(['GOODS_RECEIPT', 'OPENING_BALANCE']), 'UNMATCHED_SUPPLIER_DATASET_NOT_AVAILABLE', 'NOT_APPLICABLE')
D7['uom'] = 'EA'; D7['generation_version'] = GEN

D6['issue_status'] = np.where(D6.returned_qty == 0, 'CLOSED_FULLY_CONSUMED', np.where(D6.consumed_qty == 0, 'CLOSED_FULL_RETURN', 'CLOSED_PARTIAL_RETURN'))
D6['reconciliation_check'] = np.where(D6.issued_qty == D6.returned_qty + D6.consumed_qty, 'OK', 'FAIL')
D6['variance_pct'] = np.where(D6.theoretical_qty_with_scrap > 0, (D6.variance_vs_theoretical_qty / D6.theoretical_qty_with_scrap * 100).round(4), np.nan)
D6['order_run_link_status'] = 'CONFIRMED'; D6['hourly_slot_link_status'] = 'CONFIRMED'; D6['bom_link_status'] = 'CONFIRMED'
D6['cost_link_status'] = np.where(D6.candidate_cost_record_id.notna(), 'CANDIDATE_ONLY', 'UNMATCHED')
D6['bom_structure_confirmation_status'] = 'UNCONFIRMED_IDENTICAL_STRUCTURE_ACROSS_PRODUCTS'
D6['stage_assignment_basis'] = 'ASSUMED_SMT_FAL_MAP_NOT_IN_BOM'
D6['record_origin'] = 'GENERATED_SYNTHETIC'; D6['generation_version'] = GEN
for k in ['issue_ts', 'return_ts']: D6[k] = fmt(D6[k])
D7['transaction_ts'] = fmt(D7.transaction_ts)

d6cols = ['material_issue_id', 'production_order_id', 'production_run_id', 'source_hourly_event_id', 'plant_id', 'storage_location_id', 'line_id',
 'product_id', 'material_id', 'bom_id', 'bom_revision', 'material_batch_id', 'transaction_type', 'issue_ts', 'return_ts', 'return_ts_basis', 'uom',
 'units_started_qty', 'bom_component_qty_per_unit', 'bom_scrap_factor', 'theoretical_bom_qty', 'theoretical_qty_with_scrap', 'issued_qty',
 'returned_qty', 'consumed_qty', 'scrapped_qty', 'net_consumed_qty', 'variance_vs_theoretical_qty', 'variance_pct', 'unit_value_inr',
 'consumed_value_inr', 'scrapped_value_inr', 'issue_status', 'reconciliation_check', 'inventory_issue_txn_id', 'inventory_return_txn_id',
 'order_run_link_status', 'hourly_slot_link_status', 'bom_link_status', 'cost_link_status', 'candidate_cost_record_id',
 'bom_structure_confirmation_status', 'stage_assignment_basis', 'record_origin', 'generation_version']
d7cols = ['inventory_txn_id', 'ledger_seq', 'plant_id', 'storage_location_id', 'material_id', 'material_batch_id', 'transaction_ts', 'transaction_date',
 'transaction_type', 'transaction_subtype', 'reference_doc_type', 'reference_id', 'related_material_issue_id', 'related_production_order_id',
 'related_production_run_id', 'counterpart_inventory_txn_id', 'qty_in', 'qty_out', 'net_qty', 'uom', 'unit_value_inr', 'valuation_basis',
 'line_value_inr', 'running_balance_batch_qty', 'running_balance_material_qty', 'transaction_status', 'negative_stock_flag', 'traceability_status',
 'supplier_receipt_link_status', 'record_origin', 'generation_version']
D6[d6cols].to_csv(f'{OUT}/d6_material_issue_consumption_v1.csv', index=False)
D7[d7cols].to_csv(f'{OUT}/d7_inventory_transactions_v1.csv', index=False)

# ------------------------------------------------------------------ finalize D5
R['order_status_hint'] = None
Rout = R.copy()
for k in ['planned_start_ts', 'planned_end_ts', 'actual_start_ts', 'actual_end_ts']: Rout[k] = fmt(Rout[k])
Rout['hourly_link_status'] = 'CONFIRMED'
Rout['record_origin'] = 'GENERATED_SYNTHETIC'; Rout['generation_version'] = GEN
Rout['source_production_run_key'] = Rout.production_run_key
Rout = Rout.rename(columns={'attainment_pct': 'attainment_pct'})
rcols = ['production_run_id', 'production_order_id', 'source_production_run_key', 'source_po_number', 'plant_id', 'line_id', 'line_type', 'product_id',
 'shift_id_first', 'shift_ids_covered', 'shift_count', 'production_date_first', 'production_date_last', 'planned_qty', 'actual_qty', 'good_qty',
 'reject_qty', 'rework_qty', 'attainment_pct', 'planned_start_ts', 'planned_end_ts', 'actual_start_ts', 'actual_end_ts', 'slot_count',
 'producing_slot_count', 'zero_output_slot_count', 'downtime_min_total', 'calendar_span_hours', 'max_idle_gap_hours', 'execution_pattern',
 'run_status', 'schedule_ref', 'mes_execution_ref', 'first_source_event_id', 'last_source_event_id', 'source_suspicious_slot_count',
 'hourly_link_status', 'candidate_cost_record_count', 'record_origin', 'generation_version']
Rout[rcols].to_csv(f'{OUT}/d5_production_run_v1.csv', index=False)
Oo = O.copy()
for k in ['planned_start_ts', 'planned_end_ts', 'actual_start_ts', 'actual_end_ts']: Oo[k] = fmt(Oo[k])
Oo['record_origin'] = 'GENERATED_SYNTHETIC'; Oo['generation_version'] = GEN
ocols = ['production_order_id', 'order_context_key', 'source_po_number', 'plant_id', 'product_id', 'bom_id', 'bom_revision', 'planned_qty', 'actual_qty',
 'good_qty', 'reject_qty', 'rework_qty', 'completion_basis_run_id', 'completion_basis', 'run_count', 'routing_completeness', 'planned_start_ts',
 'planned_end_ts', 'actual_start_ts', 'actual_end_ts', 'first_production_date', 'last_production_date', 'calendar_span_days', 'order_status',
 'schedule_ref', 'source_po_traceability_status', 'order_integrity_flag', 'record_origin', 'generation_version']
Oo[ocols].to_csv(f'{OUT}/d5_production_order_v1.csv', index=False)
BR.to_csv(f'{OUT}/d5_run_source_link_v1.csv', index=False)
json.dump({'stats': stats, 'anomalies': anomaly_log, 'price': PRICE, 'target_unit_mat_cost': TARGET_UNIT_MAT_COST,
           'rows': {'order': len(Oo), 'run': len(Rout), 'link': len(BR), 'd6': len(D6), 'd7': len(D7)}}, open('/home/claude/gen_meta.json', 'w'), indent=1, default=str)
print(json.dumps({'rows': {'order': len(Oo), 'run': len(Rout), 'link': len(BR), 'd6': len(D6), 'd7': len(D7)}, 'stats': {k: v for k, v in stats.items() if k != 'mat_end'}}))
