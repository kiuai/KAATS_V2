from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.test_cycle import TestExecution


class TestStepResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "test_step_results"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    step_id: Mapped[uuid.UUID] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_outcome: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    execution: Mapped["TestExecution"] = relationship(
        "TestExecution", back_populates="step_results"
    )
    screenshot: Mapped["EvidenceScreenshot | None"] = relationship(
        "EvidenceScreenshot", back_populates="step_result", uselist=False
    )


class EvidenceScreenshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "evidence_screenshots"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    step_result_id: Mapped[uuid.UUID | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True))
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    blob_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    step_result: Mapped["TestStepResult | None"] = relationship(
        "TestStepResult", back_populates="screenshot"
    )
