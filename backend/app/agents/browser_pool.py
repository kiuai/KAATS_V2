from __future__ import annotations

import asyncio
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_pool: "BrowserPool | None" = None


class BrowserPool:
    """
    Pool of headless Chromium browser instances shared across agent runs.

    Each ``acquire()`` call creates an isolated ``BrowserContext`` (separate
    cookies and local storage) from one of the pooled browsers.  The context
    is closed on ``release()`` so state never leaks between runs.  The
    underlying ``Browser`` objects stay alive for the life of the process.

    Usage (FastAPI lifespan)::

        pool = BrowserPool(size=settings.browser_pool_size)
        await pool.start()
        ...
        await pool.stop()
    """

    def __init__(self, size: int = 3) -> None:
        self._size = size
        self._pw: Any = None
        self._browsers: list[Any] = []
        # Queue holds available browser indices
        self._available: asyncio.Queue[int] = asyncio.Queue()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch all browser instances. Call once at application startup."""
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        for i in range(self._size):
            browser = await self._pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-extensions",
                ],
            )
            self._browsers.append(browser)
            await self._available.put(i)

        log.info("browser_pool.started", size=self._size)

    async def stop(self) -> None:
        """Close all browser instances. Call at application shutdown."""
        for browser in self._browsers:
            try:
                await browser.close()
            except Exception:  # noqa: BLE001
                pass
        self._browsers.clear()

        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:  # noqa: BLE001
                pass
            self._pw = None

        log.info("browser_pool.stopped")

    # ── Context management ────────────────────────────────────────────────────

    async def acquire(self) -> tuple[Any, Any]:
        """
        Acquire an isolated browser context and a fresh page.

        Blocks until a browser becomes available (bounded by pool size).
        Returns ``(browser_context, page)`` — the caller must ``release``
        the context when the agent run finishes.
        """
        idx = await self._available.get()
        browser = self._browsers[idx]
        ctx = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            ignore_https_errors=True,
            java_script_enabled=True,
        )
        # Stash the pool index so release() knows which browser to return.
        ctx._pool_idx = idx  # type: ignore[attr-defined]
        page = await ctx.new_page()
        log.debug("browser_pool.acquired", browser_index=idx)
        return ctx, page

    async def release(self, ctx: Any) -> None:
        """Close the context and return the browser to the pool."""
        idx: int | None = getattr(ctx, "_pool_idx", None)
        try:
            await ctx.close()
        except Exception:  # noqa: BLE001
            pass
        if idx is not None:
            await self._available.put(idx)
            log.debug("browser_pool.released", browser_index=idx)


# ── Module-level singleton helpers ────────────────────────────────────────────


def get_browser_pool() -> BrowserPool:
    if _pool is None:
        raise RuntimeError(
            "BrowserPool has not been initialised. "
            "Ensure init_browser_pool() is called in the application lifespan."
        )
    return _pool


async def init_browser_pool(size: int = 3) -> None:
    global _pool
    _pool = BrowserPool(size=size)
    await _pool.start()


async def close_browser_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.stop()
        _pool = None
