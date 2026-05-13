from __future__ import annotations

import structlog
from msal import ConfidentialClientApplication

from app.config import get_settings

log = structlog.get_logger(__name__)

_msal_app: ConfidentialClientApplication | None = None


def get_msal_app() -> ConfidentialClientApplication:
    global _msal_app
    if _msal_app is None:
        settings = get_settings()
        _msal_app = ConfidentialClientApplication(
            client_id=settings.azure_client_id,
            client_credential=settings.azure_client_secret,
            authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
        )
    return _msal_app


def get_token_url() -> str:
    settings = get_settings()
    return (
        f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/authorize"
    )


async def exchange_code_for_token(code: str, redirect_uri: str) -> dict:
    """Exchange an auth code for an access token via MSAL."""
    settings = get_settings()
    app = get_msal_app()
    scopes = [f"api://{settings.azure_client_id}/access_as_user"]
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=scopes,
        redirect_uri=redirect_uri,
    )
    if "error" in result:
        raise ValueError(f"Token exchange failed: {result.get('error_description', result['error'])}")
    return result
