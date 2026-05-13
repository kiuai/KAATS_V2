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
from app.models.enums import AgentType

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
        requirement_ids  (list[str])   — UUIDs of requirements to generate scripts for
        target_formats   (list[str])   — e.g. ["playwright", "gherkin"]
        base_url         (str)         — application base URL for generated scripts
        system_context   (str)         — free-text hint about the system under test

    Output keys (in AgentOutput.output_summary):
        scripts_generated   (int)
        scripts_failed      (int)
        script_ids          (list[str])
        requirement_ids     (list[str])
        target_formats      (list[str])
    """

    agent_type = AgentType.GENERATION

    def __init__(
        self,
        run: "AgentRun",
        db: "AsyncSession",
        current_user: "CurrentUser | None",
        config: dict[str, Any],
    ) -> None:
        super().__init__(run, db, current_user, config)

    # ── BaseAgent interface ───────────────────────────────────────────────────

    async def get_system_prompt(self) -> str:
        return GENERATION_SYSTEM_PROMPT

    async def get_tools(self) -> list[StructuredTool]:
        ai_client = AzureOpenAIClient(
            agent_run_id=self.run.id,
            company_id=self.run.company_id,
        )
        try:
            blob_client = get_blob_service()
        except Exception:  # noqa: BLE001
            blob_client = None  # type: ignore[assignment]

        # Seed memory with values the tools need at call time
        triggered_by = (
            str(self.run.triggered_by_user_id)
            if self.run.triggered_by_user_id
            else None
        )
        self.memory.set("triggered_by_user_id", triggered_by)
        self.memory.set("system_context", self.config.get("system_context", ""))
        self.memory.set("base_url", self.config.get("base_url", ""))

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
        generation = build_generation_tools(ctx)
        return shared + generation

    async def run_agent(self) -> AgentOutput:
        req_ids: list[str] = self.config.get("requirement_ids", [])
        target_formats: list[str] = self.config.get("target_formats", ["playwright"])
        base_url: str = self.config.get("base_url", "")
        system_context: str = self.config.get("system_context", "")

        # Initialise memory buckets used by save_test_script tool
        self.memory.set("generated_script_ids", [])
        self.memory.set("scripts_failed", 0)

        log.info(
            "generation_agent.started",
            system_id=str(self.run.system_id),
            requirement_count=len(req_ids),
            target_formats=target_formats,
            run_id=str(self.run.id),
        )

        try:
            await self._executor.ainvoke({  # type: ignore[union-attr]
                "input": self._build_input_prompt(
                    requirement_ids=req_ids,
                    target_formats=target_formats,
                    base_url=base_url,
                    system_context=system_context,
                )
            })
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "generation_agent.executor_error",
                run_id=str(self.run.id),
                error=str(exc),
            )
            self.memory.set("executor_error", str(exc))

        script_ids: list[str] = self.memory.get("generated_script_ids", [])
        scripts_failed: int = self.memory.get("scripts_failed", 0)

        log.info(
            "generation_agent.completed",
            scripts_generated=len(script_ids),
            scripts_failed=scripts_failed,
            run_id=str(self.run.id),
        )

        return AgentOutput(
            output_summary={
                "scripts_generated": len(script_ids),
                "scripts_failed": scripts_failed,
                "script_ids": script_ids,
                "requirement_ids": req_ids,
                "target_formats": target_formats,
            }
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_input_prompt(
        requirement_ids: list[str],
        target_formats: list[str],
        base_url: str,
        system_context: str,
    ) -> str:
        if not requirement_ids:
            return (
                "No requirement IDs were provided. "
                "Nothing to generate — return a summary with 0 scripts."
            )

        ids_block = "\n".join(f"  - {rid}" for rid in requirement_ids)
        formats_block = ", ".join(target_formats)

        lines = [
            "Generate test scripts for the following requirements:",
            ids_block,
            "",
            f"Export format(s): {formats_block}",
        ]

        if base_url:
            lines.append(f"Application base URL: {base_url}")
        else:
            lines.append(
                "No base URL was supplied. "
                "Use the BASE_URL environment variable placeholder in all scripts."
            )

        if system_context:
            lines.append(f"System context: {system_context}")

        lines += [
            "",
            "For EACH requirement ID listed above, follow the workflow in your system prompt:",
            "  1. load_requirement(requirement_id)",
            "  2. check_requirement_quality(requirement_json)",
            "  3. generate_test_cases(requirement_json, quality_report_json)",
            "  4. For each requested format, call the appropriate format tool",
            "  5. validate_script_syntax(rendered_content, format)",
            "  6. save_test_script(...)",
            "",
            "Process every requirement even if earlier ones fail. "
            "When done, summarise: scripts generated, skipped, and script IDs.",
        ]

        return "\n".join(lines)
