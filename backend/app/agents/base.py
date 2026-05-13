from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from langchain.agents import AgentExecutor
from langchain.tools import BaseTool

from app.agents.memory import WorkingMemory
from app.config import get_settings
from app.cosmos import get_agent_runs_container

log = structlog.get_logger(__name__)


class AbstractAgent(ABC):
    agent_type: str

    def __init__(self, company_id: UUID, system_id: UUID | None = None) -> None:
        self.company_id = company_id
        self.system_id = system_id
        self.run_id = uuid4()
        self.memory = WorkingMemory()
        self._cosmos_doc_id: str | None = None
        self._step_traces: list[dict] = []
        self._settings = get_settings()

    @abstractmethod
    def _build_tools(self) -> list[BaseTool]:
        """Return the tool set for this agent type."""

    @abstractmethod
    def _system_prompt(self) -> str:
        """Return the system prompt for this agent type."""

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the agent run. Returns a result summary dict."""
        await self._init_cosmos_doc()
        log.info("agent.run.started", agent_type=self.agent_type, run_id=str(self.run_id))

        settings = self._settings
        try:
            result = await asyncio.wait_for(
                self._execute(**kwargs),
                timeout=settings.agent_timeout_seconds,
            )
        except asyncio.TimeoutError:
            log.warning("agent.run.timeout", run_id=str(self.run_id))
            result = {"status": "timed_out", "error": "Wall-clock timeout exceeded"}
        except Exception as exc:
            log.exception("agent.run.failed", run_id=str(self.run_id))
            result = {"status": "failed", "error": str(exc)}
        finally:
            await self._finalise_cosmos_doc(result.get("status", "failed"))

        return result

    @abstractmethod
    async def _execute(self, **kwargs: Any) -> dict[str, Any]:
        """Subclass implements the actual agent logic."""

    def _build_executor(self) -> AgentExecutor:
        from langchain_openai import AzureChatOpenAI
        from langchain.agents import create_react_agent
        from langchain import hub

        settings = self._settings
        llm = AzureChatOpenAI(
            azure_endpoint=str(settings.azure_openai_endpoint),
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_deployment_name,
            api_version="2024-02-01",
            temperature=0,
            callbacks=[self._token_callback()],
        )
        tools = self._build_tools()
        prompt = hub.pull("hwchase17/react")
        agent = create_react_agent(llm, tools, prompt)
        return AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=settings.max_agent_steps,
            handle_parsing_errors=True,
            verbose=not settings.is_production,
        )

    def _token_callback(self) -> Any:
        from langchain.callbacks.base import BaseCallbackHandler

        agent_self = self

        class TokenTracker(BaseCallbackHandler):
            def on_llm_end(self, response: Any, **_: Any) -> None:
                usage = getattr(response, "llm_output", {}).get("token_usage", {})
                agent_self.memory.increment("prompt_tokens", usage.get("prompt_tokens", 0))
                agent_self.memory.increment("completion_tokens", usage.get("completion_tokens", 0))

        return TokenTracker()

    async def _init_cosmos_doc(self) -> None:
        self._cosmos_doc_id = str(self.run_id)
        container = get_agent_runs_container()
        doc = {
            "id": self._cosmos_doc_id,
            "company_id": str(self.company_id),
            "system_id": str(self.system_id) if self.system_id else None,
            "agent_type": self.agent_type,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps": [],
            "_partitionKey": str(self.company_id),
        }
        await container.create_item(doc)

    async def _checkpoint(self) -> None:
        """Flush working memory snapshot and accumulated steps to Cosmos."""
        if not self._cosmos_doc_id:
            return
        container = get_agent_runs_container()
        try:
            doc = await container.read_item(
                self._cosmos_doc_id, partition_key=str(self.company_id)
            )
            doc["steps"] = self._step_traces
            doc["working_memory_snapshot"] = self.memory.snapshot()
            await container.replace_item(self._cosmos_doc_id, doc)
        except Exception as exc:
            log.warning("agent.checkpoint.failed", run_id=str(self.run_id), error=str(exc))

    async def _finalise_cosmos_doc(self, final_status: str) -> None:
        if not self._cosmos_doc_id:
            return
        container = get_agent_runs_container()
        try:
            doc = await container.read_item(
                self._cosmos_doc_id, partition_key=str(self.company_id)
            )
            doc["status"] = final_status
            doc["completed_at"] = datetime.now(timezone.utc).isoformat()
            doc["steps"] = self._step_traces
            doc["prompt_tokens"] = self.memory.get("prompt_tokens", 0)
            doc["completion_tokens"] = self.memory.get("completion_tokens", 0)
            await container.replace_item(self._cosmos_doc_id, doc)
        except Exception as exc:
            log.warning("agent.finalise.failed", run_id=str(self.run_id), error=str(exc))
