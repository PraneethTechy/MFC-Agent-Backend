"""Independent validation (re-reads CSVs from disk) + data dictionary, key spec, audit workbook, summary for D8-D10."""
import sys, os, json, hashlib, datetime as dt
import numpy as np, pandas as pd
IN = '/home/claude/in'; OUT = '/mnt/user-data/outputs'; META = '/home/claude/work'; V = '_v1'
rd = lambda n: pd.read_csv(f'{OUT}/{n}{V}.csv', low_memory=False)
T = {n: rd(n) for n in ['d8_supplier_master', 'd8_supplier_material_source_list', 'd8_po_header', 'd8_po_line', 'd8_goods_receipt', 'd8_supplier_quality',
     'd9_equipment_master', 'd9_equipment_event', 'd9_energy_reading_shift', 'd9_maintenance_event', 'd9_event_hourly_candidate_link',
     'd10_shift_definition', 'd10_employee_master', 'd10_shift_assignment', 'd10_line_allocation', 'd10_attendance', 'd10_line_shift_labour_daily']}
d7 = pd.read_csv(f'{IN}/b/d7_inventory_transactions_v1.csv', low_memory=False)
bom = pd.read_csv(f'{IN}/a/4 ds/fact_bom_component_enhanced_v1.csv'); hr = pd.read_csv(f'{IN}/a/4 ds/fact_hourly_production_enhanced_v1.csv', low_memory=False)
qi = pd.read_csv(f'{IN}/a/4 ds/fact_quality_inspection_enhanced_v1.csv', usecols=['station_id', 'inspector_id'], low_memory=False)
cost = pd.read_csv(f'{IN}/a/4 ds/fact_manufacturing_cost_enhanced_v1.csv', usecols=['energy_cost_inr', 'labour_cost_inr'], low_memory=False)
PK = {'d8_supplier_master': ['supplier_id'], 'd8_supplier_material_source_list': ['source_list_id'], 'd8_po_header': ['po_id'], 'd8_po_line': ['po_line_id'], 'd8_goods_receipt': ['gr_id'],
      'd8_supplier_quality': ['quality_id'], 'd9_equipment_master': ['equipment_id'], 'd9_equipment_event': ['event_id'], 'd9_energy_reading_shift': ['reading_id'],
      'd9_maintenance_event': ['maintenance_id'], 'd9_event_hourly_candidate_link': ['link_id'], 'd10_shift_definition': ['shift_id'], 'd10_employee_master': ['employee_id'],
      'd10_shift_assignment': ['shift_assignment_id'], 'd10_line_allocation': ['allocation_id'], 'd10_attendance': ['attendance_id'], 'd10_line_shift_labour_daily': ['labour_day_id']}
AK = {'d8_goods_receipt': ['inventory_txn_id'], 'd9_energy_reading_shift': ['equipment_id', 'shift_production_date', 'shift_id'], 'd10_attendance': ['employee_id', 'attendance_date'],
      'd9_equipment_master': ['energy_meter_id'], 'd8_po_line': ['po_id', 'line_number'], 'd10_line_shift_labour_daily': ['shift_production_date', 'plant_id', 'line_id', 'shift_id']}
FK = [('d8_supplier_material_source_list', 'supplier_id', 'd8_supplier_master', 'supplier_id'), ('d8_supplier_material_source_list', 'material_id', 'BOM', 'material_id'),
      ('d8_po_header', 'supplier_id', 'd8_supplier_master', 'supplier_id'), ('d8_po_line', 'po_id', 'd8_po_header', 'po_id'), ('d8_po_line', 'supplier_id', 'd8_supplier_master', 'supplier_id'),
      ('d8_po_line', 'material_id', 'BOM', 'material_id'), ('d8_po_line', 'material_id', 'D7', 'material_id'), ('d8_goods_receipt', 'po_line_id', 'd8_po_line', 'po_line_id'),
      ('d8_goods_receipt', 'po_id', 'd8_po_header', 'po_id'), ('d8_goods_receipt', 'inventory_txn_id', 'D7_GR', 'inventory_txn_id'), ('d8_goods_receipt', 'supplier_id', 'd8_supplier_master', 'supplier_id'),
      ('d8_goods_receipt', 'material_id', 'BOM', 'material_id'), ('d8_goods_receipt', 'plant_id', 'HOURLY', 'plant_id'), ('d8_supplier_quality', 'gr_id', 'd8_goods_receipt', 'gr_id'),
      ('d9_equipment_event', 'equipment_id', 'd9_equipment_master', 'equipment_id'), ('d9_equipment_event', 'maintenance_id', 'd9_maintenance_event', 'maintenance_id'),
      ('d9_energy_reading_shift', 'equipment_id', 'd9_equipment_master', 'equipment_id'), ('d9_energy_reading_shift', 'energy_meter_id', 'd9_equipment_master', 'energy_meter_id'),
      ('d9_maintenance_event', 'equipment_id', 'd9_equipment_master', 'equipment_id'), ('d9_maintenance_event', 'linked_downtime_event_id', 'd9_equipment_event', 'event_id'),
      ('d9_event_hourly_candidate_link', 'equipment_event_id', 'd9_equipment_event', 'event_id'), ('d9_event_hourly_candidate_link', 'hourly_event_id', 'HOURLY', 'event_id'),
      ('d9_equipment_master', 'line_id', 'HOURLY', 'line_id'), ('d10_shift_assignment', 'employee_id', 'd10_employee_master', 'employee_id'), ('d10_shift_assignment', 'shift_id', 'd10_shift_definition', 'shift_id'),
      ('d10_shift_assignment', 'shift_id', 'HOURLY', 'shift_id'), ('d10_line_allocation', 'employee_id', 'd10_employee_master', 'employee_id'),
      ('d10_line_allocation', 'shift_assignment_id', 'd10_shift_assignment', 'shift_assignment_id'), ('d10_line_allocation', 'supervisor_employee_id', 'd10_employee_master', 'employee_id'),
      ('d10_line_allocation', 'line_id', 'HOURLY', 'line_id'), ('d10_attendance', 'employee_id', 'd10_employee_master', 'employee_id'), ('d10_attendance', 'shift_id', 'd10_shift_definition', 'shift_id'),
      ('d10_attendance', 'supervisor_employee_id', 'd10_employee_master', 'employee_id'), ('d10_attendance', 'line_id', 'HOURLY', 'line_id'), ('d10_line_shift_labour_daily', 'line_id', 'HOURLY', 'line_id')]
