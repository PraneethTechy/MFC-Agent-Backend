import json, glob, os, pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
OUT = '/mnt/user-data/outputs'; META = '/home/claude/work'; IN = '/home/claude/in'
V = pd.read_pickle(f'{META}/val.pkl'); meta = json.load(open(f'{META}/meta.json')); S = V['stats']
D = {}
for l in """plant_id|Plant identifier (IN-KA-01, IN-TN-01); matches existing datasets
line_id|Production line identifier; valid plant+line pair from hourly feed (KA: SMT-L2/FAL-L2, TN: SMT-L1/FAL-L1)
shift_id|Shift A (06-14), B (14-22), C (22-06); matches hourly feed
material_id|Material identifier; matches BOM and D7 inventory
storage_location_id|Storage location (RM-SMT / RM-FAL) as in D7
material_batch_id|Lot/batch id as posted in D7
supplier_id|Synthetic supplier id (SUP-SYN-nnn)
record_origin|Always GENERATED_SYNTHETIC (field-level origin in field_origin column)
generation_version|Generator run tag
is_synthetic|Y = synthetic record
supplier_name|Fictional supplier name, suffixed (SYNTHETIC)
supplier_country|ISO country (assumption)
supplier_category|Supplier commodity category
supplier_tier|STRATEGIC / PREFERRED / APPROVED (assumption)
supplier_currency|Invoice currency
payment_terms_days|Payment terms in days
standard_lead_time_days|Planned supplier lead time used to place POs
supplier_status|ACTIVE
approved_plants|Plants the supplier may ship to
source_supplier_match_status|UNMATCHED: no real supplier source exists
source_list_id|Approved source list row id
source_rank|PRIMARY / SECONDARY source
planned_share_pct|Planned volume share for the source
material_in_bom_flag|Y if material exists in BOM
approval_status|Source approval status
po_id|Unique internal purchase order id (not a production PO number)
po_date|PO creation date (Monday of week; may precede 2026-08-01 because of lead time)
po_currency|PO currency
fx_rate_to_inr|INR per unit of PO currency (synthetic fixed assumption 88.00 for USD)
incoterm|Delivery term (assumption)
po_status|OPEN / PARTIALLY_RECEIVED / CLOSED
line_count|Number of PO lines
total_ordered_value_inr|Sum of line ordered value (INR)
related_production_po_link_status|Purchase PO is not linked to production source_po_number
po_line_id|Unique PO line id (po_id-nnn)
line_number|Line number within PO
uom|Unit of measure (EA, as D7)
ordered_qty|Ordered quantity
received_qty_total|Total received incl. rejected (sum of GR received_qty)
accepted_qty_total|Total accepted = qty posted to D7
rejected_qty_total|Total rejected (never posted to D7 stock)
open_qty|Ordered qty not yet received (open lines only)
delivery_variance_qty|Received minus ordered (closed lines)
line_status|OPEN / CLOSED_RECEIVED / CLOSED_SHORT
short_close_reason|Reason when closed short
over_delivery_flag|Y when received > ordered
unit_price_currency|Currency of unit_price
unit_price|Unit price in PO currency
unit_price_inr|Unit price in INR (aligned to D7 unit value; synthetic)
price_basis|How the price was derived
ordered_value_inr|Ordered qty x unit_price_inr
requested_delivery_date|Buyer requested delivery date (first delivery)
promised_delivery_date|Supplier promised date (first delivery)
first_receipt_date|Date of first GR
last_receipt_date|Date of last GR
planned_lead_time_days|Requested date minus PO date
actual_lead_time_days|First receipt date minus PO date
gr_count|Number of GRs on the line (1 or 2)
on_time_status|ON_TIME / EARLY (>=2 days) / LATE vs promised date; OPEN_NOT_DUE for open lines
days_late|Actual minus promised date (negative = early)
gr_id|Unique goods receipt id
delivery_seq|Delivery sequence within PO line
inventory_txn_id|FK to D7 GOODS_RECEIPT inventory_txn_id
d7_reference_id|D7 reference_id of the receipt
gr_posting_ts|D7 transaction timestamp
actual_delivery_date|Delivery/receipt date (= D7 transaction_date)
gr_requested_date|Requested date for this delivery
gr_promised_date|Promised date for this delivery
on_time_vs_requested|Y if delivered on/before requested date
lead_time_days_actual|Actual delivery date minus PO date
received_qty|Physically received incl. rejected
accepted_qty|Accepted qty; equals D7 qty_in
rejected_qty|Rejected at incoming inspection; not posted to D7
d7_posted_qty_in|D7 qty_in copy for reconciliation
qty_reconciliation_check|MATCH if accepted_qty = D7 qty_in
po_unit_price_inr|Price on PO line
price_variance_inr|(GR price - PO price) x accepted qty
accepted_value_inr|accepted_qty x GR unit price
d7_line_value_inr|D7 line_value_inr copy
value_diff_inr|accepted_value minus D7 line value
receipt_status|POSTED_FULL / POSTED_ACCEPTED_PORTION_ONLY
quality_status|ACCEPTED / ACCEPTED_PARTIAL_REJECT
d7_link_status|Relationship class to D7 txn (CONFIRMED)
d7_link_basis|Evidence for the D7 link
quality_id|Unique supplier quality record id
inspection_ts|Incoming inspection timestamp
inspection_type|INCOMING_AQL
lot_size_qty|Received lot size
sample_size|AQL sample size
sample_defects|Defects found in sample
sample_defect_rate_pct|Sample defects / sample size x 100
primary_defect_code|Main defect (synthetic)
severity|NONE / MINOR / MAJOR / CRITICAL
inspection_result|ACCEPT / ACCEPT_WITH_DEVIATION / PARTIAL_REJECT
reject_ppm|Rejected qty / received qty x 1e6
disposition|NONE / RETURN_TO_SUPPLIER / QUARANTINE_PENDING_RETURN
scar_raised|Y if supplier corrective action requested
equipment_id|Unique equipment id (EQ-line-nn)
equipment_type|Equipment type (assumed catalogue)
process_stage|SMT or FAL
line_type|Line type from hourly feed
sequence_in_line|Process order on line
station_id|Source station id (candidate mapping)
line_link_status|Relationship equipment -> plant/line (CONFIRMED)
station_link_status|CANDIDATE_ONLY (source stations not line-specific) / UNMATCHED / NOT_APPLICABLE
energy_meter_id|Meter id (one per equipment)
rated_power_kw|Assumed running power in kW
idle_power_factor|Idle power as fraction of rated
unplanned_down_power_factor|Unplanned-down power fraction
planned_down_power_factor|Planned-down power fraction
criticality|HIGH / MEDIUM / LOW
commissioning_year|Synthetic commissioning year
pm_interval_days|Preventive maintenance interval
last_pm_date|Last completed PM
next_pm_due_date|Last PM + interval
maintenance_status|CURRENT / DUE_WITHIN_7D / OVERDUE as of 2026-10-31
maintenance_status_as_of|As-of date
event_id|Unique equipment event id
event_type|PLANNED_DOWNTIME / UNPLANNED_DOWNTIME / IDLE (non-overlapping per equipment)
reason_code|Event reason code
reason_category|Category aligned to hourly downtime_reason vocabulary where one exists
event_start_ts|Event start
event_end_ts|Event end (exclusive)
duration_min|Event duration in minutes
start_shift_id|Shift at event start
start_shift_production_date|Shift production date at event start
is_micro_stop|Y for 1-5 minute stops
maintenance_id|Unique maintenance work order id / FK on events
hourly_link_status|CANDIDATE_ONLY or UNMATCHED vs hourly feed; never CONFIRMED
candidate_hourly_slot_count|Count of candidate hourly slots
link_id|Unique candidate link id
equipment_event_id|FK to equipment event
hourly_event_id|FK to hourly production event_id
overlap_min|Minutes of overlap with the hourly slot
hourly_slot_downtime_min|downtime_min of the hourly slot
match_basis|Matching rule
link_status|CANDIDATE_ONLY
caveat|Why the link is not confirmed
reading_id|Unique energy reading id
shift_production_date|Production date of shift (C shift starts previous evening)
period_start_ts|Reading window start (clipped to 2026-08-01..11-01)
period_end_ts|Reading window end
window_min|Minutes in window
operating_min|Window minus idle and downtime
idle_min|Idle minutes
planned_downtime_min|Planned downtime minutes
unplanned_downtime_min|Unplanned downtime minutes
energy_kwh|Synthetic kWh = rated kW x state minutes x factors x 3% noise
meter_register_start_kwh|Cumulative meter register at start
meter_register_end_kwh|Register at end (start + kWh)
tariff_inr_per_kwh|Assumed plant/shift tariff
estimated_energy_cost_inr|kWh x tariff
tariff_basis|Tariff source flag (assumption)
reading_basis|Energy value method (synthetic)
maintenance_type|PREVENTIVE / CALIBRATION / CORRECTIVE
work_order_status|COMPLETED / DEFERRED
scheduled_start_ts|Planned start (planned work only)
actual_start_ts|Work start
actual_end_ts|Work end
linked_downtime_event_id|FK to the downtime event the work belongs to
failure_reason_code|Reason of failure (corrective)
parts_replaced_flag|Y if parts replaced
estimated_cost_inr|Illustrative cost estimate
repeat_failure_within_7d_flag|Y if same equipment/reason failed again within 7 days
status_after|Equipment status after work
employee_id|Synthetic employee id (SYN-EMP-nnnnnn); no personal data
employee_role|Role
department|Department
home_line_id|Home line (blank for plant manager)
employment_type|PERMANENT / CONTRACT
grade|Synthetic grade
shift_pattern|FIXED or ROTATING_MONTHLY (A->C->B)
initial_shift_id|Shift on 2026-08-01
weekly_off_day|Weekly off day
hire_date|Synthetic hire date
employment_status|ACTIVE
is_direct_labour|Y for LINE_OPERATOR
contains_personal_data|N
shift_name|Shift label
start_time|Shift start HH:MM
end_time|Shift end HH:MM
crosses_midnight|Y for shift C
scheduled_punch_hours|On-premises hours (8)
break_minutes|Unpaid break minutes (30 full day, 0 half day)
scheduled_working_hours|Paid scheduled hours (7.5)
shift_id_link_status|CONFIRMED against hourly feed
shift_window_basis|Evidence for shift windows
shift_assignment_id|Unique roster period id
effective_from|Period start
effective_to|Period end
assignment_type|FIXED / ROTATION_PERIOD
allocation_id|Unique allocation id
crew_id|Synthetic crew (CREW-line-shift); not the hourly TEAM-xx
work_area_code|Work area / equipment type served
supervisor_employee_id|Supervisor employee id
allocation_pct|Allocation percent (100)
allocation_basis|GENERATED_ROSTER
production_run_link_status|UNMATCHED: no run attribution attempted
attendance_id|Unique attendance row id
attendance_date|Shift production date
attendance_status|PRESENT / HALF_DAY / ON_LEAVE / ABSENT
leave_category|Leave type or NONE
absence_category|PLANNED_APPROVED / UNPLANNED_UNAPPROVED / PARTIAL_DAY / NONE
scheduled_start_ts|Scheduled shift start
scheduled_end_ts|Scheduled shift end
check_in_ts|Punch in (blank if not present)
check_out_ts|Punch out (blank if not present)
late_minutes|Minutes after shift start
early_leave_minutes|Minutes left before shift end
scheduled_hours|Paid scheduled hours
actual_working_hours|(out - max(in,start) - break) in hours
regular_hours|actual - overtime
overtime_hours|Approved OT hours (multiple of 0.25)
ot_approval_status|APPROVED / NOT_APPLICABLE
late_flag|Y if late > 10 min
productive_labour_hours|Actual hours of present direct labour only; 0 for absent/leave/indirect
available_for_allocation_flag|Y if present or half day
labour_day_id|Unique line-shift-day summary id
scheduled_hc|Scheduled headcount
present_full_day_hc|Full-day present headcount
half_day_hc|Half-day headcount
absent_hc|Unplanned absent headcount
leave_hc|Approved leave headcount
direct_labour_present_hc|Present direct-labour headcount
total_actual_hours|Sum actual hours
absenteeism_pct|(absent+leave)/scheduled x 100
hourly_link_basis|Linking keys (no run/order attribution)""".split('\n'):
    k, v = l.split('|', 1); D[k] = v
