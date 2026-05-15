from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
import structlog
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from msal import ConfidentialClientApplication
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session_factory
from app.models.role import UserRole
from app.models.tenant import Company
from app.models.user import User

log = structlog.get_logger(__name__)

# ── MSAL (auth-code exchange) ────────────────────────────────────────────────

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


async def exchange_code_for_token(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange an authorization code for tokens via MSAL."""
    settings = get_settings()
    app = get_msal_app()
    scopes = [f"api://{settings.azure_client_id}/access_as_user"]
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=scopes,
        redirect_uri=redirect_uri,
    )
    if "error" in result:
        raise ValueError(
            f"Token exchange failed: {result.get('error_description', result['error'])}"
        )
    return result  # type: ignore[return-value]


# ── JWKS Validator ───────────────────────────────────────────────────────────


class AzureADTokenValidator:
    """
    Validates Azure Entra ID JWTs.
    JWKS are fetched from the tenant's discovery endpoint and cached for 1 hour.
    In non-production environments signature validation is skipped to allow
    developer-issued test tokens.
    """

    _JWKS_TTL: int = 3600  # seconds

    def __init__(self) -> None:
        self._jwks: dict[str, Any] | None = None
        self._jwks_expires_at: float = 0.0

    async def _get_jwks(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._jwks is not None and now < self._jwks_expires_at:
            return self._jwks

        settings = get_settings()
        url = (
            f"https://login.microsoftonline.com"
            f"/{settings.azure_tenant_id}/discovery/v2.0/keys"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            self._jwks = resp.json()
            self._jwks_expires_at = now + self._JWKS_TTL
            log.debug("azure_ad.jwks_refreshed")
        return self._jwks  # type: ignore[return-value]

    async def validate(self, token: str) -> dict[str, Any]:
        """
        Validate an Entra ID JWT.
        Returns decoded claims or raises HTTPException(401).
        """
        settings = get_settings()

        if not settings.is_production:
            # Dev / CI: skip signature validation.
            try:
                claims: dict[str, Any] = jwt.decode(
                    token,
                    key="",
                    algorithms=["HS256", "RS256"],
                    options={"verify_signature": False, "verify_aud": False},
                )
            except JWTError as exc:
                log.warning("azure_ad.token_invalid_dev", error=str(exc))
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from exc
            return claims

        # Production: validate against JWKS.
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            jwks = await self._get_jwks()
            matching_key = self._find_key(jwks, kid)

            if matching_key is None:
                # Unknown kid — force refresh once and retry.
                self._jwks = None
                jwks = await self._get_jwks()
                matching_key = self._find_key(jwks, kid)

            if matching_key is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unknown token signing key",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            issuer = (
                f"https://login.microsoftonline.com/{settings.azure_tenant_id}/v2.0"
            )
            audience = f"api://{settings.azure_client_id}"

            claims = jwt.decode(
                token,
                matching_key,
                algorithms=["RS256"],
                audience=audience,
                issuer=issuer,
                options={"verify_exp": True},
            )
        except JWTError as exc:
            log.warning("azure_ad.token_invalid", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        return claims

    @staticmethod
    def _find_key(
        jwks: dict[str, Any], kid: str | None
    ) -> dict[str, Any] | None:
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key
        return None


_validator: AzureADTokenValidator | None = None


def get_validator() -> AzureADTokenValidator:
    global _validator
    if _validator is None:
        _validator = AzureADTokenValidator()
    return _validator


# ── CurrentUser ──────────────────────────────────────────────────────────────


@dataclass
class CurrentUser:
    user: User
    roles: list[UserRole]
    is_global_admin: bool
    accessible_company_ids: list[UUID]
    accessible_system_ids: list[UUID]


# ── FastAPI dependencies ─────────────────────────────────────────────────────


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_header[len("Bearer "):]


async def get_current_user(request: Request) -> CurrentUser:
    """
    FastAPI dependency.
    Validates the Bearer JWT, loads (or auto-provisions) the User record,
    loads all active role assignments, and returns a CurrentUser.
    """
    token = _extract_bearer_token(request)
    claims = await get_validator().validate(token)

    # Prefer 'oid' (stable Entra object ID); fall back to 'sub' for dev tokens.
    azure_oid: str = claims.get("oid") or claims.get("sub", "")
    email: str = (
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("upn")
        or ""
    )
    display_name: str | None = claims.get("name")

    if not azure_oid and not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing required identity claims (oid/email)",
        )

    factory = get_session_factory()
    async with factory() as session:
        try:
            user = await _get_or_create_user(session, azure_oid, email, display_name)
            roles = await _load_user_roles(session, user.id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    accessible_company_ids: list[UUID] = list({
        r.company_id for r in roles if r.company_id is not None
    })
    accessible_system_ids: list[UUID] = list({
        r.system_id for r in roles if r.system_id is not None
    })

    return CurrentUser(
        user=user,
        roles=roles,
        is_global_admin=user.is_global_admin,
        accessible_company_ids=accessible_company_ids,
        accessible_system_ids=accessible_system_ids,
    )


async def get_tenant_context(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> Company:
    """
    FastAPI dependency.
    Resolves the active Company from the X-Company-Slug header (preferred)
    or from the kaats_company_id claim in the JWT (fallback).
    Validates the current user has access to the resolved company.
    Attaches the Company to request.state.active_company.
    """
    company_slug = request.headers.get("X-Company-Slug")

    factory = get_session_factory()
    async with factory() as db:
        if company_slug:
            result = await db.execute(
                select(Company).where(
                    Company.slug == company_slug,
                    Company.is_active == True,  # noqa: E712
                )
            )
            company = result.scalar_one_or_none()
            if company is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Company '{company_slug}' not found",
                )
        else:
            # Fall back to company_id set by TenantMiddleware
            raw_company_id: UUID | None = getattr(request.state, "company_id", None)
            if raw_company_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "No company context. Supply the X-Company-Slug header "
                        "or include kaats_company_id in your token."
                    ),
                )
            result = await db.execute(
                select(Company).where(
                    Company.id == raw_company_id,
                    Company.is_active == True,  # noqa: E712
                )
            )
            company = result.scalar_one_or_none()
            if company is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Company not found",
                )

    if not current_user.is_global_admin:
        if company.id not in current_user.accessible_company_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this company",
            )

    request.state.active_company = company
    return company


# ── Internal helpers ─────────────────────────────────────────────────────────


async def _get_or_create_user(
    session: AsyncSession,
    azure_oid: str,
    email: str,
    display_name: str | None,
) -> User:
    from app.config import get_settings

    settings = get_settings()
    admin_emails: frozenset[str] = frozenset(
        e.strip().lower() for e in settings.kaats_admin_emails.split(",") if e.strip()
    )
    is_bootstrap_admin = bool(email and email.lower() in admin_emails)

    user: User | None = None

    if azure_oid:
        result = await session.execute(select(User).where(User.azure_oid == azure_oid))
        user = result.scalar_one_or_none()

    if user is None and email:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if user is None:
        user = User(
            email=email,
            azure_oid=azure_oid or None,
            display_name=display_name,
            is_active=True,
            is_global_admin=is_bootstrap_admin,
            last_login_at=now,
        )
        session.add(user)
        await session.flush()
        log.info("azure_ad.user_provisioned", email=email, is_global_admin=is_bootstrap_admin)
    else:
        if azure_oid and not user.azure_oid:
            user.azure_oid = azure_oid
        if display_name and not user.display_name:
            user.display_name = display_name
        # Promote to global admin if listed in bootstrap emails
        if is_bootstrap_admin and not user.is_global_admin:
            user.is_global_admin = True
            log.info("azure_ad.user_promoted_to_admin", email=email)
        user.last_login_at = now
        await session.flush()

    return user


async def _load_user_roles(session: AsyncSession, user_id: UUID) -> list[UserRole]:
    """Return all non-expired UserRole records for a user."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await session.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            (UserRole.expires_at.is_(None)) | (UserRole.expires_at > now),
        )
    )
    return list(result.scalars().all())
