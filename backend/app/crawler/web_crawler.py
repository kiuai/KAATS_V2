from __future__ import annotations

from playwright.async_api import Browser, Page, async_playwright

from app.crawler.base import BaseCrawler, CrawlResult


class WebCrawler(BaseCrawler):
    """Generic headless browser crawler using Playwright."""

    def __init__(self, base_url: str, max_pages: int = 200) -> None:
        super().__init__(base_url, max_pages)
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._pw = None

    async def __aenter__(self) -> WebCrawler:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        context = await self._browser.new_context(viewport={"width": 1920, "height": 1080})
        self._page = await context.new_page()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def crawl_page(self, url: str) -> CrawlResult:
        assert self._page, "Crawler not started — use as async context manager"
        await self._page.goto(url, wait_until="networkidle")
        self.visited.add(url)

        title = await self._page.title()
        text = await self._page.inner_text("body")
        origin = self._origin()
        links = await self._page.eval_on_selector_all(
            "a[href]", f"els => els.map(e => e.href).filter(h => h.startsWith('{origin}'))"
        )
        elements = await self._page.query_selector_all("button, input, a, select, textarea")
        interactive = []
        for el in elements[:50]:
            tag = await el.evaluate("el => el.tagName.toLowerCase()")
            label = await el.get_attribute("aria-label") or await el.inner_text() or ""
            interactive.append({"tag": tag, "label": label[:80]})

        return CrawlResult(
            url=url,
            title=title,
            text_content=text[:5000],
            links=list(set(links)),
            interactive_elements=interactive,
        )

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._pw:
            await self._pw.stop()
            self._pw = None
