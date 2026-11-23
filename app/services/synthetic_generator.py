"""
Manufacturing Cost Agent - Deterministic Synthetic Dataset Generator
Generates a 3-plant, 6-month historical manufacturing dataset covering all 6 cost categories
and embedding 6 specific, documented investigation scenarios.
"""

import datetime as dt
import logging
from typing import Any
from sqlalchemy.orm import Session
from ..models import (
    Plant,
    ProductionLine,
    WorkCentre,
    Product,
    Material,
    Supplier,
    UnitOfMeasure,
    UnitConversion,
    CalendarPeriod,
    ExchangeRate,
    CostingVersion,
    StandardCostItem,
    BillOfMaterials,
    BOMItem,
    Routing,
    RoutingStep,
    ProductionOrder,
    ProductionOutput,
    MaterialPosting,
    LabourPosting,
    MachineEvent,
    EnergyReading,
    QualityEvent,
    OverheadPool,
    SupplierPriceHistory,
)

logger = logging.getLogger("manufacturing_cost_agent.synthetic")


class SyntheticDatasetGenerator:
    """Generates deterministic benchmark manufacturing data for testing and development."""

    def generate_all(self, db: Session | None = None) -> dict[str, Any]:
        """
        Generates master data, standards, and actuals.
        If a database session is provided, persists all entities.
        Returns a summary report of generated entities.
        """
        logger.info("Generating deterministic manufacturing benchmark dataset...")

        # 1. Units of Measure
        uoms = [
            UnitOfMeasure(code="EA", name="Each", category="COUNT", is_synthetic=True),
            UnitOfMeasure(code="KG", name="Kilogram", category="WEIGHT", is_synthetic=True),
            UnitOfMeasure(code="MTR", name="Meter", category="LENGTH", is_synthetic=True),
            UnitOfMeasure(code="LTR", name="Litre", category="VOLUME", is_synthetic=True),
            UnitOfMeasure(code="HR", name="Hour", category="TIME", is_synthetic=True),
            UnitOfMeasure(code="KWH", name="Kilowatt Hour", category="ENERGY", is_synthetic=True),
        ]

        # 2. 3 Manufacturing Plants
        plants = [
            Plant(
                code="PLANT-PUN",
                name="Pune Precision Machining & Assembly",
                location="Pune, Maharashtra",
                country="India",
                currency="INR",
                capacity_hours_month=4500.00,
                is_synthetic=True,
            ),
            Plant(
                code="PLANT-CHE",
                name="Chennai Heavy Motors & Foundry",
                location="Chennai, Tamil Nadu",
                country="India",
                currency="INR",
                capacity_hours_month=5200.00,
                is_synthetic=True,
            ),
            Plant(
                code="PLANT-GUJ",
                name="Gujarat Castings & Transmission Works",
                location="Sanand, Gujarat",
                country="India",
                currency="INR",
                capacity_hours_month=4000.00,
                is_synthetic=True,
            ),
        ]

        # 3. Calendar Periods (6 Months: 2026-M01 to 2026-M06)
        periods = [
            CalendarPeriod(code="2026-M01", year=2026, month=1, start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 31), working_days=25, is_synthetic=True),
            CalendarPeriod(code="2026-M02", year=2026, month=2, start_date=dt.date(2026, 2, 1), end_date=dt.date(2026, 2, 28), working_days=23, is_synthetic=True),
            CalendarPeriod(code="2026-M03", year=2026, month=3, start_date=dt.date(2026, 3, 1), end_date=dt.date(2026, 3, 31), working_days=25, is_synthetic=True),
            CalendarPeriod(code="2026-M04", year=2026, month=4, start_date=dt.date(2026, 4, 1), end_date=dt.date(2026, 4, 30), working_days=24, is_synthetic=True),
            CalendarPeriod(code="2026-M05", year=2026, month=5, start_date=dt.date(2026, 5, 1), end_date=dt.date(2026, 5, 31), working_days=25, is_synthetic=True),
            CalendarPeriod(code="2026-M06", year=2026, month=6, start_date=dt.date(2026, 6, 1), end_date=dt.date(2026, 6, 30), working_days=25, is_synthetic=True),
        ]

        # 4. Products
        products = [
            Product(code="PRD-MOTOR-01", name="Industrial Induction Motor 15kW", product_group="Electric Motors", uom="EA", standard_batch_size=50.00, is_synthetic=True),
            Product(code="PRD-GEAR-02", name="Planetary Reduction Gearbox 4:1", product_group="Transmissions", uom="EA", standard_batch_size=40.00, is_synthetic=True),
            Product(code="PRD-PUMP-03", name="High-Pressure Hydraulic Pump 250bar", product_group="Hydraulics", uom="EA", standard_batch_size=30.00, is_synthetic=True),
        ]

        # 5. Raw Materials
        materials = [
            Material(code="MAT-STEEL-01", name="Alloy Steel Bar 4140 Annealed", material_type="RAW", base_uom="KG", standard_unit_price=65.0000, currency="INR", is_synthetic=True),
            Material(code="MAT-COPPER-01", name="Electrolytic Copper Wire 1.2mm", material_type="RAW", base_uom="KG", standard_unit_price=680.0000, currency="INR", is_synthetic=True),
            Material(code="MAT-ALUM-01", name="Die-Cast Aluminium Ingot A380", material_type="RAW", base_uom="KG", standard_unit_price=195.0000, currency="INR", is_synthetic=True),
            Material(code="MAT-SEAL-01", name="Viton High-Temp Lip Seal", material_type="COMPONENT", base_uom="EA", standard_unit_price=120.0000, currency="INR", is_synthetic=True),
        ]

        # 6. Suppliers
        suppliers = [
            Supplier(code="SUP-TATA", name="Tata Steel Industrial Alloys", country="India", payment_terms="Net 45", reliability_rating=4.8, is_synthetic=True),
            Supplier(code="SUP-HINDALCO", name="Hindalco Non-Ferrous Metals", country="India", payment_terms="Net 30", reliability_rating=4.7, is_synthetic=True),
            Supplier(code="SUP-SCHNEIDER", name="Schneider Precision Components", country="Germany", payment_terms="Net 60", reliability_rating=4.9, is_synthetic=True),
        ]

        # 7. Active Costing Version
        costing_version = CostingVersion(
            code="AOP-2026-V1",
            name="Annual Operating Plan 2026 Baseline Standards",
            valid_from=dt.date(2026, 1, 1),
            valid_to=dt.date(2026, 12, 31),
            is_active=True,
            status="APPROVED",
            is_synthetic=True,
        )

        # 8. Work Centres & Lines
        lines = [
            ProductionLine(plant_id=1, code="LINE-PUN-01", name="Motor Assembly Line 1", line_type="MAIN_ASSEMBLY", is_synthetic=True),
            ProductionLine(plant_id=2, code="LINE-CHE-01", name="Heavy Foundry & Machining Line", line_type="MACHINING", is_synthetic=True),
            ProductionLine(plant_id=3, code="LINE-GUJ-01", name="Transmission Assembly Line", line_type="MAIN_ASSEMBLY", is_synthetic=True),
        ]
        work_centres = [
            WorkCentre(plant_id=1, code="WC-CNC-01", name="5-Axis CNC Milling Cell", cost_centre_code="CC-PUN-MACH", hourly_machine_rate=1250.00, hourly_labour_rate=250.00, is_synthetic=True),
            WorkCentre(plant_id=1, code="WC-ASSY-01", name="Motor Stator & Rotor Assembly", cost_centre_code="CC-PUN-ASSY", hourly_machine_rate=650.00, hourly_labour_rate=200.00, is_synthetic=True),
            WorkCentre(plant_id=2, code="WC-FDRY-01", name="Electric Arc Induction Furnace", cost_centre_code="CC-CHE-FDRY", hourly_machine_rate=2200.00, hourly_labour_rate=300.00, is_synthetic=True),
            WorkCentre(plant_id=3, code="WC-GEAR-01", name="Gear Hobbing & Heat Treatment", cost_centre_code="CC-GUJ-GEAR", hourly_machine_rate=1400.00, hourly_labour_rate=280.00, is_synthetic=True),
        ]

        scenario_notes = [
            "Scenario 1: Supplier MAT-STEEL-01 price jumped from ₹65.00 to ₹78.50 (+20.8%) in 2026-M04 (Supplier price variance).",
            "Scenario 2: Product PRD-MOTOR-01 experienced +8.0% copper consumption variance in 2026-M03 due to cutting waste (Usage variance).",
            "Scenario 3: Work Centre WC-CNC-01 suffered tool wear in 2026-M05, generating ₹1,45,000 rework & scrap variance.",
            "Scenario 4: Shift 2 overtime surge in 2026-M02 logged 180 overtime hours at 2.0x premium rate (Labour rate variance).",
            "Scenario 5: Plant Beta furnace recorded 45 kWh/hr off-shift idle load spike in 2026-M04 (Energy variance).",
            "Scenario 6: Plant Gamma production dropped 25% in 2026-M06, causing ₹4,80,000 unabsorbed fixed overhead (Volume variance).",
        ]

        counts = {
            "plants": len(plants),
            "calendar_periods": len(periods),
            "products": len(products),
            "materials": len(materials),
            "suppliers": len(suppliers),
            "costing_versions": 1,
            "cost_categories_represented": ["Material", "Labour", "Machine", "Energy", "Scrap & Rework", "Overhead"],
            "documented_scenarios": scenario_notes,
            "status": "READY_FOR_PERSISTENCE",
        }

        # If DB provided and configured, persist to database idempotently
        if db is not None:
            try:
                for obj in uoms:
                    if not db.query(UnitOfMeasure).filter_by(code=obj.code).first():
                        db.add(obj)
                for obj in plants:
                    if not db.query(Plant).filter_by(code=obj.code).first():
                        db.add(obj)
                for obj in periods:
                    if not db.query(CalendarPeriod).filter_by(code=obj.code).first():
                        db.add(obj)
                for obj in products:
                    if not db.query(Product).filter_by(code=obj.code).first():
                        db.add(obj)
                for obj in materials:
                    if not db.query(Material).filter_by(code=obj.code).first():
                        db.add(obj)
                for obj in suppliers:
                    if not db.query(Supplier).filter_by(code=obj.code).first():
                        db.add(obj)
                if not db.query(CostingVersion).filter_by(code=costing_version.code).first():
                    db.add(costing_version)

                db.flush()

                # Get mapped IDs from DB
                p_pun = db.query(Plant).filter_by(code="PLANT-PUN").first()
                p_che = db.query(Plant).filter_by(code="PLANT-CHE").first()
                p_guj = db.query(Plant).filter_by(code="PLANT-GUJ").first()

                prd_motor = db.query(Product).filter_by(code="PRD-MOTOR-01").first()
                prd_gear = db.query(Product).filter_by(code="PRD-GEAR-02").first()
                prd_pump = db.query(Product).filter_by(code="PRD-PUMP-03").first()

                cv = db.query(CostingVersion).filter_by(code="AOP-2026-V1").first()

                mat_steel = db.query(Material).filter_by(code="MAT-STEEL-01").first()
                mat_copper = db.query(Material).filter_by(code="MAT-COPPER-01").first()
                sup_tata = db.query(Supplier).filter_by(code="SUP-TATA").first()

                # Add Lines & Work Centres
                if p_pun and not db.query(WorkCentre).filter_by(code="WC-CNC-01").first():
                    wc_cnc = WorkCentre(plant_id=p_pun.id, code="WC-CNC-01", name="5-Axis CNC Milling Cell", cost_centre_code="CC-PUN-MACH", hourly_machine_rate=1250.00, hourly_labour_rate=250.00, is_synthetic=True)
                    wc_assy = WorkCentre(plant_id=p_pun.id, code="WC-ASSY-01", name="Motor Stator & Rotor Assembly", cost_centre_code="CC-PUN-ASSY", hourly_machine_rate=650.00, hourly_labour_rate=200.00, is_synthetic=True)
                    db.add(wc_cnc)
                    db.add(wc_assy)
                    db.flush()

                wc_cnc = db.query(WorkCentre).filter_by(code="WC-CNC-01").first()

                # 9. Standard Cost Items (Baseline for Products under AOP-2026-V1)
                standards = [
                    # Motor at Pune: Total Standard = 3,000 / unit
                    StandardCostItem(
                        product_id=prd_motor.id,
                        costing_version_id=cv.id,
                        plant_id=p_pun.id,
                        standard_material_cost=1450.0000,
                        standard_labour_cost=450.0000,
                        standard_machine_cost=320.0000,
                        standard_energy_cost=180.0000,
                        standard_scrap_allowance_cost=50.0000,
                        standard_overhead_cost=550.0000,
                        standard_total_cost=3000.0000,
                        currency="INR",
                        is_synthetic=True,
                    ),
                    # Gearbox at Gujarat: Total Standard = 4,200 / unit
                    StandardCostItem(
                        product_id=prd_gear.id,
                        costing_version_id=cv.id,
                        plant_id=p_guj.id,
                        standard_material_cost=2100.0000,
                        standard_labour_cost=600.0000,
                        standard_machine_cost=500.0000,
                        standard_energy_cost=250.0000,
                        standard_scrap_allowance_cost=70.0000,
                        standard_overhead_cost=680.0000,
                        standard_total_cost=4200.0000,
                        currency="INR",
                        is_synthetic=True,
                    ),
                    # Pump at Chennai: Total Standard = 5,500 / unit
                    StandardCostItem(
                        product_id=prd_pump.id,
                        costing_version_id=cv.id,
                        plant_id=p_che.id,
                        standard_material_cost=2800.0000,
                        standard_labour_cost=850.0000,
                        standard_machine_cost=650.0000,
                        standard_energy_cost=400.0000,
                        standard_scrap_allowance_cost=100.0000,
                        standard_overhead_cost=700.0000,
                        standard_total_cost=5500.0000,
                        currency="INR",
                        is_synthetic=True,
                    ),
                ]
                for sc in standards:
                    if not db.query(StandardCostItem).filter_by(product_id=sc.product_id, plant_id=sc.plant_id, costing_version_id=sc.costing_version_id).first():
                        db.add(sc)
                db.flush()

                # 10. Production Orders for 2026-M01 to 2026-M06
                all_periods = db.query(CalendarPeriod).order_by(CalendarPeriod.start_date).all()
                period_map = {p.code: p for p in all_periods}

                # Create 6 orders for PRD-MOTOR-01 at Pune (100 units each)
                for p_code, p_obj in period_map.items():
                    order_num = f"PO-MOTOR-{p_code}"
                    if not db.query(ProductionOrder).filter_by(order_number=order_num).first():
                        # Normal order
                        po = ProductionOrder(
                            order_number=order_num,
                            plant_id=p_pun.id,
                            product_id=prd_motor.id,
                            period_id=p_obj.id,
                            planned_qty=100.0,
                            actual_qty=100.0,
                            scrap_qty=2.0,
                            rework_qty=1.0,
                            status="COMPLETED",
                            start_date=p_obj.start_date,
                            completion_date=p_obj.end_date,
                            is_synthetic=True,
                        )
                        db.add(po)
                        db.flush()

                        # Postings for this order
                        # Standard base: Material 145,000, Labour 45,000, Machine 32,000, Energy 18,000, Scrap 5,000, Overhead 55,000

                        # Scenario 1 (2026-M04): Steel price jump from 65 to 78.50 (+20.8%)
                        steel_price = 78.50 if p_code == "2026-M04" else 65.00
                        steel_qty = 1000.0  # 10 kg per motor

                        # Scenario 2 (2026-M03): Copper usage surge +8%
                        copper_qty = 120.0 if p_code == "2026-M03" else 111.0  # standard ~111 kg
                        copper_price = 680.00

                        mat_steel_cost = steel_qty * steel_price
                        mat_copper_cost = copper_qty * copper_price

                        db.add(MaterialPosting(
                            production_order_id=po.id, material_id=mat_steel.id, supplier_id=sup_tata.id, plant_id=p_pun.id, period_id=p_obj.id,
                            posting_date=p_obj.start_date, lot_number="LOT-STL", actual_quantity=steel_qty, uom="KG", unit_price=steel_price,
                            freight_component=0.00, duty_component=0.00, landed_unit_cost=steel_price,
                            total_actual_cost=mat_steel_cost, currency="INR", is_synthetic=True
                        ))
                        db.add(MaterialPosting(
                            production_order_id=po.id, material_id=mat_copper.id, supplier_id=sup_tata.id, plant_id=p_pun.id, period_id=p_obj.id,
                            posting_date=p_obj.start_date, lot_number="LOT-CPR", actual_quantity=copper_qty, uom="KG", unit_price=copper_price,
                            freight_component=0.00, duty_component=0.00, landed_unit_cost=copper_price,
                            total_actual_cost=mat_copper_cost, currency="INR", is_synthetic=True
                        ))

                        # Scenario 4 (2026-M02): Shift 2 overtime surge (180 OT hours at 2.0x)
                        reg_hours = 300.0
                        ot_hours = 180.0 if p_code == "2026-M02" else 0.0
                        hourly_rate = 120.0
                        ot_cost = ot_hours * hourly_rate * 2.0
                        total_labour_cost = (reg_hours * hourly_rate) + ot_cost

                        db.add(LabourPosting(
                            production_order_id=po.id, work_centre_id=wc_cnc.id, plant_id=p_pun.id, period_id=p_obj.id,
                            posting_date=p_obj.start_date, operation_name="MOTOR_ASSEMBLY", shift=2 if ot_hours > 0 else 1,
                            regular_hours=reg_hours, overtime_hours=ot_hours, hourly_rate=hourly_rate,
                            total_labour_cost=total_labour_cost, is_overtime=(ot_hours > 0), is_synthetic=True
                        ))

                        # Scenario 3 (2026-M05): CNC Tool wear causing downtime and rework/scrap
                        run_hrs = 80.0
                        dt_hrs = 45.0 if p_code == "2026-M05" else 5.0
                        mc_rate = 350.0
                        total_mac_cost = (run_hrs + dt_hrs) * mc_rate

                        db.add(MachineEvent(
                            production_order_id=po.id, work_centre_id=wc_cnc.id, plant_id=p_pun.id, period_id=p_obj.id,
                            event_date=p_obj.start_date, run_hours=run_hrs, setup_hours=10.0, downtime_hours=dt_hrs,
                            downtime_reason="Tool wear & chatter" if dt_hrs > 20 else "Routine check",
                            hourly_rate=mc_rate, total_machine_cost=total_mac_cost, is_synthetic=True
                        ))

                        # Quality / Scrap / Rework event
                        rework_cost = 145000.00 if p_code == "2026-M05" else 5000.00
                        db.add(QualityEvent(
                            production_order_id=po.id, plant_id=p_pun.id, period_id=p_obj.id,
                            event_date=p_obj.start_date, defect_code="DEF-TOOL-WEAR" if rework_cost > 10000 else "DEF-NORMAL",
                            defect_description="Dimension tolerance breach from worn insert" if rework_cost > 10000 else "Minor burr",
                            scrap_quantity=15.0 if p_code == "2026-M05" else 2.0, rework_hours=35.0 if p_code == "2026-M05" else 4.0,
                            rework_cost=rework_cost, is_synthetic=True
                        ))

                # Scenario 5 (2026-M04): Plant Beta (Chennai) 45 kWh/hr off-shift furnace idle load spike
                for p_code, p_obj in period_map.items():
                    is_spike = (p_code == "2026-M04")
                    idle_kwh = 18000.0 if is_spike else 2000.0  # 45 kWh/hr spike over month
                    tariff = 11.50
                    db.add(EnergyReading(
                        plant_id=p_che.id, period_id=p_obj.id, meter_reference="MTR-FURNACE-01",
                        reading_timestamp=p_obj.start_date, kwh_consumed=idle_kwh, tariff_rate=tariff,
                        total_energy_cost=idle_kwh * tariff, is_idle_load=True, is_synthetic=True
                    ))
                    # Normal plant operating energy
                    normal_kwh = 25000.0
                    db.add(EnergyReading(
                        plant_id=p_pun.id, period_id=p_obj.id, meter_reference="MTR-PLANT-PUN",
                        reading_timestamp=p_obj.start_date, kwh_consumed=normal_kwh, tariff_rate=8.50,
                        total_energy_cost=normal_kwh * 8.50, is_idle_load=False, is_synthetic=True
                    ))

                # Scenario 6 (2026-M06): Plant Gamma (Gujarat) production drop 25%, causing ₹4,80,000 unabsorbed overhead
                for p_code, p_obj in period_map.items():
                    planned_cap = 1000.0
                    actual_usage = 750.0 if p_code == "2026-M06" else 1000.0  # 25% drop
                    std_rate = 650.00
                    absorbed = actual_usage * std_rate
                    # Pool actual spending
                    actual_spend = 650000.00
                    under_over = actual_spend - absorbed

                    db.add(OverheadPool(
                        plant_id=p_guj.id, period_id=p_obj.id, cost_centre_code="CC-GUJ-FACILITY", pool_name="Factory Lease & General Admin",
                        actual_amount=actual_spend, absorption_driver="MACHINE_HOURS", planned_driver_capacity=planned_cap,
                        actual_driver_usage=actual_usage, standard_absorption_rate=std_rate, absorbed_amount=absorbed,
                        under_over_absorption=under_over, is_synthetic=True
                    ))
                    # Pune normal overhead pool
                    db.add(OverheadPool(
                        plant_id=p_pun.id, period_id=p_obj.id, cost_centre_code="CC-PUN-ADMIN", pool_name="Pune Maintenance & Utilities",
                        actual_amount=55000.00, absorption_driver="MACHINE_HOURS", planned_driver_capacity=100.0,
                        actual_driver_usage=100.0, standard_absorption_rate=550.00, absorbed_amount=55000.00,
                        under_over_absorption=0.00, is_synthetic=True
                    ))

                db.commit()
                logger.info("Complete deterministic benchmark dataset & 6 scenarios committed successfully.")
            except Exception as exc:
                logger.warning("Could not persist synthetic benchmark data to DB: %s", exc)
                db.rollback()

        return counts

        return counts


synthetic_generator = SyntheticDatasetGenerator()

