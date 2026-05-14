"""System service — CRUD, stats, manager assignment, soft-delete guard."""
from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import System
from app.models.enums import AgentType, RequirementStatus, TestScriptStatus, UserRoleEnum
from app.schemas.system import (
    AssignManagerBody,
    SystemCreate,
    SystemDetailRead,
    SystemRead,
    SystemStats,
    SystemUpdate,
)

log = structlog.get_logger(__name__)

# Admin roles that can see ALL company systems (not just own)
_ADMIN_ROLES: frozenset[str] = frozenset({
    UserRoleEnum.GLOBAL_ADMIN.value,
    UserRoleEnum.ENTERPRISE_ADMIN.value,
    UserRoleEnum.COMPANY_ADMIN.value,
    UserRoleEnum.VALIDATION_LEAD.value,
})


class SystemService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── List ──────────────────────────────────────────────────────────────────

    async def list_systems(self, company_id: UUID) -> list[SystemRead]:
        """Backwards-compatible list (no user filtering)."""
        result = await self._db.execute(
            select(System).where(
                System.company_id == company_id,
                System.is_deleted == False,  # noqa: E712
            )
        )
        return [SystemRead.model_validate(s) for s in result.scalars().all()]

    async def list_systems_filtered(
        self,
        company_id: UUID,
        current_user,
        system_type: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> list[SystemRead]:
        """
        Filtered list with role-based scoping:
        - SYSTEM_MANAGER with no admin roles: only their own systems.
        - COMPANY_ADMIN and above: all company systems.
        """
        q = select(System).where(
            System.company_id == company_id,
            System.is_deleted == False,  # noqa: E712
        )

        # SM-only users see only their managed systems
        if _is_sm_only(current_user):
            q = q.where(System.system_manager_id == current_user.user.id)

        if system_type:
            q = q.where(System.system_type == system_type)
        if is_active is not None:
            q = q.where(System.is_active == is_active)
        if search:
            q = q.where(System.name.ilike(f"%{search}%"))

        q = q.order_by(System.created_at.desc())
        result = await self._db.execute(q)
        return [SystemRead.model_validate(s) for s in result.scalars().all()]

    # ── Create ────────────────────────────────────────────────────────────────

    async def create_system(
        self,
        body: SystemCreate,
        company_id: UUID,
        created_by: UUID,
    ) -> SystemRead:
        data = body.model_dump()
        data["company_id"] = company_id
        if not data.get("system_manager_id"):
            data["system_manager_id"] = created_by
        if "system_type" in data and hasattr(data["system_type"], "value"):
            data["system_type"] = data["system_type"].value
        system = System(**data)
        self._db.add(system)
        await self._db.flush()
        return SystemRead.model_validate(system)

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_system(self, system_id: UUID) -> SystemRead:
        system = await self._load(system_id)
        return SystemRead.model_validate(system)

    async def get_system_detail(self, system_id: UUID) -> SystemDetailRead:
        """Return system detail with computed stats."""
        system = await self._load(system_id)
        stats = await self._compute_stats(system_id)
        base = SystemDetailRead.model_validate(system)
        base.stats = stats
        return base

    # ── Update ────────────────────────────────────────────────────────────────

    async def update_system(self, system_id: UUID, body: SystemUpdate) -> SystemRead:
        system = await self._load(system_id)
        data = body.model_dump(exclude_none=True)
        if "system_type" in data and hasattr(data["system_type"], "value"):
            data["system_type"] = data["system_type"].value
        for field, value in data.items():
            setattr(system, field, value)
        await self._db.flush()
        return SystemRead.model_validate(system)

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete_system(self, system_id: UUID) -> None:
        """Soft-delete. Raises 409 if active test cycles exist."""
        from app.models.test_cycle import TestCycle
        from app.models.enums import TestCycleStatus

        system = await self._load(system_id)

        # Guard: no active test cycles
        active_cycle_count = await self._db.scalar(
            select(func.count()).where(
                TestCycle.system_id == system_id,
                TestCycle.status.in_([
                    TestCycleStatus.PLANNED.value,
                    TestCycleStatus.IN_PROGRESS.value,
                ]),
            )
        )
        if (active_cycle_count or 0) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot delete system with {active_cycle_count} active "
                    "test cycle(s). Close or abort them first."
                ),
            )

        system.is_deleted = True
        system.is_active = False
        await self._db.flush()
        log.info("system.soft_deleted", system_id=str(system_id))

    # ── Assign manager ────────────────────────────────────────────────────────

    async def assign_manager(
        self,
        system_id: UUID,
        body: AssignManagerBody,
        company_id: UUID,
    ) -> SystemRead:
        """
        Change the system_manager_id.
        Revokes any existing SM role for the old manager on this system
        and grants the SM role to the new manager.
        """
        from app.models.role import UserRole
        from app.models.user import User

        system = await self._load(system_id)

        new_manager = await self._db.get(User, body.user_id)
        if not new_manager or not new_manager.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or inactive",
            )

        old_manager_id = system.system_manager_id

        # Revoke SM role scoped to this system for the old manager
        if old_manager_id and old_manager_id != body.user_id:
            old_roles = await self._db.execute(
                select(UserRole).where(
                    UserRole.user_id == old_manager_id,
                    UserRole.system_id == system_id,
                    UserRole.role == UserRoleEnum.SYSTEM_MANAGER.value,
                )
            )
            for r in old_roles.scalars().all():
                await self._db.delete(r)

        # Grant SM role scoped to this system for the new manager
        existing = await self._db.scalar(
            select(UserRole).where(
                UserRole.user_id == body.user_id,
                UserRole.system_id == system_id,
                UserRole.role == UserRoleEnum.SYSTEM_MANAGER.value,
            )
        )
        if existing is None:
            new_role = UserRole(
                user_id=body.user_id,
                company_id=company_id,
                system_id=system_id,
                role=UserRoleEnum.SYSTEM_MANAGER.value,
            )
            self._db.add(new_role)

        system.system_manager_id = body.user_id
        await self._db.flush()
        log.info(
            "system.manager_assigned",
            system_id=str(system_id),
            new_manager_id=str(body.user_id),
        )
        return SystemRead.model_validate(system)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _load(self, system_id: UUID) -> System:
        system = await self._db.get(System, system_id)
        if not system or system.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="System not found",
            )
        return system

    async def _compute_stats(self, system_id: UUID) -> SystemStats:
        from app.models.requirement import Requirement
        from app.models.test_script import TestScript
        from app.models.agent_run import AgentRun

        req_total = await self._db.scalar(
            select(func.count()).where(
                Requirement.system_id == system_id,
                Requirement.deleted_at.is_(None),
            )
        ) or 0

        req_active = await self._db.scalar(
            select(func.count()).where(
                Requirement.system_id == system_id,
                Requirement.status == RequirementStatus.ACTIVE.value,
                Requirement.deleted_at.is_(None),
            )
        ) or 0

        script_total = await self._db.scalar(
            select(func.count()).where(
                TestScript.system_id == system_id,
                TestScript.deleted_at.is_(None),
            )
        ) or 0

        script_approved = await self._db.scalar(
            select(func.count()).where(
                TestScript.system_id == system_id,
                TestScript.status == TestScriptStatus.APPROVED.value,
                TestScript.deleted_at.is_(None),
            )
        ) or 0

        coverage = round(script_approved / req_active * 100, 1) if req_active > 0 else 0.0

        last_crawl = await self._db.scalar(
            select(func.max(AgentRun.created_at)).where(
                AgentRun.system_id == system_id,
                AgentRun.agent_type == AgentType.CRAWL.value,
            )
        )

        last_exec = await self._db.scalar(
            select(func.max(AgentRun.created_at)).where(
                AgentRun.system_id == system_id,
                AgentRun.agent_type == AgentType.EXECUTION.value,
            )
        )

        return SystemStats(
            requirement_count=req_total,
            active_requirement_count=req_active,
            script_count=script_total,
            approved_script_count=script_approved,
            coverage_pct=coverage,
            last_crawl_at=last_crawl,
            last_execution_at=last_exec,
        )


def _is_sm_only(current_user) -> bool:
    """True if user has SYSTEM_MANAGER role but NO admin-level role."""
    role_values = {r.role for r in current_user.roles}
    return (
        UserRoleEnum.SYSTEM_MANAGER.value in role_values
        and not role_values.intersection(_ADMIN_ROLES)
    )
