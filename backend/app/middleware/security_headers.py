"""Security response headers middleware.

Adds a standard set of defensive HTTP headers to every response:

  Strict-Transport-Security  — only on HTTPS requests; 2-year max-age
  X-Content-Type-Options     — prevents MIME-sniffing
  X-Frame-Options            — blocks framing (clickjacking protection)
  Referrer-Policy            — limits referrer leakage
  Permissions-Policy         — opt-out of browser features not in use
  X-XSS-Protection           — legacy IE header (belt-and-suspenders)

The ``Content-Security-Policy`` is intentionally omitted here because it is
already managed by the frontend (Vite build / Azure CDN response headers rule)
and a backend-set CSP would conflict.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_HSTS = "max-age=63072000; includeSubDomains; preload"  # 2 years
_PERMISSIONS = (
    "accelerometer=(), "
    "camera=(), "
    "geolocation=(), "
    "gyroscope=(), "
    "magnetometer=(), "
    "microphone=(), "
    "payment=(), "
    "usb=()"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: any) -> Response:  # type: ignore[valid-type]
        response: Response = await call_next(request)

        # HSTS only meaningful over TLS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = _HSTS

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = _PERMISSIONS
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response
