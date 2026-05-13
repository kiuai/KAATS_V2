from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from azure.storage.blob.aio import BlobServiceClient, ContainerClient
from azure.storage.blob import BlobSasPermissions, generate_blob_sas

from app.config import get_settings

log = structlog.get_logger(__name__)

_blob_service: BlobServiceClient | None = None


def get_blob_service() -> BlobServiceClient:
    global _blob_service
    if _blob_service is None:
        settings = get_settings()
        _blob_service = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
    return _blob_service


def get_evidence_container() -> ContainerClient:
    settings = get_settings()
    return get_blob_service().get_container_client(settings.azure_storage_container_evidence)


async def init_blob() -> None:
    """Ensure evidence container exists at startup."""
    settings = get_settings()
    container = get_evidence_container()
    try:
        await container.create_container()
        log.info("blob.container_created", container=settings.azure_storage_container_evidence)
    except Exception:
        # Container already exists — expected in most cases
        pass
    log.info("blob.connected", account=settings.azure_storage_account_name)


async def close_blob() -> None:
    global _blob_service
    if _blob_service:
        await _blob_service.close()
        _blob_service = None
    log.info("blob.closed")


def build_evidence_path(company_id: str, execution_id: str, filename: str) -> str:
    return f"tenant-{company_id}/evidence/{execution_id}/{filename}"


def generate_sas_url(blob_path: str, ttl_hours: int | None = None) -> str:
    settings = get_settings()
    hours = ttl_hours or settings.evidence_sas_ttl_hours
    expiry = datetime.now(timezone.utc) + timedelta(hours=hours)

    sas_token = generate_blob_sas(
        account_name=settings.azure_storage_account_name,
        container_name=settings.azure_storage_container_evidence,
        blob_name=blob_path,
        account_key=settings.azure_storage_account_key,
        permission=BlobSasPermissions(read=True),
        expiry=expiry,
    )
    account = settings.azure_storage_account_name
    container = settings.azure_storage_container_evidence
    return f"https://{account}.blob.core.windows.net/{container}/{blob_path}?{sas_token}"


async def upload_bytes(blob_path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    container = get_evidence_container()
    blob_client = container.get_blob_client(blob_path)
    await blob_client.upload_blob(data, overwrite=True, content_settings={"content_type": content_type})


async def download_bytes(blob_path: str) -> bytes:
    container = get_evidence_container()
    blob_client = container.get_blob_client(blob_path)
    stream = await blob_client.download_blob()
    return await stream.readall()
