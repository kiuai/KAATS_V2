from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from langchain.tools import StructuredTool

from app.agents.base import AgentOutput, BaseAgent
from app.agents.tool_registry import ToolContext, build_execution_tools, build_tools
from app.ai.client import AzureOpenAIClient
from app.ai.prompts.execution_prompts import EXECUTION_SYSTEM_PROMPT
from app.blob import get_blob_service

if TYPE_CHECKING:
    from app.auth.azure_ad import CurrentUser
    from app.models.agent_run import AgentRun
    from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


class ExecutionAgent(BaseAgent):
    """
    Executes a test script against a live system using Playwright, recording
    step-level pass/fail results and uploading screenshot evidence to Blob Storage.

    Expected ``config`` keys:
        script_id  (str)  — UUID of the TestScript to execute
    """

    agent_type = "execution"

    def __init__(
        self,
        run: "AgentRun",
        db: "AsyncSession",
        current_user: "CurrentUser | None",
        config: dict[str, Any],
    ) -> None:
        super().__init__(run, db, current_user, config)
        self._browser: Any = None
        self._page: Any = None
        self._pw_ctx: Any = None

    # ── BaseAgent interface ───────────────────────────────────────────────────

    async def get_tools(self) -> list[StructuredTool]:
        """
        Return shared + Playwright execution tools.
        Called after the browser is already started in execute().
        """
        try:
            blob_client = get_blob_service()
        except Exception:  # noqa: BLE001
            blob_client = None  # type: ignore[assignment]

        ai_client = AzureOpenAIClient(
            agent_run_id=self.run.id,
            company_id=self.run.company_id,
        )
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
        execution = build_execution_tools(self._page, self.memory, self.db)
        return shared + execution

    async def get_system_prompt(self) -> str:
        return EXECUTION_SYSTEM_PROMPT

    async def run_agent(self) -> AgentOutput:
        script_id: str = self.config.get("script_id", "")

        self.memory.set("current_step_index", 0)
        self.memory.set("step_results", [])

        log.info(
            "execution_agent.started",
            script_id=script_id,
            run_id=str(self.run.id),
        )

        try:
            await self._executor.ainvoke({  # type: ignore[union-attr]
                "input": (
                    f"Execute test script {script_id} step by step. "
                    f"For each step: perform the action, take a screenshot, "
                    f"evaluate pass/fail, and record the result using mark_step_passed "
                    f"or mark_step_failed. "
                    f"Continue through all steps even on failure unless blocked."
                )
            })
        finally:
            await self._close_playwright()

        step_results: list[dict] = self.memory.get("step_results", [])
        passed = sum(1 for s in step_results if s.get("status") == "passed")
        failed = sum(1 for s in step_results if s.get("status") == "failed")
        total = len(step_results)

        log.info(
            "execution_agent.completed",
            passed=passed,
            failed=failed,
            total=total,
            run_id=str(self.run.id),
        )
        return AgentOutput(
            output_summary={
                "script_id": script_id,
                "total_steps": total,
                "passed_count": passed,
                "failed_count": failed,
                "pass_rate": round(passed / total, 4) if total else 0.0,
            },
            status="completed" if failed == 0 else "completed_with_failures",
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
        log.debug("execution_agent.playwright_started", run_id=str(self.run.id))

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
        log.debug("execution_agent.playwright_closed", run_id=str(self.run.id))
