"""Onboarding router — invitation flow + per-company checklist.

Public (no auth):
  GET  /api/v1/onboarding/invitations/{token}  — validate token before accept
  POST /api/v1/onboarding/invitations/{token}/accept — consume token, return user

Authenticated (company_admin+):
  POST /api/v1/onboarding/invitations          — create & send invite
  GET  /api/v1/onboarding/invitations          — list pending invites
  DELETE /api/v1/onboarding/invitations/{id}   — revoke

Authenticated (any company member):
  GET   /api/v1/onboarding/status  — current company checklist
  PATCH /api/v1/onboarding/status  — mark step(s) complete
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import any_authenticated, can_manage_company
from app.dependencies import get_current_company_id, get_current_user_id, get_db
from app.middleware.rate_limit import limiter
from app.models.enums import InvitationStatus, UserRoleEnum
from app.models.invitation import InvitationToken
from app.models.onboarding import CompanyOnboarding
from app.services.audit_service import AuditService
from app.services.email import get_email_service

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_INVITE_TTL_HOURS = 48


# ── Schemas ───────────────────────────────────────────────────────────────────


class InviteCreate(BaseModel):
    email: EmailStr
    role: UserRoleEnum = UserRoleEnum.QA


class InviteRead(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class InvitePublic(BaseModel):
    """What the accept-invite page receives (no sensitive fields)."""

    email: str
    role: str
    company_name: str
    expires_at: datetime
    is_valid: bool


class AcceptInviteBody(BaseModel):
    display_name: str


class AcceptInviteResult(BaseModel):
    user_id: uuid.UUID
    email: str
    company_id: uuid.UUID
    role: str


class OnboardingStatus(BaseModel):
    company_id: uuid.UUID
    has_profile: bool
    has_team_member: bool
    has_system: bool
    has_agent_run: bool
    is_complete: bool
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class OnboardingPatch(BaseModel):
    has_profile: bool | None = None
    has_team_member: bool | None = None
    has_system: bool | None = None
    has_agent_run: bool | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_or_create_onboarding(db: AsyncSession, company_id: uuid.UUID) -> CompanyOnboarding:
    result = await db.execute(
        select(CompanyOnboarding).where(CompanyOnboarding.company_id == company_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = CompanyOnboarding(company_id=company_id)
        db.add(row)
        await db.flush()
    return row


def _check_and_complete(ob: CompanyOnboarding) -> None:
    if ob.is_complete and ob.completed_at is None:
        ob.completed_at = datetime.now(UTC).replace(tzinfo=None)


# ── Invitations — public ───────────────────────────────────────────────────────


@router.get(
    "/invitations/{token}",
    response_model=InvitePublic,
    summary="Validate an invitation token (no auth required)",
    include_in_schema=True,
)
async def get_invitation_public(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InvitePublic:
    result = await db.execute(select(InvitationToken).where(InvitationToken.token == token))
    inv = result.scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    now = datetime.utcnow()
    is_valid = inv.status == InvitationStatus.PENDING.value and inv.expires_at > now

    # Load company name
    from app.models.tenant import Company

    company = await db.get(Company, inv.company_id)
    company_name = company.name if company else "Unknown"

    return InvitePublic(
        email=inv.email,
        role=inv.role,
        company_name=company_name,
        expires_at=inv.expires_at,
        is_valid=is_valid,
    )


@router.post(
    "/invitations/{token}/accept",
    response_model=AcceptInviteResult,
    status_code=status.HTTP_200_OK,
    summary="Accept an invitation (no auth required)",
)
async def accept_invitation(
    token: str,
    body: AcceptInviteBody,
    db: AsyncSession = Depends(get_db),
) -> AcceptInviteResult:
    result = await db.execute(select(InvitationToken).where(InvitationToken.token == token))
    inv = result.scalar_one_or_none()

    now = datetime.utcnow()
    if inv is None or inv.status != InvitationStatus.PENDING.value or inv.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invitation is invalid, expired, or already used.",
        )

    # Import here to avoid circular at module level
    from app.models.role import UserRole
    from app.models.user import User

    # Upsert user — they may have an Azure AD account without a KAATS row yet
    user_result = await db.execute(select(User).where(User.email == inv.email))
    user = user_result.scalar_one_or_none()
    if user is None:
        user = User(
            email=inv.email,
            display_name=body.display_name,
            is_active=True,
        )
        db.add(user)
        await db.flush()

    # Assign role within this company (idempotent — skip if already has it)
    role_check = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.company_id == inv.company_id,
            UserRole.role == inv.role,
        )
    )
    if role_check.scalar_one_or_none() is None:
        db.add(
            UserRole(
                user_id=user.id,
                company_id=inv.company_id,
                role=inv.role,
            )
        )

    # Consume the token
    inv.status = InvitationStatus.ACCEPTED.value
    inv.accepted_at = now

    # Advance onboarding checklist
    ob = await _get_or_create_onboarding(db, inv.company_id)
    ob.has_team_member = True
    _check_and_complete(ob)

    await db.commit()
    log.info(
        "invitation.accepted",
        email=inv.email,
        company_id=str(inv.company_id),
        role=inv.role,
    )
    await AuditService(db).log(
        event_type="invitation.accepted",
        actor_user_id=user.id,
        actor_email=user.email,
        company_id=inv.company_id,
        resource_type="invitation",
        resource_id=str(inv.id),
        changes={"after": {"role": inv.role}},
    )
    return AcceptInviteResult(
        user_id=user.id,
        email=user.email,
        company_id=inv.company_id,
        role=inv.role,
    )


# ── Invitations — authenticated ────────────────────────────────────────────────


@router.post(
    "/invitations",
    response_model=InviteRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[can_manage_company],
    summary="Send an email invitation to a new team member",
)
@limiter.limit("20/minute")
async def create_invitation(
    body: InviteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InviteRead:
    company_id = get_current_company_id(request)
    inviter_id = get_current_user_id(request)

    # Prevent duplicate pending invites for the same email+company
    existing = await db.execute(
        select(InvitationToken).where(
            InvitationToken.company_id == company_id,
            InvitationToken.email == body.email,
            InvitationToken.status == InvitationStatus.PENDING.value,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending invitation for this email already exists.",
        )

    expires_at = datetime.utcnow() + timedelta(hours=_INVITE_TTL_HOURS)
    inv = InvitationToken(
        company_id=company_id,
        invited_by_id=inviter_id,
        email=str(body.email),
        role=body.role.value,
        expires_at=expires_at,
    )
    db.add(inv)
    await db.flush()

    # Load company name for the email
    from app.models.tenant import Company

    company = await db.get(Company, company_id)
    company_name = company.name if company else "KAATS"
    inviter_name = current_user.user.display_name or current_user.user.email

    settings_obj = __import__("app.config", fromlist=["get_settings"]).get_settings()
    frontend_base = getattr(settings_obj, "frontend_base_url", "https://app.kaats.kiu.ai")
    accept_url = f"{frontend_base}/accept-invite?token={inv.token}"

    await get_email_service().send_invitation(
        to=str(body.email),
        invited_by=inviter_name,
        company_name=company_name,
        role=body.role.value,
        accept_url=accept_url,
        expires_hours=_INVITE_TTL_HOURS,
    )

    await db.commit()
    await db.refresh(inv)
    log.info(
        "invitation.created",
        email=str(body.email),
        company_id=str(company_id),
        role=body.role.value,
    )
    await AuditService(db).log(
        event_type="invitation.created",
        actor_user_id=current_user.user.id,
        actor_email=current_user.user.email,
        company_id=company_id,
        resource_type="invitation",
        resource_id=str(inv.id),
        changes={"after": {"email": str(body.email), "role": body.role.value}},
        request=request,
    )
    return InviteRead.model_validate(inv)


@router.get(
    "/invitations",
    response_model=list[InviteRead],
    dependencies=[can_manage_company],
    summary="List pending invitations for the current company",
)
async def list_invitations(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> list[InviteRead]:
    company_id = get_current_company_id(request)
    result = await db.execute(
        select(InvitationToken)
        .where(
            InvitationToken.company_id == company_id,
            InvitationToken.status == InvitationStatus.PENDING.value,
        )
        .order_by(InvitationToken.created_at.desc())
    )
    return [InviteRead.model_validate(r) for r in result.scalars().all()]


@router.delete(
    "/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[can_manage_company],
    summary="Revoke a pending invitation",
)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> None:
    company_id = get_current_company_id(request)
    result = await db.execute(
        select(InvitationToken).where(
            InvitationToken.id == invitation_id,
            InvitationToken.company_id == company_id,
        )
    )
    inv = result.scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    if inv.status != InvitationStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending invitations can be revoked.",
        )
    inv.status = InvitationStatus.REVOKED.value
    await db.commit()


# ── Onboarding checklist ──────────────────────────────────────────────────────


@router.get(
    "/status",
    response_model=OnboardingStatus,
    dependencies=[any_authenticated],
    summary="Get this company's onboarding checklist",
)
async def get_onboarding_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> OnboardingStatus:
    company_id = get_current_company_id(request)
    ob = await _get_or_create_onboarding(db, company_id)
    await db.commit()
    return OnboardingStatus(
        company_id=ob.company_id,
        has_profile=ob.has_profile,
        has_team_member=ob.has_team_member,
        has_system=ob.has_system,
        has_agent_run=ob.has_agent_run,
        is_complete=ob.is_complete,
        completed_at=ob.completed_at,
    )


@router.patch(
    "/status",
    response_model=OnboardingStatus,
    dependencies=[any_authenticated],
    summary="Advance one or more onboarding steps",
)
async def patch_onboarding_status(
    body: OnboardingPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> OnboardingStatus:
    company_id = get_current_company_id(request)
    ob = await _get_or_create_onboarding(db, company_id)

    if body.has_profile is not None:
        ob.has_profile = body.has_profile
    if body.has_team_member is not None:
        ob.has_team_member = body.has_team_member
    if body.has_system is not None:
        ob.has_system = body.has_system
    if body.has_agent_run is not None:
        ob.has_agent_run = body.has_agent_run

    _check_and_complete(ob)
    await db.commit()
    log.info(
        "onboarding.updated",
        company_id=str(company_id),
        has_profile=ob.has_profile,
        has_team_member=ob.has_team_member,
        has_system=ob.has_system,
        has_agent_run=ob.has_agent_run,
        is_complete=ob.is_complete,
    )
    return OnboardingStatus(
        company_id=ob.company_id,
        has_profile=ob.has_profile,
        has_team_member=ob.has_team_member,
        has_system=ob.has_system,
        has_agent_run=ob.has_agent_run,
        is_complete=ob.is_complete,
        completed_at=ob.completed_at,
    )
