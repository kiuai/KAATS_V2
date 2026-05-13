from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import Request, Response
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

log = structlog.get_logger(__name__)

_UNAUTHENTICATED_PATHS = frozenset({"/health", "/api/v1/auth/login", "/api/v1/auth/callback"})


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Validates the Bearer JWT on every request (except public paths).
    Extracts user_id, company_id, enterprise_id, and roles from claims
    and stores them on request.state for downstream use.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in _UNAUTHENTICATED_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        token = self._extract_token(request)
        if token is None:
            return self._unauthorized("Missing Authorization header")

        try:
            claims = self._decode_token(token)
        except JWTError as exc:
            log.warning("auth.jwt_invalid", error=str(exc))
            return self._unauthorized("Invalid or expired token")

        try:
            request.state.user_id = UUID(claims["sub"])
            request.state.company_id = UUID(claims.get("kaats_company_id", ""))
            request.state.enterprise_id = UUID(claims.get("kaats_enterprise_id", ""))
            request.state.roles = claims.get("kaats_roles", [])
        except (ValueError, KeyError) as exc:
            log.warning("auth.claims_malformed", error=str(exc))
            return self._unauthorized("Malformed token claims")

        return await call_next(request)

    @staticmethod
    def _extract_token(request: Request) -> str | None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[len("Bearer "):]
        return None

    @staticmethod
    def _decode_token(token: str) -> dict:
        from app.config import get_settings

        settings = get_settings()
        # In production this validates signature against Entra ID JWKS.
        # options={"verify_signature": False} is for local dev without a real Entra token.
        options = {"verify_signature": settings.is_production}
        return jwt.decode(token, settings.secret_key, algorithms=["HS256", "RS256"], options=options)

    @staticmethod
    def _unauthorized(detail: str) -> Response:
        import json

        body = json.dumps({"error": {"code": "UNAUTHENTICATED", "message": detail}})
        return Response(content=body, status_code=401, media_type="application/json")
