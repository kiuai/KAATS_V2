from __future__ import annotations

import structlog
from azure.cosmos.aio import CosmosClient, ContainerProxy, DatabaseProxy
from azure.cosmos.exceptions import CosmosHttpResponseError

from app.config import get_settings

log = structlog.get_logger(__name__)

_client: CosmosClient | None = None
_database: DatabaseProxy | None = None

AGENT_RUNS_CONTAINER = "agent-runs"


def get_cosmos_client() -> CosmosClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = CosmosClient(
            url=str(settings.azure_cosmos_endpoint),
            credential=settings.azure_cosmos_key,
        )
    return _client


def get_cosmos_database() -> DatabaseProxy:
    global _database
    if _database is None:
        settings = get_settings()
        _database = get_cosmos_client().get_database_client(settings.azure_cosmos_database)
    return _database


def get_agent_runs_container() -> ContainerProxy:
    return get_cosmos_database().get_container_client(AGENT_RUNS_CONTAINER)


async def init_cosmos() -> None:
    """Verify Cosmos connectivity and ensure containers exist at startup."""
    settings = get_settings()
    db = get_cosmos_database()
    try:
        await db.read()
    except CosmosHttpResponseError as exc:
        log.warning("cosmos.database_not_found", database=settings.azure_cosmos_database, error=str(exc))
        return

    container = get_agent_runs_container()
    try:
        await container.read()
    except CosmosHttpResponseError:
        await db.create_container_if_not_exists(
            id=AGENT_RUNS_CONTAINER,
            partition_key={"paths": ["/company_id"], "kind": "Hash"},
        )
        log.info("cosmos.container_created", container=AGENT_RUNS_CONTAINER)

    log.info("cosmos.connected", database=settings.azure_cosmos_database)


async def close_cosmos() -> None:
    global _client, _database
    if _client:
        await _client.close()
        _client = None
        _database = None
    log.info("cosmos.closed")