SRC = {'inventory_txn_id', 'd7_reference_id', 'storage_location_id', 'material_batch_id', 'gr_posting_ts', 'actual_delivery_date', 'd7_posted_qty_in', 'd7_line_value_inr', 'accepted_qty', 'material_id', 'plant_id', 'line_id', 'shift_id', 'unit_price_inr'}
CALC = {'days_late', 'on_time_status', 'on_time_vs_requested', 'lead_time_days_actual', 'planned_lead_time_days', 'actual_lead_time_days', 'received_qty_total', 'accepted_qty_total', 'rejected_qty_total', 'open_qty', 'delivery_variance_qty',
        'ordered_value_inr', 'line_count', 'total_ordered_value_inr', 'gr_count', 'qty_reconciliation_check', 'price_variance_inr', 'accepted_value_inr', 'value_diff_inr', 'duration_min', 'window_min', 'operating_min', 'estimated_energy_cost_inr',
        'meter_register_end_kwh', 'productive_labour_hours', 'regular_hours', 'late_flag', 'actual_working_hours', 'absenteeism_pct', 'scheduled_hc', 'present_full_day_hc', 'half_day_hc', 'absent_hc', 'leave_hc', 'direct_labour_present_hc',
        'total_actual_hours', 'next_pm_due_date', 'overlap_min', 'reject_ppm', 'sample_defect_rate_pct', 'repeat_failure_within_7d_flag', 'available_for_allocation_flag'}