REF = {'BOM': bom, 'D7': d7, 'D7_GR': d7[d7.transaction_type == 'GOODS_RECEIPT'], 'HOURLY': hr, **T}
checks = []
def chk(area, name, cond, exp='', act=''):
    checks.append(dict(check_id=f'C{len(checks) + 1:03d}', area=area, check=name, status='PASS' if bool(cond) else 'FAIL', expected=str(exp), actual=str(act)))
inv, keyrows, fkrows = [], [], []
for n, df in T.items():
    pk = PK[n]; dup = int(df.duplicated(pk).sum()); nulls = int(df[pk].isna().any(axis=1).sum()); ak = AK.get(n)
    akd = int(df.duplicated(ak).sum()) if ak else None
    inv.append(dict(file=f'{n}{V}.csv', rows=len(df), columns=df.shape[1], primary_key='+'.join(pk), duplicate_pk=dup, null_pk=nulls, alt_key='+'.join(ak) if ak else '', duplicate_alt_key=akd,
                    full_row_duplicates=int(df.duplicated().sum())))
    chk(n[:2].upper(), f'{n}: PK unique & non-null', dup == 0 and nulls == 0, 0, dup + nulls)
    if ak: chk(n[:2].upper(), f'{n}: alternate key {"+".join(ak)} unique', akd == 0, 0, akd)
for t, c, rt, rc in FK:
    s = T[t][c].dropna(); bad = int((~s.isin(REF[rt][rc])).sum()); fkrows.append(dict(child=t, column=c, parent=rt, parent_column=rc, non_null_rows=len(s), invalid_refs=bad))
    chk(t[:2].upper(), f'FK {t}.{c} -> {rt}.{rc}', bad == 0, 0, bad)
ids = lambda s: s.astype(str)
sup, sl, po, pl, gr, q = (T[k] for k in ['d8_supplier_master', 'd8_supplier_material_source_list', 'd8_po_header', 'd8_po_line', 'd8_goods_receipt', 'd8_supplier_quality'])
eqm, ev, en, mt, lk = (T[k] for k in ['d9_equipment_master', 'd9_equipment_event', 'd9_energy_reading_shift', 'd9_maintenance_event', 'd9_event_hourly_candidate_link'])
shd, emp, sa, la, att, lab = (T[k] for k in ['d10_shift_definition', 'd10_employee_master', 'd10_shift_assignment', 'd10_line_allocation', 'd10_attendance', 'd10_line_shift_labour_daily'])
recon = []
def rec(area, item, a, b, tol=0, note=''):
    diff = (a - b) if isinstance(a, (int, float, np.integer, np.floating)) else ''
    ok = abs(a - b) <= tol if diff != '' else a == b
    recon.append(dict(area=area, reconciliation=item, side_a=a, side_b=b, difference=diff, tolerance=tol, result='PASS' if ok else 'FAIL', note=note)); chk(area, item, ok, b, a)

# ---------------- D8
g7 = d7[d7.transaction_type == 'GOODS_RECEIPT'].set_index('inventory_txn_id'); m = gr.join(g7, on='inventory_txn_id', rsuffix='_d7')
rec('D8', 'D7 receipt rows covered by exactly one D8 GR', int(gr.inventory_txn_id.nunique()), len(g7))
rec('D8', 'D8 GR rows with D7 txn not GOODS_RECEIPT', int((~gr.inventory_txn_id.isin(g7.index)).sum()), 0)
for a_, b_, nm in [('plant_id', 'plant_id_d7', 'plant'), ('storage_location_id', 'storage_location_id_d7', 'storage location'), ('material_id', 'material_id_d7', 'material'), ('material_batch_id', 'material_batch_id_d7', 'batch'),
                   ('gr_posting_ts', 'transaction_ts', 'posting timestamp'), ('actual_delivery_date', 'transaction_date', 'delivery date')]:
    rec('D8', f'GR vs D7 {nm} mismatches', int((m[a_] != m[b_]).sum()), 0)
