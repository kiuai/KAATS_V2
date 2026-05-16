from __future__ import annotations

from app.crawler.base import CrawlResult
from app.crawler.web_crawler import WebCrawler


class SapFioriCrawler(WebCrawler):
    """
    Specialised crawler for SAP Fiori Launchpad applications.
    Handles tile-based navigation and hash routing (#Shell-home, etc.).
    """

    async def crawl_page(self, url: str) -> CrawlResult:
        result = await super().crawl_page(url)
        assert self._page, "Crawler not started"

        # Wait for Fiori shell to render
        try:
            await self._page.wait_for_selector(".sapUshellTile", timeout=5000)
            tiles = await self._page.query_selector_all(".sapUshellTile")
            for tile in tiles[:30]:
                tile_title = await tile.get_attribute("aria-label") or await tile.inner_text()
                result.interactive_elements.append({"tag": "fiori-tile", "label": tile_title[:80]})
        except Exception:
            pass

        return result

    def should_visit(self, url: str) -> bool:
        # SAP Fiori uses hash routing — treat same-path hash variants as new pages
        if url in self.visited:
            return False
        if len(self.visited) >= self.max_pages:
            return False
        return self._origin() in url
