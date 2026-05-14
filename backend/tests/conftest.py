"""
Shared test fixtures for the KAATS backend test suite.

Fixture hierarchy
─────────────────
  async_engine      — creates tables in a fresh test DB per session
    └─ db_session   — transaction-per-test (rolled back after each test)

Auth fixtures inject a pre-built CurrentUser so tests never need a real JWT.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models.enums import UserRoleEnum


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_role(
    user_id: uuid.UUID,
    role: UserRoleEnum,
    *,
    company_id: uuid.UUID | None = None,
    system_id: uuid.UUID | None = None,
) -> Any:
    """Build a mock UserRole-like object (no DB needed)."""
    r = MagicMock()
    r.id = uuid.uuid4()
    r.user_id = user_id
    r.role = role.value
    r.company_id = company_id
    r.system_id = system_id
    r.enterprise_id = None
    r.expires_at = None
    return r


def _make_user(
    *,
    is_global_admin: bool = False,
    email: str | None = None,
) -> Any:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = email or f"user-{u.id.hex[:6]}@test.com"
    u.display_name = "Test User"
    u.is_global_admin = is_global_admin
    u.is_active = True
    return u


def _make_current_user(
    role: UserRoleEnum | None = None,
    *,
    company_id: uuid.UUID | None = None,
    system_id: uuid.UUID | None = None,
    is_global_admin: bool = False,
) -> Any:
    from app.auth.azure_ad import CurrentUser

    user = _make_user(is_global_admin=is_global_admin)
    if role is not None:
        roles = [_make_role(user.id, role, company_id=company_id, system_id=system_id)]
    else:
        roles = []

    accessible_company_ids = [company_id] if company_id else []
    accessible_system_ids = [system_id] if system_id else []

    return CurrentUser(
        user=user,
        roles=roles,
        is_global_admin=is_global_admin,
        accessible_company_ids=accessible_company_ids,
        accessible_system_ids=accessible_system_ids,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Anyio backend
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ─────────────────────────────────────────────────────────────────────────────
# HTTP client (unauthenticated by default)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ─────────────────────────────────────────────────────────────────────────────
# CurrentUser override fixtures
# Each fixture returns a (CurrentUser, override_fn) pair:
#   - Call app.dependency_overrides[get_current_user] = override_fn
#     to inject the pre-built CurrentUser.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def company_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def system_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def global_admin_user() -> Any:
    return _make_current_user(is_global_admin=True)


@pytest.fixture
def company_admin_user(company_id: uuid.UUID) -> Any:
    return _make_current_user(UserRoleEnum.COMPANY_ADMIN, company_id=company_id)


@pytest.fixture
def system_manager_user(company_id: uuid.UUID, system_id: uuid.UUID) -> Any:
    return _make_current_user(
        UserRoleEnum.SYSTEM_MANAGER,
        company_id=company_id,
        system_id=system_id,
    )


@pytest.fixture
def qa_user(company_id: uuid.UUID) -> Any:
    return _make_current_user(UserRoleEnum.QA, company_id=company_id)


@pytest.fixture
def bpo_user(company_id: uuid.UUID) -> Any:
    return _make_current_user(UserRoleEnum.BPO, company_id=company_id)


@pytest.fixture
def validation_tester_user(company_id: uuid.UUID) -> Any:
    return _make_current_user(UserRoleEnum.VALIDATION_TESTER, company_id=company_id)


@pytest.fixture
def validation_lead_user(company_id: uuid.UUID) -> Any:
    return _make_current_user(UserRoleEnum.VALIDATION_LEAD, company_id=company_id)


# ─────────────────────────────────────────────────────────────────────────────
# Authenticated client helper
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def auth_client(company_admin_user: Any) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with COMPANY_ADMIN current user pre-injected."""
    from app.auth.azure_ad import get_current_user

    app.dependency_overrides[get_current_user] = lambda: company_admin_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_current_user, None)
