"""
Integration tests for the authentication and tenant-context middleware.

These tests use a real ASGI test client against the full FastAPI app.
DB calls are bypassed by overriding FastAPI dependencies.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from jose import jwt

from app.main import app


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_TEST_OID = "00000000-0000-0000-0000-000000000099"


def _dev_token(
    sub: str = _TEST_OID,
    email: str = "test@example.com",
    name: str = "Test User",
    *,
    expired: bool = False,
) -> str:
    """Build a minimal HS256 JWT that the non-production validator will decode."""
    now = datetime.now(timezone.utc)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    payload = {
        "oid": sub,
        "sub": sub,
        "email": email,
        "preferred_username": email,
        "name": name,
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
    }
    return jwt.encode(payload, "test-secret", algorithm="HS256")


def _make_company(company_id: uuid.UUID, slug: str = "test-co") -> Any:
    c = MagicMock()
    c.id = company_id
    c.slug = slug
    c.is_active = True
    c.is_deleted = False
    c.enterprise_id = uuid.uuid4()
    return c


def _make_user_row(email: str = "test@example.com") -> Any:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = email
    u.azure_oid = _TEST_OID
    u.display_name = "Test User"
    u.is_active = True
    u.is_global_admin = False
    u.last_login_at = None
    return u


# ─────────────────────────────────────────────────────────────────────────────
# Test class
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestAuthEndpoints:
    """
    Test authentication flows using the /health endpoints which require
    no special DB setup (liveness doesn't need auth; other endpoints do).
    """

    @pytest.fixture
    async def client(self) -> AsyncClient:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    # ── Health endpoints (no auth required) ───────────────────────────────────

    async def test_liveness_no_auth_required(self, client: AsyncClient) -> None:
        resp = await client.get("/health/live")
        assert resp.status_code == 200

    async def test_readiness_no_auth_required(self, client: AsyncClient) -> None:
        resp = await client.get("/health/ready")
        # 200 or 503 depending on DB — just not 401/403
        assert resp.status_code in (200, 503)

    # ── Missing Authorization header ──────────────────────────────────────────

    async def test_protected_route_without_token_returns_401(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/v1/systems")
        assert resp.status_code == 401

    async def test_malformed_auth_header_returns_401(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/v1/systems",
            headers={"Authorization": "NotBearer something"},
        )
        assert resp.status_code == 401

    async def test_empty_bearer_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/systems",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401

    # ── Valid dev token (non-production environment) ───────────────────────────

    async def test_valid_dev_token_is_accepted(self, client: AsyncClient) -> None:
        """
        In non-production (dev/test) mode, signature validation is skipped.
        A well-formed JWT with oid+email claims should authenticate.
        """
        user = _make_user_row()
        company_id = uuid.uuid4()
        company = _make_company(company_id)

        with (
            patch("app.auth.azure_ad._get_or_create_user", new_callable=AsyncMock, return_value=user),
            patch("app.auth.azure_ad._load_user_roles", new_callable=AsyncMock, return_value=[]),
            patch("app.auth.azure_ad.get_session_factory") as mock_factory,
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.commit = AsyncMock()
            mock_factory.return_value = MagicMock(return_value=mock_session)

            token = _dev_token()
            resp = await client.get(
                "/api/v1/systems",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Company-Slug": "test-co",
                },
            )
            # 404 or 200 — any non-401/403 means auth passed
            assert resp.status_code not in (401, 403), (
                f"Expected auth to pass; got {resp.status_code}: {resp.text}"
            )

    # ── Expired token ──────────────────────────────────────────────────────────

    async def test_expired_token_returns_401(self, client: AsyncClient) -> None:
        """Expired JWT must be rejected even in dev mode."""
        token = _dev_token(expired=True)
        resp = await client.get(
            "/api/v1/systems",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    # ── Missing X-Company-Slug ────────────────────────────────────────────────

    async def test_missing_company_context_returns_400_or_404(
        self, client: AsyncClient
    ) -> None:
        """
        When a route requires get_tenant_context() and neither X-Company-Slug
        nor a state company_id is present, it should return 400 or 404.
        """
        user = _make_user_row()

        with (
            patch("app.auth.azure_ad._get_or_create_user", new_callable=AsyncMock, return_value=user),
            patch("app.auth.azure_ad._load_user_roles", new_callable=AsyncMock, return_value=[]),
            patch("app.auth.azure_ad.get_session_factory") as mock_factory,
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.commit = AsyncMock()
            mock_factory.return_value = MagicMock(return_value=mock_session)

            token = _dev_token()
            # Deliberately omit X-Company-Slug
            resp = await client.get(
                "/api/v1/requirements",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code in (400, 404, 422), (
                f"Expected 400/404/422 without company context; got {resp.status_code}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tenant isolation — cross-tenant 403
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestTenantIsolation:
    """Company context is required for all data-access routes."""

    @pytest.fixture
    async def client(self) -> AsyncClient:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    async def test_route_without_company_context_returns_400(
        self, client: AsyncClient
    ) -> None:
        """
        A valid JWT without kaats_company_id in its claims (and no company
        set via another path) must produce 400 from get_current_company_id —
        ensuring company-scoped routes reject unscoped requests.
        """
        user = _make_user_row()

        with (
            patch("app.auth.azure_ad._get_or_create_user", new_callable=AsyncMock, return_value=user),
            patch("app.auth.azure_ad._load_user_roles", new_callable=AsyncMock, return_value=[]),
            patch("app.auth.azure_ad.get_session_factory") as mock_factory,
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.commit = AsyncMock()
            mock_factory.return_value = MagicMock(return_value=mock_session)

            # Dev JWT with no kaats_company_id claim → request.state.company_id = None
            token = _dev_token()
            resp = await client.get(
                "/api/v1/requirements",
                headers={"Authorization": f"Bearer {token}"},
                # No X-Company-Slug and no kaats_company_id in token
            )
            assert resp.status_code == 400, (
                f"Expected 400 without company context; got {resp.status_code}"
            )
