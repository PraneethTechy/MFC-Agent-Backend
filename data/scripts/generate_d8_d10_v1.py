"""Generate Datasets 8 (Procurement), 9 (Equipment/Energy), 10 (Workforce). Reads existing files read-only.
Usage: python generate_d8_d10_v1.py <input_dir_with_a_and_b> <output_dir>"""
import sys, os, json, math, random, datetime as dt
from bisect import bisect_left
import numpy as np, pandas as pd

IN = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/in'
OUT = sys.argv[2] if len(sys.argv) > 2 else '/mnt/user-data/outputs'
META = '/home/claude/work'; os.makedirs(META, exist_ok=True); os.makedirs(OUT, exist_ok=True)
SEED = 20261120; R = random.Random(SEED); NP = np.random.default_rng(SEED)
GV = 'GEN-D8D10-V1-20261120'; ORIG = 'GENERATED_SYNTHETIC'
D = dt.date; DT = dt.datetime; TD = dt.timedelta
iso = lambda x: x.strftime('%Y-%m-%dT%H:%M:%S')
d7 = pd.read_csv(f'{IN}/b/d7_inventory_transactions_v1.csv', low_memory=False)
bom = pd.read_csv(f'{IN}/a/4 ds/fact_bom_component_enhanced_v1.csv')
hr = pd.read_csv(f'{IN}/a/4 ds/fact_hourly_production_enhanced_v1.csv', low_memory=False)
LINES = [('IN-KA-01', 'SMT-L2', 'SMT'), ('IN-KA-01', 'FAL-L2', 'FAL'), ('IN-TN-01', 'SMT-L1', 'SMT'), ('IN-TN-01', 'FAL-L1', 'FAL')]
assert set((p, l) for p, l, _ in LINES) == set(map(tuple, hr[['plant_id', 'line_id']].drop_duplicates().values))
meta = {'anomalies': []}
def save(df, name):
    df.to_csv(f'{OUT}/{name}.csv', index=False); return df

# =====================================================================  DATASET 8
SUP = {  # id: name,country,ccy,category,tier,lead_days,on_time_prob,base_reject_rate,terms,incoterm
 'S01': ('Aurex Silicon Ltd', 'TW', 'USD', 'SEMICONDUCTOR', 'STRATEGIC', 35, .86, .0020, 60, 'FCA'),
 'S02': ('Brightvale Memory Co', 'KR', 'USD', 'MEMORY', 'STRATEGIC', 30, .90, .0015, 60, 'FCA'),
 'S03': ('Cobalt Circuits Pvt Ltd', 'IN', 'INR', 'PCB', 'PREFERRED', 18, .93, .0040, 45, 'DAP'),
 'S04': ('Evergleam Display Corp', 'CN', 'USD', 'DISPLAY', 'STRATEGIC', 28, .88, .0060, 60, 'FCA'),
 'S05': ('Fernpower Cells Ltd', 'CN', 'USD', 'BATTERY', 'STRATEGIC', 25, .84, .0050, 45, 'FCA'),
 'S06': ('Glimmer Optics Co', 'CN', 'USD', 'CAMERA', 'PREFERRED', 28, .89, .0040, 60, 'FCA'),
 'S07': ('Hartwell Acoustics Pvt Ltd', 'IN', 'INR', 'ACOUSTIC', 'APPROVED', 14, .95, .0030, 30, 'DAP'),
 'S08': ('Ironleaf Precision Parts', 'IN', 'INR', 'MECHANICAL_RF', 'PREFERRED', 16, .92, .0050, 45, 'DAP'),
 'S09': ('Jadeglass Technologies', 'CN', 'USD', 'GLASS', 'PREFERRED', 26, .87, .0080, 60, 'FCA'),
 'S10': ('Kestrel Connect Pvt Ltd', 'IN', 'INR', 'CONNECTOR_CABLE', 'APPROVED', 15, .94, .0030, 30, 'DAP'),
 'S11': ('Lumen Pack Industries', 'IN', 'INR', 'PACKAGING', 'APPROVED', 10, .96, .0020, 30, 'DAP'),
 'S12': ('Mosaic Fasteners Pvt Ltd', 'IN', 'INR', 'FASTENER', 'APPROVED', 8, .97, .0010, 30, 'DAP'),
 'S13': ('Northbeam Silicon Trading', 'VN', 'USD', 'SEMICONDUCTOR', 'APPROVED', 40, .78, .0040, 60, 'FCA'),
 'S14': ('Orchid Display Systems', 'KR', 'USD', 'DISPLAY', 'APPROVED', 32, .85, .0050, 60, 'FCA'),
 'S15': ('Pinewood Energy Cells', 'IN', 'INR', 'BATTERY', 'APPROVED', 20, .90, .0040, 45, 'DAP')}
SID = {k: f'SUP-SYN-{int(k[1:]):03d}' for k in SUP}
PRIM = {'MAT-SOC-001': 'S01', 'MAT-MEM-002': 'S02', 'MAT-NAND-003': 'S02', 'MAT-PCB-004': 'S03', 'MAT-DSP-005': 'S04', 'MAT-BAT-006': 'S05',
        'MAT-CAM-007': 'S06', 'MAT-CAM-008': 'S06', 'MAT-HSG-009': 'S08', 'MAT-GLS-010': 'S09', 'MAT-SPK-011': 'S07', 'MAT-ANT-012': 'S08',
        'MAT-CON-013': 'S10', 'MAT-BOX-014': 'S11', 'MAT-CBL-015': 'S10', 'MAT-SCR-016': 'S12'}
ALT = {'MAT-SOC-001': 'S13', 'MAT-DSP-005': 'S14', 'MAT-BAT-006': 'S15'}
DEFECTS = {'SEMICONDUCTOR': ['SOLDERABILITY_FAIL', 'LEAD_COPLANARITY', 'MARKING_ERROR'], 'MEMORY': ['FUNCTIONAL_FAIL', 'MARKING_ERROR', 'PACKAGE_DAMAGE'],
           'PCB': ['WARPAGE', 'PLATING_DEFECT', 'DIMENSION_OOT'], 'DISPLAY': ['DEAD_PIXEL', 'MURA_DEFECT', 'BACKLIGHT_UNIFORMITY'],
           'BATTERY': ['CAPACITY_LOW', 'SWELLING', 'TERMINAL_DAMAGE'], 'CAMERA': ['FOCUS_FAIL', 'DUST_IN_MODULE', 'ALIGNMENT_OOT'],
           'ACOUSTIC': ['SENSITIVITY_OOT', 'MESH_DAMAGE', 'DIMENSION_OOT'], 'MECHANICAL_RF': ['DIMENSION_OOT', 'SURFACE_SCRATCH', 'PLATING_DEFECT'],
           'GLASS': ['SCRATCH', 'EDGE_CHIP', 'COATING_DEFECT'], 'CONNECTOR_CABLE': ['PIN_BENT', 'CONTINUITY_FAIL', 'DIMENSION_OOT'],
           'PACKAGING': ['PRINT_DEFECT', 'DIMENSION_OOT', 'DAMAGED_CARTON'], 'FASTENER': ['THREAD_DEFECT', 'PLATING_DEFECT', 'DIMENSION_OOT']}