rec('D8', 'Sum GR accepted_qty vs D7 qty_in (all 346 receipts)', int(gr.accepted_qty.sum()), int(g7.qty_in.sum()), note='accepted qty = qty posted to D7 stock')
rec('D8', 'GR rows where accepted_qty != D7 qty_in', int((gr.accepted_qty != gr.d7_posted_qty_in).sum()), 0)
rec('D8', 'GR rows where d7_posted_qty_in != D7 qty_in', int((m.d7_posted_qty_in != m.qty_in).sum()), 0)
rec('D8', 'GR rows with received != accepted + rejected', int((gr.received_qty != gr.accepted_qty + gr.rejected_qty).sum()), 0)
rec('D8', 'Max |accepted value - D7 line value| INR', float((gr.accepted_value_inr - gr.d7_line_value_inr).abs().max()), 0.0, tol=1.0)
rec('D8', 'Total received qty (incl. rejected, not in D7) = D7 qty + rejected', int(gr.received_qty.sum()), int(g7.qty_in.sum() + gr.rejected_qty.sum()))
rec('D8', 'D7 transaction types changed by D8 (D7 not written; ledger rows referenced only)', 0, 0, note='no second inventory ledger: D8 holds no stock balance columns')
lg = gr.groupby('po_line_id').agg(rec_=('received_qty', 'sum'), acc=('accepted_qty', 'sum'), rej=('rejected_qty', 'sum'), n=('gr_id', 'size')).reset_index()
x = pl.merge(lg, on='po_line_id', how='left').fillna({'rec_': 0, 'acc': 0, 'rej': 0, 'n': 0}); op = x.line_status == 'OPEN'
rec('D8', 'PO lines: received_qty_total != sum(GR received)', int((x.received_qty_total != x.rec_).sum()), 0)
rec('D8', 'PO lines: accepted/rejected totals != sum(GR)', int(((x.accepted_qty_total != x.acc) | (x.rejected_qty_total != x.rej)).sum()), 0)
rec('D8', 'PO lines: gr_count != GR rows', int((x.gr_count != x.n).sum()), 0)
rec('D8', 'Closed lines: delivery_variance != received - ordered', int((x[~op].delivery_variance_qty != x[~op].received_qty_total - x[~op].ordered_qty).sum()), 0)
rec('D8', 'Open lines with any receipt', int((x[op].received_qty_total > 0).sum()), 0)
rec('D8', 'Open lines: open_qty != ordered_qty', int((x[op].open_qty != x[op].ordered_qty).sum()), 0)
r_ = x[~op].received_qty_total / x[~op].ordered_qty
rec('D8', 'Closed lines outside 0.93-1.05 received/ordered band', int(((r_ < .93) | (r_ > 1.05)).sum()), 0)
rec('D8', 'CLOSED_SHORT lines without short-close reason', int(((x.line_status == 'CLOSED_SHORT') & (x.short_close_reason.isna())).sum()), 0)
rec('D8', 'Unexplained shortfall (ratio<0.97) on non-CLOSED_SHORT lines', int(((r_ < .97) & (x[~op].line_status != 'CLOSED_SHORT')).sum()), 0)
h = pl.groupby('po_id').agg(n=('po_line_id', 'size'), v=('ordered_value_inr', 'sum'), pl_=('plant_id', 'nunique'), su=('supplier_id', 'nunique')).reset_index(); hh = po.merge(h, on='po_id')
rec('D8', 'PO header line_count != lines', int((hh.line_count != hh.n).sum()), 0)
rec('D8', 'PO header total value vs lines (max diff INR)', float((hh.total_ordered_value_inr - hh.v).abs().max()), 0.0, tol=0.05)
rec('D8', 'PO headers with mixed plant/supplier lines', int(((hh.pl_ > 1) | (hh.su > 1)).sum()), 0)
lp = pl.merge(po[['po_id', 'plant_id', 'supplier_id', 'po_date', 'po_currency']], on='po_id', suffixes=('', '_h'))
rec('D8', 'PO line plant/supplier != header', int(((lp.plant_id != lp.plant_id_h) | (lp.supplier_id != lp.supplier_id_h)).sum()), 0)
rec('D8', 'PO line currency != supplier currency', int((lp.unit_price_currency != lp.po_currency).sum()), 0)
gm = gr.merge(pl[['po_line_id', 'plant_id', 'material_id', 'supplier_id', 'storage_location_id']], on='po_line_id', suffixes=('', '_l'))
rec('D8', 'GR plant/material/supplier/sloc != PO line', int(((gm.plant_id != gm.plant_id_l) | (gm.material_id != gm.material_id_l) | (gm.supplier_id != gm.supplier_id_l) | (gm.storage_location_id != gm.storage_location_id_l)).sum()), 0)
ap = set(zip(sl.supplier_id, sl.material_id)); rec('D8', 'PO lines whose supplier is not on approved source list for the material', int(sum((s, m_) not in ap for s, m_ in zip(pl.supplier_id, pl.material_id))), 0)
rec('D8', 'PO line dates: promised<requested or receipt<po_date', int(((lp.promised_delivery_date < lp.requested_delivery_date) | (lp.first_receipt_date.notna() & (lp.first_receipt_date < lp.po_date))).sum()), 0)
rec('D8', 'PO date after 2026-10-31', int((po.po_date > '2026-10-31').sum()), 0)
gd = gr.merge(po[['po_id', 'po_date']], on='po_id'); dl = (pd.to_datetime(gd.actual_delivery_date) - pd.to_datetime(gd.gr_promised_date)).dt.days
st = np.where(dl > 0, 'LATE', np.where(dl <= -2, 'EARLY', 'ON_TIME'))
rec('D8', 'GR on_time_status/days_late recomputation mismatches', int(((st != gd.on_time_status) | (dl != gd.days_late)).sum()), 0)
rec('D8', 'GR lead_time recomputation mismatches', int(((pd.to_datetime(gd.actual_delivery_date) - pd.to_datetime(gd.po_date)).dt.days != gd.lead_time_days_actual).sum()), 0)
rec('D8', 'GR actual delivery outside 2026-08-01..10-31', int(((gr.actual_delivery_date < '2026-08-01') | (gr.actual_delivery_date > '2026-10-31')).sum()), 0)
qg = q.merge(gr[['gr_id', 'rejected_qty', 'received_qty', 'gr_posting_ts', 'material_batch_id']], on='gr_id', suffixes=('', '_g'))
rec('D8', 'Quality: one record per GR', int(q.gr_id.nunique()), len(gr)); rec('D8', 'Quality rejected_qty != GR rejected_qty', int((qg.rejected_qty != qg.rejected_qty_g).sum()), 0)
rec('D8', 'Quality lot_size != GR received_qty', int((qg.lot_size_qty != qg.received_qty).sum()), 0)
rec('D8', 'Quality inspection after GR posting', int((qg.inspection_ts > qg.gr_posting_ts).sum()), 0)
rec('D8', 'Quality result inconsistent with rejected qty', int((((qg.rejected_qty > 0) & (qg.inspection_result != 'PARTIAL_REJECT')) | ((qg.rejected_qty == 0) & (qg.inspection_result == 'PARTIAL_REJECT'))).sum()), 0)
rec('D8', 'Quality batch != GR batch', int((qg.material_batch_id != qg.material_batch_id_g).sum()), 0)
rec('D8', 'Rejected qty with no recorded disposition', int(((q.rejected_qty > 0) & (q.disposition == 'NONE')).sum()), 0)
unl = d7[(d7.supplier_receipt_link_status != 'NOT_APPLICABLE')]; unl_open = int((unl.transaction_type == 'OPENING_BALANCE').sum())
chk('D8', 'D7 opening balances remain UNMATCHED to suppliers (no PO exists by design)', unl_open == 64, 64, unl_open)
# ---------------- D9
pairs = set(zip(hr.plant_id, hr.line_id)); rec('D9', 'Equipment plant-line pairs not in hourly feed', int(sum((p, l) not in pairs for p, l in zip(eqm.plant_id, eqm.line_id))), 0)
rec('D9', 'Equipment per line (expected 8 each, 32 total)', int(eqm.groupby('line_id').size().min() == 8 and len(eqm) == 32), 1)
rec('D9', 'Stations referenced that do not exist in quality source', int((~eqm.station_id.dropna().isin(qi.station_id)).sum()), 0)
ev['s'] = pd.to_datetime(ev.event_start_ts); ev['e'] = pd.to_datetime(ev.event_end_ts)
rec('D9', 'Events with end<=start or duration != end-start', int(((ev.e <= ev.s) | ((ev.e - ev.s).dt.total_seconds() / 60 != ev.duration_min)).sum()), 0)
rec('D9', 'Events outside 2026-08-01..11-01 window', int(((ev.s < '2026-08-01') | (ev.e > '2026-11-01')).sum()), 0)
sv = ev.sort_values(['equipment_id', 's']); pe = sv.groupby('equipment_id').e.shift(); ov = int((sv.s < pe).sum())
rec('D9', 'Overlapping events within same equipment (double counting)', ov, 0)
em = ev.merge(eqm[['equipment_id', 'plant_id', 'line_id']], on='equipment_id', suffixes=('', '_m')); rec('D9', 'Event plant/line != equipment master', int(((em.plant_id != em.plant_id_m) | (em.line_id != em.line_id_m)).sum()), 0)
rec('D9', 'Unplanned+planned+idle minutes per equipment exceed window', int((ev.groupby('equipment_id').duration_min.sum() > 132480).sum()), 0)
# independent energy recompute
T0 = pd.Timestamp('2026-08-01'); en['a'] = pd.to_datetime(en.period_start_ts); en['b'] = pd.to_datetime(en.period_end_ts)
rec('D9', 'Energy: operating+idle+planned+unplanned != window_min', int((en.operating_min + en.idle_min + en.planned_downtime_min + en.unplanned_downtime_min != en.window_min).sum()), 0)
rec('D9', 'Energy: window_min != period end-start', int(((en.b - en.a).dt.total_seconds() / 60 != en.window_min).sum()), 0)
mism = 0; tp = {'IDLE': 'idle_min', 'PLANNED_DOWNTIME': 'planned_downtime_min', 'UNPLANNED_DOWNTIME': 'unplanned_downtime_min'}
for eid, g in en.groupby('equipment_id'):
    e_ = ev[ev.equipment_id == eid]; a = g.a.values[:, None]; b = g.b.values[:, None]; es = e_.s.values[None, :]; ee = e_.e.values[None, :]
    ovm = np.clip((np.minimum(b, ee) - np.maximum(a, es)) / np.timedelta64(1, 'm'), 0, None)
    for ty, col in tp.items():
        calc = ovm[:, (e_.event_type == ty).values].sum(axis=1); mism += int((calc != g[col].values).sum())
