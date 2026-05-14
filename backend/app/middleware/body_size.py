"""Request body size limit middleware.

Rejects requests whose ``Content-Length`` exceeds a configured cap before the
body is read into memory.  Evidence upload endpoints get a larger cap.

Default cap  : 1 MiB  (all endpoints)
Evidence cap : 50 MiB (any path containing /evidence)

A missing ``Content-Length`` header is not rejected here — streaming uploads
are handled upstream by the Container Apps ingress (4 MiB default).
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

_DEFAULT_MAX = 1 * 1024 * 1024        # 1 MiB
_EVIDENCE_MAX = 50 * 1024 * 1024      # 50 MiB


class ContentSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        max_bytes: int = _DEFAULT_MAX,
        evidence_max_bytes: int = _EVIDENCE_MAX,
    ) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes
        self._evidence_max = evidence_max_bytes

    async def dispatch(self, request: Request, call_next: any) -> Response:  # type: ignore[valid-type]
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header."},
                )
            limit = (
                self._evidence_max
                if "/evidence" in request.url.path
                else self._max_bytes
            )
            if size > limit:
                limit_mb = limit / (1024 * 1024)
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": (
                            f"Request body too large. "
                            f"Maximum allowed size is {limit_mb:.0f} MiB."
                        )
                    },
                )
        return await call_next(request)
