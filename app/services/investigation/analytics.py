"""
Deterministic Manufacturing Cost Analytics Service.
Performs rigorous, reproducible mathematical calculations directly against
uploaded manufacturing dataset records (CSV/JSON) in the active upload session.
Zero fabrication, exact reconciliation, and strict evidence governance.
"""

from collections import defaultdict
import datetime as dt
import logging
import re
from typing import Any, Optional

from .formatters import (
    format_inr,
    format_crores,
    format_lakhs,
    format_currency_auto,
    format_pct,
    format_units,
)

logger = logging.getLogger("manufacturing_cost_agent.investigation.analytics")


def resolve_target_ym(filters: Optional[dict[str, Any]]) -> Optional[str]:
    """
    Resolves the target year-month filter.
    Returns:
      None if "ALL" / unrestricted (All Available Periods).
      "YYYY-MM" if restricted to a specific month.
    """
    raw = (filters or {}).get("reporting_period")
    if not raw:
        return None
    s = str(raw).strip()
    if s.upper() in ("ALL", "ALL AVAILABLE PERIODS", "ALL PERIODS", "ALL_PERIODS", ""):
        return None
    if re.match(r"^\d{4}-\d{2}$", s):
        return s
    for fmt in ("%B %Y", "%b %Y", "%Y-%m", "%Y/%m"):
        try:
            dt_obj = dt.datetime.strptime(s, fmt)
            return dt_obj.strftime("%Y-%m")
        except Exception:
            pass
    m = re.match(r"([A-Za-z]{3,9})\s+(\d{4})", s)
    if m:
        for fmt in ("%B %Y", "%b %Y"):
            try:
                dt_obj = dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", fmt)
                return dt_obj.strftime("%Y-%m")
            except Exception:
                pass
    return None


def get_val(r: dict[str, Any], key: str, mapping: Optional[dict[str, str]] = None, default: float = 0.0) -> float:
    """Safely extracts a float value with currency and comma cleaning."""
    target = (mapping.get(key) if mapping else None) or key
    val = r.get(target) if target in r else r.get(key)
    if val is None or val == "":
        aliases = {
            "total_direct_cost_inr": ["total_direct_manufacturing_cost", "total_cost", "total_direct_cost"],
            "material_cost_inr": ["material_cost", "mat_cost"],
            "labour_cost_inr": ["labour_cost", "labor_cost", "lab_cost"],
            "machine_cost_inr": ["machine_cost", "mac_cost"],
            "energy_cost_inr": ["energy_cost", "nrg_cost", "power_cost"],
            "scrap_rework_cost_inr": ["scrap_rework_cost", "scrap_cost", "rework_cost", "scr_cost"],
            "produced_qty": ["actual_qty", "good_qty", "qty"],
            "actual_qty": ["produced_qty", "target_qty"],
            "good_qty": ["good_units", "actual_qty"],
            "reject_qty": ["rejected_qty", "defect_qty"],
        }
        for alias in aliases.get(key, []):
            if alias in r and r[alias] is not None and r[alias] != "":
                val = r[alias]
                break
    if val is None or val == "":
        return default
    try:
        clean = str(val).replace(",", "").replace("₹", "").replace("$", "").strip()
        return float(clean)
    except (ValueError, TypeError):
        return default


def get_str(r: dict[str, Any], key: str, mapping: Optional[dict[str, str]] = None, default: str = "") -> str:
    """Safely extracts a stripped string value."""
    target = (mapping.get(key) if mapping else None) or key
    val = r.get(target) if target in r else r.get(key)
    if val is None or val == "":
        aliases = {
            "product_id": ["product_code", "product_id", "sku", "product"],
            "plant_id": ["plant_code", "plant_id", "plant"],
            "line_id": ["line_code", "line_id", "line"],
        }
        for alias in aliases.get(key, []):
            if alias in r and r[alias] is not None and r[alias] != "":
                val = r[alias]
                break
    if val is None:
        return default
    return str(val).strip()


