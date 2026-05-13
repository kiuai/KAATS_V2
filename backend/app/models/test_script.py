from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.requirement import Requirement
    from app.models.test_cycle import TestExecution


class TestScript(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "test_scripts"

    requirement_id: Mapped[uuid.UUID | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("requirements.id"))
    system_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(50), nullable=False, default="playwright_python")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")

    requirement: Mapped["Requirement | None"] = relationship(
        "Requirement", back_populates="test_scripts"
    )
    cases: Mapped[list["TestCase"]] = relationship("TestCase", back_populates="script")
    executions: Mapped[list["TestExecution"]] = relationship(
        "TestExecution", back_populates="script"
    )


class TestCase(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "test_cases"

    script_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_scripts.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    stop_on_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    script: Mapped["TestScript"] = relationship("TestScript", back_populates="cases")
    steps: Mapped[list["TestStep"]] = relationship(
        "TestStep", back_populates="case", order_by="TestStep.step_number"
    )


class TestStep(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "test_steps"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_cases.id"), nullable=False, index=True
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[str | None] = mapped_column(Text)

    case: Mapped["TestCase"] = relationship("TestCase", back_populates="steps")
