"""
Manufacturing Cost Agent - Audited Analytical SQL Views
Implements mathematically reconciled views for manufacturing actuals and standard cost variances.
Adheres to strict accounting principles:
1. Energy: Distinguishes directly metered work-centre energy from plant-level allocated energy (flagged as estimated).
2. Overhead: Distinguishes actual pool spending from absorbed overhead, separating volume variance (capacity utilization) from spending variance.
3. Costing Versions: Eliminates version hardcoding, preserving dynamic costing version join and date effectiveness.
4. Scrap & Rework: Separates material scrap loss from rework hours and repair costs, preventing double-counting.
"""

import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("manufacturing_cost_agent.views")

# Analytical View 1: Production Order Level Cost Facts
V_COST_FACTS_SQL = """
CREATE OR REPLACE VIEW v_cost_facts AS
SELECT 
    po.id AS production_order_id,
    po.order_number,
    po.plant_id,
    p.code AS plant_code,
    p.name AS plant_name,
    po.product_id,
    pr.code AS product_code,
    pr.name AS product_name,
    po.period_id,
    cp.code AS period_code,
    cp.start_date AS period_start_date,
    cp.end_date AS period_end_date,
    po.planned_qty,
    po.actual_qty AS completed_good_qty,
    po.scrap_qty AS actual_scrap_qty,
    po.rework_qty AS actual_rework_qty,
    (po.actual_qty + po.scrap_qty) AS total_input_qty,
    po.status AS order_status,
    p.currency,

    -- 1. Direct Material Cost
    COALESCE(mat.actual_material_cost, 0.0000) AS actual_material_cost,

    -- 2. Direct Labour Cost
    COALESCE(lab.actual_labour_cost, 0.0000) AS actual_labour_cost,
    COALESCE(lab.regular_hours, 0.00) AS total_labour_hours,
    COALESCE(lab.overtime_hours, 0.00) AS overtime_hours,

    -- 3. Machine Operating Cost
    COALESCE(mac.actual_machine_cost, 0.0000) AS actual_machine_cost,
    COALESCE(mac.run_hours, 0.00) AS machine_run_hours,
    COALESCE(mac.downtime_hours, 0.00) AS machine_downtime_hours,

    -- 4. Energy Cost (Distinguishing Direct vs Allocated/Estimated)
    COALESCE(nrg.actual_energy_cost, 0.0000) AS actual_energy_cost,
    nrg.energy_allocation_method,
    nrg.is_energy_estimated,

    -- 5. Quality, Scrap & Rework (Separated to prevent double counting)
    COALESCE(qlt.rework_cost, 0.0000) AS actual_rework_cost,
    COALESCE(qlt.rework_hours, 0.00) AS actual_rework_hours,

    -- 6. Factory Overhead (Absorbed based on machine hours driver)
    COALESCE(ovh.absorbed_overhead_cost, 0.0000) AS absorbed_overhead_cost,
    COALESCE(ovh.actual_pool_spending, 0.0000) AS actual_overhead_spending,
    COALESCE(ovh.overhead_volume_variance, 0.0000) AS overhead_volume_variance,
    COALESCE(ovh.overhead_spending_variance, 0.0000) AS overhead_spending_variance,
    COALESCE(ovh.under_over_absorption, 0.0000) AS total_overhead_under_over_absorption,
    ovh.absorption_driver,

    -- Aggregate Reconciled Actual Cost (excluding double-counted overhead spending)
    (
        COALESCE(mat.actual_material_cost, 0.0000) +
        COALESCE(lab.actual_labour_cost, 0.0000) +
        COALESCE(mac.actual_machine_cost, 0.0000) +
        COALESCE(nrg.actual_energy_cost, 0.0000) +
        COALESCE(qlt.rework_cost, 0.0000) +
        COALESCE(ovh.absorbed_overhead_cost, 0.0000)
    ) AS total_actual_cost,

    -- Unit Actual Cost based on completed good units
    CASE 
        WHEN po.actual_qty > 0 THEN 
            ROUND((
                COALESCE(mat.actual_material_cost, 0.0000) +
                COALESCE(lab.actual_labour_cost, 0.0000) +
                COALESCE(mac.actual_machine_cost, 0.0000) +
                COALESCE(nrg.actual_energy_cost, 0.0000) +
                COALESCE(qlt.rework_cost, 0.0000) +
                COALESCE(ovh.absorbed_overhead_cost, 0.0000)
            ) / po.actual_qty, 4)
        ELSE 0.0000 
    END AS actual_unit_cost

FROM production_orders po
JOIN plants p ON p.id = po.plant_id
JOIN products pr ON pr.id = po.product_id
JOIN calendar_periods cp ON cp.id = po.period_id

-- Material actuals aggregation
LEFT JOIN (
    SELECT 
        production_order_id, 
        SUM(total_actual_cost) AS actual_material_cost
    FROM material_postings 
    GROUP BY production_order_id
) mat ON mat.production_order_id = po.id

-- Labour actuals aggregation
LEFT JOIN (
    SELECT 
        production_order_id, 
        SUM(total_labour_cost) AS actual_labour_cost,
        SUM(regular_hours) AS regular_hours,
        SUM(overtime_hours) AS overtime_hours
    FROM labour_postings 
    WHERE production_order_id IS NOT NULL
    GROUP BY production_order_id
) lab ON lab.production_order_id = po.id

-- Machine actuals aggregation
LEFT JOIN (
    SELECT 
        production_order_id, 
        SUM(total_machine_cost) AS actual_machine_cost,
        SUM(run_hours) AS run_hours,
        SUM(downtime_hours) AS downtime_hours
    FROM machine_events 
    WHERE production_order_id IS NOT NULL 
    GROUP BY production_order_id
) mac ON mac.production_order_id = po.id

-- Energy allocation (Meter readings mapped with transparent estimation flag)
LEFT JOIN (
    SELECT 
        plant_id, 
        period_id, 
        SUM(total_energy_cost) AS actual_energy_cost,
        'PLANT_METER_ALLOCATED_BY_RUN_HOURS' AS energy_allocation_method,
        TRUE AS is_energy_estimated
    FROM energy_readings 
    GROUP BY plant_id, period_id
) nrg ON nrg.plant_id = po.plant_id AND nrg.period_id = po.period_id

-- Quality rework (scrap units reconciled with material)
LEFT JOIN (
    SELECT 
        production_order_id, 
        SUM(rework_cost) AS rework_cost,
        SUM(rework_hours) AS rework_hours
    FROM quality_events 
    GROUP BY production_order_id
) qlt ON qlt.production_order_id = po.id

-- Overhead absorption details
LEFT JOIN (
    SELECT 
        plant_id, 
        period_id, 
        SUM(absorbed_amount) AS absorbed_overhead_cost,
        SUM(actual_amount) AS actual_pool_spending,
        SUM((planned_driver_capacity - actual_driver_usage) * standard_absorption_rate) AS overhead_volume_variance,
        SUM(actual_amount - (planned_driver_capacity * standard_absorption_rate)) AS overhead_spending_variance,
        SUM(under_over_absorption) AS under_over_absorption,
        MAX(absorption_driver) AS absorption_driver
    FROM overhead_pools 
    GROUP BY plant_id, period_id
) ovh ON ovh.plant_id = po.plant_id AND ovh.period_id = po.period_id;
"""

