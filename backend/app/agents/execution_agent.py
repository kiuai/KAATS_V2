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
from app.models.enums import AgentType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.auth.azure_ad import CurrentUser
    from app.models.agent_run import AgentRun

log = structlog.get_logger(__name__)


class ExecutionAgent(BaseAgent):
    """
    Executes test scripts step-by-step against a live system, capturing
    annotated screenshot evidence after every step and generating a PDF report.

    Expected ``config`` keys:
        script_ids   (list[str])  — UUIDs of TestScripts to execute
        base_url     (str)        — application base URL (injected into prompt)

    Output keys (in AgentOutput.output_summary):
        runs_completed   (int)
        total_passed     (int)
        total_failed     (int)
        run_ids          (list[str])
        report_urls      (list[str])
    """

    agent_type = AgentType.EXECUTION

    def __init__(
        self,
        run: AgentRun,
        db: AsyncSession,
        current_user: CurrentUser | None,
        config: dict[str, Any],
    ) -> None:
        super().__init__(run, db, current_user, config)
        self._browser: Any = None
        self._page: Any = None
        self._pw_ctx: Any = None

    # ── BaseAgent interface ───────────────────────────────────────────────────

    async def get_system_prompt(self) -> str:
        return EXECUTION_SYSTEM_PROMPT

    async def get_tools(self) -> list[StructuredTool]:
        """
        Return shared + Playwright execution tools.
        Called after the browser is already started in execute().
        """
        triggered_by = str(self.run.triggered_by_user_id) if self.run.triggered_by_user_id else None
        self.memory.set("triggered_by_user_id", triggered_by)

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
            page=self._page,
        )
        shared = build_tools(ctx)
        execution = build_execution_tools(ctx)
        return shared + execution

    async def run_agent(self) -> AgentOutput:
        script_ids: list[str] = self.config.get("script_ids", [])
        base_url: str = self.config.get("base_url", "")

        # Single script_id legacy support
        if not script_ids and self.config.get("script_id"):
            script_ids = [self.config["script_id"]]

        # Initialise memory tracking
        self.memory.set("execution_run_ids", [])
        self.memory.set("report_urls", [])
        self.memory.set("step_screenshots", [])
        self.memory.set("saved_step_result_ids", [])

        log.info(
            "execution_agent.started",
            script_count=len(script_ids),
            run_id=str(self.run.id),
        )

        try:
            await self._executor.ainvoke(  # type: ignore[union-attr]
                {"input": self._build_input_prompt(script_ids, base_url)}
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "execution_agent.executor_error",
                run_id=str(self.run.id),
                error=str(exc),
            )
            self.memory.set("executor_error", str(exc))

        run_ids: list[str] = self.memory.get("execution_run_ids") or []
        report_urls: list[str] = self.memory.get("report_urls") or []

        # Compute pass/fail totals from step result records
        total_passed, total_failed = await self._tally_outcomes(run_ids)

        log.info(
            "execution_agent.completed",
            runs_completed=len(run_ids),
            total_passed=total_passed,
            total_failed=total_failed,
            run_id=str(self.run.id),
        )

        return AgentOutput(
            output_summary={
                "runs_completed": len(run_ids),
                "total_passed": total_passed,
                "total_failed": total_failed,
                "run_ids": run_ids,
                "report_urls": report_urls,
            }
        )

    # ── execute() override — Playwright lifecycle ─────────────────────────────

    async def execute(self) -> AgentRun:
        """Start a dedicated Playwright browser, run the agent, then shut it down."""
        await self._start_playwright()
        try:
            return await super().execute()
        except Exception:
            raise
        finally:
            await self._close_playwright()

    # ── Playwright lifecycle ──────────────────────────────────────────────────

    async def _start_playwright(self) -> None:
        from playwright.async_api import async_playwright

        self._pw_ctx = await async_playwright().start()
        self._browser = await self._pw_ctx.chromium.launch(headless=True)
        browser_context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        self._page = await browser_context.new_page()
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

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _build_input_prompt(script_ids: list[str], base_url: str) -> str:
        if not script_ids:
            return "No script IDs were provided. Nothing to execute — return a summary with 0 runs."

        ids_block = "\n".join(f"  - {sid}" for sid in script_ids)
        lines = [
            "Execute the following test scripts:",
            ids_block,
            "",
        ]
        if base_url:
            lines.append(f"Application base URL: {base_url}")
        else:
            lines.append(
                "No base URL was supplied. "
                "Use the base_url from each script's preconditions or step parameters."
            )
        lines += [
            "",
            "For EACH script ID above, follow the workflow in your system prompt:",
            "  1. load_test_script(script_id)",
            "  2. create_execution_run(script_id)",
            "  3. For each step: execute → take_step_screenshot → save_step_result",
            "  4. finalize_execution_run(run_id)",
            "  5. generate_evidence_report(run_id)",
            "",
            "Process every script even if an earlier one fails. "
            "When done, provide a summary of all runs.",
        ]
        return "\n".join(lines)

    async def _tally_outcomes(self, run_ids: list[str]) -> tuple[int, int]:
        """Read DB step totals from finalised ExecutionRun records."""
        if not run_ids:
            return 0, 0
        from app.models.execution_evidence import ExecutionRun

        total_passed = 0
        total_failed = 0
        for rid in run_ids:
            try:
                run_uuid = UUID(rid)
            except ValueError:
                continue
            run = await self.db.get(ExecutionRun, run_uuid)
            if run:
                total_passed += run.passed_steps
                total_failed += run.failed_steps
        return total_passed, total_failed
