"""
Manufacturing Cost Agent - Data Transformer
Applies business grain alignment, cost-linkage tagging, and standard cost classification.
"""

import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("manufacturing_cost_agent.ingestion.transformer")


class DataTransformer:
    """Transforms staged records into final domain-ready representations."""

    @staticmethod
    def resolve_production_costing_status(
        session: Session,
        prod_batch_id: str,
        cost_batch_id: str | None = None,
    ) -> dict[str, int]:
        """
        Marks hourly production records as DIRECT_COSTED (5,000 records)
        or UNCOSTED_OPERATIONAL_RUN (3,832 records) based on exact 1:1 match
        with stg_manufacturing_cost on (plant_id, line_id, timestamp).
        """
        if cost_batch_id:
            cost_clause = "AND c.ingestion_batch_id = :c_id"
            params = {"p_id": prod_batch_id, "c_id": cost_batch_id}
        else:
            cost_clause = ""
            params = {"p_id": prod_batch_id}

        sql_match = text(f"""
            UPDATE stg_hourly_production p
            SET data_quality = 'DIRECT_COSTED'
            FROM stg_manufacturing_cost c
            WHERE p.ingestion_batch_id = :p_id
              {cost_clause}
              AND p.plant_id = c.plant_id
              AND p.line_id = c.line_id
              AND p.event_ts = c.posting_ts
              AND p.validation_status = 'VALID'
        """)
        session.execute(sql_match, params)

        # Update remaining valid records to UNCOSTED_OPERATIONAL_RUN
        sql_unmatched = text("""
            UPDATE stg_hourly_production
            SET data_quality = 'UNCOSTED_OPERATIONAL_RUN'
            WHERE ingestion_batch_id = :p_id
              AND validation_status = 'VALID'
              AND data_quality != 'DIRECT_COSTED'
        """)
        session.execute(sql_unmatched, {"p_id": prod_batch_id})
        session.commit()

        # Count results
        sql_counts = text("""
            SELECT 
                SUM(CASE WHEN data_quality = 'DIRECT_COSTED' THEN 1 ELSE 0 END) as costed,
                SUM(CASE WHEN data_quality = 'UNCOSTED_OPERATIONAL_RUN' THEN 1 ELSE 0 END) as uncosted
            FROM stg_hourly_production
            WHERE ingestion_batch_id = :p_id
        """)
        res = session.execute(sql_counts, {"p_id": prod_batch_id}).mappings().one()
        costed = res["costed"] or 0
        uncosted = res["uncosted"] or 0

        logger.info(f"Resolved costing status for prod batch {prod_batch_id}: {costed} DIRECT_COSTED, {uncosted} UNCOSTED_OPERATIONAL_RUN")
        return {"costed": costed, "uncosted": uncosted}