LINKS = {'link_status', 'hourly_link_status', 'station_link_status', 'line_link_status', 'd7_link_status', 'shift_id_link_status', 'production_run_link_status', 'source_supplier_match_status', 'related_production_po_link_status', 'hourly_event_id'}
files = sorted(glob.glob(f'{OUT}/d[0-9]*_v1.csv')); rows = []; missing = set()
FKS = V['FK']; PKS = V['PK']; AKS = V['AK']
for f in files:
    n = os.path.basename(f)[:-7]; df = pd.read_csv(f, low_memory=False)
    for c in df.columns:
        role = 'PK' if c in PKS[n] else 'AK' if c in (AKS.get(n) or []) else 'FK' if any(t == n and cc == c for t, cc, _, _ in FKS) else ''
        org = 'KEY' if role == 'PK' else 'SOURCE_DERIVED' if (c in SRC and n.startswith(('d8_goods', 'd8_po_line')) and c not in ('unit_price_inr',) or (c in ('plant_id', 'line_id', 'shift_id', 'material_id', 'storage_location_id') and not n.startswith('d8_po_line'))) else 'CALCULATED' if c in CALC else 'LINK_CLASSIFICATION' if c in LINKS else 'SYNTHETIC'
        if n == 'd8_goods_receipt' and c == 'unit_price_inr': org = 'SOURCE_DERIVED'
        if n == 'd8_po_line' and c == 'unit_price_inr': org = 'SYNTHETIC (aligned to D7)'
        if n in ('d8_supplier_master', 'd8_supplier_material_source_list', 'd8_po_header', 'd8_supplier_quality') and c in ('plant_id', 'material_id') and org == 'SOURCE_DERIVED': org = 'SOURCE_DERIVED (identifier)'
        if c not in D: missing.add(c)
        rows.append(dict(file=f'{n}_v1.csv', column=c, data_type=str(df[c].dtype).replace('str', 'string').replace('object', 'string'), key_role=role, nullable='Y' if df[c].isna().any() else 'N',
                         distinct_values=int(df[c].nunique()), example='' if df[c].dropna().empty else str(df[c].dropna().iloc[0]), field_origin=org, description=D.get(c, '')))
