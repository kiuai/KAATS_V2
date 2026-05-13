from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import (
    CurrentUser,
    exchange_code_for_token,
    get_current_user,
    get_token_url,
)
from app.auth.permissions import any_authenticated
from app.config import get_settings
from app.dependencies import get_db
from app.models.role import UserRole
from app.models.tenant import Company

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class TokenRequest(BaseModel):
    code: str
    redirect_uri: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class RoleOut(BaseModel):
    id: UUID
    role: str
    enterprise_id: UUID | None
    company_id: UUID | None
    system_id: UUID | None
    business_domain: str | None
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    user_id: UUID
    email: str
    display_name: str | None
    is_global_admin: bool
    roles: list[RoleOut]
    accessible_company_ids: list[UUID]
    accessible_system_ids: list[UUID]


class CompanyOut(BaseModel):
    id: UUID
    name: str
    slug: str
    industry: str | None
    enterprise_id: UUID

    model_config = {"from_attributes": True}


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/login")
async def login_redirect() -> dict:
    """Return the Entra ID authorization URL for the SPA to initiate OAuth2."""
    settings = get_settings()
    return {
        "authorization_url": get_token_url(),
        "client_id": settings.azure_client_id,
        "tenant_id": settings.azure_tenant_id,
    }


@router.post("/token", response_model=TokenResponse, status_code=200)
async def exchange_token(body: TokenRequest) -> TokenResponse:
    """
    Exchange an Azure AD authorization code for an access token.
    The SPA calls this after the OAuth2 redirect with the auth code.
    """
    try:
        result = await exchange_code_for_token(body.code, body.redirect_uri)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    return TokenResponse(
        access_token=result["access_token"],
        token_type="bearer",
        expires_in=result.get("expires_in", 3600),
    )


# Keep the old path as an alias so existing integrations don't break.
@router.post("/callback", response_model=TokenResponse, include_in_schema=False)
async def auth_callback(body: TokenRequest) -> TokenResponse:
    return await exchange_token(body)


@router.get("/me", response_model=MeResponse, dependencies=[any_authenticated])
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
) -> MeResponse:
    """Return the current user's profile, roles, and accessible resources."""
    return MeResponse(
        user_id=current_user.user.id,
        email=current_user.user.email,
        display_name=current_user.user.display_name,
        is_global_admin=current_user.is_global_admin,
        roles=[RoleOut.model_validate(r) for r in current_user.roles],
        accessible_company_ids=current_user.accessible_company_ids,
        accessible_system_ids=current_user.accessible_system_ids,
    )


@router.post("/logout", status_code=204, response_model=None, dependencies=[any_authenticated])
async def logout(request: Request) -> None:
    """
    Stateless logout — the client discards the token.
    Included for API completeness and future token-revocation hooks.
    """
    # No server-side session to invalidate for JWT-based auth.
    # Future: add token to a Redis deny-list here if needed.
    return None


@router.get("/companies", response_model=list[CompanyOut], dependencies=[any_authenticated])
async def list_accessible_companies(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CompanyOut]:
    """
    Return all companies the current user can access.
    Used by the frontend tenant-switcher.
    Global admins see all active companies.
    """
    if current_user.is_global_admin:
        result = await db.execute(
            select(Company).where(Company.is_active == True)  # noqa: E712
        )
        companies = list(result.scalars().all())
    else:
        if not current_user.accessible_company_ids:
            return []
        result = await db.execute(
            select(Company).where(
                Company.id.in_(current_user.accessible_company_ids),
                Company.is_active == True,  # noqa: E712
            )
        )
        companies = list(result.scalars().all())

    return [CompanyOut.model_validate(c) for c in companies]
