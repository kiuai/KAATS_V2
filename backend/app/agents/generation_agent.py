from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from langchain.tools import StructuredTool

from app.agents.base import AgentOutput, BaseAgent
from app.agents.tool_registry import ToolContext, build_generation_tools, build_tools
from app.ai.client import AzureOpenAIClient
from app.ai.prompts.generation_prompts import GENERATION_SYSTEM_PROMPT
from app.blob import get_blob_service

if TYPE_CHECKING:
    from app.auth.azure_ad import CurrentUser
    from app.models.agent_run import AgentRun
    from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


class GenerationAgent(BaseAgent):
    """
    Generates executable test scripts from structured requirements using Azure OpenAI.
    No browser required — pure LLM + tool-call loop.

    Expected ``config`` keys:
        requirement_ids  (list[str])  — UUIDs of requirements to generate scripts for
        target_formats   (list[str])  — e.g. ["playwright_python", "gherkin"]
    """

    agent_type = "generation"

    def __init__(
        self,
        run: "AgentRun",
        db: "AsyncSession",
        current_user: "CurrentUser | None",
        config: dict[str, Any],
    ) -> None:
        super().__init__(run, db, current_user, config)

    # ── BaseAgent interface ───────────────────────────────────────────────────

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
        )
        shared = build_tools(ctx)
        generation = build_generation_tools(self.db, self.memory)
        return shared + generation

    async def get_system_prompt(self) -> str:
        return GENERATION_SYSTEM_PROMPT

    async def run_agent(self) -> AgentOutput:
        req_ids: list[str] = self.config.get("requirement_ids", [])
        target_formats: list[str] = self.config.get("target_formats", ["playwright_python"])

        req_ids_str = (
            ", ".join(req_ids) if req_ids else "all requirements for the system"
        )
        formats_str = ", ".join(target_formats)

        log.info(
            "generation_agent.started",
            system_id=str(self.run.system_id),
            requirement_count=len(req_ids),
            run_id=str(self.run.id),
        )

        await self._executor.ainvoke({  # type: ignore[union-attr]
            "input": (
                f"Generate test scripts for the following requirements: {req_ids_str}. "
                f"Target formats: {formats_str}. "
                f"Validate Playwright Python syntax before saving. "
                f"Cover the happy path and critical edge cases."
            )
        })

        scripts = self.memory.get("generated_scripts", [])

        log.info(
            "generation_agent.completed",
            scripts_generated=len(scripts),
            run_id=str(self.run.id),
        )
        return AgentOutput(
            output_summary={
                "scripts_generated": len(scripts),
                "requirement_ids": req_ids,
                "target_formats": target_formats,
            }
        )
