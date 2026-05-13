from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from langchain.tools import StructuredTool

from app.agents.base import AgentOutput, BaseAgent
from app.agents.tool_registry import ToolContext, build_crawl_tools, build_tools
from app.ai.client import AzureOpenAIClient
from app.ai.prompts.crawl_prompts import CRAWL_SYSTEM_PROMPT
from app.blob import get_blob_service
from app.config import get_settings

if TYPE_CHECKING:
    from app.auth.azure_ad import CurrentUser
    from app.models.agent_run import AgentRun
    from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


class CrawlAgent(BaseAgent):
    """
    Crawls a web application with Playwright to discover UI flows and generate
    structured requirements.

    Expected ``config`` keys:
        base_url  (str)  — root URL to start crawling
        max_pages (int, optional) — override settings.max_crawl_pages
    """

    agent_type = "crawl"

    def __init__(
        self,
        run: "AgentRun",
        db: "AsyncSession",
        current_user: "CurrentUser | None",
        config: dict[str, Any],
    ) -> None:
        super().__init__(run, db, current_user, config)
        # Playwright handles set up in execute() override below.
        self._browser: Any = None
        self._page: Any = None
        self._pw_ctx: Any = None

    # ── BaseAgent interface ───────────────────────────────────────────────────

    async def get_tools(self) -> list[StructuredTool]:
        """
        Return shared + Playwright crawl tools.
        Called after the browser is already started in execute().
        """
        ai_client = AzureOpenAIClient(
            agent_run_id=self.run.id,
            company_id=self.run.company_id,
        )
        try:
            blob_client = get_blob_service()
        except Exception:  # noqa: BLE001
            blob_client = None  # type: ignore[assignment]

        ctx = ToolContext(
            db=self.db,
            blob_client=blob_client,
            company_id=self.run.company_id,
            system_id=self.run.system_id,  # type: ignore[arg-type]
            agent_run_id=self.run.id,
            memory=self.memory,
            ai_client=ai_client,
        )
        shared = build_tools(ctx)
        crawl = build_crawl_tools(self._page, self.memory)
        return shared + crawl

    async def get_system_prompt(self) -> str:
        return CRAWL_SYSTEM_PROMPT

    async def run_agent(self) -> AgentOutput:
        settings = get_settings()
        base_url: str = self.config.get("base_url", "")
        max_pages: int = self.config.get("max_pages", settings.max_crawl_pages)

        self.memory.set("visited_urls", set())
        self.memory.set("discovered_requirements", [])

        log.info(
            "crawl_agent.started",
            base_url=base_url,
            max_pages=max_pages,
            run_id=str(self.run.id),
        )

        try:
            await self._executor.ainvoke({  # type: ignore[union-attr]
                "input": (
                    f"Crawl the web application at {base_url}. "
                    f"Discover all UI flows and generate structured requirements. "
                    f"Stay within the same origin. "
                    f"Stop after visiting {max_pages} unique pages."
                )
            })
        finally:
            await self._close_playwright()

        requirements = self.memory.get("discovered_requirements", [])
        pages_visited = len(list(self.memory.get("visited_urls", set())))

        log.info(
            "crawl_agent.completed",
            run_id=str(self.run.id),
            requirements_found=len(requirements),
            pages_visited=pages_visited,
        )
        return AgentOutput(
            output_summary={
                "requirements_generated": len(requirements),
                "pages_visited": pages_visited,
                "base_url": base_url,
            }
        )

    # ── Playwright lifecycle ──────────────────────────────────────────────────

    async def execute(self) -> "AgentRun":
        """Start Playwright before the base lifecycle, shut it down after."""
        await self._start_playwright()
        try:
            return await super().execute()
        except Exception:
            await self._close_playwright()
            raise

    async def _start_playwright(self) -> None:
        from playwright.async_api import async_playwright

        self._pw_ctx = await async_playwright().start()
        self._browser = await self._pw_ctx.chromium.launch(headless=True)
        browser_ctx = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        self._page = await browser_ctx.new_page()
        log.debug("crawl_agent.playwright_started", run_id=str(self.run.id))

    async def _close_playwright(self) -> None:
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:  # noqa: BLE001
                pass
            self._browser = None
        if self._pw_ctx is not None:
            try:
                await self._pw_ctx.stop()
            except Exception:  # noqa: BLE001
                pass
            self._pw_ctx = None
        self._page = None
        log.debug("crawl_agent.playwright_closed", run_id=str(self.run.id))