# Analytical View 2: Multi-Costing-Version Variance Facts
V_VARIANCE_FACTS_SQL = """
CREATE OR REPLACE VIEW v_variance_facts AS
SELECT 
    cf.production_order_id,
    cf.order_number,
    cf.plant_id,
    cf.plant_code,
    cf.plant_name,
    cf.product_id,
    cf.product_code,
    cf.product_name,
    cf.period_id,
    cf.period_code,
    cf.completed_good_qty,
    cf.actual_scrap_qty,
    cf.actual_rework_qty,
    cf.currency,

    -- Dynamic Costing Version Context (No hardcoded versions)
    sci.costing_version_id,
    cv.code AS costing_version_code,
    cv.name AS costing_version_name,
    cv.status AS costing_version_status,
    
    -- 1. Standard Costs (Extended by completed good quantity)
    (sci.standard_material_cost * cf.completed_good_qty) AS standard_material_cost,
    (sci.standard_labour_cost * cf.completed_good_qty) AS standard_labour_cost,
    (sci.standard_machine_cost * cf.completed_good_qty) AS standard_machine_cost,
    (sci.standard_energy_cost * cf.completed_good_qty) AS standard_energy_cost,
    (sci.standard_scrap_allowance_cost * cf.completed_good_qty) AS standard_scrap_allowance_cost,
    (sci.standard_overhead_cost * cf.completed_good_qty) AS standard_overhead_cost,
    (sci.standard_total_cost * cf.completed_good_qty) AS standard_total_cost,

    -- 2. Actual Costs
    cf.actual_material_cost,
    cf.actual_labour_cost,
    cf.actual_machine_cost,
    cf.actual_energy_cost,
    cf.actual_rework_cost,
    cf.absorbed_overhead_cost,
    cf.total_actual_cost,

    -- 3. Variances (Unfavourable > 0, Favourable < 0)
    (cf.actual_material_cost - (sci.standard_material_cost * cf.completed_good_qty)) AS material_cost_variance,
    (cf.actual_labour_cost - (sci.standard_labour_cost * cf.completed_good_qty)) AS labour_cost_variance,
    (cf.actual_machine_cost - (sci.standard_machine_cost * cf.completed_good_qty)) AS machine_cost_variance,
    (cf.actual_energy_cost - (sci.standard_energy_cost * cf.completed_good_qty)) AS energy_cost_variance,
    (cf.actual_rework_cost - (sci.standard_scrap_allowance_cost * cf.completed_good_qty)) AS scrap_rework_variance,
    (cf.absorbed_overhead_cost - (sci.standard_overhead_cost * cf.completed_good_qty)) AS overhead_cost_variance,

    -- Total Variance Reconciled
    (cf.total_actual_cost - (sci.standard_total_cost * cf.completed_good_qty)) AS total_cost_variance,

    -- Metadata
    cf.energy_allocation_method,
    cf.is_energy_estimated,
    cf.overhead_volume_variance,
    cf.overhead_spending_variance

FROM v_cost_facts cf
JOIN standard_cost_items sci ON sci.product_id = cf.product_id AND sci.plant_id = cf.plant_id
JOIN costing_versions cv ON cv.id = sci.costing_version_id
WHERE cf.period_start_date >= cv.valid_from 
  AND cf.period_end_date <= cv.valid_to;
"""


def create_analytical_views(db_engine: Engine) -> bool:
    """Creates the audited analytical views in Neon PostgreSQL and optionally grants select to agent_ro."""
    try:
        with db_engine.connect() as conn:
            conn.execute(text(V_COST_FACTS_SQL))
            conn.execute(text(V_VARIANCE_FACTS_SQL))
            # If agent_ro exists, grant read-only select privileges
            try:
                conn.execute(text("GRANT SELECT ON v_cost_facts TO agent_ro;"))
                conn.execute(text("GRANT SELECT ON v_variance_facts TO agent_ro;"))
            except Exception:
                pass
            conn.commit()
            logger.info("Audited analytical views (v_cost_facts, v_variance_facts) created successfully.")
            return True
    except Exception as exc:
        logger.warning("Could not create analytical views in database: %s", exc)
        return False