assert not missing, missing
pd.DataFrame(rows).to_csv(f'{OUT}/data_dictionary_d8_d10_v1.csv', index=False)
# key relationship spec
ks = []
for n, pk in PKS.items(): ks.append(dict(key_type='PK', table=f'{n}_v1', columns='+'.join(pk), references_table='', references_column='', relationship_status='', note='Unique generated key'))
for n, ak in AKS.items(): ks.append(dict(key_type='AK', table=f'{n}_v1', columns='+'.join(ak), references_table='', references_column='', relationship_status='', note='Unique alternate/natural key'))
EXT = {'BOM': 'fact_bom_component_enhanced_v1', 'D7': 'd7_inventory_transactions_v1', 'D7_GR': 'd7_inventory_transactions_v1 (transaction_type=GOODS_RECEIPT)', 'HOURLY': 'fact_hourly_production_enhanced_v1'}
for t, c, rt, rc in FKS:
    ext = rt in EXT; ks.append(dict(key_type='FK (external)' if ext else 'FK', table=f'{t}_v1', columns=c, references_table=EXT.get(rt, rt + '_v1'), references_column=rc, relationship_status='CONFIRMED' if ext else 'INTERNAL',
        note='Identifier validated, 0 invalid' if ext else 'Many : 1, validated, 0 invalid'))
