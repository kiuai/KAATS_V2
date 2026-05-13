from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AbstractAgent
from app.agents.tool_registry import build_generation_tools
from app.ai.prompts.generation_prompts import GENERATION_SYSTEM_PROMPT

log = structlog.get_logger(__name__)


class GenerationAgent(AbstractAgent):
    agent_type = "generation"

    def __init__(
        self,
        company_id: UUID,
        system_id: UUID,
        db: AsyncSession,
        requirement_ids: list[UUID] | None = None,
        target_formats: list[str] | None = None,
    ) -> None:
        super().__init__(company_id=company_id, system_id=system_id)
        self._db = db
        self._requirement_ids = requirement_ids
        self._target_formats = target_formats or ["playwright_python"]

    def _system_prompt(self) -> str:
        return GENERATION_SYSTEM_PROMPT

    def _build_tools(self) -> list:
        return build_generation_tools(self._db, self.memory)

    async def _execute(self, **kwargs: Any) -> dict[str, Any]:
        tools = self._build_tools()
        executor = self._build_executor_with_tools(tools)

        req_ids_str = (
            ", ".join(str(r) for r in self._requirement_ids)
            if self._requirement_ids
            else "all requirements for the system"
        )
        formats_str = ", ".join(self._target_formats)

        log.info("generation_agent.started", system_id=str(self.system_id), run_id=str(self.run_id))

        result = await executor.ainvoke({
            "input": (
                f"Generate test scripts for the following requirements: {req_ids_str}. "
                f"Target formats: {formats_str}. "
                f"Validate Playwright Python syntax before saving. "
                f"Cover the happy path and critical edge cases."
            )
        })

        scripts = self.memory.get("pending_scripts", [])
        log.info("generation_agent.completed", scripts_generated=len(scripts), run_id=str(self.run_id))

        return {"status": "completed", "scripts_generated": len(scripts)}

    def _build_executor_with_tools(self, tools: list) -> Any:
        from langchain_openai import AzureChatOpenAI
        from langchain.agents import create_react_agent, AgentExecutor
        from langchain import hub

        settings = self._settings
        llm = AzureChatOpenAI(
            azure_endpoint=str(settings.azure_openai_endpoint),
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_deployment_name,
            api_version="2024-02-01",
            temperature=0,
        )
        prompt = hub.pull("hwchase17/react")
        agent = create_react_agent(llm, tools, prompt)
        return AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=settings.max_agent_steps,
            handle_parsing_errors=True,
            verbose=not settings.is_production,
        )
