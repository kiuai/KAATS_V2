from __future__ import annotations

from functools import lru_cache

from openai import AsyncAzureOpenAI

from app.config import get_settings


@lru_cache
def get_openai_client() -> AsyncAzureOpenAI:
    settings = get_settings()
    return AsyncAzureOpenAI(
        azure_endpoint=str(settings.azure_openai_endpoint),
        api_key=settings.azure_openai_api_key,
        api_version="2024-02-01",
    )
