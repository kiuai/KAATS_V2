from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.scheduled_job import ScheduledJob, ScheduledJobRun

log = structlog.get_logger(__name__)


async def dispatch_job(db: AsyncSession, job: ScheduledJob) -> ScheduledJobRun:
    """
    Create a ScheduledJobRun record and publish an AgentJobMessage to Service Bus.
    Called by the scheduler evaluator loop and the manual trigger endpoint.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    run = ScheduledJobRun(
        job_id=job.id,
        status="enqueued",
        scheduled_for=now,
    )
    db.add(run)
    await db.flush()

    await _publish_to_service_bus(job, run)
    log.info("scheduler.job_dispatched", job_id=str(job.id), run_id=str(run.id))
    return run


async def _publish_to_service_bus(job: ScheduledJob, run: ScheduledJobRun) -> None:
    settings = get_settings()
    payload = json.dumps({
        "job_id": str(job.id),
        "job_run_id": str(run.id),
        "company_id": str(job.company_id),
        "system_id": str(job.system_id),
        "agent_type": job.agent_type,
        "scheduled_for": run.scheduled_for.isoformat(),
    })
    async with ServiceBusClient.from_connection_string(
        settings.azure_service_bus_connection_string
    ) as client:
        sender = client.get_topic_sender(settings.service_bus_topic_ai_jobs)
        async with sender:
            msg = ServiceBusMessage(payload, application_properties={"company_id": str(job.company_id)})
            await sender.send_messages(msg)