FX = 88.00  # INR per USD - synthetic assumption, not a market rate
CAT_OF = lambda sup: SUP[sup][3]
sup_df = pd.DataFrame([dict(supplier_id=SID[k], supplier_name=v[0] + ' (SYNTHETIC)', supplier_country=v[1], supplier_category=v[3], supplier_tier=v[4],
        supplier_currency=v[2], payment_terms_days=v[8], standard_lead_time_days=v[5], supplier_status='ACTIVE', approved_plants='IN-KA-01;IN-TN-01',
        is_synthetic='Y', source_supplier_match_status='UNMATCHED_NO_SOURCE_SUPPLIER_DATA', record_origin=ORIG, generation_version=GV) for k, v in SUP.items()])
bom_mats = set(bom.material_id)
sl_rows = []
for m, s in PRIM.items():
    assert m in bom_mats
    sl_rows.append((s, m, 'PRIMARY', 75 if m in ALT else 100))
    if m in ALT: sl_rows.append((ALT[m], m, 'SECONDARY', 25))
sl_df = pd.DataFrame([dict(source_list_id=f'SRC-SYN-{i + 1:03d}', supplier_id=SID[s], material_id=m, source_rank=r, planned_share_pct=sh,
        material_in_bom_flag='Y', approval_status='APPROVED', record_origin=ORIG, generation_version=GV) for i, (s, m, r, sh) in enumerate(sl_rows)])

gr = d7[d7.transaction_type == 'GOODS_RECEIPT'].sort_values(['plant_id', 'material_id', 'transaction_ts']).reset_index(drop=True)
assert len(gr) == 346 and gr.groupby('material_id').storage_location_id.nunique().max() == 1
SLOC = gr.groupby('material_id').storage_location_id.first().to_dict()
gdate = gr.transaction_date.map(D.fromisoformat)
def delay_for(sup, plant, d):
    ot = SUP[sup][6]
    if sup == 'S01' and plant == 'IN-KA-01' and d >= D(2026, 10, 1): ot = .40      # injected
    if sup == 'S05' and plant == 'IN-TN-01' and d >= D(2026, 9, 1): ot = .55        # injected
    if R.random() < ot: return R.choice([0] * 10 + [-1, -1, -2, -3])
    base = R.choice([1, 1, 2, 2, 3, 4, 5, 7]) + (R.choice([0, 1, 2]) if SUP[sup][1] != 'IN' else 0)
    if sup == 'S01' and plant == 'IN-KA-01' and d >= D(2026, 10, 1): base = R.randint(4, 9)
    return base
def reject_for(sup, plant, d, acc):
    p, lo, hi = .14, 1, 5
    if sup == 'S05' and plant == 'IN-TN-01' and d >= D(2026, 9, 1): p, lo, hi = .50, 4, 12   # injected
    if R.random() >= p: return 0
    rate = SUP[sup][7] * R.uniform(lo, hi)
    return int(math.ceil(max(100, rate * acc) / 10) * 10)
L = []
for (pl, mat), g in gr.groupby(['plant_id', 'material_id'], sort=True):
    ix = list(g.index); i = 0
    while i < len(ix):
        n = 2 if (i + 1 < len(ix) and R.random() < .12 and (gdate[ix[i + 1]] - gdate[ix[i]]).days <= 14) else 1
        sup = ALT[mat] if (mat in ALT and R.random() < .25) else PRIM[mat]
        L.append(dict(plant=pl, mat=mat, sup=sup, ix=ix[i:i + n], open=False)); i += n
for ln in L:
    ln['grs'] = []
    for j in ln['ix']:
        act = gdate[j]; dl = delay_for(ln['sup'], ln['plant'], act)
        prom = act - TD(days=dl); req = prom - TD(days=R.choice([0, 0, 0, 0, 1, 2]))
        acc = int(gr.qty_in[j]); rej = reject_for(ln['sup'], ln['plant'], act, acc)
        ln['grs'].append(dict(j=j, act=act, prom=prom, req=req, acc=acc, rej=rej, rec=acc + rej, price=float(gr.unit_value_inr[j])))
    rec = sum(x['rec'] for x in ln['grs']); u = R.random()
    if u < .08: f = R.uniform(.93, .96); ln['ordered'] = int(round(rec / f / 10) * 10); ln['status'] = 'CLOSED_SHORT'; ln['sc'] = R.choice(['SUPPLIER_SHORT_SHIPMENT_BALANCE_CANCELLED', 'PARTIAL_REJECT_NOT_REPLACED'])
    elif u < .14: f = R.uniform(1.005, 1.03); ln['ordered'] = int(round(rec / f / 10) * 10); ln['status'] = 'CLOSED_RECEIVED'; ln['sc'] = ''
    else: ln['ordered'] = rec; ln['status'] = 'CLOSED_RECEIVED'; ln['sc'] = ''
for pl in ['IN-KA-01', 'IN-TN-01']:           # one open (not yet received) line per plant-material, due after the window
    for mat in sorted(PRIM):
        sub = gr[(gr.plant_id == pl) & (gr.material_id == mat)]; sup = PRIM[mat]
        po = D(2026, 10, R.randint(10, 30)); req = max(po + TD(days=SUP[sup][5] + R.randint(0, 3)), D(2026, 11, 1) + TD(days=R.randint(0, 6)))
        L.append(dict(plant=pl, mat=mat, sup=sup, open=True, grs=[dict(req=req, prom=req + TD(days=R.choice([0, 0, 1, 2])), act=None, acc=0, rej=0, rec=0,
                 price=round(float(sub.unit_value_inr.mean()) * R.uniform(.98, 1.03), 2))], ordered=int(round(sub.qty_in.mean() / 100) * 100), status='OPEN', sc='', po_pref=po))
hk = {}
for ln in L:
    f = ln['grs'][0]
    if ln['open']: raw = ln['po_pref']
    else: raw = f['req'] - TD(days=max(5, SUP[ln['sup']][5] + R.randint(-2, 3)))
    mon = raw - TD(days=raw.weekday()); ln['hkey'] = (mon, ln['plant'], ln['sup']); hk.setdefault(ln['hkey'], []).append(ln)