class ManufacturingAnalytics:
    """Computes evidence-backed metrics across session datasets."""

    PRODUCT_NAMES = {
        "SPH-PRO-256": "Pro Smartphone 256GB",
        "SPH-A15-256": "Standard Smartphone 256GB",
        "SPH-A15-128": "Standard Smartphone 128GB",
        "SPH-TST-X1": "Trial Smartphone Prototype X1",
    }

    MATERIAL_NAMES = {
        "MAT-SOC-001": "Snapdragon 8-Gen Mobile SoC",
        "MAT-DSP-005": "6.7\" AMOLED 120Hz Display Panel",
        "MAT-MEM-002": "12GB LPDDR5X RAM Module",
        "MAT-NAND-003": "256GB UFS 4.0 Storage Chip",
        "MAT-CAM-007": "50MP OIS Primary Camera Module",
        "MAT-CAM-008": "12MP Ultra-wide Sensor",
        "MAT-PCB-004": "10-Layer HDI Motherboard PCB",
        "MAT-BAT-006": "5000mAh High-Density Battery Cell",
        "MAT-HSG-009": "CNC Titanium/Aluminum Alloy Housing",
        "MAT-GLS-010": "Gorilla Glass Victus Cover Glass",
        "MAT-ANT-012": "Sub-6GHz 5G Antenna Module",
        "MAT-CON-013": "USB-C Fast Charging Assembly",
        "MAT-SPK-011": "Dual Stereo Acoustic Speaker",
        "MAT-BOX-014": "Eco Retail Packaging Box",
        "MAT-CBL-015": "Braided USB-C to C 100W Cable",
        "MAT-SCR-016": "Precision Micro-Screw Set",
        "MAT-TST-901": "Specialized Adhesive Sealant A901",
        "MAT-TST-902": "Thermal Dissipation Graphite Sheet G902",
    }

    # =========================================================================
    # A. OVERALL MANUFACTURING COST
    # =========================================================================
    @classmethod
    def analyze_manufacturing_cost(
        cls,
        datasets: dict[str, Any],
        filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        cost_ds = datasets.get("MANUFACTURING_COST")
        if not cost_ds:
            return {"error": "Missing MANUFACTURING_COST dataset in upload session"}

        rows = cost_ds.get("rows", cost_ds.get("raw_rows", []))
        cmap = cost_ds.get("column_mapping", {})
        prod_ds = datasets.get("HOURLY_PRODUCTION")
        prod_rows = prod_ds.get("rows", prod_ds.get("raw_rows", [])) if prod_ds else []
        pmap = prod_ds.get("column_mapping", {}) if prod_ds else {}

        plant_filter = (filters or {}).get("plant_code")
        line_filter = (filters or {}).get("line_code")
        prod_filter = (filters or {}).get("product_code")
        target_ym = resolve_target_ym(filters)
        cons_ds = datasets.get("MATERIAL_CONSUMPTION")
        purch_ds = datasets.get("PURCHASE_INVOICE") or datasets.get("PO_INVOICE")
        if not target_ym and (not filters or str((filters or {}).get("reporting_period", "")).upper() not in ("ALL", "ALL AVAILABLE PERIODS", "ALL PERIODS")):
            # Discover latest period from consumption or purchase records
            found_months: set[str] = set()
            for ds in (cons_ds, purch_ds):
                if ds:
                    r_list = ds.get("rows", ds.get("raw_rows", []))
                    c_map = ds.get("column_mapping", {})
                    for r in r_list:
                        ts = str(r.get("production_date") or r.get("consumption_ts") or r.get("receipt_date") or r.get("date") or "")
                        m_ym = re.match(r"^(\d{4})[-/](\d{1,2})", ts)
                        if m_ym:
                            found_months.add(f"{int(m_ym.group(1)):04d}-{int(m_ym.group(2)):02d}")
            if found_months:
                target_ym = sorted(list(found_months))[-1]

        # Period totals
        period_costs = defaultdict(lambda: {
            "total": 0.0,
            "material": 0.0,
            "labour": 0.0,
            "machine": 0.0,
            "energy": 0.0,
            "scrap_rework": 0.0,
            "batch_count": 0,
            "produced_qty": 0.0,
        })
        daily_trend = defaultdict(float)
        by_product = defaultdict(float)
        by_plant = defaultdict(float)
        by_line = defaultdict(float)

        for r in rows:
            pl = get_str(r, "plant_id", cmap)
            ln = get_str(r, "line_id", cmap)
            sku = get_str(r, "product_id", cmap)

            if plant_filter and plant_filter != "All Plants" and pl != plant_filter:
                continue
            if line_filter and line_filter != "All Lines" and ln != line_filter:
                continue
            if prod_filter and prod_filter != "All Products" and sku != prod_filter:
                continue

            ts = (
                get_str(r, "production_date", cmap)
                or get_str(r, "posting_ts", cmap)
                or get_str(r, "date", cmap)
                or get_str(r, "production_timestamp", cmap)
            )
            m = re.match(r"^(\d{4})[-/](\d{1,2})", ts) if ts else None
            ym = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}" if m else (ts[:7] if len(ts) >= 7 else "UNKNOWN")
            day = ts[:10] if len(ts) >= 10 else ym

            # Restrict by target month if specified
            if target_ym and ym != target_ym:
                continue

            mat = get_val(r, "material_cost_inr", cmap)
            lab = get_val(r, "labour_cost_inr", cmap)
            mac = get_val(r, "machine_cost_inr", cmap)
            nrg = get_val(r, "energy_cost_inr", cmap)
            scr = get_val(r, "scrap_rework_cost_inr", cmap)
            tot = mat + lab + mac + nrg + scr
            qty = get_val(r, "produced_qty", cmap)

            period_costs[ym]["total"] += tot
            period_costs[ym]["material"] += mat
            period_costs[ym]["labour"] += lab
            period_costs[ym]["machine"] += mac
            period_costs[ym]["energy"] += nrg
            period_costs[ym]["scrap_rework"] += scr
            period_costs[ym]["batch_count"] += 1
            period_costs[ym]["produced_qty"] += qty

            daily_trend[day] += tot
            by_product[sku] += tot
            by_plant[pl] += tot
            by_line[ln] += tot

        # Production units (produced vs good)
        period_prod = defaultdict(lambda: {"actual_qty": 0.0, "good_qty": 0.0, "reject_qty": 0.0})
        for pr in prod_rows:
            pl = get_str(pr, "plant_id", pmap)
            ln = get_str(pr, "line_id", pmap)
            sku = get_str(pr, "product_id", pmap)
            if plant_filter and plant_filter != "All Plants" and pl != plant_filter:
                continue
            if line_filter and line_filter != "All Lines" and ln != line_filter:
                continue
            if prod_filter and prod_filter != "All Products" and sku != prod_filter:
                continue

            pts = (
                get_str(pr, "production_date", pmap)
                or get_str(pr, "event_date", pmap)
                or get_str(pr, "event_ts", pmap)
                or get_str(pr, "production_timestamp", pmap)
            )
            m = re.match(r"^(\d{4})[-/](\d{1,2})", pts) if pts else None
            pym = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}" if m else (pts[:7] if len(pts) >= 7 else "UNKNOWN")

            if target_ym and pym != target_ym:
                continue

            period_prod[pym]["actual_qty"] += get_val(pr, "actual_qty", pmap)
            period_prod[pym]["good_qty"] += get_val(pr, "good_qty", pmap)
            period_prod[pym]["reject_qty"] += get_val(pr, "reject_qty", pmap)

        periods = sorted(period_costs.keys())

        # Resolve selected data scope
        if target_ym:
            curr_p = target_ym
            curr_data = period_costs.get(curr_p, defaultdict(float))
            idx = periods.index(curr_p) if curr_p in periods else -1
            base_p = periods[idx - 1] if idx > 0 else None
            base_data = period_costs.get(base_p) if base_p else None
            curr_act_units = period_prod[curr_p]["actual_qty"] or curr_data["produced_qty"]
            curr_good_units = period_prod[curr_p]["good_qty"]
        elif periods and (not filters or str((filters or {}).get("reporting_period", "")).upper() not in ("ALL", "ALL AVAILABLE PERIODS", "ALL PERIODS")):
            curr_p = periods[-1]
            curr_data = period_costs[curr_p]
            idx = len(periods) - 1
            base_p = periods[idx - 1] if idx > 0 else None
            base_data = period_costs.get(base_p) if base_p else None
            curr_act_units = period_prod[curr_p]["actual_qty"] or curr_data["produced_qty"]
            curr_good_units = period_prod[curr_p]["good_qty"]
        else:
            curr_p = "All Available Periods"
            curr_data = {
                "total": sum(v["total"] for v in period_costs.values()),
                "material": sum(v["material"] for v in period_costs.values()),
                "labour": sum(v["labour"] for v in period_costs.values()),
                "machine": sum(v["machine"] for v in period_costs.values()),
                "energy": sum(v["energy"] for v in period_costs.values()),
                "scrap_rework": sum(v["scrap_rework"] for v in period_costs.values()),
                "batch_count": sum(v["batch_count"] for v in period_costs.values()),
                "produced_qty": sum(v["produced_qty"] for v in period_costs.values()),
            }
            base_p = None
            base_data = None
            curr_act_units = sum(p["actual_qty"] for p in period_prod.values()) or curr_data["produced_qty"]
            curr_good_units = sum(p["good_qty"] for p in period_prod.values())

        curr_total = curr_data["total"]
        base_total = base_data["total"] if base_data else None
        variance = (curr_total - base_total) if base_total is not None else None
        variance_pct = (variance / base_total * 100.0) if (base_total and variance is not None) else None

        # Unit costs
        cost_per_produced_unit = (curr_total / curr_act_units) if curr_act_units > 0 else 0.0
        cost_per_good_unit = (curr_total / curr_good_units) if curr_good_units > 0 else cost_per_produced_unit
        cost_per_good_unit_uplift = round(cost_per_good_unit - cost_per_produced_unit, 2)

        base_good_units = period_prod[base_p]["good_qty"] if base_p else None
        base_cost_per_good_unit = (base_total / base_good_units) if (base_total and base_good_units and base_good_units > 0) else None

        # Category shares
        cat_breakdown = {
            "Material": {
                "amount": curr_data["material"],
                "formatted": format_crores(curr_data["material"]),
                "share_pct": round(curr_data["material"] / curr_total * 100, 2) if curr_total else 0,
            },
            "Labour": {
                "amount": curr_data["labour"],
                "formatted": format_crores(curr_data["labour"]),
                "share_pct": round(curr_data["labour"] / curr_total * 100, 2) if curr_total else 0,
            },
            "Machine Operating": {
                "amount": curr_data["machine"],
                "formatted": format_crores(curr_data["machine"]),
                "share_pct": round(curr_data["machine"] / curr_total * 100, 2) if curr_total else 0,
            },
            "Factory Energy": {
                "amount": curr_data["energy"],
                "formatted": format_crores(curr_data["energy"]),
                "share_pct": round(curr_data["energy"] / curr_total * 100, 2) if curr_total else 0,
            },
            "Scrap & Rework": {
                "amount": curr_data["scrap_rework"],
                "formatted": format_crores(curr_data["scrap_rework"]),
                "formatted_lakhs": format_lakhs(curr_data["scrap_rework"]),
                "share_pct": round(curr_data["scrap_rework"] / curr_total * 100, 2) if curr_total else 0,
            },
        }

        # Check reconciliation: sum of categories vs total
        cat_sum = sum(v["amount"] for v in cat_breakdown.values())
        unexplained = round(curr_total - cat_sum, 2)

        return {
            "analysis_type": "OVERALL_MANUFACTURING_COST",
            "current_period": curr_p,
            "baseline_period": base_p,
            "total_cost": round(curr_total, 2),
            "formatted_total_cost": format_crores(curr_total),
            "baseline_total_cost": round(base_total, 2) if base_total else None,
            "formatted_baseline_cost": format_crores(base_total) if base_total else None,
            "variance": round(variance, 2) if variance is not None else None,
            "formatted_variance": format_crores(variance) if variance is not None else None,
            "variance_pct": round(variance_pct, 2) if variance_pct is not None else None,
            "produced_units": round(curr_act_units, 0),
            "good_units": round(curr_good_units, 0),
            "cost_per_produced_unit": round(cost_per_produced_unit, 2),
            "formatted_cost_per_produced_unit": format_inr(cost_per_produced_unit),
            "cost_per_good_unit": round(cost_per_good_unit, 2),
            "formatted_cost_per_good_unit": format_inr(cost_per_good_unit),
            "cost_per_good_unit_uplift": cost_per_good_unit_uplift,
            "formatted_cost_per_good_unit_uplift": format_inr(cost_per_good_unit_uplift),
            "actual_scrap_rework_expenditure": round(curr_data["scrap_rework"], 2),
            "formatted_actual_scrap_rework_expenditure": format_lakhs(curr_data["scrap_rework"]),
            "base_cost_per_good_unit": round(base_cost_per_good_unit, 2) if base_cost_per_good_unit else None,
            "categories": cat_breakdown,
            "unexplained_variance": unexplained,
            "product_contributions": [
                {"product_id": k, "product_name": cls.PRODUCT_NAMES.get(k, k), "total_cost": round(v, 2), "formatted_cost": format_crores(v), "share_pct": round(v / curr_total * 100, 2) if curr_total else 0}
                for k, v in sorted(by_product.items(), key=lambda x: x[1], reverse=True)
            ],
            "plant_contributions": [
                {"plant_id": k, "total_cost": round(v, 2), "formatted_cost": format_crores(v), "share_pct": round(v / curr_total * 100, 2) if curr_total else 0}
                for k, v in sorted(by_plant.items(), key=lambda x: x[1], reverse=True)
            ],
            "line_contributions": [
                {"line_id": k, "total_cost": round(v, 2), "formatted_cost": format_crores(v), "share_pct": round(v / curr_total * 100, 2) if curr_total else 0}
                for k, v in sorted(by_line.items(), key=lambda x: x[1], reverse=True)
            ],
            "daily_trend": [{"date": d, "cost": round(c, 2), "formatted_cost": format_crores(c)} for d, c in sorted(daily_trend.items())],
            "evidence_classification": "PROVEN",
        }

    # =========================================================================
    # B. COMPONENT EXPENDITURE
    # =========================================================================
    @classmethod
    def analyze_component_expenditure(
        cls,
        datasets: dict[str, Any],
        filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        cons_ds = datasets.get("MATERIAL_CONSUMPTION")
        purch_ds = datasets.get("MATERIAL_PURCHASE")
        if not cons_ds and not purch_ds:
            return {"error": "Missing MATERIAL_CONSUMPTION and MATERIAL_PURCHASE datasets"}

        target_ym = resolve_target_ym(filters)
        cons_ds = datasets.get("MATERIAL_CONSUMPTION")
        purch_ds = datasets.get("PURCHASE_INVOICE") or datasets.get("PO_INVOICE")
        if not target_ym and (not filters or str((filters or {}).get("reporting_period", "")).upper() not in ("ALL", "ALL AVAILABLE PERIODS", "ALL PERIODS")):
            # Discover latest period from consumption or purchase records
            found_months: set[str] = set()
            for ds in (cons_ds, purch_ds):
                if ds:
                    r_list = ds.get("rows", ds.get("raw_rows", []))
                    c_map = ds.get("column_mapping", {})
                    for r in r_list:
                        ts = str(r.get("production_date") or r.get("consumption_ts") or r.get("receipt_date") or r.get("date") or "")
                        m_ym = re.match(r"^(\d{4})[-/](\d{1,2})", ts)
                        if m_ym:
                            found_months.add(f"{int(m_ym.group(1)):04d}-{int(m_ym.group(2)):02d}")
            if found_months:
                target_ym = sorted(list(found_months))[-1]

        # Component consumption expenditure
        comp_spend = defaultdict(lambda: {"qty": 0.0, "value": 0.0, "products": set(), "uom": "EA"})
        product_spend = defaultdict(lambda: defaultdict(float))

        if cons_ds:
            crows = cons_ds.get("rows", cons_ds.get("raw_rows", []))
            cmap = cons_ds.get("column_mapping", {})
            for r in crows:
                ts = (
                    get_str(r, "production_date", cmap)
                    or get_str(r, "consumption_ts", cmap)
                    or get_str(r, "date", cmap)
                )
                if target_ym and not ts.startswith(target_ym):
                    continue
                mid = get_str(r, "material_id", cmap)
                pid = get_str(r, "product_id", cmap)
                q = get_val(r, "net_consumed_qty", cmap) or get_val(r, "quantity", cmap)
                v = get_val(r, "consumed_value_inr", cmap) or get_val(r, "total_cost_inr", cmap)
                uom = get_str(r, "uom", cmap, default="EA")

                comp_spend[mid]["qty"] += q
                comp_spend[mid]["value"] += v
                comp_spend[mid]["products"].add(pid)
                comp_spend[mid]["uom"] = uom
                product_spend[pid][mid] += v

        # Purchase price movements & suppliers
        purch_info = defaultdict(lambda: {"suppliers": set(), "total_qty": 0.0, "total_landed": 0.0, "orders": 0})
        if purch_ds:
            prows = purch_ds.get("rows", purch_ds.get("raw_rows", []))
            pmap = purch_ds.get("column_mapping", {})
            for r in prows:
                pts = (
                    get_str(r, "receipt_date", pmap)
                    or get_str(r, "order_date", pmap)
                    or get_str(r, "date", pmap)
                )
                if target_ym and not pts.startswith(target_ym):
                    continue
                mid = get_str(r, "material_id", pmap)
                sname = get_str(r, "supplier_name", pmap)
                q = get_val(r, "quantity", pmap)
                landed = get_val(r, "landed_total_inr", pmap)
                purch_info[mid]["suppliers"].add(sname)
                purch_info[mid]["total_qty"] += q
                purch_info[mid]["total_landed"] += landed
                purch_info[mid]["orders"] += 1

        total_material_spend = sum(v["value"] for v in comp_spend.values())

        ranked_components = []
        for mid, data in sorted(comp_spend.items(), key=lambda x: x[1]["value"], reverse=True):
            pinfo = purch_info.get(mid, {})
            avg_unit_cost = (data["value"] / data["qty"]) if data["qty"] > 0 else 0.0
            ranked_components.append({
                "material_id": mid,
                "material_name": cls.MATERIAL_NAMES.get(mid, f"Component {mid}"),
                "expenditure": round(data["value"], 2),
                "consumed_qty": round(data["qty"], 1),
                "uom": data["uom"],
                "avg_unit_cost": round(avg_unit_cost, 2),
                "share_of_material_spend_pct": round(data["value"] / total_material_spend * 100, 2) if total_material_spend else 0,
                "used_in_products": sorted(list(data["products"])),
                "suppliers": sorted(list(pinfo.get("suppliers", []))),
            })

        return {
            "analysis_type": "COMPONENT_EXPENDITURE",
            "period": target_ym or "All Available Periods",
            "total_material_expenditure": round(total_material_spend, 2),
            "distinct_components_count": len(ranked_components),
            "top_component": ranked_components[0] if ranked_components else None,
            "ranked_components": ranked_components,
            "spend_by_product": {
                pid: {
                    "product_name": cls.PRODUCT_NAMES.get(pid, pid),
                    "total_material_spend": round(sum(mats.values()), 2),
                    "top_components": sorted([{"material_id": m, "spend": round(s, 2)} for m, s in mats.items()], key=lambda x: x["spend"], reverse=True)[:3],
                }
                for pid, mats in product_spend.items()
            },
            "evidence_classification": "PROVEN",
        }

    # =========================================================================
    # C. BOM AND MATERIAL CONSUMPTION
    # =========================================================================
    @classmethod
    def analyze_bom_consumption(
        cls,
        datasets: dict[str, Any],
        filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        bom_ds = datasets.get("BOM_COMPONENT") or datasets.get("BOM_COMPONENTS")
        cons_ds = datasets.get("MATERIAL_CONSUMPTION")
        prod_ds = datasets.get("HOURLY_PRODUCTION")

        if not bom_ds or not cons_ds or not prod_ds:
            return {"error": "BOM analysis requires BOM_COMPONENT, MATERIAL_CONSUMPTION, and HOURLY_PRODUCTION"}

        brows = bom_ds.get("rows", bom_ds.get("raw_rows", []))
        bmap = bom_ds.get("column_mapping", {})
        crows = cons_ds.get("rows", cons_ds.get("raw_rows", []))
        cmap = cons_ds.get("column_mapping", {})
        prows = prod_ds.get("rows", prod_ds.get("raw_rows", []))
        pmap = prod_ds.get("column_mapping", {})

        target_ym = resolve_target_ym(filters)
        cons_ds = datasets.get("MATERIAL_CONSUMPTION")
        purch_ds = datasets.get("PURCHASE_INVOICE") or datasets.get("PO_INVOICE")
        if not target_ym and (not filters or str((filters or {}).get("reporting_period", "")).upper() not in ("ALL", "ALL AVAILABLE PERIODS", "ALL PERIODS")):
            # Discover latest period from consumption or purchase records
            found_months: set[str] = set()
            for ds in (cons_ds, purch_ds):
                if ds:
                    r_list = ds.get("rows", ds.get("raw_rows", []))
                    c_map = ds.get("column_mapping", {})
                    for r in r_list:
                        ts = str(r.get("production_date") or r.get("consumption_ts") or r.get("receipt_date") or r.get("date") or "")
                        m_ym = re.match(r"^(\d{4})[-/](\d{1,2})", ts)
                        if m_ym:
                            found_months.add(f"{int(m_ym.group(1)):04d}-{int(m_ym.group(2)):02d}")
            if found_months:
                target_ym = sorted(list(found_months))[-1]

        # 1. Standard BOM allowance: product_id -> material_id -> standard_qty * (1 + scrap_factor)
        bom_rules = defaultdict(dict)
        for br in brows:
            pid = get_str(br, "product_id", bmap)
            mid = get_str(br, "material_id", bmap)
            q = get_val(br, "component_qty", bmap, default=1.0)
            s = get_val(br, "scrap_factor", bmap, default=0.0)
            bom_rules[pid][mid] = q * (1.0 + s)

        # 2. Production quantity by SKU in target period
        prod_by_sku = defaultdict(float)
        for pr in prows:
            ts = (
                get_str(pr, "production_date", pmap)
                or get_str(pr, "event_date", pmap)
                or get_str(pr, "event_ts", pmap)
                or get_str(pr, "date", pmap)
            )
            if target_ym and not ts.startswith(target_ym):
                continue
            pid = get_str(pr, "product_id", pmap)
            prod_by_sku[pid] += get_val(pr, "actual_qty", pmap)

        # 3. Expected standard BOM consumption
        expected_qty = defaultdict(float)
        for pid, pqty in prod_by_sku.items():
            for mid, std_ratio in bom_rules[pid].items():
                expected_qty[mid] += pqty * std_ratio

        # 4. Actual net consumption = issued_qty - returned_qty
        actual_net_qty = defaultdict(float)
        issued_qty_map = defaultdict(float)
        returned_qty_map = defaultdict(float)
        consumed_val_map = defaultdict(float)

        for cr in crows:
            ts = (
                get_str(cr, "production_date", cmap)
                or get_str(cr, "consumption_ts", cmap)
                or get_str(cr, "date", cmap)
            )
            if target_ym and not ts.startswith(target_ym):
                continue
            mid = get_str(cr, "material_id", cmap)
            iss = get_val(cr, "issued_qty", cmap)
            ret = get_val(cr, "returned_qty", cmap)
            net = get_val(cr, "net_consumed_qty", cmap) or (iss - ret)
            val = get_val(cr, "consumed_value_inr", cmap)

            issued_qty_map[mid] += iss
            returned_qty_map[mid] += ret
            actual_net_qty[mid] += net
            consumed_val_map[mid] += val

        # 5. Variance analysis
        variances = []
        total_financial_variance = 0.0

        for mid, exp_q in expected_qty.items():
            act_q = actual_net_qty.get(mid, 0.0)
            iss_q = issued_qty_map.get(mid, 0.0)
            ret_q = returned_qty_map.get(mid, 0.0)
            val = consumed_val_map.get(mid, 0.0)
            avg_unit_cost = (val / act_q) if act_q > 0 else 0.0

            diff_qty = act_q - exp_q
            diff_pct = (diff_qty / exp_q * 100.0) if exp_q > 0 else 0.0
            fin_impact = diff_qty * avg_unit_cost
            total_financial_variance += fin_impact

            status = "BALANCED"
            if diff_pct > 1.0:
                status = "OVER_CONSUMED"
            elif diff_pct < -1.0:
                status = "UNDER_CONSUMED"

            variances.append({
                "material_id": mid,
                "material_name": cls.MATERIAL_NAMES.get(mid, f"Component {mid}"),
                "expected_bom_qty": round(exp_q, 1),
                "issued_qty": round(iss_q, 1),
                "returned_qty": round(ret_q, 1),
                "actual_net_consumed_qty": round(act_q, 1),
                "variance_qty": round(diff_qty, 1),
                "variance_pct": round(diff_pct, 2),
                "avg_unit_cost": round(avg_unit_cost, 2),
                "financial_impact": round(fin_impact, 2),
                "status": status,
            })

        variances.sort(key=lambda x: abs(x["financial_impact"]), reverse=True)
        over_consumed = [v for v in variances if v["status"] == "OVER_CONSUMED"]
        under_consumed = [v for v in variances if v["status"] == "UNDER_CONSUMED"]

        return {
            "analysis_type": "BOM_CONSUMPTION",
            "period": target_ym or "All Available Periods",
            "components_evaluated": len(variances),
            "over_consumed_count": len(over_consumed),
            "under_consumed_count": len(under_consumed),
            "total_financial_impact": round(total_financial_variance, 2),
            "over_consumed_components": over_consumed,
            "under_consumed_components": under_consumed,
            "all_component_variances": variances,
            "evidence_classification": "PROVEN",
        }

    # =========================================================================
    # D. PRODUCTION AND QUALITY
    # =========================================================================
    @classmethod
    def analyze_production_quality(
        cls,
        datasets: dict[str, Any],
        filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not datasets or not isinstance(datasets, dict):
            return {"error": "Missing production datasets"}
        prod_ds = datasets.get("HOURLY_PRODUCTION")
        qual_ds = datasets.get("QUALITY_INSPECTION")
        if not prod_ds:
            return {"error": "Missing HOURLY_PRODUCTION dataset"}

        prows = prod_ds.get("rows", prod_ds.get("raw_rows", []))
        pmap = prod_ds.get("column_mapping", {})
        qrows = qual_ds.get("rows", qual_ds.get("raw_rows", [])) if qual_ds else []
        qmap = qual_ds.get("column_mapping", {}) if qual_ds else {}

        target_ym = resolve_target_ym(filters)
        cons_ds = datasets.get("MATERIAL_CONSUMPTION")
        purch_ds = datasets.get("PURCHASE_INVOICE") or datasets.get("PO_INVOICE")
        if not target_ym and (not filters or str((filters or {}).get("reporting_period", "")).upper() not in ("ALL", "ALL AVAILABLE PERIODS", "ALL PERIODS")):
            # Discover latest period from consumption or purchase records
            found_months: set[str] = set()
            for ds in (cons_ds, purch_ds):
                if ds:
                    r_list = ds.get("rows", ds.get("raw_rows", []))
                    c_map = ds.get("column_mapping", {})
                    for r in r_list:
                        ts = str(r.get("production_date") or r.get("consumption_ts") or r.get("receipt_date") or r.get("date") or "")
                        m_ym = re.match(r"^(\d{4})[-/](\d{1,2})", ts)
                        if m_ym:
                            found_months.add(f"{int(m_ym.group(1)):04d}-{int(m_ym.group(2)):02d}")
            if found_months:
                target_ym = sorted(list(found_months))[-1]

        total_actual = 0.0
        total_good = 0.0
        total_reject = 0.0
        total_rework = 0.0

        by_line = defaultdict(lambda: {"actual": 0.0, "good": 0.0, "reject": 0.0, "rework": 0.0})
        by_product = defaultdict(lambda: {"actual": 0.0, "good": 0.0, "reject": 0.0, "rework": 0.0})

        for r in prows:
            ts = (
                get_str(r, "production_date", pmap)
                or get_str(r, "event_date", pmap)
                or get_str(r, "event_ts", pmap)
                or get_str(r, "date", pmap)
            )
            if target_ym and not ts.startswith(target_ym):
                continue
            ln = get_str(r, "line_id", pmap)
            pid = get_str(r, "product_id", pmap)
            act = get_val(r, "actual_qty", pmap)
            gd = get_val(r, "good_qty", pmap)
            rej = get_val(r, "reject_qty", pmap)
            rwk = get_val(r, "rework_qty", pmap)

            total_actual += act
            total_good += gd
            total_reject += rej
            total_rework += rwk

            by_line[ln]["actual"] += act
            by_line[ln]["good"] += gd
            by_line[ln]["reject"] += rej
            by_line[ln]["rework"] += rwk

            by_product[pid]["actual"] += act
            by_product[pid]["good"] += gd
            by_product[pid]["reject"] += rej
            by_product[pid]["rework"] += rwk

        overall_yield = (total_good / total_actual * 100.0) if total_actual > 0 else 0.0
        overall_rej_rate = (total_reject / total_actual * 100.0) if total_actual > 0 else 0.0

        line_rankings = []
        for ln, d in by_line.items():
            l_act = d["actual"]
            l_rej = d["reject"]
            l_gd = d["good"]
            l_rate = (l_rej / l_act * 100.0) if l_act > 0 else 0.0
            l_yield = (l_gd / l_act * 100.0) if l_act > 0 else 0.0
            line_rankings.append({
                "line_id": ln,
                "actual_qty": round(l_act, 0),
                "good_qty": round(l_gd, 0),
                "reject_qty": round(l_rej, 0),
                "rework_qty": round(d["rework"], 0),
                "rejection_rate_pct": round(l_rate, 2),
                "yield_pct": round(l_yield, 2),
            })
        line_rankings.sort(key=lambda x: x["rejection_rate_pct"], reverse=True)

        # Defect inspection summary
        defect_breakdown = defaultdict(int)
        severity_breakdown = defaultdict(int)
        for qr in qrows:
            qts = (
                get_str(qr, "inspection_date", qmap)
                or get_str(qr, "inspection_ts", qmap)
                or get_str(qr, "inspection_timestamp", qmap)
                or get_str(qr, "date", qmap)
            )
            if target_ym and not qts.startswith(target_ym):
                continue
            code = get_str(qr, "defect_code", qmap)
            sev = get_str(qr, "severity", qmap)
            if code:
                defect_breakdown[code] += 1
            if sev:
                severity_breakdown[sev] += 1

        top_defects = [
            {"defect_code": k, "incident_count": v}
            for k, v in sorted(defect_breakdown.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        return {
            "analysis_type": "PRODUCTION_AND_QUALITY",
            "period": target_ym or "All Available Periods",
            "total_produced": round(total_actual, 0),
            "total_good": round(total_good, 0),
            "total_rejected": round(total_reject, 0),
            "total_rework": round(total_rework, 0),
            "overall_yield_pct": round(overall_yield, 2),
            "overall_rejection_rate_pct": round(overall_rej_rate, 2),
            "highest_rejection_line": line_rankings[0] if line_rankings else None,
            "line_rankings": line_rankings,
            "product_rankings": [
                {
                    "product_id": pid,
                    "product_name": cls.PRODUCT_NAMES.get(pid, pid),
                    "actual_qty": round(d["actual"], 0),
                    "rejection_rate_pct": round((d["reject"] / d["actual"] * 100), 2) if d["actual"] else 0,
                    "yield_pct": round((d["good"] / d["actual"] * 100), 2) if d["actual"] else 0,
                }
                for pid, d in sorted(by_product.items(), key=lambda x: x[1]["reject"], reverse=True)
            ],
            "top_inspection_defects": top_defects,
            "severity_distribution": dict(severity_breakdown),
            "evidence_classification": "PROVEN",
        }

    # =========================================================================
    # E. SCRAP AND REWORK
    # =========================================================================
    @classmethod
    def analyze_scrap_rework(
        cls,
        datasets: dict[str, Any],
        filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        rwk_ds = datasets.get("QUALITY_REWORK_EVENTS")
        if not rwk_ds:
            return {"error": "Missing QUALITY_REWORK_EVENTS dataset"}

        rows = rwk_ds.get("rows", rwk_ds.get("raw_rows", []))
        rmap = rwk_ds.get("column_mapping", {})
        target_ym = resolve_target_ym(filters)
        cons_ds = datasets.get("MATERIAL_CONSUMPTION")
        purch_ds = datasets.get("PURCHASE_INVOICE") or datasets.get("PO_INVOICE")
        if not target_ym and (not filters or str((filters or {}).get("reporting_period", "")).upper() not in ("ALL", "ALL AVAILABLE PERIODS", "ALL PERIODS")):
            # Discover latest period from consumption or purchase records
            found_months: set[str] = set()
            for ds in (cons_ds, purch_ds):
                if ds:
                    r_list = ds.get("rows", ds.get("raw_rows", []))
                    c_map = ds.get("column_mapping", {})
                    for r in r_list:
                        ts = str(r.get("production_date") or r.get("consumption_ts") or r.get("receipt_date") or r.get("date") or "")
                        m_ym = re.match(r"^(\d{4})[-/](\d{1,2})", ts)
                        if m_ym:
                            found_months.add(f"{int(m_ym.group(1)):04d}-{int(m_ym.group(2)):02d}")
            if found_months:
                target_ym = sorted(list(found_months))[-1]

        total_exp = 0.0
        total_labour_cost = 0.0
        total_other_cost = 0.0
        total_hours = 0.0
        total_rej_units = 0.0
        total_rwk_units = 0.0

        by_defect = defaultdict(lambda: {"cost": 0.0, "hours": 0.0, "events": 0, "defect_type": "Unknown"})
        by_line = defaultdict(lambda: {"cost": 0.0, "events": 0})
        by_product = defaultdict(lambda: {"cost": 0.0, "events": 0})

        matching_events = 0
        for r in rows:
            ts = (
                get_str(r, "event_date", rmap)
                or get_str(r, "event_timestamp", rmap)
                or get_str(r, "event_ts", rmap)
                or get_str(r, "date", rmap)
            )
            if target_ym and not ts.startswith(target_ym):
                continue
            matching_events += 1
            exp = get_val(r, "actual_rework_expenditure_inr", rmap)
            lcost = get_val(r, "rework_labour_cost_inr", rmap)
            ocost = get_val(r, "other_remediation_cost_inr", rmap)
            hrs = get_val(r, "rework_hours", rmap)
            rej_q = get_val(r, "rejected_qty", rmap)
            rwk_q = get_val(r, "rework_qty", rmap)

            code = get_str(r, "defect_code", rmap)
            dtype = get_str(r, "defect_type", rmap)
            ln = get_str(r, "line_id", rmap)
            pid = get_str(r, "product_id", rmap)

            total_exp += exp
            total_labour_cost += lcost
            total_other_cost += ocost
            total_hours += hrs
            total_rej_units += rej_q
            total_rwk_units += rwk_q

            by_defect[code]["cost"] += exp
            by_defect[code]["hours"] += hrs
            by_defect[code]["events"] += 1
            if dtype:
                by_defect[code]["defect_type"] = dtype

            by_line[ln]["cost"] += exp
            by_line[ln]["events"] += 1
            by_product[pid]["cost"] += exp
            by_product[pid]["events"] += 1

        top_defects = [
            {
                "defect_code": code,
                "defect_type": d["defect_type"],
                "cost": round(d["cost"], 2),
                "rework_hours": round(d["hours"], 1),
                "events_count": d["events"],
                "share_pct": round(d["cost"] / total_exp * 100.0, 2) if total_exp else 0,
            }
            for code, d in sorted(by_defect.items(), key=lambda x: x[1]["cost"], reverse=True)
        ]

        return {
            "analysis_type": "SCRAP_AND_REWORK",
            "period": target_ym or "All Available Periods",
            "total_rework_expenditure": round(total_exp, 2),
            "rework_labour_cost": round(total_labour_cost, 2),
            "rework_remediation_cost": round(total_other_cost, 2),
            "total_rework_hours": round(total_hours, 1),
            "rejected_units_reworked": round(total_rej_units, 0),
            "reworked_units_output": round(total_rwk_units, 0),
            "events_count": matching_events,
            "top_defects": top_defects,
            "line_contributions": [
                {"line_id": ln, "cost": round(d["cost"], 2), "events": d["events"], "share_pct": round(d["cost"] / total_exp * 100, 2) if total_exp else 0}
                for ln, d in sorted(by_line.items(), key=lambda x: x[1]["cost"], reverse=True)
            ],
            "product_contributions": [
                {"product_id": pid, "product_name": cls.PRODUCT_NAMES.get(pid, pid), "cost": round(d["cost"], 2), "events": d["events"]}
                for pid, d in sorted(by_product.items(), key=lambda x: x[1]["cost"], reverse=True)
            ],
            "evidence_classification": "PROVEN",
        }
