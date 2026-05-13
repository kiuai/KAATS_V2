from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from playwright.async_api import async_playwright
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AbstractAgent
from app.agents.tool_registry import build_execution_tools
from app.ai.prompts.execution_prompts import EXECUTION_SYSTEM_PROMPT

log = structlog.get_logger(__name__)


class ExecutionAgent(AbstractAgent):
    agent_type = "execution"

    def __init__(
        self,
        company_id: UUID,
        system_id: UUID,
        script_id: UUID,
        execution_id: UUID,
        db: AsyncSession,
    ) -> None:
        super().__init__(company_id=company_id, system_id=system_id)
        self._script_id = script_id
        self._execution_id = execution_id
        self._db = db

    def _system_prompt(self) -> str:
        return EXECUTION_SYSTEM_PROMPT

    def _build_tools(self) -> list:
        return []

    async def _execute(self, **kwargs: Any) -> dict[str, Any]:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1920, "height": 1080})
            page = await context.new_page()

            tools = build_execution_tools(page, self.memory, self._db)
            executor = self._build_executor_with_tools(tools)

            self.memory.set("current_step_index", 0)
            self.memory.set("passed_steps", [])
            self.memory.set("failed_steps", [])

            log.info(
                "execution_agent.started",
                script_id=str(self._script_id),
                run_id=str(self.run_id),
            )

            result = await executor.ainvoke({
                "input": (
                    f"Execute test script {self._script_id} step by step. "
                    f"For each step: perform the action, take a screenshot, "
                    f"evaluate pass/fail, and record the result. "
                    f"Generate a PDF evidence report when all steps are complete."
                )
            })

            passed = len(self.memory.get("passed_steps", []))
            failed = len(self.memory.get("failed_steps", []))
            log.info(
                "execution_agent.completed",
                passed=passed,
                failed=failed,
                run_id=str(self.run_id),
            )
            await browser.close()

        return {
            "status": "completed" if failed == 0 else "failed",
            "passed_count": passed,
            "failed_count": failed,
        }

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
