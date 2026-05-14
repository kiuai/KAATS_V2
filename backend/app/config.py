from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # ── Environment ───────────────────────────────────────────────────────────
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    secret_key: str = Field(min_length=32)
    allowed_origins: list[str] = ["http://localhost:5173"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # ── Azure AD / Entra ID ───────────────────────────────────────────────────
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str | None = None  # Optional — use MSI when not provided

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("azure_openai_api_key", "openai_api_key"),
    )
    azure_openai_deployment_name: str = "gpt-4o"

    # ── Azure SQL — accepts a full connection string ──────────────────────────
    # Reads from DATABASE_URL or AZURE_SQL_CONNECTION_STRING env var.
    database_url: str = Field(
        validation_alias=AliasChoices("database_url", "azure_sql_connection_string"),
    )
    db_login_timeout: int = 30
    db_pool_timeout: int = 30

    @property
    def sqlalchemy_url(self) -> str:
        import urllib.parse

        url = self.database_url
        if "authentication=activedirectorymsi" in url.lower():
            # Use azure-identity token injection (SQL_COPT_SS_ACCESS_TOKEN) instead
            # of the ODBC driver's own MSI flow.  Build an explicit odbc_connect string
            # so SQLAlchemy cannot add Trusted_Connection/Integrated Security — those
            # are incompatible with access-token injection (ODBC error FA005).
            parsed = urllib.parse.urlparse(url.replace("mssql+pyodbc://", "mssql+aioodbc://", 1))
            server = parsed.hostname or ""
            database = parsed.path.lstrip("/")
            odbc = (
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server=tcp:{server},1433;"
                f"Database={database};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=yes;"
                f"Connection Timeout={self.db_login_timeout};"
            )
            return f"mssql+aioodbc:///?odbc_connect={urllib.parse.quote_plus(odbc)}"

        # Non-MSI path: swap driver, add login timeout
        url = url.replace("mssql+pyodbc://", "mssql+aioodbc://", 1)
        if "LoginTimeout=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}LoginTimeout={self.db_login_timeout}"
        return url

    # ── Azure Cosmos DB ───────────────────────────────────────────────────────
    azure_cosmos_endpoint: str = Field(
        validation_alias=AliasChoices("azure_cosmos_endpoint", "cosmos_endpoint"),
    )
    azure_cosmos_key: str = Field(
        validation_alias=AliasChoices("azure_cosmos_key", "cosmos_key"),
    )
    azure_cosmos_database: str = "kaats"

    # ── Azure Service Bus ─────────────────────────────────────────────────────
    azure_service_bus_connection_string: str = Field(
        validation_alias=AliasChoices(
            "azure_service_bus_connection_string", "service_bus_connection_string"
        ),
    )
    service_bus_topic_ai_jobs: str = "ai-jobs"
    service_bus_topic_crawl_jobs: str = "crawl-jobs"
    service_bus_topic_result_events: str = "result-events"
    service_bus_subscription_worker: str = "worker"

    # ── Azure Blob Storage ────────────────────────────────────────────────────
    # Accepts a full connection string OR individual name + key.
    # When a full connection string is provided, name and key are parsed from it.
    azure_storage_conn_str: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "azure_storage_connection_string", "storage_connection_string"
        ),
    )
    azure_storage_account_name: str | None = None
    azure_storage_account_key: str | None = None
    azure_storage_container_evidence: str = "kaats-evidence"

    @model_validator(mode="after")
    def _parse_storage_conn_str(self) -> "Settings":
        """If only a full connection string is provided, extract name and key."""
        raw = self.azure_storage_conn_str
        if raw and not self.azure_storage_account_name:
            name_match = re.search(r"AccountName=([^;]+)", raw, re.IGNORECASE)
            if name_match:
                object.__setattr__(self, "azure_storage_account_name", name_match.group(1))
        if raw and not self.azure_storage_account_key:
            key_match = re.search(r"AccountKey=([^;]+)", raw, re.IGNORECASE)
            if key_match:
                object.__setattr__(self, "azure_storage_account_key", key_match.group(1))
        return self

    @property
    def azure_storage_connection_string(self) -> str:
        if self.azure_storage_conn_str:
            return self.azure_storage_conn_str
        return (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={self.azure_storage_account_name};"
            f"AccountKey={self.azure_storage_account_key};"
            f"EndpointSuffix=core.windows.net"
        )

    # ── Azure Key Vault ───────────────────────────────────────────────────────
    azure_key_vault_url: str | None = None

    # ── Scheduler ────────────────────────────────────────────────────────────
    scheduler_interval_seconds: int = 60
    scheduler_max_jobs_per_cycle: int = 100
    scheduler_catchup_hours: int = 24

    # ── Agent limits ──────────────────────────────────────────────────────────
    max_agent_steps: int = 50
    agent_timeout_seconds: int = 1800
    agent_tool_timeout_seconds: int = 30
    max_crawl_pages: int = 200
    llm_max_retries: int = 3
    llm_retry_base_seconds: float = 2.0
    checkpoint_every_n_steps: int = 10
    browser_pool_size: int = 3

    # ── Evidence ──────────────────────────────────────────────────────────────
    evidence_retention_days: int = 365
    evidence_sas_ttl_hours: int = 1

    # ── Worker ────────────────────────────────────────────────────────────────
    max_concurrent_agents: int = 3

    # ── Observability ──────────────────────────────────────────────────────────
    applicationinsights_connection_string: str | None = None
    otlp_endpoint: str | None = None
    otel_service_name: str = "kaats-api"

    # ── Azure Communication Services ──────────────────────────────────────────
    acs_connection_string: str | None = None
    acs_sender_address: str | None = None

    # ── Frontend ──────────────────────────────────────────────────────────────
    frontend_base_url: str = "https://app.kaats.kiu.ai"

    # ── Stripe billing ────────────────────────────────────────────────────────
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_pro: str | None = None
    stripe_price_enterprise: str | None = None

    # ── Feature flags ─────────────────────────────────────────────────────────
    openapi_enabled: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
