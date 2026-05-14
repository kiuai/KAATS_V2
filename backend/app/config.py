from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
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
    azure_client_secret: str

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment_name: str = "gpt-4o"

    # ── Azure SQL ─────────────────────────────────────────────────────────────
    azure_sql_server: str
    azure_sql_database: str
    azure_sql_username: str
    azure_sql_password: str
    # Seconds to wait for a new connection to be established (ODBC LoginTimeout).
    db_login_timeout: int = 30
    # Seconds to wait for a connection from the pool before raising TimeoutError.
    db_pool_timeout: int = 30

    @property
    def sqlalchemy_url(self) -> str:
        driver = "ODBC+Driver+18+for+SQL+Server"
        return (
            f"mssql+aioodbc://{self.azure_sql_username}:{self.azure_sql_password}"
            f"@{self.azure_sql_server}/{self.azure_sql_database}"
            f"?driver={driver}&TrustServerCertificate=yes"
            f"&LoginTimeout={self.db_login_timeout}"
        )

    # ── Azure Cosmos DB ───────────────────────────────────────────────────────
    azure_cosmos_endpoint: str
    azure_cosmos_key: str
    azure_cosmos_database: str = "kaats"

    # ── Azure Service Bus ─────────────────────────────────────────────────────
    azure_service_bus_connection_string: str
    service_bus_topic_ai_jobs: str = "ai-jobs"
    service_bus_topic_crawl_jobs: str = "crawl-jobs"
    service_bus_topic_result_events: str = "result-events"
    service_bus_subscription_worker: str = "worker"

    # ── Azure Blob Storage ────────────────────────────────────────────────────
    azure_storage_account_name: str
    azure_storage_account_key: str
    azure_storage_container_evidence: str = "kaats-evidence"

    @property
    def azure_storage_connection_string(self) -> str:
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
    # Set by Container Apps env var injected from Bicep monitoring.bicep output.
    applicationinsights_connection_string: str | None = None
    # Optional generic OTLP endpoint (e.g. local Jaeger / Grafana Tempo).
    otlp_endpoint: str | None = None
    # OpenTelemetry service name — overridden per container (api/worker/scheduler).
    otel_service_name: str = "kaats-api"

    # ── Azure Communication Services ──────────────────────────────────────────
    acs_connection_string: str | None = None
    acs_sender_address: str | None = None

    # ── Frontend ──────────────────────────────────────────────────────────────
    frontend_base_url: str = "https://app.kaats.kiu.ai"

    # ── Stripe billing ────────────────────────────────────────────────────────
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    # Maps plan tier name → Stripe price ID
    stripe_price_pro: str | None = None
    stripe_price_enterprise: str | None = None

    # ── Feature flags ─────────────────────────────────────────────────────────
    openapi_enabled: bool = True  # disabled in production via override

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