for r in V['rel'].itertuples(): ks.append(dict(key_type='RELATIONSHIP_CLASS', table=r.relationship, columns=r.keys, references_table='', references_column='', relationship_status=r.status, note=f'{r.rows_or_keys} rows/keys. {r.basis}'))
pd.DataFrame(ks).to_csv(f'{OUT}/key_relationship_spec_d8_d10_v1.csv', index=False)
# assumptions
hr = pd.read_csv(f'{IN}/a/4 ds/fact_hourly_production_enhanced_v1.csv', usecols=['line_id', 'downtime_min', 'downtime_reason'])
ev = pd.read_csv(f'{OUT}/d9_equipment_event_v1.csv')
A = [('D8', 'PO creation dates may precede 2026-08-01 (up to ~6 weeks before first receipt); all POs are dated on/before 2026-10-31. 32 open PO lines (1 per plant-material) are due after the window and have no receipts.', 'Open'),
     ('D8', 'All suppliers, names, countries, tiers, lead times, on-time and reject behaviour are synthetic. No source supplier or PO data exists, so no supplier is CONFIRMED against a real record.', 'Open'),
     ('D8', 'PO unit price is aligned to D7 unit_value_inr (itself a generated standard price); USD prices use a fixed synthetic 88.00 INR/USD. These are not real purchase prices.', 'Open'),
     ('D8', 'D7 posts only accepted quantity. Rejected quantity is held at the dock / returned and never enters D7 (not valued, no second ledger). Hence D8 received = D7 qty_in + rejected.', 'Open'),
     ('D8', 'D7 is read-only, so its supplier_receipt_link_status still reads UNMATCHED_SUPPLIER_DATASET_NOT_AVAILABLE. The authoritative link is d8_goods_receipt.d7_link_status = CONFIRMED.', 'Open'),
     ('D8', 'D7 opening balances (64 lots) have no PO/supplier by design and remain UNMATCHED. Transfers/adjustments are not procurement events.', 'Open'),
     ('D8', 'Split deliveries (30 PO lines, 2 GRs) take the line price from the first GR; the second GR may differ (price_variance_inr). Dates on the line refer to the first delivery.', 'Open'),
     ('D9', 'Equipment catalogue (8 per line), rated kW, power factors, failure rates and repair times are assumptions. Equipment runs 24x7 as the hourly feed does; no scheduled-off time.', 'Open'),
     ('D9', 'Source stations appear on every line, so equipment->station is CANDIDATE_ONLY; assembly robot and laminator have no matching source station (UNMATCHED).', 'Open'),
     ('D9', 'Equipment events were generated independently of hourly downtime. They are NOT confirmed against hourly downtime; only same-line + hour-overlap + equal-reason pairs are listed as CANDIDATE_ONLY. Magnitudes differ (see Info_CrossScope).', 'Open'),
     ('D9', 'Energy covers main process equipment only (no HVAC, utilities, lighting). Tariffs by plant/shift are assumptions; kWh = rated kW x state minutes x factor x 3% noise. Not reconciled to cost-file energy_cost_inr.', 'Open'),
     ('D9', 'Energy windows follow shift_production_date; the 2026-07-31 C shift is clipped to 2026-08-01 00:00-06:00 and the 2026-10-31 C shift to 22:00-24:00. Events/maintenance stay inside 08-01..11-01.', 'Open'),
     ('D10', 'Headcount (248), roles, rosters, monthly A->C->B rotation, 6-day weeks, absence/leave/OT rates, festival-week absence uplift (Oct 17-21) are assumptions. IDs are SYN-EMP-nnnnnn; no personal data.', 'Open'),
     ('D10', 'Attendance rows exist only for scheduled working days (weekly-off days and public holidays are not modelled as rows). Shift C attendance_date is the shift start date; 74 punches on 2026-10-31 C-shift check out on/after 2026-11-01.', 'Open'),
     ('D10', 'Hours rule: 30-min unpaid break, 7.5 paid scheduled hours, OT approved in 0.25h steps (max 4h/day, 60h/week, >=8h rest). Absent/leave rows carry zero hours; productive labour counts present direct-labour operators only.', 'Open'),
     ('D10', 'Hourly C-shift slots of 2026-07-31 (00:00-05:59 on Aug 1) have no workforce record (attendance starts 2026-08-01): 4 line-shifts UNMATCHED.', 'Open'),
     ('D10', 'No employee-to-production-run/order attribution is claimed. Workforce links to hourly production only at plant+line+shift+shift_production_date (CANDIDATE_ONLY). Source TEAM-xx and inspector EMP-xxxx ids are not tied to synthetic employees (UNMATCHED).', 'Open'),
     ('ALL', 'Existing seven logical datasets were read only; MD5 of the inputs used is listed in Source_Checksums. Intentional RCA test patterns exist only in sheet Injected_Anomalies, not as CSV flags.', 'Open')]
