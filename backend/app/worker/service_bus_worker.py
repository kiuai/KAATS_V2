from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

import structlog
from azure.servicebus import ServiceBusReceivedMessage
from azure.servicebus.aio import ServiceBusClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.agent_run import AgentRun
from app.models.enums import AgentRunStatus

log = structlog.get_logger(__name__)

# Service Bus delivers up to this many times before dead-lettering automatically.
# We mirror this on our side to skip poisoned messages quickly.
_MAX_DELIVERY_COUNT = 3


# ── Legacy helper (kept for backward compat with AgentRunService) ─────────────


async def publish_agent_job(
    run_id: object,
    agent_type: str,
    system_id: object | None = None,
    script_id: object | None = None,
) -> None:
    """
    Publish an agent job to Service Bus.

    Deprecated: prefer ``AgentDispatcher`` which creates the AgentRun and
    publishes atomically.  This shim is kept so existing ``AgentRunService``
    code continues to work.
    """
    settings = get_settings()
    from azure.servicebus import ServiceBusMessage

    payload = json.dumps({
        "run_id": str(run_id),
        "agent_type": agent_type,
        "system_id": str(system_id) if system_id else None,
        "script_id": str(script_id) if script_id else None,
    })
    async with ServiceBusClient.from_connection_string(
        settings.azure_service_bus_connection_string
    ) as client:
        sender = client.get_topic_sender(settings.service_bus_topic_ai_jobs)
        async with sender:
            await sender.send_messages(ServiceBusMessage(payload))


# ── Worker internals ──────────────────────────────────────────────────────────


async def _load_current_user(
    db: AsyncSession,
    user_id: UUID,
) -> "CurrentUser | None":
    """
    Build a CurrentUser for worker context (no HTTP request available).
    Returns None if the user no longer exists.
    """
    from app.auth.azure_ad import CurrentUser
    from app.models.role import UserRole
    from app.models.user import User

    user = await db.get(User, user_id)
    if user is None:
        log.warning("worker.user_not_found", user_id=str(user_id))
        return None

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            (UserRole.expires_at.is_(None)) | (UserRole.expires_at > now),
        )
    )
    roles = list(result.scalars().all())

    accessible_company_ids: list[UUID] = list({
        r.company_id for r in roles if r.company_id is not None
    })
    accessible_system_ids: list[UUID] = list({
        r.system_id for r in roles if r.system_id is not None
    })

    return CurrentUser(
        user=user,
        roles=roles,
        is_global_admin=user.is_global_admin,
        accessible_company_ids=accessible_company_ids,
        accessible_system_ids=accessible_system_ids,
    )


async def _process_message(message: ServiceBusReceivedMessage) -> None:
    """
    Deserialise one Service Bus message, load the AgentRun, instantiate the
    correct agent, and call execute().
    """
    body = b"".join(message.body)
    payload = json.loads(body)
    run_id_str: str | None = payload.get("run_id")
    agent_type: str = payload.get("agent_type", "")

    if not run_id_str:
        log.error("worker.missing_run_id", payload=payload)
        return

    try:
        run_id = UUID(run_id_str)
    except ValueError:
        log.error("worker.invalid_run_id", run_id=run_id_str)
        return

    log.info("worker.message_received", run_id=run_id_str, agent_type=agent_type)

    from app.database import get_session_factory

    factory = get_session_factory()
    async with factory() as db:
        run = await db.get(AgentRun, run_id)
        if run is None:
            log.error("worker.run_not_found", run_id=run_id_str)
            return

        # Skip runs that are no longer pending (duplicate delivery or cancel).
        if run.status not in (AgentRunStatus.PENDING.value, "pending"):
            log.info(
                "worker.run_skipped",
                run_id=run_id_str,
                status=run.status,
            )
            return

        # Optionally rebuild CurrentUser so the agent can check permissions.
        current_user = None
        if run.triggered_by_user_id:
            current_user = await _load_current_user(db, run.triggered_by_user_id)

        config: dict = run.input_config or {}

        try:
            agent = _build_agent(agent_type, run, db, current_user, config)
        except ValueError as exc:
            log.error("worker.unknown_agent_type", agent_type=agent_type, error=str(exc))
            run.status = AgentRunStatus.FAILED.value
            run.error_message = str(exc)
            run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.flush()
            await db.commit()
            return

        try:
            await agent.execute()
            await db.commit()
            log.info("worker.run_completed", run_id=run_id_str, agent_type=agent_type)
        except Exception as exc:
            log.exception(
                "worker.run_failed", run_id=run_id_str, agent_type=agent_type
            )
            # execute() already sets run.status = FAILED; just commit.
            try:
                await db.commit()
            except Exception:  # noqa: BLE001
                await db.rollback()


def _build_agent(
    agent_type: str,
    run: AgentRun,
    db: AsyncSession,
    current_user: "CurrentUser | None",
    config: dict,
) -> "BaseAgent":
    from app.agents.base import BaseAgent

    if agent_type == "crawl":
        from app.agents.crawl_agent import CrawlAgent
        return CrawlAgent(run=run, db=db, current_user=current_user, config=config)
    elif agent_type == "generation":
        from app.agents.generation_agent import GenerationAgent
        return GenerationAgent(run=run, db=db, current_user=current_user, config=config)
    elif agent_type == "execution":
        from app.agents.execution_agent import ExecutionAgent
        return ExecutionAgent(run=run, db=db, current_user=current_user, config=config)
    else:
        raise ValueError(f"Unknown agent type: {agent_type!r}")


# ── Worker loop ───────────────────────────────────────────────────────────────


async def worker_loop() -> None:
    """
    Subscribe to the ai-jobs topic and process messages in a continuous loop.

    Dead-letter behaviour:
    - Messages with delivery_count >= _MAX_DELIVERY_COUNT are dead-lettered
      immediately rather than allowing infinite retries.
    - All other processing errors abandon the message (Service Bus will retry
      with a back-off up to its own MaxDeliveryCount).
    """
    settings = get_settings()
    log.info("worker.loop.started", topic=settings.service_bus_topic_ai_jobs)

    async with ServiceBusClient.from_connection_string(
        settings.azure_service_bus_connection_string
    ) as client:
        receiver = client.get_subscription_receiver(
            topic_name=settings.service_bus_topic_ai_jobs,
            subscription_name=settings.service_bus_subscription_worker,
        )
        async with receiver:
            async for message in receiver:
                delivery_count: int = message.delivery_count or 0
                if delivery_count >= _MAX_DELIVERY_COUNT:
                    log.warning(
                        "worker.dead_lettering",
                        delivery_count=delivery_count,
                        message_id=str(message.message_id),
                    )
                    await receiver.dead_letter_message(
                        message,
                        reason="MaxDeliveryCountExceeded",
                        error_description=f"Failed after {delivery_count} attempts",
                    )
                    continue

                try:
                    await _process_message(message)
                    await receiver.complete_message(message)
                except Exception:
                    log.exception(
                        "worker.message_processing_failed",
                        message_id=str(message.message_id),
                        delivery_count=delivery_count,
                    )
                    await receiver.abandon_message(message)