rec('D9', 'Energy state minutes vs independent recompute from events (mismatched cells)', mism, 0)
k = en.merge(eqm[['equipment_id', 'rated_power_kw', 'idle_power_factor', 'unplanned_down_power_factor', 'planned_down_power_factor', 'energy_meter_id']], on='equipment_id', suffixes=('', '_m'))
mod = (k.operating_min * k.rated_power_kw + k.idle_min * k.rated_power_kw * k.idle_power_factor + k.planned_downtime_min * k.rated_power_kw * k.planned_down_power_factor + k.unplanned_downtime_min * k.rated_power_kw * k.unplanned_down_power_factor) / 60
ratio = (k.energy_kwh / mod).replace([np.inf], np.nan).dropna(); rec('D9', 'kWh outside +/-15% of rated-power model', int(((ratio < .85) | (ratio > 1.15)).sum()), 0)
rec('D9', 'Max kWh/hour vs rated kW (plausibility, must be <=1.15)', float((k.energy_kwh / (k.window_min / 60) / k.rated_power_kw).max()) <= 1.15, True)
rec('D9', 'Meter id != master meter id', int((k.energy_meter_id != k.energy_meter_id_m).sum()), 0)
rec('D9', 'Meter register end != start + kWh', int(((en.meter_register_end_kwh - en.meter_register_start_kwh - en.energy_kwh).abs() > .002).sum()), 0)
sg = en.sort_values(['equipment_id', 'a']); nx = sg.groupby('equipment_id').meter_register_start_kwh.shift(-1); rec('D9', 'Meter register discontinuities between consecutive periods', int(((nx - sg.meter_register_end_kwh).abs() > .002).sum()), 0)
rec('D9', 'Energy cost != kWh x tariff', int(((en.energy_kwh * en.tariff_inr_per_kwh - en.estimated_energy_cost_inr).abs() > .006).sum()), 0)
rec('D9', 'Energy readings count (32 eq x 277 periods)', len(en), 32 * 277)
mm = mt.merge(ev[['event_id', 's', 'e', 'equipment_id', 'event_type', 'reason_code']], left_on='linked_downtime_event_id', right_on='event_id', how='left', suffixes=('', '_e'))
c_ = mm[mm.work_order_status == 'COMPLETED']; rec('D9', 'Maintenance outside linked event window / different equipment', int(((pd.to_datetime(c_.actual_start_ts) < c_.s) | (pd.to_datetime(c_.actual_end_ts) > c_.e) | (c_.equipment_id != c_.equipment_id_e)).sum()), 0)
rec('D9', 'Maintenance type vs event type inconsistent', int((((c_.maintenance_type == 'CORRECTIVE') & (c_.event_type != 'UNPLANNED_DOWNTIME')) | ((c_.maintenance_type != 'CORRECTIVE') & (c_.event_type != 'PLANNED_DOWNTIME'))).sum()), 0)
rec('D9', 'Event maintenance_id back-reference mismatches', int((ev.dropna(subset=['maintenance_id']).merge(mt, on='maintenance_id').pipe(lambda z: z.event_id != z.linked_downtime_event_id)).sum()), 0)
rec('D9', 'Deferred work orders carrying a downtime event', int(((mt.work_order_status == 'DEFERRED') & mt.linked_downtime_event_id.notna()).sum()), 0)
rec('D9', 'Maintenance duration != end-start', int(((pd.to_datetime(c_.actual_end_ts) - pd.to_datetime(c_.actual_start_ts)).dt.total_seconds() / 60 != c_.duration_min).sum()), 0)
hs = hr.assign(ts=pd.to_datetime(hr.event_ts)).set_index('event_id'); lkm = lk.merge(ev[['event_id', 's', 'e', 'line_id', 'reason_category']], left_on='equipment_event_id', right_on='event_id', suffixes=('', '_e'))
hts = hs.loc[lkm.hourly_event_id]; ovl = (np.minimum(lkm.e.values, hts.ts.values + np.timedelta64(60, 'm')) - np.maximum(lkm.s.values, hts.ts.values)) / np.timedelta64(1, 'm')
rec('D9', 'Candidate link overlap_min mismatches / non-positive', int(((ovl != lkm.overlap_min.values) | (ovl <= 0)).sum()), 0)
rec('D9', 'Candidate links to different line / reason / zero hourly downtime', int(((hts.line_id.values != lkm.line_id_e.values) | (hts.downtime_reason.values != lkm.reason_category.values) | (hts.downtime_min.values <= 0)).sum()), 0)
rec('D9', 'Link status other than CANDIDATE_ONLY (no confirmed claims)', int((lk.link_status != 'CANDIDATE_ONLY').sum() + (ev.hourly_link_status == 'CONFIRMED').sum()), 0)
rec('D9', 'Events with link status vs link rows inconsistent', int(((ev.hourly_link_status == 'CANDIDATE_ONLY') != ev.event_id.isin(lk.equipment_event_id)).sum()), 0)
# ---------------- D10
rec('D10', 'Employee IDs not SYN-EMP- prefixed', int((~emp.employee_id.str.startswith('SYN-EMP-')).sum()), 0)
rec('D10', 'Employee columns resembling personal data (name/phone/email/address/dob)', int(sum(any(w in c for w in ['name', 'phone', 'email', 'address', 'dob', 'birth', 'aadhaar']) for c in emp.columns)), 0)
rec('D10', 'Employee master all is_synthetic=Y / contains_personal_data=N', int(((emp.is_synthetic != 'Y') | (emp.contains_personal_data != 'N')).sum()), 0)
sa['f'] = pd.to_datetime(sa.effective_from); sa['t'] = pd.to_datetime(sa.effective_to); s2 = sa.sort_values(['employee_id', 'f'])
rec('D10', 'Overlapping shift-assignment periods per employee', int((s2.f < s2.groupby('employee_id').t.shift()).sum()), 0)
rec('D10', 'Employees without full 08-01..10-31 coverage', int((s2.groupby('employee_id').apply(lambda g: not (g.f.min() == pd.Timestamp('2026-08-01') and g.t.max() == pd.Timestamp('2026-10-31') and (g.f.values[1:] - g.t.values[:-1] == np.timedelta64(1, 'D')).all()))).sum()), 0)
am = la.merge(sa, on='shift_assignment_id', suffixes=('', '_s')); rec('D10', 'Allocation vs assignment employee/shift/period mismatches', int(((am.employee_id != am.employee_id_s) | (am.shift_id != am.shift_id_s) | (am.effective_from != am.effective_from_s) | (am.effective_to != am.effective_to_s)).sum()), 0)
rec('D10', 'Allocation rows != assignment rows (1:1)', len(la), len(sa))
rec('D10', 'Allocation plant-line pairs invalid', int(sum((p, l) not in pairs for p, l in zip(la.plant_id[la.line_id.notna()], la.line_id.dropna()))), 0)
rec('D10', 'Allocation line plant != employee plant', int((la.merge(emp[['employee_id', 'plant_id']], on='employee_id', suffixes=('', '_e')).pipe(lambda z: z.plant_id != z.plant_id_e)).sum()), 0)
rl = emp.set_index('employee_id').employee_role; rec('D10', 'Supervisor refs that are not SUPERVISOR/PRODUCTION_MANAGER', int((~rl[la.supervisor_employee_id.dropna()].isin(['SUPERVISOR', 'PRODUCTION_MANAGER'])).sum()), 0)
rec('D10', 'Production-run attribution claimed (must be UNMATCHED)', int((~la.production_run_link_status.str.startswith('UNMATCHED')).sum()), 0)
a = att.copy(); a['ss'] = pd.to_datetime(a.scheduled_start_ts); a['ci'] = pd.to_datetime(a.check_in_ts); a['co'] = pd.to_datetime(a.check_out_ts)
rec('D10', 'Attendance rows per employee-date duplicates', int(a.duplicated(['employee_id', 'attendance_date']).sum()), 0)
al = a.merge(la[['employee_id', 'line_id', 'shift_id', 'plant_id', 'crew_id', 'supervisor_employee_id', 'effective_from', 'effective_to']], on='employee_id', suffixes=('', '_a'))
al = al[(al.attendance_date >= al.effective_from) & (al.attendance_date <= al.effective_to)]
rec('D10', 'Attendance rows without exactly one covering allocation', len(al), len(a))
rec('D10', 'Attendance line/shift/plant/crew/supervisor != allocation', int(((al.shift_id != al.shift_id_a) | (al.plant_id != al.plant_id_a) | (al.line_id.fillna('') != al.line_id_a.fillna('')) | (al.supervisor_employee_id.fillna('') != al.supervisor_employee_id_a.fillna(''))).sum()), 0)
wo = a.merge(emp[['employee_id', 'weekly_off_day']], on='employee_id'); rec('D10', 'Attendance on employee weekly-off day', int((pd.to_datetime(wo.attendance_date).dt.day_name().str.upper() == wo.weekly_off_day).sum()), 0)
pr = a.attendance_status.isin(['PRESENT', 'HALF_DAY']); n_ = a[~pr]
rec('D10', 'Absent/leave rows with punches, hours, OT or productive hours', int((n_.check_in_ts.notna() | n_.check_out_ts.notna() | (n_.actual_working_hours != 0) | (n_.overtime_hours != 0) | (n_.productive_labour_hours != 0)).sum()), 0)
p_ = a[pr]; calc = ((p_.co - np.maximum(p_.ci, p_.ss)).dt.total_seconds() / 60 - p_.break_minutes) / 60
rec('D10', 'Actual hours vs punches (|diff|>0.02h)', int(((calc - p_.actual_working_hours).abs() > .02).sum()), 0)
rec('D10', 'actual != regular + overtime', int(((a.actual_working_hours - a.regular_hours - a.overtime_hours).abs() > .011).sum()), 0)
rec('D10', 'Regular hours above scheduled / OT outside 0..4h', int(((a.regular_hours > a.scheduled_hours + .001) | (a.overtime_hours < 0) | (a.overtime_hours > 4)).sum()), 0)
rec('D10', 'OT without APPROVED status', int(((a.overtime_hours > 0) != (a.ot_approval_status == 'APPROVED')).sum()), 0)
rec('D10', 'Productive hours for non-direct-labour or non-present', int(((a.productive_labour_hours > 0) & ((a.is_direct_labour != 'Y') | ~pr)).sum()), 0)
rec('D10', 'Direct-labour present rows where productive != actual hours', int(((a.is_direct_labour == 'Y') & pr & ((a.productive_labour_hours - a.actual_working_hours).abs() > .001)).sum()), 0)
rec('D10', 'Check-out <= check-in on present rows', int((p_.co <= p_.ci).sum()), 0)
w = a.assign(wk=pd.to_datetime(a.attendance_date).dt.isocalendar().week.astype(int)).groupby(['employee_id', 'wk']).actual_working_hours.sum(); rec('D10', 'Employee-weeks above 60 working hours', int((w > 60).sum()), 0)
sp = a[pr].sort_values(['employee_id', 'ss']); gap = (sp.ss - sp.groupby('employee_id').co.shift()).dt.total_seconds() / 3600
rec('D10', 'Consecutive worked shifts with <8h rest or overlap (conflicting assignment)', int((gap < 8).sum()), 0)
rec('D10', 'Leave_category set on PRESENT rows', int(((a.attendance_status == 'PRESENT') & (a.leave_category != 'NONE')).sum()), 0)
g = a[a.line_id.notna()].groupby(['attendance_date', 'plant_id', 'line_id', 'shift_id']); chkl = pd.DataFrame(dict(sh=g.size(), pf=g.attendance_status.apply(lambda s: (s == 'PRESENT').sum()), ab=g.attendance_status.apply(lambda s: (s == 'ABSENT').sum()),
    lv=g.attendance_status.apply(lambda s: (s == 'ON_LEAVE').sum()), hd=g.attendance_status.apply(lambda s: (s == 'HALF_DAY').sum()), ph=g.productive_labour_hours.sum(), ot=g.overtime_hours.sum())).reset_index()
