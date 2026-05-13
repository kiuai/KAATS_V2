from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Integer, SmallInteger, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.system import System
    from app.models.test_script import TestScript


class Requirement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "requirements"

    system_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="agent")

    system: Mapped["System"] = relationship("System", back_populates="requirements")
    test_scripts: Mapped[list["TestScript"]] = relationship(
        "TestScript", back_populates="requirement"
    )
