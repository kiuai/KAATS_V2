from __future__ import annotations

import base64
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    pagination: PaginationMeta


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Offset + cursor pagination
# ---------------------------------------------------------------------------


class Page(BaseModel, Generic[T]):
    """Unified paginated response with both offset metadata and optional cursor."""

    items: list[T]
    total: int
    limit: int
    offset: int
    next_cursor: str | None = None


def encode_cursor(dt: datetime) -> str:
    """Encode a datetime as an opaque base64 cursor string."""
    return base64.b64encode(dt.isoformat().encode()).decode()


def decode_cursor(cursor: str) -> datetime:
    """Decode a cursor string back to a datetime. Raises ValueError on bad input."""
    try:
        return datetime.fromisoformat(base64.b64decode(cursor.encode()).decode())
    except Exception as exc:
        raise ValueError(f"Invalid cursor: {cursor!r}") from exc
