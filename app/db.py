import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from .config import settings
from .models import (
    Base,
    Conversation,
    Message,
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
    AnalysisRun,
    ScenarioRun,
    Recommendation,
    AuditEvent,
    InvestigationReportRecord,
    ImportBatch,
    DataQualityIssue,
)

logger = logging.getLogger("manufacturing_cost_agent.db")

# Neon Engine using the single configured DATABASE_URL (via psycopg 3 with SSL)
engine = create_engine(
    settings.sqlalchemy_database_url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    connect_args={
        "connect_timeout": 30,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    },
)

# Under single connection architecture, ro_engine and direct_engine alias to engine
ro_engine = engine
direct_engine = engine

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
DirectSessionLocal = SessionLocal


def get_db() -> Generator[Session | None, None, None]:
    """
    Dependency for yielding transactional database sessions.
    If Neon connection string is unconfigured, yields None so handlers can
    explicitly distinguish persistent database mode from unconfigured/test mode.
    """
    if not settings.is_database_configured:
        yield None
        return
    db = SessionLocal()
    try:
        yield db
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()


def check_db_connection() -> dict:
    """
    Verifies actual connectivity to Neon managed PostgreSQL via SQLAlchemy engine.
    Executes:
      - SELECT version();
      - SELECT current_database();
      - SELECT current_user;
    Strictly sanitizes credentials, tokens, and passwords in the diagnostic output.
    """
    if not settings.is_database_configured:
        return {
            "status": "unconfigured",
            "provider": "Neon Managed PostgreSQL",
            "ssl_active": True,
            "configured": False,
            "message": "Neon connection string in backend/.env contains template placeholders.",
        }

    try:
        with engine.connect() as conn:
            ver = conn.execute(text("SELECT version();")).scalar() or ""
            curr_db = conn.execute(text("SELECT current_database();")).scalar() or ""
            curr_user = conn.execute(text("SELECT current_user;")).scalar() or ""
            
            # Shorten version string for clean display
            short_ver = ver.split(", compiled")[0] if ", compiled" in ver else ver[:60]

            return {
                "status": "connected",
                "provider": "Neon Managed PostgreSQL",
                "database": curr_db,
                "current_user": curr_user,
                "version": short_ver,
                "ssl_active": "sslmode=require" in settings.database_url,
                "configured": True,
                "message": f"Successfully connected to Neon PostgreSQL database '{curr_db}' as user '{curr_user}'.",
            }
    except Exception as exc:
        logger.error("Failed to connect to Neon database: %s", type(exc).__name__)
        return {
            "status": "unreachable",
            "provider": "Neon Managed PostgreSQL",
            "ssl_active": False,
            "configured": True,
            "error_type": type(exc).__name__,
            "message": f"Neon connection failed ({type(exc).__name__}). Check network access and credentials.",
        }


def init_db() -> bool:
    """
    Initializes all manufacturing tables and analytical views in Neon PostgreSQL.
    Catches connection failures gracefully so the backend service can report
    diagnostics even when credentials are not yet accessible.
    """
    if not settings.is_database_configured:
        logger.info("Neon database credentials contain placeholders; skipping live schema creation.")
        return False

    try:
        from .db_views import create_analytical_views
        Base.metadata.create_all(bind=engine)
        create_analytical_views(engine)
        logger.info("Neon PostgreSQL schema and views initialized successfully.")
        return True
    except Exception as exc:
        logger.warning(
            "Could not connect to Neon during schema initialization (%s). "
            "Please ensure Neon credentials in backend/.env are configured and SSL is active.",
            type(exc).__name__,
        )
        return False
