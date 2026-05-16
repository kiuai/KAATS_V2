"""Rate-limiting helpers using slowapi (backed by the limits library).

Key strategy:
  - Public endpoints  → keyed by client IP (get_remote_address)
  - Authenticated endpoints → keyed by user_id (injected by TenantMiddleware)

The ``limiter`` singleton is imported by main.py (to register the SlowAPI
exception handler + middleware) and by individual routers to apply per-route
decorators.

Usage in a router::

    from app.middleware.rate_limit import limiter
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    @router.post("/some-endpoint")
    @limiter.limit("10/minute")
    async def some_endpoint(request: Request, ...):
        ...
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _user_or_ip(request: Request) -> str:
    """Return user_id for authenticated requests, client IP otherwise."""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return str(user_id)
    return get_remote_address(request)


# Global limiter — imported by main.py and routers.
# No default_limits so every route explicitly opts in.
limiter = Limiter(key_func=_user_or_ip, default_limits=[])
