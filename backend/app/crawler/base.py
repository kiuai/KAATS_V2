from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CrawlResult:
    url: str
    title: str
    text_content: str
    links: list[str] = field(default_factory=list)
    interactive_elements: list[dict] = field(default_factory=list)


class BaseCrawler(ABC):
    """Base class for all crawler implementations."""

    def __init__(self, base_url: str, max_pages: int = 200) -> None:
        self.base_url = base_url
        self.max_pages = max_pages
        self.visited: set[str] = set()

    @abstractmethod
    async def crawl_page(self, url: str) -> CrawlResult:
        """Navigate to a URL and return a CrawlResult."""

    @abstractmethod
    async def close(self) -> None:
        """Release browser/session resources."""

    def should_visit(self, url: str) -> bool:
        if url in self.visited:
            return False
        if len(self.visited) >= self.max_pages:
            return False
        return url.startswith(self._origin())

    def _origin(self) -> str:
        parts = self.base_url.split("/")
        return "/".join(parts[:3])