hdr, pol, grr, qlt = [], [], [], []
gcount = 0
for hn, key in enumerate(sorted(hk), 1):
    po_id = f'PUR-PO-{hn:06d}'; mon, pl, sup = key; lns = sorted(hk[key], key=lambda x: (x['grs'][0]['req'], x['mat']))
    ccy = SUP[sup][2]; fx = FX if ccy == 'USD' else 1.0; tot = 0
    for k, ln in enumerate(lns, 1):
        f = ln['grs'][0]; lid = f'{po_id}-{k * 10:03d}'; price = f['price']; ordv = round(ln['ordered'] * price, 2); tot += ordv
        rec = sum(x['rec'] for x in ln['grs']); acc = sum(x['acc'] for x in ln['grs']); rej = sum(x['rej'] for x in ln['grs'])
        dl = None if ln['open'] else (f['act'] - f['prom']).days
        ots = 'OPEN_NOT_DUE' if ln['open'] else ('LATE' if dl > 0 else 'EARLY' if dl <= -2 else 'ON_TIME')
        pol.append(dict(po_line_id=lid, po_id=po_id, line_number=k * 10, plant_id=pl, storage_location_id=SLOC[ln['mat']], supplier_id=SID[sup], material_id=ln['mat'], uom='EA',
            ordered_qty=ln['ordered'], received_qty_total=rec, accepted_qty_total=acc, rejected_qty_total=rej, open_qty=max(ln['ordered'] - rec, 0) if ln['open'] else 0,
            delivery_variance_qty=None if ln['open'] else rec - ln['ordered'], line_status=ln['status'], short_close_reason=ln['sc'],
            over_delivery_flag='Y' if (not ln['open'] and rec > ln['ordered']) else 'N', unit_price_currency=ccy, unit_price=round(price / fx, 4), unit_price_inr=price,
            price_basis='ALIGNED_TO_D7_UNIT_VALUE_SYNTHETIC' if not ln['open'] else 'SYNTHETIC_MEAN_D7_UNIT_VALUE', ordered_value_inr=ordv,
            requested_delivery_date=f['req'].isoformat(), promised_delivery_date=f['prom'].isoformat(),
            first_receipt_date=None if ln['open'] else f['act'].isoformat(), last_receipt_date=None if ln['open'] else ln['grs'][-1]['act'].isoformat(),
            planned_lead_time_days=(f['req'] - mon).days, actual_lead_time_days=None if ln['open'] else (f['act'] - mon).days, gr_count=0 if ln['open'] else len(ln['grs']),
            on_time_status=ots, days_late=dl, record_origin=ORIG, generation_version=GV))
        for q, x in enumerate(ln['grs'], 1):
            if ln['open']: continue
            gcount += 1; gid = f'PUR-GR-{gcount:05d}'; row = gr.loc[x['j']]; dl2 = (x['act'] - x['prom']).days
            accv = round(x['acc'] * x['price'], 2)
            grr.append(dict(gr_id=gid, po_line_id=lid, po_id=po_id, delivery_seq=q, inventory_txn_id=row.inventory_txn_id, d7_reference_id=row.reference_id, plant_id=pl,
                storage_location_id=row.storage_location_id, material_id=ln['mat'], material_batch_id=row.material_batch_id, supplier_id=SID[sup],
                gr_posting_ts=row.transaction_ts, actual_delivery_date=x['act'].isoformat(), gr_requested_date=x['req'].isoformat(), gr_promised_date=x['prom'].isoformat(),
                days_late=dl2, on_time_status='LATE' if dl2 > 0 else 'EARLY' if dl2 <= -2 else 'ON_TIME', on_time_vs_requested='Y' if x['act'] <= x['req'] else 'N',
                lead_time_days_actual=(x['act'] - mon).days, received_qty=x['rec'], accepted_qty=x['acc'], rejected_qty=x['rej'], d7_posted_qty_in=int(row.qty_in),
                qty_reconciliation_check='MATCH' if x['acc'] == int(row.qty_in) else 'MISMATCH', po_unit_price_inr=price, unit_price_inr=x['price'],
                price_variance_inr=round((x['price'] - price) * x['acc'], 2), accepted_value_inr=accv, d7_line_value_inr=float(row.line_value_inr),
                value_diff_inr=round(accv - float(row.line_value_inr), 2), receipt_status='POSTED_FULL' if x['rej'] == 0 else 'POSTED_ACCEPTED_PORTION_ONLY',
                quality_status='ACCEPTED' if x['rej'] == 0 else 'ACCEPTED_PARTIAL_REJECT', d7_link_status='CONFIRMED',
                d7_link_basis='EXACT_TXN_ID+PLANT+SLOC+MATERIAL+BATCH+DATE+QTY(accepted=qty_in)', record_origin=ORIG, generation_version=GV))
            rate = x['rej'] / x['rec']
            if x['rej'] > 0:
                sd = max(1, int(round(rate * 500 * R.uniform(.7, 1.3)))); res = 'PARTIAL_REJECT'; sev = 'CRITICAL' if rate > .03 else 'MAJOR'
                disp = R.choice(['RETURN_TO_SUPPLIER', 'RETURN_TO_SUPPLIER', 'QUARANTINE_PENDING_RETURN']); scar = 'Y' if rate > .01 else 'N'
            else:
                sd = 0 if R.random() < .88 else R.randint(1, 2); res = 'ACCEPT' if sd == 0 else 'ACCEPT_WITH_DEVIATION'; sev = 'NONE' if sd == 0 else 'MINOR'; disp = 'NONE'; scar = 'N'
            pts = DT.fromisoformat(row.transaction_ts); its = max(pts - TD(minutes=R.randint(30, 150)), DT.combine(pts.date(), dt.time(0)))
            qlt.append(dict(quality_id=f'PUR-QR-{gcount:05d}', gr_id=gid, plant_id=pl, supplier_id=SID[sup], material_id=ln['mat'], material_batch_id=row.material_batch_id,
                inspection_ts=iso(its), inspection_type='INCOMING_AQL', lot_size_qty=x['rec'], sample_size=500, sample_defects=sd, sample_defect_rate_pct=round(sd / 5, 2),
                primary_defect_code='NONE' if sd == 0 else R.choice(DEFECTS[CAT_OF(sup)]), severity=sev, inspection_result=res, rejected_qty=x['rej'],
                reject_ppm=int(round(rate * 1e6)), disposition=disp, scar_raised=scar, record_origin=ORIG, generation_version=GV))
    sts = {x['line_status'] for x in pol if x['po_id'] == po_id}
    hdr.append(dict(po_id=po_id, supplier_id=SID[sup], plant_id=pl, po_date=mon.isoformat(), po_currency=ccy, fx_rate_to_inr=fx, payment_terms_days=SUP[sup][8], incoterm=SUP[sup][9],
        po_status='OPEN' if sts == {'OPEN'} else 'PARTIALLY_RECEIVED' if 'OPEN' in sts else 'CLOSED', line_count=len(lns), total_ordered_value_inr=round(tot, 2),
        is_synthetic='Y', related_production_po_link_status='NOT_APPLICABLE_PURCHASE_PO_NOT_PRODUCTION_PO', record_origin=ORIG, generation_version=GV))
po_h = pd.DataFrame(hdr); po_l = pd.DataFrame(pol); gr_df = pd.DataFrame(grr); q_df = pd.DataFrame(qlt)
meta['anomalies'] += [dict(dataset='D8', pattern='Supplier SUP-SYN-001 (S01) to IN-KA-01 on-time probability cut to 0.40 and delays 4-9 days from 2026-10-01'),
                      dict(dataset='D8', pattern='Supplier SUP-SYN-005 (S05) to IN-TN-01 from 2026-09-01: lot reject probability 0.50 (vs 0.14), reject rate 4-12x base, on-time prob 0.55')]
for n, df in [('d8_supplier_master_v1', sup_df), ('d8_supplier_material_source_list_v1', sl_df), ('d8_po_header_v1', po_h), ('d8_po_line_v1', po_l),
              ('d8_goods_receipt_v1', gr_df), ('d8_supplier_quality_v1', q_df)]: save(df, n)

