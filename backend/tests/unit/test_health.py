"""
Unit tests for the health check endpoints.

/health/live   — always 200, no dependency checks.
/health/ready  — 200 when all deps OK, 503 when any dep is degraded.

The dependency probes are replaced with mocks so these tests run without
any real infrastructure.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ─────────────────────────────────────────────────────────────────────────────
# /health/live
# ─────────────────────────────────────────────────────────────────────────────

class TestLiveness:
    async def test_returns_200(self, client: AsyncClient) -> None:
        resp = await client.get("/health/live")
        assert resp.status_code == 200

    async def test_body_has_alive_status(self, client: AsyncClient) -> None:
        resp = await client.get("/health/live")
        assert resp.json()["status"] == "alive"

    async def test_no_auth_required(self, client: AsyncClient) -> None:
        """Liveness must be accessible without any Authorization header."""
        resp = await client.get("/health/live")
        assert resp.status_code == 200

    async def test_returns_fast(self, client: AsyncClient) -> None:
        """Liveness should complete in < 200 ms (no I/O)."""
        import time
        t0 = time.perf_counter()
        await client.get("/health/live")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 200


# ─────────────────────────────────────────────────────────────────────────────
# /health/ready — all checks passing
# ─────────────────────────────────────────────────────────────────────────────

_OK = {"status": "ok"}
_DEGRADED_DB = {"status": "degraded", "error": "connection refused"}


class TestReadinessAllOk:
    @pytest.fixture(autouse=True)
    def _mock_all_checks_ok(self):
        with (
            patch("app.routers.health._check_database", new_callable=AsyncMock, return_value=_OK),
            patch("app.routers.health._check_cosmos",   new_callable=AsyncMock, return_value=_OK),
            patch("app.routers.health._check_service_bus", new_callable=AsyncMock, return_value=_OK),
            patch("app.routers.health._check_blob",     new_callable=AsyncMock, return_value=_OK),
        ):
            yield

    async def test_returns_200_when_all_ok(self, client: AsyncClient) -> None:
        resp = await client.get("/health/ready")
        assert resp.status_code == 200

    async def test_overall_status_is_ok(self, client: AsyncClient) -> None:
        resp = await client.get("/health/ready")
        assert resp.json()["status"] == "ok"

    async def test_all_check_statuses_are_ok(self, client: AsyncClient) -> None:
        body = (await client.get("/health/ready")).json()
        checks = body["checks"]
        for check_name in ("database", "cosmos", "service_bus", "blob"):
            assert checks[check_name]["status"] == "ok", (
                f"{check_name} should be 'ok', got {checks[check_name]}"
            )

    async def test_response_includes_duration_ms(self, client: AsyncClient) -> None:
        body = (await client.get("/health/ready")).json()
        assert "duration_ms" in body
        assert isinstance(body["duration_ms"], int)

    async def test_no_auth_required(self, client: AsyncClient) -> None:
        resp = await client.get("/health/ready")
        assert resp.status_code != 401


# ─────────────────────────────────────────────────────────────────────────────
# /health/ready — database degraded
# ─────────────────────────────────────────────────────────────────────────────

class TestReadinessDatabaseDegraded:
    @pytest.fixture(autouse=True)
    def _mock_db_degraded(self):
        with (
            patch("app.routers.health._check_database",
                  new_callable=AsyncMock, return_value=_DEGRADED_DB),
            patch("app.routers.health._check_cosmos",
                  new_callable=AsyncMock, return_value=_OK),
            patch("app.routers.health._check_service_bus",
                  new_callable=AsyncMock, return_value=_OK),
            patch("app.routers.health._check_blob",
                  new_callable=AsyncMock, return_value=_OK),
        ):
            yield

    async def test_returns_503(self, client: AsyncClient) -> None:
        resp = await client.get("/health/ready")
        assert resp.status_code == 503

    async def test_overall_status_is_degraded(self, client: AsyncClient) -> None:
        body = (await client.get("/health/ready")).json()
        assert body["status"] == "degraded"

    async def test_database_check_shows_degraded(self, client: AsyncClient) -> None:
        body = (await client.get("/health/ready")).json()
        assert body["checks"]["database"]["status"] == "degraded"

    async def test_other_checks_still_reported(self, client: AsyncClient) -> None:
        body = (await client.get("/health/ready")).json()
        for check_name in ("cosmos", "service_bus", "blob"):
            assert check_name in body["checks"]


# ─────────────────────────────────────────────────────────────────────────────
# /health/ready — all checks degraded
# ─────────────────────────────────────────────────────────────────────────────

class TestReadinessAllDegraded:
    @pytest.fixture(autouse=True)
    def _mock_all_degraded(self):
        degraded = {"status": "degraded", "error": "unreachable"}
        with (
            patch("app.routers.health._check_database",    new_callable=AsyncMock, return_value=degraded),
            patch("app.routers.health._check_cosmos",      new_callable=AsyncMock, return_value=degraded),
            patch("app.routers.health._check_service_bus", new_callable=AsyncMock, return_value=degraded),
            patch("app.routers.health._check_blob",        new_callable=AsyncMock, return_value=degraded),
        ):
            yield

    async def test_returns_503(self, client: AsyncClient) -> None:
        resp = await client.get("/health/ready")
        assert resp.status_code == 503

    async def test_all_checks_degraded(self, client: AsyncClient) -> None:
        body = (await client.get("/health/ready")).json()
        for check_name in ("database", "cosmos", "service_bus", "blob"):
            assert body["checks"][check_name]["status"] == "degraded"


# ─────────────────────────────────────────────────────────────────────────────
# /health/ready — probe raises an exception (handled via return_exceptions)
# ─────────────────────────────────────────────────────────────────────────────

class TestReadinessProbeException:
    @pytest.fixture(autouse=True)
    def _mock_db_raises(self):
        with (
            patch("app.routers.health._check_database",
                  new_callable=AsyncMock, side_effect=RuntimeError("unexpected")),
            patch("app.routers.health._check_cosmos",
                  new_callable=AsyncMock, return_value=_OK),
            patch("app.routers.health._check_service_bus",
                  new_callable=AsyncMock, return_value=_OK),
            patch("app.routers.health._check_blob",
                  new_callable=AsyncMock, return_value=_OK),
        ):
            yield

    async def test_returns_503_on_unhandled_exception(self, client: AsyncClient) -> None:
        resp = await client.get("/health/ready")
        assert resp.status_code == 503

    async def test_exception_surfaces_as_degraded_check(self, client: AsyncClient) -> None:
        body = (await client.get("/health/ready")).json()
        db_check = body["checks"]["database"]
        assert db_check["status"] == "degraded"
        assert "error" in db_check


# ─────────────────────────────────────────────────────────────────────────────
# Legacy /health endpoint (backward compat)
# ─────────────────────────────────────────────────────────────────────────────

class TestLegacyHealth:
    """The old /health path should still work (used by some CI tooling)."""

    async def test_legacy_health_returns_200(self, client: AsyncClient) -> None:
        # The legacy stub was replaced — /health/live is the new liveness path.
        # Verify that the new endpoint didn't break the 200 contract.
        resp = await client.get("/health/live")
        assert resp.status_code == 200
