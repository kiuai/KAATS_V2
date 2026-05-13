from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from playwright.async_api import async_playwright

from app.agents.base import AbstractAgent
from app.agents.tool_registry import build_crawl_tools
from app.ai.prompts.crawl_prompts import CRAWL_SYSTEM_PROMPT
from app.config import get_settings

log = structlog.get_logger(__name__)


class CrawlAgent(AbstractAgent):
    agent_type = "crawl"

    def __init__(self, company_id: UUID, system_id: UUID, base_url: str) -> None:
        super().__init__(company_id=company_id, system_id=system_id)
        self._base_url = base_url

    def _system_prompt(self) -> str:
        return CRAWL_SYSTEM_PROMPT

    def _build_tools(self) -> list:
        # Tools are built with a live Playwright page in _execute
        return []

    async def _execute(self, **kwargs: Any) -> dict[str, Any]:
        settings = get_settings()
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1920, "height": 1080})
            page = await context.new_page()

            tools = build_crawl_tools(page, self.memory)

            executor = self._build_executor_with_tools(tools)
            self.memory.set("visited_urls", set())
            self.memory.set("generated_requirements", [])

            log.info("crawl_agent.started", base_url=self._base_url, run_id=str(self.run_id))

            result = await executor.ainvoke({
                "input": (
                    f"Crawl the web application at {self._base_url}. "
                    f"Discover all UI flows and generate structured requirements. "
                    f"Max pages: {settings.max_crawl_pages}."
                )
            })

            requirements = self.memory.get("generated_requirements", [])
            log.info(
                "crawl_agent.completed",
                run_id=str(self.run_id),
                requirements_found=len(requirements),
            )
            await browser.close()

        return {
            "status": "completed",
            "requirements_generated": len(requirements),
            "pages_visited": len(self.memory.get("visited_urls", set())),
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
