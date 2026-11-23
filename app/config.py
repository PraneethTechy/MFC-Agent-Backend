from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """
    Backend configuration loaded exclusively from backend/.env.
    Adheres strictly to the variable names defined for Neon PostgreSQL and Domo AI Services.
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH) if ENV_PATH.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Domo AI Services
    domo_subdomain: str = "gwcteq-partner"
    domo_token: str = "YOUR_DOMO_DEVELOPER_TOKEN"
    domo_model: Optional[str] = "YOUR_ENABLED_DOMO_MODEL_ID"

    # Neon PostgreSQL — single connection URL
    database_url: str = "postgresql+psycopg://AGENT_RW_USER:YOUR_PASSWORD@YOUR_NEON_POOLER_HOST/YOUR_DATABASE?sslmode=require"

    # CORS Configuration — comma-separated allowed origins or '*'
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Data Mode Policy: "PRODUCTION" (real production/baseline only) or "DEMO" (real + synthetic benchmarks)
    data_mode: str = "PRODUCTION"

    @property
    def parsed_cors_origins(self) -> list[str]:
        """
        Parses comma-separated CORS origins from environment variable.
        Supports '*' for permissive environments or comma-delimited origin URLs.
        Retains local Vite development origins for seamless local developer experience.
        """
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        for local_origin in ["http://localhost:5173", "http://127.0.0.1:5173"]:
            if local_origin not in origins:
                origins.append(local_origin)
        return origins

    @property
    def sqlalchemy_database_url(self) -> str:
        """
        Normalizes the database URL to ensure the psycopg driver scheme is used
        (postgresql+psycopg://) while preserving all query parameters (e.g. sslmode).
        """
        url = self.database_url.strip()
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def readonly_database_url(self) -> str:
        """For single-connection architecture, defaults to primary database_url."""
        return self.sqlalchemy_database_url

    @property
    def direct_database_url(self) -> str:
        """For single-connection architecture, defaults to primary database_url."""
        return self.sqlalchemy_database_url

    @property
    def clean_domo_subdomain(self) -> str:
        """Strips https://, http://, and .domo.com suffixes from the subdomain."""
        sub = self.domo_subdomain.strip()
        if sub.startswith("https://"):
            sub = sub[len("https://"):]
        elif sub.startswith("http://"):
            sub = sub[len("http://"):]
        if sub.endswith(".domo.com"):
            sub = sub[:-len(".domo.com")]
        return sub.strip("/")

    @property
    def domo_api_url(self) -> str:
        """Returns the full endpoint URL for the Domo Text Generation API."""
        return f"https://{self.clean_domo_subdomain}.domo.com/api/ai/v1/text/generation"

    @property
    def is_domo_configured(self) -> bool:
        """Checks if Domo credentials have been replaced with real values."""
        return bool(
            self.domo_token
            and self.domo_token != "YOUR_DOMO_DEVELOPER_TOKEN"
            and self.domo_subdomain
        )

    @property
    def is_database_configured(self) -> bool:
        """Checks if Neon database credentials have been replaced with real values."""
        placeholder_tokens = [
            "YOUR_PASSWORD",
            "YOUR_NEON_POOLER_HOST",
            "AGENT_RW_USER",
            "AGENT_RO_USER",
            "localhost:5432",
        ]
        return not any(token in self.database_url for token in placeholder_tokens)

    @property
    def is_migration_configured(self) -> bool:
        """Under single-connection mode, true whenever database_url is configured."""
        return self.is_database_configured


settings = Settings()