# workbook
wb = Workbook(); HF = Font(name='Arial', bold=True, color='FFFFFF'); HFILL = PatternFill('solid', fgColor='1F4E78'); BF = Font(name='Arial')
def sheet(name, df, widths=None):
    ws = wb.create_sheet(name); ws.append(list(df.columns))
    for r in df.itertuples(index=False): ws.append([None if (isinstance(x, float) and pd.isna(x)) else x for x in r])
    for c in ws[1]: c.font = HF; c.fill = HFILL; c.alignment = Alignment(wrap_text=True, vertical='top')
    for row in ws.iter_rows(min_row=2):
        for c in row: c.font = BF
    for i, col in enumerate(df.columns, 1): ws.column_dimensions[ws.cell(1, i).column_letter].width = min(max(len(str(col)) + 2, int(df[col].astype(str).str.len().quantile(.9)) + 2 if len(df) else 10), 70)
    ws.freeze_panes = 'A2'; return ws
ws0 = wb.active; ws0.title = 'Summary'
sheet('File_Inventory', V['inv']); sheet('Key_Checks', V['fk']); sheet('Validation_Checks', V['chk']); sheet('Reconciliation', V['recon']); sheet('Relationship_Status', V['rel'])
sheet('Assumptions', pd.DataFrame(A, columns=['area', 'assumption', 'status'])); sheet('Injected_Anomalies', pd.DataFrame(meta['anomalies']).assign(note='RCA test patterns; ground truth only in this sheet'))
sheet('Source_Checksums', V['src'])
hl = hr.groupby('line_id').apply(lambda g: pd.Series(dict(hourly_downtime_min=int(g.downtime_min.sum()))), include_groups=False).reset_index()
eu = ev[ev.event_type.isin(['UNPLANNED_DOWNTIME', 'PLANNED_DOWNTIME'])].groupby('line_id').duration_min.sum().rename('equipment_downtime_min_sum_over_equipment').reset_index()
info = hl.merge(eu, on='line_id'); ws = sheet('Info_CrossScope', info)
ws['E1'] = 'ratio equipment/hourly'; ws['E1'].font = HF; ws['E1'].fill = HFILL
for r in range(2, 2 + len(info)): ws[f'E{r}'] = f'=C{r}/B{r}'; ws[f'E{r}'].number_format = '0.00'
n0 = len(info) + 4
for i, (lab, val) in enumerate([('Equipment energy cost, estimated (INR)', S['energy_cost']), ('Cost file energy_cost_inr, sum of 5,000 rows (INR)', S['cost_file_energy'])]): ws[f'A{n0 + i}'] = lab; ws[f'B{n0 + i}'] = val
ws[f'A{n0 + 2}'] = 'Equipment / cost-file energy'; ws[f'B{n0 + 2}'] = f'=B{n0}/B{n0 + 1}'; ws[f'B{n0 + 2}'].number_format = '0.0%'
ws[f'A{n0 + 4}'] = 'INFORMATIONAL ONLY. Different scope and grain (equipment events are independent of hourly downtime; energy covers main process equipment, cost file is a 5,000-row sample). No reconciliation claimed.'
n = len(V['chk']) + 1; ni = len(V['inv']) + 1; nk = len(V['fk']) + 1; nr = len(V['rel']) + 1; nc = len(V['recon']) + 1
summ = [('Metric', 'Value', 'Source'), ('Logical datasets generated', 3, 'D8, D9, D10'), ('Physical CSV files', f'=COUNTA(File_Inventory!A2:A{ni})', 'File_Inventory'), ('Total rows', f'=SUM(File_Inventory!B2:B{ni})', 'File_Inventory'),
        ('Duplicate primary keys', f'=SUM(File_Inventory!E2:E{ni})', 'File_Inventory'), ('Null primary keys', f'=SUM(File_Inventory!F2:F{ni})', 'File_Inventory'), ('Duplicate alternate keys', f'=SUM(File_Inventory!H2:H{ni})', 'File_Inventory'),
        ('Foreign keys checked', f'=COUNTA(Key_Checks!A2:A{nk})', 'Key_Checks'), ('Invalid foreign-key references', f'=SUM(Key_Checks!F2:F{nk})', 'Key_Checks'),
        ('Validation checks run', f'=COUNTA(Validation_Checks!A2:A{n})', 'Validation_Checks'), ('Checks PASS', f'=COUNTIF(Validation_Checks!D2:D{n},"PASS")', 'Validation_Checks'), ('Checks FAIL', f'=COUNTIF(Validation_Checks!D2:D{n},"FAIL")', 'Validation_Checks'),
        ('Reconciliations FAIL', f'=COUNTIF(Reconciliation!G2:G{nc},"FAIL")', 'Reconciliation'), ('Relationships CONFIRMED (classes)', f'=COUNTIF(Relationship_Status!C2:C{nr},"CONFIRMED")', 'Relationship_Status'),
        ('Relationships CANDIDATE_ONLY (classes)', f'=COUNTIF(Relationship_Status!C2:C{nr},"CANDIDATE_ONLY")', 'Relationship_Status'), ('Relationships UNMATCHED (classes)', f'=COUNTIF(Relationship_Status!C2:C{nr},"UNMATCHED")', 'Relationship_Status')]
