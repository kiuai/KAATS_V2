from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.auth.azure_ad import exchange_code_for_token, get_token_url
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class AuthCodeRequest(BaseModel):
    code: str
    redirect_uri: str


@router.get("/login")
async def login_redirect() -> dict:
    """Return the Entra ID authorization URL for the SPA to initiate the OAuth2 flow."""
    settings = get_settings()
    return {
        "authorization_url": get_token_url(),
        "client_id": settings.azure_client_id,
        "tenant_id": settings.azure_tenant_id,
    }


@router.post("/callback", response_model=TokenResponse)
async def auth_callback(body: AuthCodeRequest) -> TokenResponse:
    """Exchange an authorization code for an access token."""
    try:
        result = await exchange_code_for_token(body.code, body.redirect_uri)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return TokenResponse(
        access_token=result["access_token"],
        token_type="bearer",
        expires_in=result.get("expires_in", 3600),
    )


@router.get("/me")
async def get_me(request: Request) -> dict:
    """Return the decoded JWT claims for the current user."""
    return {
        "user_id": str(getattr(request.state, "user_id", None)),
        "company_id": str(getattr(request.state, "company_id", None)),
        "roles": getattr(request.state, "roles", []),
    }
