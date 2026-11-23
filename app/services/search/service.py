"""
Global Manufacturing Intelligence Search Service.
Executes efficient, parameterized SQL queries across Neon PostgreSQL manufacturing tables
and classifies investigative questions for direct AI Cost Agent orchestration.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.models.real_datasets import (
    LineCostBatch,
    HourlyProductionLog,
    SerializedQualityInspection,
    BomComponentRecord,
)
from .schemas import SearchResultItem, SearchNavigationTarget, GlobalSearchResponse

logger = logging.getLogger(__name__)

# Known component catalog descriptions and categories matching manufacturing BOM standards
KNOWN_COMPONENTS = [
    {
        "id": "SOC-SNAP-8G3",
        "name": "Snapdragon 8 Gen 3 Application Processor",
        "category": "Semiconductor / SoC",
        "unit_cost": "₹4,120.00",
        "used_in": ["SPH-PRO-256"],
        "keywords": ["soc", "processor", "cpu", "snapdragon", "chip", "semiconductor"],
    },
    {
        "id": "DISP-AMOLED-67",
        "name": "6.7\" LTPO 120Hz AMOLED Flexible Display",
        "category": "Display & Touch",
        "unit_cost": "₹2,450.00",
        "used_in": ["SPH-PRO-256"],
        "keywords": ["display", "screen", "amoled", "ltpo", "oled", "touch", "panel", "mat-dsp-005"],
    },
    {
        "id": "NAND-256G-UFS",
        "name": "256GB UFS 4.0 High-Speed NAND Flash",
        "category": "Memory & Storage",
        "unit_cost": "₹1,280.00",
        "used_in": ["SPH-PRO-256", "SPH-A15-256"],
        "keywords": ["nand", "flash", "storage", "256gb", "memory", "ufs", "mat-nand-003"],
    },
    {
        "id": "NAND-128G-UFS",
        "name": "128GB UFS 3.1 High-Speed NAND Flash",
        "category": "Memory & Storage",
        "unit_cost": "₹920.00",
        "used_in": ["SPH-A15-128"],
        "keywords": ["nand", "flash", "storage", "128gb", "memory", "ufs"],
    },
    {
        "id": "CAM-MOD-50M",
        "name": "50MP Primary Optical Stabilization Camera",
        "category": "Optics / Camera",
        "unit_cost": "₹1,650.00",
        "used_in": ["SPH-PRO-256"],
        "keywords": ["camera", "sensor", "50mp", "optics", "lens", "ois", "mat-cam-007"],
    },
    {
        "id": "RAM-12G-LPDDR5",
        "name": "12GB LPDDR5X Low-Power Mobile DRAM",
        "category": "Memory & Storage",
        "unit_cost": "₹890.00",
        "used_in": ["SPH-PRO-256"],
        "keywords": ["ram", "lpddr5", "dram", "memory", "12gb", "mat-mem-002"],
    },
    {
        "id": "RAM-8G-LPDDR5",
        "name": "8GB LPDDR5 Low-Power Mobile DRAM",
        "category": "Memory & Storage",
        "unit_cost": "₹680.00",
        "used_in": ["SPH-A15-256", "SPH-A15-128"],
        "keywords": ["ram", "lpddr5", "dram", "memory", "8gb"],
    },
    {
        "id": "BAT-5000-LI",
        "name": "5000mAh Dual-Cell Lithium-Ion Battery Pack",
        "category": "Power / Battery",
        "unit_cost": "₹540.00",
        "used_in": ["SPH-PRO-256", "SPH-A15-256", "SPH-A15-128"],
        "keywords": ["battery", "power", "5000mah", "cell", "lithium", "mat-bat-006"],
    },
    {
        "id": "HSG-ALUM-CNC",
        "name": "CNC Machined Aerospace Aluminium Chassis Frame",
        "category": "Mechanical / Structure",
        "unit_cost": "₹420.00",
        "used_in": ["SPH-PRO-256"],
        "keywords": ["housing", "chassis", "frame", "aluminium", "cnc", "body", "mat-hsg-009"],
    },
]

# Standard Cost Analysis Categories
COST_ANALYSIS_TOPICS = [
    {
        "id": "material",
        "title": "Direct Material Cost & Inflation",
        "subtitle": "₹299.50 Cr • 95.26% Share of Direct Expenditure",
        "description": "Material variance decomposed into PPV (₹96.65M) and MUV (₹35.68M).",
        "relevant_metric": "95.26% Share",
        "tab": "material",
        "keywords": ["material", "materials", "raw material", "purchase price", "ppv", "muv", "material cost"],
    },
    {
        "id": "labour",
        "title": "Direct Labour Expenditure",
        "subtitle": "₹8.29 Cr • 2.64% Share • Line FAL-L1 & FAL-L2",
        "description": "Standard vs actual shift man-hours and operator staffing dynamics.",
        "relevant_metric": "2.64% Share",
        "tab": "labour",
        "keywords": ["labour", "labor", "worker", "shift", "operator", "manpower", "wage"],
    },
    {
        "id": "machine",
        "title": "Machine Depreciation & Tooling",
        "subtitle": "₹4.74 Cr • 1.51% Share • SMT & Assembly Lines",
        "description": "High-speed pick-and-place uptime and line equipment depreciation.",
        "relevant_metric": "1.51% Share",
        "tab": "machine",
        "keywords": ["machine", "tooling", "depreciation", "equipment", "smt", "maintenance"],
    },
    {
        "id": "energy",
        "title": "Energy & Factory Utilities",
        "subtitle": "₹1.46 Cr • 0.46% Share • Cleanroom & SMT Reflow",
        "description": "Power consumption, HVAC cleanroom nitrogen, and reflow oven energy.",
        "relevant_metric": "0.46% Share",
        "tab": "energy",
        "keywords": ["energy", "electricity", "power", "utility", "utilities", "hvac", "kilowatt"],
    },
    {
        "id": "scrap",
        "title": "Scrap & Quality Rework Costs",
        "subtitle": "₹0.42 Cr • Defect Rework & Discarded Assemblies",
        "description": "Direct losses incurred from SMT solder bridges and defective displays.",
        "relevant_metric": "₹0.42 Cr",
        "tab": "scrap",
        "keywords": ["scrap", "rework", "defect", "waste", "yield loss", "rejected"],
    },
    {
        "id": "variance",
        "title": "Deterministic Variance Analysis Bridge",
        "subtitle": "Price Effect (₹9.69 Cr) vs Usage Effect (₹3.62 Cr)",
        "description": "Full mathematical decomposition of the ₹22.93 Cr cost movement.",
        "relevant_metric": "₹22.93 Cr Delta",
        "tab": "variance",
        "keywords": ["variance", "bridge", "price effect", "usage effect", "volume mix", "residual"],
    },
    {
        "id": "drivers",
        "title": "Key Manufacturing Cost Drivers",
        "subtitle": "Ranked contributors to smartphone manufacturing cost increases",
        "description": "NAND flash price escalation, AMOLED yield loss, and Line L2 rework.",
        "relevant_metric": "Top 5 Drivers",
        "tab": "drivers",
        "keywords": ["driver", "drivers", "root cause", "contributor", "escalation", "inflation"],
    },
]

# Plant and Line metadata
PRODUCTION_FACILITIES = [
    {
        "id": "IN-KA-01",
        "type": "PLANT",
        "title": "Plant IN-KA-01 (Karnataka Facility)",
        "subtitle": "High-Density SMT & Electronics Module Assembly",
        "description": "Host to Lines FAL-L2 and SMT-L2. Total output: 687,136 units.",
        "relevant_metric": "687,136 units",
        "tab": "production-quality",
        "params": {"plant": "IN-KA-01"},
        "keywords": ["karnataka", "in-ka-01", "ka-01", "bangalore"],
    },
    {
        "id": "IN-TN-01",
        "type": "PLANT",
        "title": "Plant IN-TN-01 (Tamil Nadu Facility)",
        "subtitle": "Final Assembly & Packout Operations (FAL)",
        "description": "Host to Lines FAL-L1 and SMT-L1. Total output: 682,727 units.",
        "relevant_metric": "682,727 units",
        "tab": "production-quality",
        "params": {"plant": "IN-TN-01"},
        "keywords": ["tamil nadu", "in-tn-01", "tn-01", "chennai"],
    },
    {
        "id": "FAL-L1",
        "type": "PRODUCTION_LINE",
        "title": "Production Line FAL-L1",
        "subtitle": "Final Assembly Line 1 • Plant IN-TN-01",
        "description": "1,268 promoted cost batches • 283,878 units produced • High assembly yield.",
        "relevant_metric": "283,878 units",
        "tab": "production-quality",
        "params": {"line": "FAL-L1"},
        "keywords": ["fal-l1", "line fal-l1", "assembly line 1"],
    },
    {
        "id": "FAL-L2",
        "type": "PRODUCTION_LINE",
        "title": "Production Line FAL-L2",
        "subtitle": "Final Assembly Line 2 • Plant IN-KA-01",
        "description": "1,256 cost batches • 284,478 units produced • Higher rework frequency.",
        "relevant_metric": "284,478 units",
        "tab": "production-quality",
        "params": {"line": "FAL-L2"},
        "keywords": ["fal-l2", "line fal-l2", "assembly line 2"],
    },
    {
        "id": "SMT-L1",
        "type": "PRODUCTION_LINE",
        "title": "Production Line SMT-L1",
        "subtitle": "Surface Mount Technology Line 1 • Plant IN-TN-01",
        "description": "1,237 cost batches • 398,849 units produced • High speed component placement.",
        "relevant_metric": "398,849 units",
        "tab": "production-quality",
        "params": {"line": "SMT-L1"},
        "keywords": ["smt-l1", "line smt-l1", "smt line 1"],
    },
    {
        "id": "SMT-L2",
        "type": "PRODUCTION_LINE",
        "title": "Production Line SMT-L2",
        "subtitle": "Surface Mount Technology Line 2 • Plant IN-KA-01",
        "description": "1,239 cost batches • 402,658 units produced • Solder bridge defect focus.",
        "relevant_metric": "402,658 units",
        "tab": "production-quality",
        "params": {"line": "SMT-L2"},
        "keywords": ["smt-l2", "line smt-l2", "smt line 2"],
    },
]

# Quality Defect Codes
DEFECT_DEFINITIONS = [
    {
        "code": "D001",
        "title": "Defect D001: SMT Solder Bridge Short",
        "subtitle": "SMT Line station failure • High rework frequency",
        "description": "Excess solder paste bridging adjacent IC pins on main logic board.",
        "relevant_metric": "Line SMT-L2",
        "tab": "production-quality",
        "params": {"defect": "D001"},
        "keywords": ["d001", "solder", "bridge", "short circuit"],
    },
    {
        "code": "D002",
        "title": "Defect D002: Surface Contamination & Residue",
        "subtitle": "Optical inspection reject • Cleanroom particulate",
        "description": "Flux residue or dust particles detected prior to optical bonding.",
        "relevant_metric": "Scrap & Hold",
        "tab": "production-quality",
        "params": {"defect": "D002"},
        "keywords": ["d002", "contamination", "dust", "flux", "residue"],
    },
    {
        "code": "D004",
        "title": "Defect D004: Passive Component Misalignment",
        "subtitle": "SMT Pick & Place nozzle pressure variance",
        "description": "Chip resistors and capacitors shifted during high-speed placement.",
        "relevant_metric": "SMT Placement",
        "tab": "production-quality",
        "params": {"defect": "D004"},
        "keywords": ["d004", "misalignment", "nozzle", "shift"],
    },
    {
        "code": "D007",
        "title": "Defect D007: Display Pixel Blemish / Mura",
        "subtitle": "AMOLED panel inspection failure • Supplier Lot Variance",
        "description": "Non-uniform brightness or subpixel dead spot on display assembly.",
        "relevant_metric": "Display Reject",
        "tab": "production-quality",
        "params": {"defect": "D007"},
        "keywords": ["d007", "display blemish", "pixel", "mura", "screen defect"],
    },
]


class GlobalSearchService:
    """Enterprise service orchestrating global search across all manufacturing entities."""

    QUESTION_STARTERS = (
        "why", "which", "what", "how", "compare", "analyze", "is",
        "explain", "where", "identify", "can", "tell me", "does", "who"
    )

    QUESTION_KEYWORDS = (
        "increase", "higher", "highest", "opportunity", "saving", "scrap",
        "variance", "rejection", "affecting", "cost increase", "rework",
        "contribute", "between", "versus", "vs", "opportunity"
    )

    @classmethod
    def is_question(cls, query: str) -> bool:
        """Determines if query represents an analytical question rather than a static entity lookup."""
        q = query.strip().lower()
        if not q:
            return False
        if q.endswith("?"):
            return True
        first_word = q.split()[0] if q.split() else ""
        if first_word in cls.QUESTION_STARTERS:
            return True
        if len(q.split()) >= 4 and any(k in q for k in cls.QUESTION_KEYWORDS):
            return True
        return False

    @classmethod
    def execute_global_search(
        cls,
        db: Session,
        query: str,
        limit: int = 10,
    ) -> GlobalSearchResponse:
        """
        Executes unified search across Products, Materials, Components, Cost Analysis,
        Production Lines, and Quality Inspections.
        """
        raw_q = query.strip()
        if not raw_q:
            return GlobalSearchResponse(query=query, is_question=False, total_matches=0, categories={})

        q_lower = raw_q.lower()
        is_q = cls.is_question(raw_q)

        categories: Dict[str, List[SearchResultItem]] = {
            "PRODUCTS": [],
            "MATERIALS_COMPONENTS": [],
            "COST_ANALYSIS": [],
            "PRODUCTION_QUALITY": [],
        }

        # 1. SEARCH PRODUCTS (From line_cost_batches actuals in Neon DB)
        products = cls._search_products(db, q_lower, limit=5)
        if products:
            categories["PRODUCTS"] = products

        # 2. SEARCH MATERIALS & COMPONENTS (BOM, specifications, pricing)
        components = cls._search_materials_and_components(db, q_lower, limit=5)
        if components:
            categories["MATERIALS_COMPONENTS"] = components

        # 3. SEARCH COST ANALYSIS TOPICS & VARIANCES
        costs = cls._search_cost_analysis(q_lower, limit=4)
        if costs:
            categories["COST_ANALYSIS"] = costs

        # 4. SEARCH PRODUCTION & QUALITY (Facilities, Lines, Defect Codes)
        prod_qual = cls._search_production_and_quality(db, q_lower, limit=5)
        if prod_qual:
            categories["PRODUCTION_QUALITY"] = prod_qual

        # Clean empty categories
        populated_categories = {k: v for k, v in categories.items() if v}
        total_count = sum(len(v) for v in populated_categories.values())

        return GlobalSearchResponse(
            query=raw_q,
            is_question=is_q,
            suggested_investigation=raw_q if is_q else None,
            total_matches=total_count,
            categories=populated_categories,
        )

    @classmethod
    def _search_products(cls, db: Session, q: str, limit: int = 5) -> List[SearchResultItem]:
        """Queries line_cost_batches aggregated by product for actual direct cost and volume."""
        results: List[SearchResultItem] = []
        try:
            sql = text("""
                SELECT 
                    product_code,
                    count(*) as batch_count,
                    sum(total_direct_cost_inr) as total_cost,
                    sum(material_cost_inr) as mat_cost,
                    sum(produced_qty) as total_qty
                FROM line_cost_batches
                WHERE lower(product_code) LIKE :pattern
                   OR lower(product_code) LIKE :fuzzy
                GROUP BY product_code
                ORDER BY total_cost DESC
                LIMIT :limit;
            """)
            rows = db.execute(
                sql,
                {
                    "pattern": f"%{q}%",
                    "fuzzy": f"%{q.replace('-', '%')}%",
                    "limit": limit,
                },
            ).fetchall()

            product_meta = {
                "SPH-PRO-256": {"name": "Pro Smartphone 256GB (AMOLED LTPO + 50MP)", "badge": "PRO"},
                "SPH-A15-256": {"name": "Standard Smartphone 256GB (High Volume)", "badge": "A15"},
                "SPH-A15-128": {"name": "Standard Smartphone 128GB (Entry Tier)", "badge": "A15"},
                "SPH-PRO-512": {"name": "Pro Smartphone 512GB (High-Density Tier)", "badge": "PRO"},
            }

            for r in rows:
                p_code = r[0]
                tot_cost = float(r[2] or 0.0)
                tot_qty = float(r[4] or 0.0)
                avg_unit = (tot_cost / tot_qty) if tot_qty > 0 else 0.0
                cost_cr = round(tot_cost / 10000000.0, 2)
                meta = product_meta.get(p_code, {"name": f"Manufacturing SKU {p_code}", "badge": "SKU"})

                results.append(
                    SearchResultItem(
                        id=f"prod_{p_code}",
                        entity_type="PRODUCT",
                        category="PRODUCTS",
                        title=p_code,
                        subtitle=meta["name"],
                        description=f"Total Cost: ₹{cost_cr} Cr • {int(tot_qty):,} Units Produced across {r[1]} batches",
                        relevant_metric=f"₹{avg_unit:,.2f} / unit",
                        badge=meta["badge"],
                        navigation_target=SearchNavigationTarget(
                            tab="product-analysis",
                            params={"product": p_code},
                        ),
                    )
                )
        except Exception as exc:
            logger.warning("Error querying products in global search: %s", exc)

        # Fallback keyword match if specific product words matched but not raw code
        if not results:
            if any(term in q for term in ["phone", "smartphone", "sph", "pro", "product", "sku"]):
                for p_code in ["SPH-PRO-256", "SPH-A15-256", "SPH-A15-128"]:
                    results.append(
                        SearchResultItem(
                            id=f"prod_fallback_{p_code}",
                            entity_type="PRODUCT",
                            category="PRODUCTS",
                            title=p_code,
                            subtitle="Smartphone Manufacturing SKU",
                            description="Direct actual batch costing and BOM variance reconciliation.",
                            relevant_metric="View Model",
                            badge="PRODUCT",
                            navigation_target=SearchNavigationTarget(
                                tab="product-analysis",
                                params={"product": p_code},
                            ),
                        )
                    )
        return results

    @classmethod
    def _search_materials_and_components(cls, db: Session, q: str, limit: int = 5) -> List[SearchResultItem]:
        """Searches component catalog and database BOM component records."""
        results: List[SearchResultItem] = []

        # 1. Match from authoritative component catalog
        for comp in KNOWN_COMPONENTS:
            matches_id = q in comp["id"].lower()
            matches_name = q in comp["name"].lower()
            matches_category = q in comp["category"].lower()
            matches_keywords = any(q in kw or kw in q for kw in comp["keywords"])

            if matches_id or matches_name or matches_category or matches_keywords:
                results.append(
                    SearchResultItem(
                        id=f"comp_{comp['id']}",
                        entity_type="COMPONENT",
                        category="MATERIALS_COMPONENTS",
                        title=comp["name"],
                        subtitle=f"{comp['id']} • {comp['category']}",
                        description=f"Used in: {', '.join(comp['used_in'])}",
                        relevant_metric=comp["unit_cost"],
                        badge=comp["category"].split()[0],
                        navigation_target=SearchNavigationTarget(
                            tab="component-analysis",
                            params={"component": comp["id"]},
                        ),
                    )
                )
                if len(results) >= limit:
                    break

        # 2. Also check database bom_component_records for raw codes (e.g. MAT-NAND-003)
        if len(results) < limit:
            try:
                sql = text("""
                    SELECT DISTINCT material_code, product_code, component_qty, scrap_factor
                    FROM bom_component_records
                    WHERE lower(material_code) LIKE :pattern
                    ORDER BY material_code
                    LIMIT :limit;
                """)
                rows = db.execute(sql, {"pattern": f"%{q}%", "limit": limit - len(results)}).fetchall()
                for r in rows:
                    mat_code = r[0]
                    if not any(item.id.endswith(mat_code) for item in results):
                        results.append(
                            SearchResultItem(
                                id=f"bom_mat_{mat_code}",
                                entity_type="MATERIAL",
                                category="MATERIALS_COMPONENTS",
                                title=mat_code,
                                subtitle=f"BOM Standard Component for {r[1]}",
                                description=f"Std Qty: {r[2]} per unit • Scrap Factor: {float(r[3])*100:.1f}%",
                                relevant_metric=f"Qty: {r[2]}",
                                badge="MATERIAL",
                                navigation_target=SearchNavigationTarget(
                                    tab="component-analysis",
                                    params={"component": mat_code},
                                ),
                            )
                        )
            except Exception as exc:
                logger.warning("Error querying bom_component_records in search: %s", exc)

        return results[:limit]

    @classmethod
    def _search_cost_analysis(cls, q: str, limit: int = 4) -> List[SearchResultItem]:
        """Matches cost categories, variance decomposition topics, and financial breakdown concepts."""
        results: List[SearchResultItem] = []
        for topic in COST_ANALYSIS_TOPICS:
            matches_title = q in topic["title"].lower()
            matches_sub = q in topic["subtitle"].lower()
            matches_desc = q in topic["description"].lower()
            matches_kw = any(q in kw or kw in q for kw in topic["keywords"])

            if matches_title or matches_sub or matches_desc or matches_kw:
                results.append(
                    SearchResultItem(
                        id=f"cost_{topic['id']}",
                        entity_type="COST_RECORD",
                        category="COST_ANALYSIS",
                        title=topic["title"],
                        subtitle=topic["subtitle"],
                        description=topic["description"],
                        relevant_metric=topic["relevant_metric"],
                        badge="COST",
                        navigation_target=SearchNavigationTarget(
                            tab="cost-analysis",
                            params={"tab": topic["tab"]},
                        ),
                    )
                )
                if len(results) >= limit:
                    break
        return results

    @classmethod
    def _search_production_and_quality(cls, db: Session, q: str, limit: int = 5) -> List[SearchResultItem]:
        """Matches Plants, Production Lines, and Quality Defect Dispositions."""
        results: List[SearchResultItem] = []

        # 1. Match facilities and lines
        for fac in PRODUCTION_FACILITIES:
            matches_title = q in fac["title"].lower()
            matches_sub = q in fac["subtitle"].lower()
            matches_kw = any(q in kw or kw in q for kw in fac["keywords"])

            if matches_title or matches_sub or matches_kw:
                results.append(
                    SearchResultItem(
                        id=f"fac_{fac['id']}",
                        entity_type=fac["type"],
                        category="PRODUCTION_QUALITY",
                        title=fac["title"],
                        subtitle=fac["subtitle"],
                        description=fac["description"],
                        relevant_metric=fac["relevant_metric"],
                        badge=fac["id"],
                        navigation_target=SearchNavigationTarget(
                            tab="production-quality",
                            params=fac["params"],
                        ),
                    )
                )
                if len(results) >= limit:
                    break

        # 2. Match Defect Codes
        if len(results) < limit:
            for defect in DEFECT_DEFINITIONS:
                matches_code = q in defect["code"].lower()
                matches_title = q in defect["title"].lower()
                matches_kw = any(q in kw or kw in q for kw in defect["keywords"])

                if matches_code or matches_title or matches_kw:
                    results.append(
                        SearchResultItem(
                            id=f"defect_{defect['code']}",
                            entity_type="QUALITY_DEFECT",
                            category="PRODUCTION_QUALITY",
                            title=defect["title"],
                            subtitle=defect["subtitle"],
                            description=defect["description"],
                            relevant_metric=defect["relevant_metric"],
                            badge=defect["code"],
                            navigation_target=SearchNavigationTarget(
                                tab="production-quality",
                                params=defect["params"],
                            ),
                        )
                    )
                    if len(results) >= limit:
                        break

        return results[:limit]