# =====================================================================  DATASET 9
T0 = DT(2026, 8, 1); T1 = DT(2026, 11, 1); TOT = int((T1 - T0).total_seconds() // 60); ASOF = D(2026, 10, 31)
# type, station, kw, idle_f, unplanned_f, planned_f, lam/day, repair_median_min, criticality, pm_min, changeover_sensitive, calibrated
CATALOG = {'SMT': [('STENCIL_PRINTER', 'ST-SMT-010', 3.0, .35, .10, .05, .45, 25, 'MEDIUM', 90, 1, 0), ('SPI_3D', 'ST-SMT-020', 1.5, .40, .10, .05, .35, 20, 'MEDIUM', 60, 0, 1),
        ('CHIP_SHOOTER', 'ST-SMT-030', 9.0, .30, .10, .05, .70, 30, 'HIGH', 180, 1, 0), ('FLEX_MOUNTER', 'ST-SMT-040', 7.5, .30, .10, .05, .65, 30, 'HIGH', 180, 1, 0),
        ('REFLOW_OVEN', 'ST-SMT-050', 24.0, .65, .35, .30, .35, 45, 'HIGH', 240, 0, 0), ('AOI', 'ST-SMT-060', 2.0, .40, .10, .05, .30, 20, 'MEDIUM', 60, 0, 1),
        ('UNDERFILL_DISPENSER', 'ST-SMT-070', 3.5, .40, .10, .05, .40, 25, 'MEDIUM', 90, 0, 0), ('XRAY_INSPECTION', 'ST-SMT-080', 4.0, .35, .10, .05, .28, 35, 'MEDIUM', 90, 0, 1)],
    'FAL': [('ASSEMBLY_ROBOT_CELL', None, 4.5, .30, .10, .05, .65, 25, 'HIGH', 120, 1, 0), ('DISPLAY_LAMINATOR', None, 6.5, .35, .10, .05, .42, 40, 'HIGH', 150, 1, 0),
        ('RF_TEST_CHAMBER', 'ST-TST-010', 2.5, .40, .10, .05, .38, 25, 'MEDIUM', 60, 0, 1), ('CAMERA_TEST_STATION', 'ST-TST-020', 1.8, .40, .10, .05, .38, 20, 'MEDIUM', 60, 0, 1),
        ('DISPLAY_TEST_STATION', 'ST-TST-030', 1.6, .40, .10, .05, .35, 20, 'MEDIUM', 60, 0, 1), ('BURN_IN_CHAMBER', 'ST-TST-040', 12.0, .70, .30, .25, .25, 50, 'MEDIUM', 120, 0, 0),
        ('AUDIO_FUNCTIONAL_TEST', 'ST-TST-050', 1.4, .40, .10, .05, .38, 20, 'LOW', 60, 0, 1), ('FINAL_QA_PACK_STATION', 'ST-QA-010', 2.2, .40, .10, .05, .42, 20, 'MEDIUM', 60, 1, 0)]}
GEN = [('SENSOR_FAULT', 'EQUIPMENT_FAULT', 3), ('SOFTWARE_HANG', 'EQUIPMENT_FAULT', 2), ('CONVEYOR_JAM', 'MICRO_STOP', 3), ('OPERATOR_ADJUSTMENT', 'MICRO_STOP', 2), ('POWER_DIP_TRIP', 'EQUIPMENT_FAULT', 1)]
FEED = [('FEEDER_JAM', 'FEEDER_JAM', 8), ('NOZZLE_CLOG', 'FEEDER_JAM', 4), ('VISION_ALIGN_ERROR', 'EQUIPMENT_FAULT', 3)]
VIS = [('CAMERA_VISION_FAULT', 'EQUIPMENT_FAULT', 4), ('CALIBRATION_DRIFT', 'EQUIPMENT_FAULT', 3)]
TST = [('FIXTURE_CONTACT_FAULT', 'EQUIPMENT_FAULT', 6), ('CALIBRATION_DRIFT', 'EQUIPMENT_FAULT', 3)]
TEMP = [('TEMPERATURE_ZONE_EXCURSION', 'EQUIPMENT_FAULT', 5)]
EXTRA = {'STENCIL_PRINTER': [('STENCIL_CLEANING_FAULT', 'EQUIPMENT_FAULT', 4), ('SQUEEGEE_PRESSURE_ALARM', 'EQUIPMENT_FAULT', 3)], 'CHIP_SHOOTER': FEED, 'FLEX_MOUNTER': FEED,
         'REFLOW_OVEN': TEMP + [('CHAIN_CONVEYOR_FAULT', 'EQUIPMENT_FAULT', 3)], 'BURN_IN_CHAMBER': TEMP, 'SPI_3D': VIS, 'AOI': VIS, 'XRAY_INSPECTION': VIS,
         'UNDERFILL_DISPENSER': [('DISPENSE_NOZZLE_CLOG', 'FEEDER_JAM', 5)], 'ASSEMBLY_ROBOT_CELL': [('SCREW_FEEDER_JAM', 'FEEDER_JAM', 8), ('GRIPPER_FAULT', 'EQUIPMENT_FAULT', 4)],
         'DISPLAY_LAMINATOR': [('VACUUM_LEAK', 'EQUIPMENT_FAULT', 4), ('ADHESIVE_DISPENSE_FAULT', 'EQUIPMENT_FAULT', 4)], 'RF_TEST_CHAMBER': TST, 'CAMERA_TEST_STATION': TST,
         'DISPLAY_TEST_STATION': TST, 'AUDIO_FUNCTIONAL_TEST': TST, 'FINAL_QA_PACK_STATION': [('LABEL_PRINTER_FAULT', 'EQUIPMENT_FAULT', 3), ('SCANNER_FAULT', 'EQUIPMENT_FAULT', 3)]}
IDLE = [('STARVED_NO_MATERIAL', 'NO_MATERIAL', 40), ('BLOCKED_DOWNSTREAM', 'IDLE_OTHER', 30), ('NO_SCHEDULE_OR_DEMAND', 'IDLE_OTHER', 20), ('WAITING_FOR_OPERATOR', 'IDLE_OTHER', 10)]
def wchoice(lst): return R.choices(lst, weights=[x[2] for x in lst])[0]
def shift_of(ts):
    h = ts.hour; s = 'A' if 6 <= h < 14 else 'B' if 14 <= h < 22 else 'C'
    return s, (ts.date() - TD(days=1) if (s == 'C' and h < 6) else ts.date())
def place(S, E, s, e):
    i = bisect_left(S, s)
    if i > 0 and E[i - 1] > s: return False
    if i < len(S) and S[i] < e: return False
    S.insert(i, s); E.insert(i, e); return True
eq_rows, ev = [], []; poisson = lambda lam: int(NP.poisson(lam))
changeovers = {l: sorted(R.randint(0, TOT - 60) for _ in range(40)) for _, l, _ in LINES}
all_eq = []
for pl, ln, lt in LINES:
    for k, c in enumerate(CATALOG[lt], 1):
        all_eq.append(dict(id=f'EQ-{ln}-{k:02d}', meter=f'EM-{ln}-{k:02d}', plant=pl, line=ln, lt=lt, seq=k, c=c))
deferred = set(R.sample([e['id'] for e in all_eq if e['c'][8] != 'LOW'], 2))
maint = []
def add_ev(e, s, d, typ, reason, cat, mk=None, micro=False):
    ev.append(dict(eq=e, s=s, d=d, typ=typ, reason=reason, cat=cat, micro=micro, mk=mk)); return ev[-1]
for e in all_eq:
    ty, st, kw, idf, unf, plf, lam, med, crit, pmm, cos, cal = e['c']; S, E = [], []
    for mi, (mstart, mend) in enumerate([(3, 26), (34, 57), (65, 88)]):          # monthly PM windows (day offsets from Aug 1)
        day = R.randint(mstart, mend)
        if e['id'] in deferred and mi == 2:
            maint.append(dict(eq=e, typ='PREVENTIVE', status='DEFERRED', sched=T0 + TD(days=day, hours=9), ev=None, reason=None)); continue
        s = day * 1440 + R.randint(8, 11) * 60 + R.choice([0, 15, 30, 45]); d = int(pmm * R.uniform(.85, 1.2))
        if place(S, E, s, s + d):
            x = add_ev(e, s, d, 'PLANNED_DOWNTIME', 'PREVENTIVE_MAINTENANCE', 'MAINTENANCE_PLANNED'); maint.append(dict(eq=e, typ='PREVENTIVE', status='COMPLETED', ev=x, reason=None))
    if cal:
        s = R.randint(10, 80) * 1440 + 13 * 60; d = R.randint(45, 75)
        if place(S, E, s, s + d):
            x = add_ev(e, s, d, 'PLANNED_DOWNTIME', 'CALIBRATION', 'MAINTENANCE_PLANNED'); maint.append(dict(eq=e, typ='CALIBRATION', status='COMPLETED', ev=x, reason=None))
    if cos:
        for c0 in changeovers[e['line']]:
            s = c0 + R.randint(0, 3); d = R.randint(15, 45)
            if s + d < TOT and place(S, E, s, s + d): add_ev(e, s, d, 'PLANNED_DOWNTIME', 'MODEL_CHANGEOVER', 'CHANGEOVER')
    reasons = GEN + EXTRA[ty]; n = poisson(lam * 92)
    for _ in range(n):
        if R.random() < .35: d = R.randint(1, 5); rs, ct, micro = 'MICRO_STOP', 'MICRO_STOP', True
        else: rs, ct, _w = wchoice(reasons); d = int(min(360, max(10, R.lognormvariate(math.log(med), .8)))); micro = False
        for _t in range(8):
            s = R.randint(0, TOT - d - 1)
            if place(S, E, s, s + d): add_ev(e, s, d, 'UNPLANNED_DOWNTIME', rs, ct, micro=micro); break
    for _ in range(poisson(18)):
        rs, ct, _w = wchoice(IDLE); d = R.randint(10, 150)
        for _t in range(6):
            s = R.randint(0, TOT - d - 1)
            if place(S, E, s, s + d): add_ev(e, s, d, 'IDLE', rs, ct); break
    e['S'], e['E'] = S, E
def inject(eid, n, lo, hi, reason, cat, dlo, dhi):
    e = next(x for x in all_eq if x['id'] == eid); k = 0
    for _ in range(n * 4):
        if k >= n: break
        s = R.randint(lo, hi); d = R.randint(dlo, dhi)
        if place(e['S'], e['E'], s, s + d): add_ev(e, s, d, 'UNPLANNED_DOWNTIME', reason, cat); k += 1
inject('EQ-SMT-L2-05', 12, 40 * 1440, 51 * 1440, 'TEMPERATURE_ZONE_EXCURSION', 'EQUIPMENT_FAULT', 40, 120)
inject('EQ-SMT-L1-03', 25, 61 * 1440, 91 * 1440, 'FEEDER_JAM', 'FEEDER_JAM', 15, 60)
meta['anomalies'] += [dict(dataset='D9', pattern='EQ-SMT-L2-05 (reflow, IN-KA-01): 12 extra TEMPERATURE_ZONE_EXCURSION events 2026-09-10..09-20'),
                      dict(dataset='D9', pattern='EQ-SMT-L1-03 (chip shooter, IN-TN-01): 25 extra FEEDER_JAM events during October')]
ev.sort(key=lambda x: (x['eq']['id'], x['s']))
for i, x in enumerate(ev, 1): x['id'] = f'EQE-{i:06d}'
# corrective maintenance for unplanned non-micro >=20 min (60 %)
for x in ev:
    if x['typ'] == 'UNPLANNED_DOWNTIME' and not x['micro'] and x['d'] >= 20 and R.random() < .6:
        maint.append(dict(eq=x['eq'], typ='CORRECTIVE', status='COMPLETED', ev=x, reason=x['reason']))
mrows = []
for m in sorted(maint, key=lambda m: (m['eq']['id'], iso(T0 + TD(minutes=m['ev']['s'])) if m['ev'] else iso(m['sched']))):
    e = m['eq']
    if m['ev'] is None:
        mrows.append(dict(eq=e['id'], typ=m['typ'], st='DEFERRED', sched=iso(m['sched']), a0=None, a1=None, dur=None, ev=None, fr=None, parts='N', cost=0.0)); continue
    x = m['ev']; s = x['s'] + (R.randint(1, min(5, x['d'] - 1)) if m['typ'] == 'CORRECTIVE' else 0); a0 = T0 + TD(minutes=s); a1 = T0 + TD(minutes=x['s'] + x['d'])
    parts = 'Y' if (m['typ'] == 'CORRECTIVE' and R.random() < .35) else 'N'
    cost = round((x['d'] / 60) * 650 + (R.uniform(2000, 40000) if parts == 'Y' else 0) + (1500 if m['typ'] != 'CORRECTIVE' else 0), 2)
    mrows.append(dict(eq=e['id'], typ=m['typ'], st='COMPLETED', sched=None if m['typ'] == 'CORRECTIVE' else iso(T0 + TD(minutes=x['s'])), a0=iso(a0), a1=iso(a1),
                      dur=int((a1 - a0).total_seconds() // 60), ev=x['id'], fr=m['reason'], parts=parts, cost=cost)); x['maint_ref'] = len(mrows)
m_df = pd.DataFrame(mrows); m_df.insert(0, 'maintenance_id', [f'MNT-{i:06d}' for i in range(1, len(m_df) + 1)])
evid_to_m = dict(zip(m_df.ev, m_df.maintenance_id))
eq_of = {e['id']: e for e in all_eq}
m_df['repeat_failure_within_7d_flag'] = 'N'
c = m_df[m_df.typ == 'CORRECTIVE'].copy(); c['t0'] = pd.to_datetime(c.a0); c['t1'] = pd.to_datetime(c.a1)
for (eid, fr), g in c.groupby(['eq', 'fr']):
    g = g.sort_values('t0')
    for a, b in zip(g.index, g.index[1:]):
        if (g.loc[b, 't0'] - g.loc[a, 't1']).days < 7: m_df.loc[a, 'repeat_failure_within_7d_flag'] = 'Y'
m_out = pd.DataFrame(dict(maintenance_id=m_df.maintenance_id, equipment_id=m_df['eq'], plant_id=m_df['eq'].map(lambda i: eq_of[i]['plant']), line_id=m_df['eq'].map(lambda i: eq_of[i]['line']),
    maintenance_type=m_df.typ, work_order_status=m_df.st, scheduled_start_ts=m_df.sched, actual_start_ts=m_df.a0, actual_end_ts=m_df.a1, duration_min=m_df.dur,
    linked_downtime_event_id=m_df.ev, failure_reason_code=m_df.fr, parts_replaced_flag=m_df.parts, estimated_cost_inr=m_df.cost,
    repeat_failure_within_7d_flag=m_df.repeat_failure_within_7d_flag, status_after='RETURNED_TO_SERVICE', is_synthetic='Y', record_origin=ORIG, generation_version=GV))
m_out.loc[m_out.work_order_status == 'DEFERRED', 'status_after'] = 'NOT_APPLICABLE_DEFERRED'
# equipment master
last_pm = m_out[(m_out.maintenance_type == 'PREVENTIVE') & (m_out.work_order_status == 'COMPLETED')].groupby('equipment_id').actual_end_ts.max().str[:10].to_dict()
erows = []
for e in all_eq:
    ty, st, kw, idf, unf, plf, lam, med, crit, pmm, cos, cal = e['c']; lp = D.fromisoformat(last_pm[e['id']]); nd = lp + TD(days=30)
    ms = 'OVERDUE' if nd < ASOF else 'DUE_WITHIN_7D' if nd <= ASOF + TD(days=7) else 'CURRENT'
    erows.append(dict(equipment_id=e['id'], equipment_type=ty, process_stage=e['lt'], plant_id=e['plant'], line_id=e['line'], line_type=e['lt'], sequence_in_line=e['seq'], station_id=st,
        line_link_status='CONFIRMED', station_link_status='CANDIDATE_ONLY' if st else 'UNMATCHED', energy_meter_id=e['meter'], rated_power_kw=kw, idle_power_factor=idf,
        unplanned_down_power_factor=unf, planned_down_power_factor=plf, criticality=crit, commissioning_year=R.randint(2022, 2025), pm_interval_days=30, last_pm_date=lp.isoformat(),
        next_pm_due_date=nd.isoformat(), maintenance_status=ms, maintenance_status_as_of=ASOF.isoformat(), is_synthetic='Y', record_origin=ORIG, generation_version=GV))
eq_df = pd.DataFrame(erows)
# hourly candidate links (read-only use of D4 hourly)
hr['_i'] = ((pd.to_datetime(hr.event_ts) - T0).dt.total_seconds() // 3600).astype(int)
H = {ln: g.sort_values('_i') for ln, g in hr.groupby('line_id')}
for ln, g in H.items(): assert g._i.tolist() == list(range(2208))
HD = {ln: (g.downtime_min.values, g.downtime_reason.values, g.event_id.values) for ln, g in H.items()}
erows2, lrows = [], []
for x in ev:
    e = x['eq']; s, d = x['s'], x['d']; st, sd = shift_of(T0 + TD(minutes=s)); links = []
    if x['cat'] in ('EQUIPMENT_FAULT', 'FEEDER_JAM', 'MICRO_STOP', 'CHANGEOVER', 'NO_MATERIAL'):
        dm, rs, ids = HD[e['line']]
        for hi in range(s // 60, (s + d - 1) // 60 + 1):
            if hi < 2208 and dm[hi] > 0 and rs[hi] == x['cat']:
                links.append((ids[hi], min(s + d, (hi + 1) * 60) - max(s, hi * 60), int(dm[hi])))
    x['links'] = links
    erows2.append(dict(event_id=x['id'], equipment_id=e['id'], plant_id=e['plant'], line_id=e['line'], station_id=e['c'][1], event_type=x['typ'],
        reason_code=x['reason'], reason_category=x['cat'], event_start_ts=iso(T0 + TD(minutes=s)), event_end_ts=iso(T0 + TD(minutes=s + d)), duration_min=d,
        start_shift_id=st, start_shift_production_date=sd.isoformat(), is_micro_stop='Y' if x['micro'] else 'N', maintenance_id=evid_to_m.get(x['id']),
        hourly_link_status='CANDIDATE_ONLY' if links else 'UNMATCHED', candidate_hourly_slot_count=len(links), is_synthetic='Y', record_origin=ORIG, generation_version=GV))
    for lid, ov, dmin in links: lrows.append(dict(equipment_event_id=x['id'], hourly_event_id=lid, line_id=e['line'], overlap_min=ov, hourly_slot_downtime_min=dmin,
        match_basis='SAME_LINE+TIME_OVERLAP+REASON_CATEGORY_EQUAL', link_status='CANDIDATE_ONLY',
        caveat='Hourly downtime_min has no intra-hour position and no equipment id; not confirmed'))
ev_df = pd.DataFrame(erows2); lk_df = pd.DataFrame(lrows); lk_df.insert(0, 'link_id', [f'EQL-{i:06d}' for i in range(1, len(lk_df) + 1)])
# energy readings per equipment x shift period
periods = []
for k in range(-1, 92):
    d0 = D(2026, 8, 1) + TD(days=k)
    for s, h0 in (('A', 6), ('B', 14), ('C', 22)):
        st = DT.combine(d0, dt.time(h0)); en = st + TD(hours=8); a = max(st, T0); b = min(en, T1)
        if b > a: periods.append((d0, s, int((a - T0).total_seconds() // 60), int((b - T0).total_seconds() // 60)))
TAR = {('IN-KA-01', 'A'): 8.20, ('IN-KA-01', 'B'): 9.60, ('IN-KA-01', 'C'): 7.10, ('IN-TN-01', 'A'): 7.80, ('IN-TN-01', 'B'): 9.10, ('IN-TN-01', 'C'): 6.80}
CODE = {'IDLE': 1, 'PLANNED_DOWNTIME': 2, 'UNPLANNED_DOWNTIME': 3}
erd = []; n = 0
evs_by = {}
for x in ev: evs_by.setdefault(x['eq']['id'], []).append(x)
for e in all_eq:
    arr = np.zeros(TOT, dtype=np.int8)
    for x in evs_by[e['id']]: arr[x['s']:x['s'] + x['d']] = CODE[x['typ']]
    kw, idf, unf, plf = e['c'][2], e['c'][3], e['c'][4], e['c'][5]; reg = float(R.randint(50000, 400000))
    for d0, s, a, b in periods:
        cnt = np.bincount(arr[a:b], minlength=4); w = b - a; n += 1
        kwh = round((cnt[0] * kw + cnt[1] * kw * idf + cnt[2] * kw * plf + cnt[3] * kw * unf) / 60 * float(NP.lognormal(0, .03)), 3); tar = TAR[(e['plant'], s)]
        erd.append(dict(reading_id=f'EN-{n:07d}', energy_meter_id=e['meter'], equipment_id=e['id'], plant_id=e['plant'], line_id=e['line'], shift_production_date=d0.isoformat(),
            shift_id=s, period_start_ts=iso(T0 + TD(minutes=a)), period_end_ts=iso(T0 + TD(minutes=b)), window_min=w, operating_min=int(cnt[0]), idle_min=int(cnt[1]),
            planned_downtime_min=int(cnt[2]), unplanned_downtime_min=int(cnt[3]), energy_kwh=kwh, meter_register_start_kwh=round(reg, 3), meter_register_end_kwh=round(reg + kwh, 3),
            tariff_inr_per_kwh=tar, estimated_energy_cost_inr=round(kwh * tar, 2), tariff_basis='SYNTHETIC_PLANT_SHIFT_TARIFF_ASSUMPTION',
            reading_basis='SYNTHETIC_MODEL_RATED_KW_X_STATE_MINUTES', is_synthetic='Y', record_origin=ORIG, generation_version=GV)); reg = round(reg + kwh, 3)
en_df = pd.DataFrame(erd)
for nme, df in [('d9_equipment_master_v1', eq_df), ('d9_equipment_event_v1', ev_df), ('d9_energy_reading_shift_v1', en_df), ('d9_maintenance_event_v1', m_out),
                ('d9_event_hourly_candidate_link_v1', lk_df)]: save(df, nme)

# =====================================================================  DATASET 10
SHIFTS = {'A': (6, 14), 'B': (14, 22), 'C': (22, 6)}; CYC = ['A', 'C', 'B']; BR = .5; SCH = 7.5
sh_df = pd.DataFrame([dict(shift_id=s, shift_name=f'Shift {s}', start_time=f'{a:02d}:00', end_time=f'{b:02d}:00', crosses_midnight='Y' if b < a else 'N', scheduled_punch_hours=8.0,
        break_minutes=30, scheduled_working_hours=SCH, shift_id_link_status='CONFIRMED', shift_window_basis='hour-to-shift mapping validated against hourly production feed',
        record_origin=ORIG, generation_version=GV) for s, (a, b) in SHIFTS.items()])
WD = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
FAL_AREAS = [0] * 6 + [1] * 3 + [2] * 2 + [3] * 2 + [4] * 2 + [5] * 2 + [6] * 2 + [7] * 3
ROLES = {'SMT': [('LINE_OPERATOR', 8), ('QUALITY_INSPECTOR', 1), ('MATERIAL_HANDLER', 1), ('EQUIPMENT_TECHNICIAN', 1), ('SUPERVISOR', 1)],
         'FAL': [('LINE_OPERATOR', 22), ('QUALITY_INSPECTOR', 3), ('MATERIAL_HANDLER', 2), ('EQUIPMENT_TECHNICIAN', 1), ('SUPERVISOR', 1)]}
DEPT = {'LINE_OPERATOR': 'PRODUCTION', 'QUALITY_INSPECTOR': 'QUALITY', 'MATERIAL_HANDLER': 'MATERIALS', 'EQUIPMENT_TECHNICIAN': 'MAINTENANCE', 'SUPERVISOR': 'PRODUCTION', 'PRODUCTION_MANAGER': 'MANAGEMENT'}
emps = []; eid = 0
def new_emp(**kw):
    global eid; eid += 1; kw.update(emp_id=f'SYN-EMP-{eid:06d}', idx=eid); emps.append(kw); return kw
mgr = {}
for pl in ['IN-KA-01', 'IN-TN-01']:
    mgr[pl] = new_emp(plant=pl, line=None, role='PRODUCTION_MANAGER', shift0='A', rot=False, slot=None, sup=None)
for pl, ln, lt in LINES:
    for s in 'ABC':
        sup_e = new_emp(plant=pl, line=ln, role='SUPERVISOR', shift0=s, rot=False, slot=0, sup=mgr[pl]['emp_id'], lt=lt)
        for role, cnt in ROLES[lt]:
            if role == 'SUPERVISOR': continue
            for k in range(cnt):
                if s != 'A' and role == 'LINE_OPERATOR' and k % 3 == 0: continue     # rotating slots created once (A triple) below
                if role == 'LINE_OPERATOR' and k % 3 == 0:
                    trio = [new_emp(plant=pl, line=ln, role=role, shift0=ss, rot=True, slot=k, sup=None, lt=lt) for ss in 'ABC']
                else: new_emp(plant=pl, line=ln, role=role, shift0=s, rot=False, slot=k, sup=None, lt=lt)
SUPV = {(e['line'], e['shift0']): e['emp_id'] for e in emps if e['role'] == 'SUPERVISOR'}
def shift_for(e, d): return CYC[(CYC.index(e['shift0']) + (d.month - 8)) % 3] if e['rot'] else e['shift0']
def area(e):
    r, k, lt = e['role'], e['slot'], e.get('lt')
    if r == 'LINE_OPERATOR':
        if lt == 'SMT': c = CATALOG['SMT'][k]
        else: c = CATALOG['FAL'][FAL_AREAS[k]]
        return c[1], c[0]
    if r == 'QUALITY_INSPECTOR': return ('ST-SMT-060', 'AOI') if lt == 'SMT' else ('ST-QA-010', 'FINAL_QA_PACK_STATION')
    return None, {'MATERIAL_HANDLER': 'MATERIAL_SUPPLY', 'EQUIPMENT_TECHNICIAN': 'LINE_MAINTENANCE', 'SUPERVISOR': 'LINE_SUPERVISION', 'PRODUCTION_MANAGER': 'PLANT_MANAGEMENT'}[r]
for e in emps: e['wo'] = (e['idx'] * 3) % 7 if e['role'] != 'PRODUCTION_MANAGER' else 6
emp_df = pd.DataFrame([dict(employee_id=e['emp_id'], employee_role=e['role'], department=DEPT[e['role']], plant_id=e['plant'], home_line_id=e['line'],
    employment_type=R.choices(['PERMANENT', 'CONTRACT'], [.7, .3])[0], grade=('G3' if e['role'] in ('SUPERVISOR', 'PRODUCTION_MANAGER') else 'G2' if e['role'] in ('EQUIPMENT_TECHNICIAN', 'QUALITY_INSPECTOR') else 'G1'),
    shift_pattern='ROTATING_MONTHLY' if e['rot'] else 'FIXED', initial_shift_id=e['shift0'], weekly_off_day=WD[e['wo']], hire_date=(D(2019, 1, 1) + TD(days=R.randint(0, 2760))).isoformat(),
    employment_status='ACTIVE', is_direct_labour='Y' if e['role'] == 'LINE_OPERATOR' else 'N', is_synthetic='Y', contains_personal_data='N', record_origin=ORIG, generation_version=GV) for e in emps])
MP = [(D(2026, 8, 1), D(2026, 8, 31)), (D(2026, 9, 1), D(2026, 9, 30)), (D(2026, 10, 1), D(2026, 10, 31))]
sa, la = [], []
for e in emps:
    plist = [(MP[i][0], MP[i][1], shift_for(e, MP[i][0])) for i in range(3)] if e['rot'] else [(MP[0][0], MP[2][1], e['shift0'])]
    for a, b, s in plist:
        sid = f'SAS-{len(sa) + 1:05d}'; st, wa = area(e)
        sa.append(dict(shift_assignment_id=sid, employee_id=e['emp_id'], plant_id=e['plant'], shift_id=s, effective_from=a.isoformat(), effective_to=b.isoformat(), weekly_off_day=WD[e['wo']],
            assignment_type='ROTATION_PERIOD' if e['rot'] else 'FIXED', record_origin=ORIG, generation_version=GV))
        la.append(dict(allocation_id=f'ALC-{len(la) + 1:05d}', employee_id=e['emp_id'], shift_assignment_id=sid, plant_id=e['plant'], line_id=e['line'], shift_id=s,
            crew_id=f"CREW-{e['line']}-{s}" if e['line'] else None, station_id=st, work_area_code=wa,
            station_link_status='NOT_APPLICABLE' if (st is None and e['role'] != 'LINE_OPERATOR') else ('CANDIDATE_ONLY' if st else 'UNMATCHED'),
            supervisor_employee_id=(SUPV[(e['line'], s)] if e['role'] != 'SUPERVISOR' and e['line'] else (mgr[e['plant']]['emp_id'] if e['role'] == 'SUPERVISOR' else None)),
            effective_from=a.isoformat(), effective_to=b.isoformat(), allocation_pct=100, allocation_basis='GENERATED_ROSTER', production_run_link_status='UNMATCHED_NO_EVIDENCE_NOT_ATTEMPTED',
            record_origin=ORIG, generation_version=GV))
sa_df = pd.DataFrame(sa); la_df = pd.DataFrame(la)
alloc = {}
for r in la: alloc.setdefault(r['employee_id'], []).append(r)
def alloc_for(emp_id, d): return next(r for r in alloc[emp_id] if r['effective_from'] <= d.isoformat() <= r['effective_to'])
def sstart(d, s): return DT.combine(d, dt.time(SHIFTS[s][0]))
FEST = (D(2026, 10, 17), D(2026, 10, 21)); ARO = (D(2026, 9, 8), D(2026, 9, 28)); LOGM = {}
att = []; wk_hours = {}
days = [D(2026, 8, 1) + TD(days=i) for i in range(92)]
for d in days:
    for e in emps:
        if d.weekday() == e['wo']: continue
        s = shift_for(e, d); ar = alloc_for(e['emp_id'], d); ln = e['line']; st0 = sstart(d, s); en0 = st0 + TD(hours=8)
        m = 1.4 if d.weekday() == 0 else 1.15 if d.weekday() == 5 else 1.0
        if FEST[0] <= d <= FEST[1]: m *= 1.8
        if d == D(2026, 8, 15): m *= 1.5
        if s == 'C': m *= 1.15
        spike = (ln == 'FAL-L2' and s == 'B' and ARO[0] <= d <= ARO[1] and e['role'] != 'PRODUCTION_MANAGER')
        pab = .022 * m * (3.5 if spike else 1); plv = .035 * (1 + .5 * (m - 1)); phd = .012
        u = R.random(); status = lc = ab = None
        if u < pab: status, lc, ab = 'ABSENT', 'NONE', 'UNPLANNED_UNAPPROVED'
        elif u < pab + plv: status, ab = 'ON_LEAVE', 'PLANNED_APPROVED'; lc = R.choices(['CASUAL_LEAVE', 'SICK_LEAVE', 'EARNED_LEAVE', 'LEAVE_WITHOUT_PAY'], [34, 43, 20, 3])[0]
        elif u < pab + plv + phd: status, lc, ab = 'HALF_DAY', 'CASUAL_LEAVE_HALF_DAY', 'PARTIAL_DAY'
        else: status, lc, ab = 'PRESENT', 'NONE', 'NONE'
        row = dict(employee_id=e['emp_id'], attendance_date=d.isoformat(), plant_id=e['plant'], line_id=ln, shift_id=s, supervisor_employee_id=ar['supervisor_employee_id'], crew_id=ar['crew_id'],
                   attendance_status=status, leave_category=lc, absence_category=ab, scheduled_start_ts=iso(st0), scheduled_end_ts=iso(en0), check_in_ts=None, check_out_ts=None, break_minutes=0,
                   late_minutes=0, early_leave_minutes=0, scheduled_hours=SCH, actual_working_hours=0.0, regular_hours=0.0, overtime_hours=0.0, ot_approval_status='NOT_APPLICABLE')
        if status in ('PRESENT', 'HALF_DAY'):
            if status == 'HALF_DAY':
                cin = st0 - TD(minutes=R.randint(0, 10)); cout = st0 + TD(hours=3.75); act = 3.75; reg = 3.75; ot = 0.0; late = early = 0; br = 0
            else:
                r2 = R.random(); late = 0 if r2 < .78 else R.randint(1, 10) if r2 < .92 else R.randint(11, 45)
                cin = st0 + TD(minutes=late) if late else st0 - TD(minutes=R.randint(0, 15)); early = R.randint(15, 60) if R.random() < .03 else 0
                ot = 0.0
                if not early:
                    nd = d + TD(days=1)
                    while nd.weekday() == e['wo']: nd += TD(days=1)
                    slack = (sstart(nd, shift_for(e, nd)) - en0).total_seconds() / 3600 - 8 if nd <= days[-1] else 4
                    otmax = math.floor(min(4, max(slack, 0)) * 4) / 4
                    pot = .12 * (2.5 if spike else 1)
                    if R.random() < pot:
                        c = R.choice([.5, 1, 1, 1.5, 2, 2, 3, 4])
                        wk = (e['emp_id'], d.isocalendar()[:2])
                        if c <= otmax and wk_hours.get(wk, 0) + SCH + c <= 60: ot = c
                cout = en0 - TD(minutes=early) + TD(hours=ot); br = 30
                act = round(SCH - late / 60 - early / 60 + ot, 2); reg = round(act - ot, 2)
            wk = (e['emp_id'], d.isocalendar()[:2]); wk_hours[wk] = wk_hours.get(wk, 0) + act
            row.update(check_in_ts=iso(cin), check_out_ts=iso(cout), break_minutes=br, late_minutes=late, early_leave_minutes=early, actual_working_hours=act, regular_hours=reg, overtime_hours=ot,
                       ot_approval_status='APPROVED' if ot > 0 else 'NOT_APPLICABLE')
        row['late_flag'] = 'Y' if row['late_minutes'] > 10 else 'N'
        row['is_direct_labour'] = 'Y' if e['role'] == 'LINE_OPERATOR' else 'N'
        row['productive_labour_hours'] = row['actual_working_hours'] if (row['is_direct_labour'] == 'Y' and status in ('PRESENT', 'HALF_DAY')) else 0.0
        row['available_for_allocation_flag'] = 'Y' if status in ('PRESENT', 'HALF_DAY') else 'N'
        row['record_origin'] = ORIG; row['generation_version'] = GV
        att.append(row)
meta['anomalies'].append(dict(dataset='D10', pattern='FAL-L2 shift B 2026-09-08..09-28: unplanned absence probability x3.5 and overtime probability x2.5 (co-worker cover)'))
att_df = pd.DataFrame(att); att_df.insert(0, 'attendance_id', [f'ATT-{i:06d}' for i in range(1, len(att_df) + 1)])
# line-shift-day labour summary (line employees only)
a = att_df[att_df.line_id.notna()]
g = a.groupby(['attendance_date', 'plant_id', 'line_id', 'shift_id'])
lab = pd.DataFrame(dict(scheduled_hc=g.size(), present_full_day_hc=g.attendance_status.apply(lambda s: (s == 'PRESENT').sum()), half_day_hc=g.attendance_status.apply(lambda s: (s == 'HALF_DAY').sum()),
    absent_hc=g.attendance_status.apply(lambda s: (s == 'ABSENT').sum()), leave_hc=g.attendance_status.apply(lambda s: (s == 'ON_LEAVE').sum()),
    direct_labour_present_hc=g.apply(lambda x: ((x.is_direct_labour == 'Y') & (x.available_for_allocation_flag == 'Y')).sum()), total_actual_hours=g.actual_working_hours.sum().round(2),
    productive_labour_hours=g.productive_labour_hours.sum().round(2), overtime_hours=g.overtime_hours.sum().round(2))).reset_index()
lab['absenteeism_pct'] = ((lab.absent_hc + lab.leave_hc) / lab.scheduled_hc * 100).round(2)
hs = hr.groupby(['plant_id', 'line_id', 'shift_id', 'shift_production_date']).size().rename('n').reset_index()
hs['attendance_date'] = hs.shift_production_date
lab = lab.merge(hs[['plant_id', 'line_id', 'shift_id', 'attendance_date', 'n']], how='left', on=['plant_id', 'line_id', 'shift_id', 'attendance_date'])
lab['candidate_hourly_slot_count'] = lab.n.fillna(0).astype(int); lab['hourly_link_status'] = np.where(lab.candidate_hourly_slot_count > 0, 'CANDIDATE_ONLY', 'UNMATCHED')
lab['hourly_link_basis'] = 'plant+line+shift_id+shift_production_date (no run/order attribution)'
lab = lab.drop(columns='n').rename(columns={'attendance_date': 'shift_production_date'})
lab.insert(0, 'labour_day_id', [f'LAB-{i:05d}' for i in range(1, len(lab) + 1)]); lab['record_origin'] = ORIG; lab['generation_version'] = GV
for nme, df in [('d10_shift_definition_v1', sh_df), ('d10_employee_master_v1', emp_df), ('d10_shift_assignment_v1', sa_df), ('d10_line_allocation_v1', la_df),
                ('d10_attendance_v1', att_df), ('d10_line_shift_labour_daily_v1', lab)]: save(df, nme)
json.dump(meta, open(f'{META}/meta.json', 'w'), indent=1)
for f in sorted(os.listdir(OUT)):
    if f.endswith('.csv'): print(f, len(pd.read_csv(f'{OUT}/{f}', low_memory=False)))
