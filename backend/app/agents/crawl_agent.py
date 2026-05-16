from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from langchain.tools import StructuredTool

from app.agents.base import AgentOutput, BaseAgent
from app.agents.tool_registry import ToolContext, build_crawl_tools, build_tools
from app.ai.client import AzureOpenAIClient
from app.ai.prompts.crawl_prompts import CRAWL_SYSTEM_PROMPT
from app.blob import get_blob_service
from app.models.enums import (
    AgentRunStatus,
    AgentType,
    CrawlerType,
    CrawlJobStatus,
    CrawlTriggerType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.auth.azure_ad import CurrentUser
    from app.models.agent_run import AgentRun

log = structlog.get_logger(__name__)


class CrawlAgent(BaseAgent):
    """
    Crawls a web application with Playwright to discover all UI flows and
    generate structured business requirements stored in the database.

    Expected ``config`` keys:
        target_url         (str)   — root URL to start crawling
        crawler_type       (str)   — "web" | "sap_fiori"  (default "web")
        max_pages          (int)   — page cap (default settings.max_crawl_pages)
        max_depth          (int)   — link depth cap (default 3)
        auth_config        (dict)  — {username, password} for authenticated crawls
        include_patterns   (list)  — URL prefixes to include (empty = all in domain)
        exclude_patterns   (list)  — URL patterns to skip
        system_context     (str)   — free-text hint about the system being crawled

    Lifecycle additions on top of BaseAgent.execute():
        1. Acquire a browser context from BrowserPool
        2. Create a CrawlJob record (status=RUNNING)
        3. Run the base execute() lifecycle
        4. Finalise the CrawlJob (COMPLETED / FAILED)
        5. Release the browser context
        6. Optionally dispatch a GenerationAgent run (auto_generate_scripts)
    """

    agent_type = AgentType.CRAWL  # "crawl" via str-Enum

    def __init__(
        self,
        run: AgentRun,
        db: AsyncSession,
        current_user: CurrentUser | None,
        config: dict[str, Any],
    ) -> None:
        super().__init__(run, db, current_user, config)
        self._browser_ctx: Any = None
        self._page: Any = None
        self._crawl_job_id: UUID | None = None

    # ── BaseAgent interface ───────────────────────────────────────────────────

    async def get_system_prompt(self) -> str:
        return CRAWL_SYSTEM_PROMPT

    async def get_tools(self) -> list[StructuredTool]:
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
            page=self._page,
            crawl_job_id=self._crawl_job_id,
        )
        shared = build_tools(ctx)
        crawl = build_crawl_tools(ctx)
        return shared + crawl

    async def run_agent(self) -> AgentOutput:
        from app.config import get_settings

        settings = get_settings()
        target_url: str = self.config.get("target_url", "")
        crawler_type: str = self.config.get("crawler_type", CrawlerType.WEB.value)
        max_pages: int = self.config.get("max_pages", settings.max_crawl_pages)
        max_depth: int = self.config.get("max_depth", 3)
        auth_config: dict | None = self.config.get("auth_config")
        include_patterns: list = self.config.get("include_patterns", [])
        exclude_patterns: list = self.config.get("exclude_patterns", [])
        system_context: str = self.config.get("system_context", "")

        self.memory.set("visited_urls", set())
        self.memory.set("crawl_requirement_ids", [])
        self.memory.set("crawl_screenshots", [])
        self.memory.set("failed_pages", [])

        log.info(
            "crawl_agent.started",
            target_url=target_url,
            crawler_type=crawler_type,
            max_pages=max_pages,
            run_id=str(self.run.id),
        )

        try:
            await self._executor.ainvoke(
                {  # type: ignore[union-attr]
                    "input": self._build_input_prompt(
                        target_url=target_url,
                        crawler_type=crawler_type,
                        max_pages=max_pages,
                        max_depth=max_depth,
                        auth_config=auth_config,
                        include_patterns=include_patterns,
                        exclude_patterns=exclude_patterns,
                        system_context=system_context,
                    )
                }
            )
        except Exception as exc:  # noqa: BLE001
            # The agent failed mid-run — record the error and surface a
            # partial output instead of crashing the entire lifecycle.
            log.warning(
                "crawl_agent.executor_error",
                run_id=str(self.run.id),
                error=str(exc),
            )
            self.memory.set("executor_error", str(exc))

        visited = self.memory.get("visited_urls", set())
        req_ids: list[str] = self.memory.get("crawl_requirement_ids", [])
        failed: list = self.memory.get("failed_pages", [])

        pages_visited = len(list(visited))
        req_count = len(req_ids)

        log.info(
            "crawl_agent.completed",
            run_id=str(self.run.id),
            pages_visited=pages_visited,
            requirements_generated=req_count,
        )

        return AgentOutput(
            output_summary={
                "pages_visited": pages_visited,
                "requirements_generated": req_count,
                "failed_pages": len(failed),
                "crawl_job_id": str(self._crawl_job_id) if self._crawl_job_id else None,
                "target_url": target_url,
                "crawler_type": crawler_type,
            }
        )

    # ── execute() override — browser + CrawlJob lifecycle ─────────────────────

    async def execute(self) -> AgentRun:
        """
        Wrap BaseAgent.execute() with:
        - BrowserPool acquisition / release
        - CrawlJob creation / finalisation
        - Post-crawl GenerationAgent dispatch (if enabled)
        """
        from app.agents.browser_pool import get_browser_pool

        pool = get_browser_pool()
        self._browser_ctx, self._page = await pool.acquire()

        try:
            await self._create_crawl_job()
            run = await super().execute()
            await self._finish_crawl_job(run.status)
        except Exception:
            if self._crawl_job_id:
                await self._finish_crawl_job(AgentRunStatus.FAILED.value)
            raise
        finally:
            self._page = None
            await pool.release(self._browser_ctx)
            self._browser_ctx = None

        # Auto-generate test scripts for newly discovered requirements
        if run.status == AgentRunStatus.COMPLETED.value:
            await self._maybe_dispatch_generation()

        return run

    # ── CrawlJob helpers ──────────────────────────────────────────────────────

    async def _create_crawl_job(self) -> None:
        from app.models.crawl_job import CrawlJob

        trigger = (
            CrawlTriggerType.SCHEDULED.value
            if self.run.scheduled_job_id
            else CrawlTriggerType.MANUAL.value
        )
        crawl_job = CrawlJob(
            system_id=self.run.system_id,
            company_id=self.run.company_id,
            crawler_type=self.config.get("crawler_type", CrawlerType.WEB.value),
            target_url=self.config.get("target_url", "")[:2048],
            crawl_config=self.config,
            status=CrawlJobStatus.RUNNING.value,
            triggered_by=trigger,
            scheduled_job_id=self.run.scheduled_job_id,
            agent_run_id=self.run.id,
            created_by=self.run.triggered_by_user_id,
            started_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.db.add(crawl_job)
        await self.db.flush()
        self._crawl_job_id = crawl_job.id
        log.info(
            "crawl_agent.crawl_job_created",
            crawl_job_id=str(self._crawl_job_id),
            run_id=str(self.run.id),
        )

    async def _finish_crawl_job(self, run_status: str) -> None:
        if not self._crawl_job_id:
            return
        from app.models.crawl_job import CrawlJob

        crawl_job = await self.db.get(CrawlJob, self._crawl_job_id)
        if crawl_job is None:
            return

        crawl_job.status = (
            CrawlJobStatus.COMPLETED.value
            if run_status == AgentRunStatus.COMPLETED.value
            else CrawlJobStatus.FAILED.value
        )
        crawl_job.completed_at = datetime.now(UTC).replace(tzinfo=None)
        if run_status != AgentRunStatus.COMPLETED.value:
            crawl_job.error_message = self.memory.get("executor_error", "")[:1000]
        try:
            await self.db.flush()
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "crawl_agent.finish_crawl_job_failed",
                error=str(exc),
                run_id=str(self.run.id),
            )

    # ── Auto-generation ───────────────────────────────────────────────────────

    async def _maybe_dispatch_generation(self) -> None:
        """
        If the system has ``auto_generate_scripts: true`` in its settings JSON
        and the crawl produced at least one requirement, dispatch a GenerationAgent
        run for all newly created requirements.
        """
        req_ids_str: list[str] = self.memory.get("crawl_requirement_ids", [])
        if not req_ids_str:
            return

        if not self.run.system_id:
            return

        from app.models.system import System

        system = await self.db.get(System, self.run.system_id)
        if system is None:
            return

        system_settings: dict = system.settings or {}
        if not system_settings.get("auto_generate_scripts"):
            return

        from app.services.agent_dispatcher import AgentDispatcher

        req_ids = [UUID(rid) for rid in req_ids_str if rid]
        dispatcher = AgentDispatcher(self.db)
        generation_run = await dispatcher.dispatch_generation(
            company_id=self.run.company_id,
            system_id=self.run.system_id,
            requirement_ids=req_ids,
            triggered_by_user_id=self.run.triggered_by_user_id,
            scheduled_job_id=None,  # This is a follow-on run, not a scheduled one
        )
        log.info(
            "crawl_agent.auto_generation_dispatched",
            generation_run_id=str(generation_run.id),
            requirement_count=len(req_ids),
            run_id=str(self.run.id),
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_input_prompt(
        target_url: str,
        crawler_type: str,
        max_pages: int,
        max_depth: int,
        auth_config: dict | None,
        include_patterns: list,
        exclude_patterns: list,
        system_context: str,
    ) -> str:
        lines = [
            f"Crawl the web application starting at: {target_url}",
            f"Crawler type: {crawler_type}",
            f"Maximum pages to visit: {max_pages}",
            f"Maximum link depth: {max_depth}",
        ]
        if system_context:
            lines.append(f"System context: {system_context}")
        if include_patterns:
            lines.append(f"Only follow URLs matching these prefixes: {include_patterns}")
        if exclude_patterns:
            lines.append(f"Skip URLs matching these patterns: {exclude_patterns}")
        if auth_config and crawler_type == CrawlerType.SAP_FIORI.value:
            username = auth_config.get("username", "")
            lines.append(
                f"This is a SAP Fiori system. "
                f"Start by calling handle_sap_fiori_login with username={username!r}."
            )
        elif auth_config:
            lines.append(
                "Authentication credentials are provided in auth_config. "
                "If you encounter a login page, use handle_sap_fiori_login or "
                "fill the form fields manually."
            )
        lines.append(
            "\nFollow the crawl strategy in your system prompt. "
            "Begin by navigating to the target URL."
        )
        return "\n".join(lines)