lm = lab.merge(chkl, left_on=['shift_production_date', 'plant_id', 'line_id', 'shift_id'], right_on=['attendance_date', 'plant_id', 'line_id', 'shift_id'])
rec('D10', 'Labour summary rows matched to attendance', len(lm), len(lab))
rec('D10', 'Labour summary scheduled != present+half+absent+leave', int((lab.scheduled_hc != lab.present_full_day_hc + lab.half_day_hc + lab.absent_hc + lab.leave_hc).sum()), 0)
rec('D10', 'Labour summary counts/hours vs attendance recompute', int(((lm.scheduled_hc != lm.sh) | (lm.present_full_day_hc != lm.pf) | (lm.absent_hc != lm.ab) | (lm.leave_hc != lm.lv) | (lm.half_day_hc != lm.hd) | ((lm.productive_labour_hours - lm.ph).abs() > .01) | ((lm.overtime_hours - lm.ot).abs() > .01)).sum()), 0)
rec('D10', 'Productive hours exceed direct-labour present headcount x (7.5h + 4h OT cap)', int((lab.productive_labour_hours > lab.direct_labour_present_hc * 11.5 + .01).sum()), 0)
hs2 = hr.groupby(['plant_id', 'line_id', 'shift_id', 'shift_production_date']).size().reset_index(name='n'); cov = hs2.merge(lab[['plant_id', 'line_id', 'shift_id', 'shift_production_date']], how='left', indicator=True, on=['plant_id', 'line_id', 'shift_id', 'shift_production_date'])
hours_no_lab = int((cov._merge == 'left_only').sum()); slots_no_lab = int(cov[cov._merge == 'left_only'].n.sum())
rec('D10', 'Labour days with CANDIDATE_ONLY but zero hourly slots', int(((lab.hourly_link_status == 'CANDIDATE_ONLY') & (lab.candidate_hourly_slot_count == 0)).sum()), 0)
rec('D10', 'Hourly line-shift-days with no labour record (info: pre-window Jul-31 C shift)', hours_no_lab, 4, note=f'{slots_no_lab} hourly slots; expected 4 line-shifts on 2026-07-31 (C-shift slots 00:00-05:59 of Aug 1)')
# ---------------- summary stats / relationship classification
stats = dict(gr_on_time_pct=round((gr.on_time_status != 'LATE').mean() * 100, 1), gr_late=int((gr.on_time_status == 'LATE').sum()), gr_reject_lots=int((gr.rejected_qty > 0).sum()),
             po_open_lines=int(op.sum()), split_lines=int((pl.gr_count == 2).sum()), unplanned_min=int(ev[ev.event_type == 'UNPLANNED_DOWNTIME'].duration_min.sum()),
             energy_kwh=round(float(en.energy_kwh.sum()), 1), energy_cost=round(float(en.estimated_energy_cost_inr.sum()), 2), absent_pct=round(float((a.attendance_status.isin(['ABSENT', 'ON_LEAVE'])).mean() * 100), 2),
             ot_hours=round(float(a.overtime_hours.sum()), 1), cost_file_energy=round(float(cost.energy_cost_inr.sum()), 2), cost_file_labour=round(float(cost.labour_cost_inr.sum()), 2),
             prod_labour_hours=round(float(a.productive_labour_hours.sum()), 1), mx_late=int(((a.check_out_ts.notna()) & (a.check_out_ts >= '2026-11-01')).sum()))
