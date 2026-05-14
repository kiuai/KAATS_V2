from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.callbacks.base import AsyncCallbackHandler
from langchain.tools import StructuredTool
from langchain_core.outputs import LLMResult
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import AzureChatOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.memory import AgentMemory
from app.config import get_settings
from app.cosmos import get_agent_runs_container
from app.models.agent_run import AgentRun, AgentToolCall
from app.models.enums import AgentRunStatus

if TYPE_CHECKING:
    from app.auth.azure_ad import CurrentUser

log = structlog.get_logger(__name__)

_PROMPT_TOKEN_COST = Decimal("0.000005")
_COMPLETION_TOKEN_COST = Decimal("0.000015")


@dataclass
class AgentOutput:
    output_summary: dict[str, Any]
    status: str = "completed"


class LoggingCallbackHandler(AsyncCallbackHandler):
    """
    LangChain async callback handler.
    Logs every tool call to the AgentToolCall table and tracks token usage
    in WorkingMemory so BaseAgent.execute() can persist the totals.
    """

    def __init__(self, agent: "BaseAgent") -> None:
        super().__init__()
        self._agent = agent
        self._tool_start_times: dict[str, float] = {}
        self._tool_inputs: dict[str, Any] = {}
        self._tool_names: dict[str, str] = {}

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        key = str(run_id or "")
        self._tool_start_times[key] = time.monotonic()
        self._tool_inputs[key] = input_str
        self._tool_names[key] = serialized.get("name", "unknown")
        log.debug(
            "agent.tool.start",
            tool=self._tool_names[key],
            run_id=str(self._agent.run.id),
        )

    async def on_tool_end(
        self,
        output: str,
        *,
        run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        key = str(run_id or "")
        duration_ms = int((time.monotonic() - self._tool_start_times.pop(key, time.monotonic())) * 1000)
        tool_name = self._tool_names.pop(key, "unknown")
        tool_input = self._tool_inputs.pop(key, "")
        await self._agent._record_tool_call(
            tool_name=tool_name,
            tool_input={"input": tool_input},
            tool_output={"output": output[:4096]},
            duration_ms=duration_ms,
            success=True,
        )

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        key = str(run_id or "")
        duration_ms = int((time.monotonic() - self._tool_start_times.pop(key, time.monotonic())) * 1000)
        tool_name = self._tool_names.pop(key, "unknown")
        tool_input = self._tool_inputs.pop(key, "")
        await self._agent._record_tool_call(
            tool_name=tool_name,
            tool_input={"input": tool_input},
            tool_output={"error": str(error)[:4096]},
            duration_ms=duration_ms,
            success=False,
        )

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        total_chars = sum(len(p) for p in prompts)
        log.debug(
            "agent.llm.start",
            prompt_chars=total_chars,
            run_id=str(self._agent.run.id),
        )

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        llm_output = response.llm_output or {}
        token_usage = llm_output.get("token_usage", {})
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        self._agent.memory.increment("prompt_tokens", prompt_tokens)
        self._agent.memory.increment("completion_tokens", completion_tokens)
        log.debug(
            "agent.llm.end",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            run_id=str(self._agent.run.id),
        )


class BaseAgent(ABC):
    """
    Abstract base for all KAATS agents.

    Subclasses implement:
        get_tools()         → list[StructuredTool]
        get_system_prompt() → str
        run_agent()         → AgentOutput   (uses self._executor)

    The concrete execute() method handles the full lifecycle:
    DB status management, LangChain executor setup, token/cost tracking,
    Cosmos checkpointing, and scheduled-job feedback.
    """

    # Subclasses must declare this.
    agent_type: str

    def __init__(
        self,
        run: AgentRun,
        db: AsyncSession,
        current_user: CurrentUser | None,
        config: dict[str, Any],
    ) -> None:
        self.run = run
        self.db = db
        self.current_user = current_user
        self.config = config
        self.memory = AgentMemory()
        self._executor: AgentExecutor | None = None
        self._cosmos_doc_id: str | None = None

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    async def get_tools(self) -> list[StructuredTool]:
        """Return the tool set for this agent type."""

    @abstractmethod
    async def get_system_prompt(self) -> str:
        """Return the system prompt for this agent type."""

    @abstractmethod
    async def run_agent(self) -> AgentOutput:
        """
        Implement the agent-specific logic here.
        ``self._executor`` is ready to use via ``await self._executor.ainvoke({...})``.
        """

    # ── Concrete lifecycle ────────────────────────────────────────────────────

    async def execute(self) -> AgentRun:
        """
        Full agent lifecycle:
        1. Set run.status = RUNNING
        2. Build LangChain AgentExecutor
        3. Register LoggingCallbackHandler
        4. Call run_agent() within a wall-clock timeout
        5. Persist status, tokens, cost, timestamps
        6. Return the updated AgentRun record
        """
        settings = get_settings()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # 1. Transition to RUNNING
        self.run.status = AgentRunStatus.RUNNING.value
        self.run.started_at = now
        await self.db.flush()

        log.info(
            "agent.execute.start",
            agent_type=self.agent_type,
            run_id=str(self.run.id),
            company_id=str(self.run.company_id),
        )

        # 2 & 3. Build executor with logging callback
        tools = await self.get_tools()
        system_prompt = await self.get_system_prompt()
        callback_handler = LoggingCallbackHandler(self)
        self._executor = self._build_executor(tools, system_prompt, callback_handler, settings)

        # Initialise Cosmos run document
        await self._init_cosmos_doc()

        # 4. Run with wall-clock timeout
        try:
            result = await asyncio.wait_for(
                self.run_agent(),
                timeout=settings.agent_timeout_seconds,
            )
            # 5a. Success
            self.run.status = AgentRunStatus.COMPLETED.value
            self.run.output_summary = result.output_summary
            log.info(
                "agent.execute.completed",
                run_id=str(self.run.id),
                summary=result.output_summary,
            )
        except asyncio.TimeoutError:
            log.warning("agent.execute.timeout", run_id=str(self.run.id))
            self.run.status = "timed_out"
            self.run.error_message = "Wall-clock timeout exceeded"
        except Exception as exc:
            log.exception("agent.execute.failed", run_id=str(self.run.id))
            self.run.status = AgentRunStatus.FAILED.value
            self.run.error_message = str(exc)[:1000]

        # 7. Persist token counts, cost, timestamps
        self.run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.run.prompt_tokens = self.memory.get("prompt_tokens", 0)
        self.run.completion_tokens = self.memory.get("completion_tokens", 0)
        self.run.total_cost_usd = (
            Decimal(str(self.run.prompt_tokens)) * _PROMPT_TOKEN_COST
            + Decimal(str(self.run.completion_tokens)) * _COMPLETION_TOKEN_COST
        )
        await self.db.flush()

        # Update linked scheduled job (if any)
        await self._update_scheduled_job(self.run.status)

        # Upsert daily token usage for billing dashboards
        await self._upsert_token_usage()

        # Notify triggering user of completion / failure
        await self._notify_triggering_user(self.run.status)

        # Finalise Cosmos document
        await self._finalise_cosmos_doc(self.run.status)

        return self.run

    # ── Tool-call recording ───────────────────────────────────────────────────

    async def _record_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: dict[str, Any] | None,
        duration_ms: int,
        success: bool,
    ) -> None:
        tool_call = AgentToolCall(
            agent_run_id=self.run.id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            duration_ms=duration_ms,
            success=success,
            called_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.db.add(tool_call)
        try:
            await self.db.flush()
        except Exception as exc:  # noqa: BLE001
            log.warning("agent.tool_call.persist_failed", error=str(exc))

    # ── Scheduled-job feedback ────────────────────────────────────────────────

    async def _update_scheduled_job(self, status: str) -> None:
        if not self.run.scheduled_job_id:
            return
        from app.models.scheduled_job import ScheduledJob, ScheduledJobRun

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        result = await self.db.execute(
            select(ScheduledJobRun).where(ScheduledJobRun.agent_run_id == self.run.id)
        )
        job_run = result.scalar_one_or_none()
        if job_run:
            job_run.status = "completed" if status == AgentRunStatus.COMPLETED.value else "failed"
            job_run.completed_at = now

        job = await self.db.get(ScheduledJob, self.run.scheduled_job_id)
        if job:
            job.last_run_status = "success" if status == AgentRunStatus.COMPLETED.value else "failed"

        try:
            await self.db.flush()
        except Exception as exc:  # noqa: BLE001
            log.warning("agent.scheduled_job.update_failed", error=str(exc))

    # ── Token usage (billing) ─────────────────────────────────────────────────

    async def _upsert_token_usage(self) -> None:
        from app.models.agent_run import CompanyTokenUsage

        today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        )
        result = await self.db.execute(
            select(CompanyTokenUsage).where(
                CompanyTokenUsage.company_id == self.run.company_id,
                CompanyTokenUsage.agent_type == self.agent_type,
                CompanyTokenUsage.usage_date == today,
            )
        )
        usage = result.scalar_one_or_none()
        if usage is None:
            usage = CompanyTokenUsage(
                company_id=self.run.company_id,
                agent_type=self.agent_type,
                usage_date=today,
                prompt_tokens=0,
                completion_tokens=0,
            )
            self.db.add(usage)

        usage.prompt_tokens += self.run.prompt_tokens
        usage.completion_tokens += self.run.completion_tokens
        if usage.total_cost_usd is None:
            usage.total_cost_usd = self.run.total_cost_usd
        elif self.run.total_cost_usd is not None:
            usage.total_cost_usd += self.run.total_cost_usd

        try:
            await self.db.flush()
        except Exception as exc:  # noqa: BLE001
            log.warning("agent.token_usage.upsert_failed", error=str(exc))

    # ── In-app notifications ──────────────────────────────────────────────────

    async def _notify_triggering_user(self, status: str) -> None:
        if not self.run.triggered_by_user_id:
            return
        from app.models.enums import AgentRunStatus
        from app.services.notification_service import NotificationService

        is_success = status == AgentRunStatus.COMPLETED.value
        notif_type = "success" if is_success else "error"
        title = (
            f"{self.agent_type.replace('_', ' ').title()} agent completed"
            if is_success
            else f"{self.agent_type.replace('_', ' ').title()} agent failed"
        )
        action_url = f"/agents/{self.run.id}"

        try:
            await NotificationService(self.db).create(
                user_id=self.run.triggered_by_user_id,
                company_id=self.run.company_id,
                type=notif_type,
                title=title,
                action_url=action_url,
                resource_type="agent_run",
                resource_id=str(self.run.id),
            )
        except Exception:  # noqa: BLE001
            log.warning("agent.notify.failed", run_id=str(self.run.id))

    # ── Cosmos document lifecycle ─────────────────────────────────────────────

    async def _init_cosmos_doc(self) -> None:
        self._cosmos_doc_id = str(self.run.id)
        container = get_agent_runs_container()
        doc: dict[str, Any] = {
            "id": self._cosmos_doc_id,
            "company_id": str(self.run.company_id),
            "system_id": str(self.run.system_id) if self.run.system_id else None,
            "agent_type": self.agent_type,
            "status": AgentRunStatus.RUNNING.value,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps": [],
            "_partitionKey": str(self.run.company_id),
        }
        try:
            await container.upsert_item(doc)
        except Exception as exc:  # noqa: BLE001
            log.warning("agent.cosmos.init_failed", run_id=self._cosmos_doc_id, error=str(exc))

    async def _checkpoint(self) -> None:
        if not self._cosmos_doc_id:
            return
        container = get_agent_runs_container()
        try:
            doc = await container.read_item(
                self._cosmos_doc_id, partition_key=str(self.run.company_id)
            )
            doc["working_memory_snapshot"] = self.memory.snapshot()
            await container.replace_item(self._cosmos_doc_id, doc)
        except Exception as exc:  # noqa: BLE001
            log.warning("agent.checkpoint.failed", run_id=str(self.run.id), error=str(exc))

    async def _finalise_cosmos_doc(self, final_status: str) -> None:
        if not self._cosmos_doc_id:
            return
        container = get_agent_runs_container()
        try:
            doc = await container.read_item(
                self._cosmos_doc_id, partition_key=str(self.run.company_id)
            )
            doc["status"] = final_status
            doc["completed_at"] = datetime.now(timezone.utc).isoformat()
            doc["prompt_tokens"] = self.run.prompt_tokens
            doc["completion_tokens"] = self.run.completion_tokens
            doc["output_summary"] = self.run.output_summary
            await container.replace_item(self._cosmos_doc_id, doc)
        except Exception as exc:  # noqa: BLE001
            log.warning("agent.cosmos.finalise_failed", run_id=str(self.run.id), error=str(exc))

    # ── LangChain executor builder ────────────────────────────────────────────

    @staticmethod
    def _build_executor(
        tools: list[StructuredTool],
        system_prompt: str,
        callback_handler: LoggingCallbackHandler,
        settings: Any,
    ) -> AgentExecutor:
        llm = AzureChatOpenAI(
            azure_endpoint=str(settings.azure_openai_endpoint),
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_deployment_name,
            api_version="2024-10-01-preview",
            temperature=0,
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])
        agent = create_tool_calling_agent(llm, tools, prompt)
        return AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=settings.max_agent_steps,
            handle_parsing_errors=True,
            verbose=True,
            callbacks=[callback_handler],
        )


# ── Backward-compatible alias ─────────────────────────────────────────────────
AbstractAgent = BaseAgent
