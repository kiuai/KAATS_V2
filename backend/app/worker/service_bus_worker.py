from __future__ import annotations

import asyncio
import json

import structlog
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusReceivedMessage

from app.config import get_settings

log = structlog.get_logger(__name__)


async def publish_agent_job(
    run_id: object,
    agent_type: str,
    system_id: object | None = None,
    script_id: object | None = None,
) -> None:
    """Publish an on-demand agent job message to Service Bus."""
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


async def _process_message(message: ServiceBusReceivedMessage) -> None:
    body = b"".join(message.body)
    payload = json.loads(body)
    agent_type = payload.get("agent_type")
    log.info("worker.message_received", agent_type=agent_type)

    from app.database import get_session_factory
    factory = get_session_factory()
    async with factory() as db:
        if agent_type == "crawl":
            from app.agents.crawl_agent import CrawlAgent
            # Full agent invocation wired in Prompt 3 (agent implementation prompt)
            log.info("worker.crawl_agent.dispatched", payload=payload)
        elif agent_type == "generation":
            from app.agents.generation_agent import GenerationAgent
            log.info("worker.generation_agent.dispatched", payload=payload)
        elif agent_type == "execution":
            from app.agents.execution_agent import ExecutionAgent
            log.info("worker.execution_agent.dispatched", payload=payload)
        else:
            log.warning("worker.unknown_agent_type", agent_type=agent_type)


async def worker_loop() -> None:
    """Subscribe to the ai-jobs topic and process messages."""
    settings = get_settings()
    log.info("worker.loop.started")
    async with ServiceBusClient.from_connection_string(
        settings.azure_service_bus_connection_string
    ) as client:
        receiver = client.get_subscription_receiver(
            topic_name=settings.service_bus_topic_ai_jobs,
            subscription_name=settings.service_bus_subscription_worker,
        )
        async with receiver:
            async for message in receiver:
                try:
                    await _process_message(message)
                    await receiver.complete_message(message)
                except Exception:
                    log.exception("worker.message_processing_failed")
                    await receiver.abandon_message(message)
