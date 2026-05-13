from __future__ import annotations

import json
from uuid import UUID, uuid4

import structlog
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

log = structlog.get_logger(__name__)

_UNAUTHENTICATED_PATHS = frozenset({
    "/health",
    "/api/v1/auth/login",
    "/api/v1/auth/callback",
    "/api/v1/auth/token",
})


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Runs on every request (except public paths):

    1. Generates / propagates a Correlation ID (X-Correlation-ID header).
    2. Validates the Bearer JWT via AzureADTokenValidator (JWKS in prod,
       skip-signature in dev).
    3. Extracts identity and tenant claims and stores them on request.state
       so route handlers and FastAPI dependencies can consume them.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # ── Correlation ID ────────────────────────────────────────────────────
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        request.state.correlation_id = correlation_id

        path = request.url.path
        if path in _UNAUTHENTICATED_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response

        # ── Token extraction ──────────────────────────────────────────────────
        token = self._extract_token(request)
        if token is None:
            return self._unauthorized("Missing Authorization header", correlation_id)

        # ── JWT validation via AzureADTokenValidator ──────────────────────────
        from app.auth.azure_ad import get_validator

        validator = get_validator()
        try:
            claims = await validator.validate(token)
        except HTTPException as exc:
            log.warning("auth.jwt_invalid", correlation_id=correlation_id, detail=exc.detail)
            return self._unauthorized(exc.detail, correlation_id)

        # ── Populate request.state ────────────────────────────────────────────
        try:
            # 'oid' is the stable Entra object ID; fall back to 'sub' for dev tokens.
            oid: str = claims.get("oid") or claims.get("sub", "")
            request.state.azure_oid = oid
            request.state.email = (
                claims.get("preferred_username")
                or claims.get("email")
                or claims.get("upn")
                or ""
            )

            # user_id is the OID when present, otherwise sub.
            request.state.user_id = UUID(oid) if oid else None

            raw_company = claims.get("kaats_company_id")
            request.state.company_id = UUID(raw_company) if raw_company else None

            raw_enterprise = claims.get("kaats_enterprise_id")
            request.state.enterprise_id = UUID(raw_enterprise) if raw_enterprise else None

            request.state.roles = claims.get("kaats_roles", [])
        except (ValueError, AttributeError) as exc:
            log.warning("auth.claims_malformed", error=str(exc), correlation_id=correlation_id)
            return self._unauthorized("Malformed token claims", correlation_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @staticmethod
    def _extract_token(request: Request) -> str | None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[len("Bearer "):]
        return None

    @staticmethod
    def _unauthorized(detail: str, correlation_id: str) -> Response:
        body = json.dumps({
            "error": {
                "code": "UNAUTHENTICATED",
                "message": detail,
                "correlation_id": correlation_id,
            }
        })
        response = Response(content=body, status_code=401, media_type="application/json")
        response.headers["X-Correlation-ID"] = correlation_id
        return response