for r in summ: ws0.append(list(r))
for c in ws0[1]: c.font = HF; c.fill = HFILL
for row in ws0.iter_rows(min_row=2):
    for c in row: c.font = BF
ws0.column_dimensions['A'].width = 40; ws0.column_dimensions['B'].width = 14; ws0.column_dimensions['C'].width = 24
ws0['A19'] = 'All new data is SYNTHETIC. Existing datasets 1-7 read-only. Validation re-read all CSVs from disk once after writing.'; ws0['A19'].font = Font(name='Arial', italic=True)
wb.save(f'{OUT}/cross_dataset_audit_d8_d10_v1.xlsx')
# summary md
inv = V['inv']; tot = int(inv.rows.sum())
tb = '\n'.join(f"| {r.file} | {r.rows:,} | {r.columns} | {r.primary_key} | {r.duplicate_pk} |" for r in inv.itertuples())
rl = V['rel'].groupby('status').size().to_dict()
md = f"""# Generation Summary - Datasets 8, 9, 10 (v1)
All new data is **synthetic**; existing seven datasets were read only (not rewritten). Run tag `GEN-D8D10-V1-20261120`.

## Files ({len(inv)} CSV, {tot:,} rows)
| File | Rows | Cols | Primary key | Dup PK |
|---|---|---|---|---|
{tb}

Docs: `data_dictionary_d8_d10_v1.csv` (226 unique columns, field_origin tagged), `key_relationship_spec_d8_d10_v1.csv`, `cross_dataset_audit_d8_d10_v1.xlsx`. Scripts: `generate_d8_d10_v1.py`, `validate_and_document_d8_d10_v1.py`, `build_docs_d8_d10_v1.py`.

## Validation (one run, files re-read from disk)
**{V['chk'].status.eq('PASS').sum()}/{len(V['chk'])} checks PASS.** Duplicate PKs 0, duplicate alternate keys 0, {len(V['fk'])} FK checks with 0 invalid references, 0 failed reconciliations.
One validator rule was mis-specified on the first run (productive hours ceiling ignored overtime); I corrected the check, not the data, and re-ran.

## Key reconciliations
- **D8 <-> D7:** all 346 D7 `GOODS_RECEIPT` rows have exactly one D8 GR (txn id, plant, sloc, material, batch, timestamp match). `accepted_qty` = D7 `qty_in` on every row; value diff <= INR 1. Received = accepted + rejected ({int(pd.read_csv(f'{OUT}/d8_goods_receipt_v1.csv').rejected_qty.sum()):,} units rejected at dock, never in D7). No stock balance is held in D8.
- **D8 PO lines:** totals equal sum of GRs; 30 split deliveries, 32 open lines (due after window); every shortfall is a CLOSED_SHORT with a reason.
- **D9:** 0 overlapping events per equipment; shift energy windows reconcile to event minutes recomputed independently; meter registers continuous; kWh within +/-15% of the rated-power model.
- **D10:** actual hours = punches; actual = regular + OT; absent/leave rows have zero hours/productive hours; 0 rest or assignment conflicts; labour-day summary matches attendance.

## Relationship classes
CONFIRMED {rl.get('CONFIRMED', 0)}, CANDIDATE_ONLY {rl.get('CANDIDATE_ONLY', 0)}, UNMATCHED {rl.get('UNMATCHED', 0)} (see `Relationship_Status`). Only identifier-level links (GR->D7, material, plant/line, shift) are CONFIRMED. Equipment events vs hourly downtime ({int((ev.hourly_link_status == 'CANDIDATE_ONLY').sum())} events), station mappings and labour-day vs hourly slots are CANDIDATE_ONLY. Employee-to-run attribution, supplier-to-real-source, purchase PO vs production PO, and energy vs cost file are UNMATCHED.

## Headline figures
GR on-time {S['gr_on_time_pct']}% ({S['gr_late']} late), {S['gr_reject_lots']} lots with rejects; equipment unplanned downtime {S['unplanned_min']:,} min; energy {S['energy_kwh']:,.0f} kWh / INR {S['energy_cost']:,.0f}; absence+leave {S['absent_pct']}%; OT {S['ot_hours']:,.0f} h.

## Unresolved assumptions (full list in workbook `Assumptions`)
1. Supplier, price, FX (88.00), tariff, equipment catalogue and headcount are assumptions; none are real. 2. D7's own supplier status stays UNMATCHED (read-only); the link lives in `d8_goods_receipt`. 3. Equipment downtime is not confirmed against hourly downtime (magnitudes differ; see `Info_CrossScope`). 4. Energy is not reconciled to cost-file energy. 5. 2026-07-31 C-shift hourly slots have no workforce rows; 74 Oct-31 C-shift punches check out on 2026-11-01. 6. Intentional RCA test patterns exist only in `Injected_Anomalies`.
"""
open(f'{OUT}/generation_summary_d8_d10_v1.md', 'w').write(md); print('docs done', len(rows), 'dictionary rows')
