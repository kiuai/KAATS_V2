from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any, TypeVar
from uuid import UUID, uuid4

import structlog
import tiktoken
from openai import AsyncAzureOpenAI, RateLimitError
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# GPT-4o pricing (USD per token)
_PROMPT_TOKEN_COST = Decimal("0.000005")  # $5.00 / 1M
_COMPLETION_TOKEN_COST = Decimal("0.000015")  # $15.00 / 1M

# GPT-4o context window
_CONTEXT_WINDOW_TOKENS = 128_000

_AI_LOG_CONTAINER = "ai_generation_log"


@dataclass
class CallUsage:
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    cost_usd: Decimal


class AzureOpenAIClient:
    """
    Thin wrapper around AsyncAzureOpenAI that adds:
    - Tenacity retry on RateLimitError (3 attempts, exponential back-off)
    - tiktoken token counting before every call (raises if over context window)
    - Per-call logging to Cosmos DB ``ai_generation_log`` container
    """

    def __init__(
        self,
        agent_run_id: UUID | None = None,
        company_id: UUID | None = None,
    ) -> None:
        settings = get_settings()
        self._client = AsyncAzureOpenAI(
            azure_endpoint=str(settings.azure_openai_endpoint),
            api_key=settings.azure_openai_api_key,
            api_version="2024-10-01-preview",
        )
        self._deployment = settings.azure_openai_deployment_name
        self._agent_run_id = agent_run_id
        self._company_id = company_id

        try:
            self._encoding = tiktoken.encoding_for_model("gpt-4o")
        except KeyError:
            self._encoding = tiktoken.get_encoding("cl100k_base")

    # ── Public API ────────────────────────────────────────────────────────────

    async def complete(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        """Call the LLM and return the text completion."""
        self._check_token_budget(messages, max_tokens)

        t0 = time.monotonic()
        success = False
        prompt_tokens = 0
        completion_tokens = 0

        try:
            response = await self._call_with_retry(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=response_format,
            )
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            success = True
            return response.choices[0].message.content or ""
        finally:
            latency_ms = int((time.monotonic() - t0) * 1000)
            asyncio.ensure_future(
                self._log_call(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency_ms,
                    success=success,
                )
            )

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        output_schema: type[T],
        max_tokens: int = 4096,
    ) -> T:
        """
        Call the LLM using OpenAI structured output mode.
        Returns a validated Pydantic model instance.
        """
        self._check_token_budget(messages, max_tokens)

        t0 = time.monotonic()
        success = False
        prompt_tokens = 0
        completion_tokens = 0

        try:
            response = await self._client.beta.chat.completions.parse(
                model=self._deployment,
                messages=messages,  # type: ignore[arg-type]
                response_format=output_schema,
                max_tokens=max_tokens,
            )
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            success = True
            parsed = response.choices[0].message.parsed
            if parsed is None:
                raise ValueError("Structured output returned None")
            return parsed
        finally:
            latency_ms = int((time.monotonic() - t0) * 1000)
            asyncio.ensure_future(
                self._log_call(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency_ms,
                    success=success,
                )
            )

    # ── Internal ──────────────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True,
    )
    async def _call_with_retry(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        response_format: dict[str, str] | None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self._deployment,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format
        return await self._client.chat.completions.create(**kwargs)

    def _check_token_budget(self, messages: list[dict[str, str]], max_tokens: int) -> None:
        """Raise ValueError if the message context would exceed the context window."""
        total = sum(len(self._encoding.encode(m.get("content", "") or "")) for m in messages)
        if total + max_tokens > _CONTEXT_WINDOW_TOKENS:
            raise ValueError(
                f"Token budget exceeded: {total} prompt tokens + {max_tokens} "
                f"max completion tokens > {_CONTEXT_WINDOW_TOKENS} context window"
            )

    async def _log_call(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        success: bool,
    ) -> None:
        cost = (
            Decimal(str(prompt_tokens)) * _PROMPT_TOKEN_COST
            + Decimal(str(completion_tokens)) * _COMPLETION_TOKEN_COST
        )
        doc: dict[str, Any] = {
            "id": str(uuid4()),
            "type": "ai_call",
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_run_id": str(self._agent_run_id) if self._agent_run_id else None,
            "company_id": str(self._company_id) if self._company_id else None,
            "model": self._deployment,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": str(cost),
            "latency_ms": latency_ms,
            "success": success,
            "_partitionKey": str(self._company_id) if self._company_id else "global",
        }
        try:
            from app.cosmos import get_cosmos_database

            db = get_cosmos_database()
            container = db.get_container_client(_AI_LOG_CONTAINER)
            await container.upsert_item(doc)
        except Exception as exc:  # noqa: BLE001
            log.warning("ai_client.log_failed", error=str(exc))


@lru_cache
def get_openai_client() -> AsyncAzureOpenAI:
    """Backward-compatible singleton for code that uses the raw AsyncAzureOpenAI."""
    settings = get_settings()
    return AsyncAzureOpenAI(
        azure_endpoint=str(settings.azure_openai_endpoint),
        api_key=settings.azure_openai_api_key,
        api_version="2024-10-01-preview",
    )