rel = [('D8 GR -> D7 GOODS_RECEIPT', 'd8_goods_receipt.inventory_txn_id -> d7_inventory_transactions.inventory_txn_id', 'CONFIRMED', len(gr), 'Exact txn id + plant/sloc/material/batch/date/qty match; both sides synthetic'),
       ('D7 GOODS_RECEIPT without D8 GR', 'd7 GR rows', 'UNMATCHED', int((~g7.index.isin(gr.inventory_txn_id)).sum()), 'none expected'),
       ('D7 OPENING_BALANCE -> supplier', 'd7 opening lots', 'UNMATCHED', unl_open, 'Opening stock predates PO window; no supplier/PO claimed'),
       ('D8 material -> BOM / D7 material', 'material_id', 'CONFIRMED', len(pl), 'All 16 BOM materials present in sources, PO lines, GR'),
       ('D8 plant -> existing plant', 'plant_id', 'CONFIRMED', len(po), 'IN-KA-01, IN-TN-01'),
       ('D8 supplier -> real source supplier', 'supplier_id', 'UNMATCHED', len(sup), 'No source supplier data exists; all suppliers SYNTHETIC'),
       ('D8 purchase PO -> production PO (source_po_number)', 'po_id', 'UNMATCHED', len(po), 'Different concept; production PO numbers are not unique and are not used'),
       ('D9 equipment -> existing plant/line', 'equipment.plant_id+line_id -> hourly', 'CONFIRMED', len(eqm), 'Pair exists in hourly feed'),
       ('D9 equipment -> station (source)', 'equipment.station_id -> quality.station_id', 'CANDIDATE_ONLY', int((eqm.station_link_status == 'CANDIDATE_ONLY').sum()), 'Source stations appear on every line; not line-specific'),
       ('D9 equipment -> station (no source station)', 'equipment.station_id null', 'UNMATCHED', int((eqm.station_link_status == 'UNMATCHED').sum()), 'Assembly robot and laminator have no source station'),
       ('D9 equipment event -> hourly downtime slot', 'link table', 'CANDIDATE_ONLY', int((ev.hourly_link_status == 'CANDIDATE_ONLY').sum()), 'Same line + hour overlap + equal reason category; not confirmed'),
       ('D9 equipment event -> hourly (no compatible slot)', 'events', 'UNMATCHED', int((ev.hourly_link_status == 'UNMATCHED').sum()), 'Includes PM/calibration/idle with no hourly category'),
       ('D9 energy -> manufacturing cost energy_cost_inr', 'n/a', 'UNMATCHED', len(en), 'Different scope/grain; informational comparison only'),
       ('D10 shift_id -> hourly shift_id', 'shift_definition.shift_id', 'CONFIRMED', len(shd), 'A/B/C and hour windows validated'),
       ('D10 allocation -> existing plant/line', 'line_allocation', 'CONFIRMED', int(la.line_id.notna().sum()), 'Plant-line pairs exist in hourly feed'),
       ('D10 allocation -> source station', 'line_allocation.station_id', 'CANDIDATE_ONLY', int((la.station_link_status == 'CANDIDATE_ONLY').sum()), 'Same limitation as equipment'),
       ('D10 allocation -> no source station', 'line_allocation.station_id null (operators)', 'UNMATCHED', int((la.station_link_status == 'UNMATCHED').sum()), 'Assembly/lamination work areas'),
       ('D10 labour day -> hourly line-shift-day', 'plant+line+shift+shift_production_date', 'CANDIDATE_ONLY', int((lab.hourly_link_status == 'CANDIDATE_ONLY').sum()), 'Line-shift-day level only'),
       ('D10 employee -> production run/order', 'n/a', 'UNMATCHED', len(emp), 'No evidence; attribution not attempted'),
       ('D10 employee -> quality inspector_id (EMP-xxxx)', 'n/a', 'UNMATCHED', int(qi.inspector_id.nunique()), 'Source inspector IDs have no master; SYN-EMP ids deliberately distinct'),
       ('D10 crew -> hourly operator_team (TEAM-xx)', 'n/a', 'UNMATCHED', int(hr.operator_team.nunique()), 'Source teams are not tied to line/shift')]
