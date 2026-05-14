"""User service — company-scoped user management, role assignment with hierarchy."""
from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.role import UserRole
from app.models.user import User
from app.models.enums import UserRoleEnum
from app.schemas.user import UserCreate, UserRead, UserRoleAssign, UserRoleRead, UserUpdate

log = structlog.get_logger(__name__)

# Role hierarchy — higher number = higher privilege
_ROLE_RANK: dict[str, int] = {
    UserRoleEnum.GLOBAL_ADMIN.value: 10,
    UserRoleEnum.ENTERPRISE_ADMIN.value: 9,
    UserRoleEnum.COMPANY_ADMIN.value: 8,
    UserRoleEnum.SYSTEM_MANAGER.value: 7,
    UserRoleEnum.VALIDATION_LEAD.value: 6,
    UserRoleEnum.QA.value: 5,
    UserRoleEnum.VALIDATION_TESTER.value: 4,
    UserRoleEnum.BPO.value: 3,
}


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_user(self, user_id: UUID) -> UserRead:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return UserRead.model_validate(user)

    async def get_user_with_roles(self, user_id: UUID) -> UserRead:
        result = await self._db.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return UserRead.model_validate(user)

    # ── List ──────────────────────────────────────────────────────────────────

    async def list_users(self) -> list[UserRead]:
        """Backwards-compat list (no company scoping)."""
        result = await self._db.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        return [UserRead.model_validate(u) for u in result.scalars().all()]

    async def list_users_for_company(self, company_id: UUID) -> list[UserRead]:
        """
        List active users who have at least one role scoped to this company.
        """
        result = await self._db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(
                User.is_active == True,  # noqa: E712
                UserRole.company_id == company_id,
            )
            .distinct()
            .order_by(User.email)
        )
        return [UserRead.model_validate(u) for u in result.scalars().all()]

    async def list_system_team(self, system_id: UUID) -> list[dict]:
        """
        List users with role assignments on a specific system.
        Returns { user, role, business_domain } for each assignment.
        """
        result = await self._db.execute(
            select(UserRole)
            .where(UserRole.system_id == system_id)
            .options(selectinload(UserRole.user))
            .order_by(UserRole.role)
        )
        roles = result.scalars().all()
        return [
            {
                "user": UserRead.model_validate(r.user),
                "role": UserRoleRead.model_validate(r),
                "business_domain": r.business_domain,
            }
            for r in roles
            if r.user and r.user.is_active
        ]

    # ── Create / invite ───────────────────────────────────────────────────────

    async def invite_user(self, body: UserCreate) -> UserRead:
        existing = await self._db.scalar(select(User).where(User.email == body.email))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
        user = User(**body.model_dump())
        self._db.add(user)
        await self._db.flush()
        return UserRead.model_validate(user)

    async def invite_user_with_role(
        self,
        body: UserCreate,
        initial_role: UserRoleAssign,
        invited_by: UUID,
        company_id: UUID,
    ) -> UserRead:
        """Invite a user and optionally assign an initial role."""
        existing = await self._db.scalar(select(User).where(User.email == body.email))
        if existing:
            # Re-invite: just assign the role if not already present
            user = existing
        else:
            user = User(**body.model_dump())
            self._db.add(user)
            await self._db.flush()

        if initial_role:
            role = UserRole(
                user_id=user.id,
                role=initial_role.role.value if hasattr(initial_role.role, "value") else initial_role.role,
                company_id=initial_role.company_id or company_id,
                system_id=initial_role.system_id,
                enterprise_id=initial_role.enterprise_id,
                business_domain=initial_role.business_domain,
                expires_at=initial_role.expires_at,
                granted_by=invited_by,
            )
            self._db.add(role)
            await self._db.flush()

        log.info("user.invited", user_id=str(user.id), email=body.email, invited_by=str(invited_by))
        return UserRead.model_validate(user)

    # ── Update ────────────────────────────────────────────────────────────────

    async def update_user(self, user_id: UUID, body: UserUpdate) -> UserRead:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(user, field, value)
        await self._db.flush()
        return UserRead.model_validate(user)

    # ── Deactivate ────────────────────────────────────────────────────────────

    async def remove_user(self, user_id: UUID) -> None:
        """Backwards-compat soft-deactivate."""
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        user.is_active = False
        await self._db.flush()

    async def deactivate_user(self, user_id: UUID, actor: "CurrentUser") -> None:
        """Deactivate a user. Cannot deactivate yourself."""
        if user_id == actor.user.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot deactivate your own account",
            )
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        user.is_active = False
        await self._db.flush()
        log.info("user.deactivated", user_id=str(user_id), by=str(actor.user.id))

    # ── Roles ─────────────────────────────────────────────────────────────────

    async def get_roles(self, user_id: UUID) -> list[UserRoleRead]:
        result = await self._db.execute(
            select(UserRole).where(UserRole.user_id == user_id).order_by(UserRole.created_at.desc())
        )
        return [UserRoleRead.model_validate(r) for r in result.scalars().all()]

    async def assign_role(
        self,
        user_id: UUID,
        body: UserRoleAssign,
        granted_by: UUID,
        actor_roles: list | None = None,
    ) -> UserRoleRead:
        """
        Assign a role to a user.
        - SM role requires system_id.
        - Cannot assign a role higher than your own.
        """
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        role_str = body.role.value if hasattr(body.role, "value") else str(body.role)

        # SM role requires system_id
        if role_str == UserRoleEnum.SYSTEM_MANAGER.value and not body.system_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="system_id is required when assigning SYSTEM_MANAGER role",
            )

        # Hierarchy check: caller cannot grant a role higher than their own
        if actor_roles:
            actor_max_rank = max((_ROLE_RANK.get(r.role, 0) for r in actor_roles), default=0)
            target_rank = _ROLE_RANK.get(role_str, 0)
            if target_rank > actor_max_rank:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot assign role '{role_str}' — it exceeds your own permission level",
                )

        role = UserRole(
            user_id=user_id,
            role=role_str,
            enterprise_id=body.enterprise_id,
            company_id=body.company_id,
            system_id=body.system_id,
            business_domain=body.business_domain,
            expires_at=body.expires_at,
            granted_by=granted_by,
        )
        self._db.add(role)
        await self._db.flush()
        log.info("user.role_assigned", user_id=str(user_id), role=role_str, granted_by=str(granted_by))
        return UserRoleRead.model_validate(role)

    async def revoke_role(self, user_id: UUID, role_id: UUID) -> None:
        result = await self._db.execute(
            select(UserRole).where(
                UserRole.id == role_id,
                UserRole.user_id == user_id,
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Role assignment not found"
            )
        await self._db.delete(role)
        await self._db.flush()
        log.info("user.role_revoked", user_id=str(user_id), role_id=str(role_id))
