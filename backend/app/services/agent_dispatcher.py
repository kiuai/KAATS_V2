from __future__ import annotations

import json
from uuid import UUID

import structlog
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.agent_run import AgentRun
from app.models.enums import AgentRunStatus, AgentTriggerType

log = structlog.get_logger(__name__)


class AgentDispatcher:
    """
    Creates AgentRun records and publishes messages to the AI-jobs Service Bus topic.

    Always use this class to trigger agent runs — never publish to Service Bus
    directly from a router or scheduler. This ensures every run has a DB record
    before the worker picks it up.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Typed dispatch methods ────────────────────────────────────────────────

    async def dispatch_crawl(
        self,
        company_id: UUID,
        system_id: UUID,
        base_url: str,
        triggered_by_user_id: UUID | None = None,
        scheduled_job_id: UUID | None = None,
        max_pages: int | None = None,
    ) -> AgentRun:
        """Create a crawl AgentRun and enqueue it for processing."""
        config: dict = {"base_url": base_url}
        if max_pages is not None:
            config["max_pages"] = max_pages
        return await self._create_and_publish(
            agent_type="crawl",
            company_id=company_id,
            system_id=system_id,
            triggered_by_user_id=triggered_by_user_id,
            scheduled_job_id=scheduled_job_id,
            input_config=config,
        )

    async def dispatch_generation(
        self,
        company_id: UUID,
        system_id: UUID,
        requirement_ids: list[UUID],
        target_formats: list[str] | None = None,
        triggered_by_user_id: UUID | None = None,
        scheduled_job_id: UUID | None = None,
    ) -> AgentRun:
        """Create a generation AgentRun and enqueue it for processing."""
        config: dict = {
            "requirement_ids": [str(r) for r in requirement_ids],
            "target_formats": target_formats or ["playwright_python"],
        }
        return await self._create_and_publish(
            agent_type="generation",
            company_id=company_id,
            system_id=system_id,
            triggered_by_user_id=triggered_by_user_id,
            scheduled_job_id=scheduled_job_id,
            input_config=config,
        )

    async def dispatch_execution(
        self,
        company_id: UUID,
        system_id: UUID,
        script_id: UUID,
        triggered_by_user_id: UUID | None = None,
        scheduled_job_id: UUID | None = None,
    ) -> AgentRun:
        """Create an execution AgentRun and enqueue it for processing."""
        config: dict = {"script_id": str(script_id)}
        return await self._create_and_publish(
            agent_type="execution",
            company_id=company_id,
            system_id=system_id,
            triggered_by_user_id=triggered_by_user_id,
            scheduled_job_id=scheduled_job_id,
            input_config=config,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _create_and_publish(
        self,
        agent_type: str,
        company_id: UUID,
        system_id: UUID | None,
        triggered_by_user_id: UUID | None,
        scheduled_job_id: UUID | None,
        input_config: dict,
    ) -> AgentRun:
        # ── Quota enforcement ─────────────────────────────────────────────────
        # Skip quota check for scheduler-triggered runs so the system doesn't
        # silently drop scheduled jobs mid-month — operators get alerted via the
        # Monitor alert instead.
        if not scheduled_job_id:
            from app.services.usage_service import UsageService

            await UsageService(self._db).assert_agent_run_allowed(company_id)

        trigger_type = (
            AgentTriggerType.SCHEDULED.value if scheduled_job_id else AgentTriggerType.MANUAL.value
        )
        run = AgentRun(
            agent_type=agent_type,
            company_id=company_id,
            system_id=system_id,
            triggered_by_user_id=triggered_by_user_id,
            scheduled_job_id=scheduled_job_id,
            trigger_type=trigger_type,
            status=AgentRunStatus.PENDING.value,
            input_config=input_config,
        )
        self._db.add(run)
        await self._db.flush()

        try:
            await _publish_run_message(run.id, agent_type, company_id)
        except Exception as exc:  # noqa: BLE001
            # Don't block the caller — the worker can be triggered later or the run
            # will be picked up by the scheduler recovery sweep.
            log.warning(
                "agent_dispatcher.publish_failed",
                run_id=str(run.id),
                error=str(exc),
            )

        log.info(
            "agent_dispatcher.dispatched",
            run_id=str(run.id),
            agent_type=agent_type,
            company_id=str(company_id),
            trigger_type=trigger_type,
        )
        return run


async def _publish_run_message(
    run_id: UUID,
    agent_type: str,
    company_id: UUID,
) -> None:
    """Publish a minimal run message; worker loads full context from DB."""
    settings = get_settings()
    payload = json.dumps({"run_id": str(run_id), "agent_type": agent_type})
    async with ServiceBusClient.from_connection_string(
        settings.azure_service_bus_connection_string
    ) as client:
        sender = client.get_topic_sender(settings.service_bus_topic_ai_jobs)
        async with sender:
            msg = ServiceBusMessage(
                payload,
                application_properties={"company_id": str(company_id)},
            )
            await sender.send_messages(msg)