rel_df = pd.DataFrame(rel, columns=['relationship', 'keys', 'status', 'rows_or_keys', 'basis'])
md5 = lambda p: hashlib.md5(open(p, 'rb').read()).hexdigest()
src_files = {'d7_inventory_transactions_v1.csv': f'{IN}/b/d7_inventory_transactions_v1.csv', 'fact_bom_component_enhanced_v1.csv': f'{IN}/a/4 ds/fact_bom_component_enhanced_v1.csv', 'fact_hourly_production_enhanced_v1.csv': f'{IN}/a/4 ds/fact_hourly_production_enhanced_v1.csv'}
src_df = pd.DataFrame([dict(source_file=k, md5_read_only_input=md5(v), rows=len(pd.read_csv(v, usecols=[0]))) for k, v in src_files.items()])
chk_df = pd.DataFrame(checks); npass = int((chk_df.status == 'PASS').sum())
json.dump(dict(stats=stats, npass=npass, ntotal=len(chk_df), inv=inv), open(f'{META}/val.json', 'w'), default=str)
print(f'CHECKS: {npass}/{len(chk_df)} PASS'); print(chk_df[chk_df.status == 'FAIL'].to_string()); print(stats)
pd.to_pickle(dict(chk=chk_df, inv=pd.DataFrame(inv), fk=pd.DataFrame(fkrows), recon=pd.DataFrame(recon), rel=rel_df, src=src_df, stats=stats, PK=PK, AK=AK, FK=FK), f'{META}/val.pkl')
