"""Billing router — Stripe Checkout, Customer Portal, and webhook receiver.

POST /billing/checkout        — create a Stripe Checkout session (redirect URL)
POST /billing/portal          — create a Stripe Customer Portal session
POST /billing/webhook         — Stripe webhook receiver (raw body, no auth)
GET  /billing/status          — current plan + subscription status
"""
from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import any_authenticated, can_manage_company
from app.config import get_settings
from app.dependencies import get_current_company_id, get_db
from app.models.tenant import Company
from app.services.billing_service import BillingService
from app.services.usage_service import UsageService

router = APIRouter(prefix="/billing", tags=["billing"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class CheckoutRequest(BaseModel):
    plan_tier: str  # "pro" | "enterprise"


class CheckoutResponse(BaseModel):
    checkout_url: str | None
    message: str | None = None


class PortalResponse(BaseModel):
    portal_url: str | None
    message: str | None = None


class BillingStatus(BaseModel):
    plan_tier: str
    monthly_token_limit: int | None
    monthly_run_limit: int | None
    stripe_configured: bool


# ── Helpers ───────────────────────────────────────────────────────────────────


def _frontend_url() -> str:
    return get_settings().frontend_base_url


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/status", response_model=BillingStatus, dependencies=[any_authenticated])
async def get_billing_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BillingStatus:
    company_id = get_current_company_id(request)
    plan = await UsageService(db).get_plan(company_id)
    settings = get_settings()
    return BillingStatus(
        plan_tier=plan.plan_tier if plan else "free",
        monthly_token_limit=plan.monthly_token_limit if plan else None,
        monthly_run_limit=plan.monthly_agent_run_limit if plan else None,
        stripe_configured=bool(settings.stripe_secret_key),
    )


@router.post("/checkout", response_model=CheckoutResponse, dependencies=[can_manage_company])
async def create_checkout(
    body: CheckoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CheckoutResponse:
    company_id = get_current_company_id(request)
    company = await db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    url = await BillingService.create_checkout_session(
        company_id=company_id,
        company_name=company.name,
        admin_email=current_user.user.email,
        plan_tier=body.plan_tier,
        success_url=f"{_frontend_url()}/billing?success=1",
        cancel_url=f"{_frontend_url()}/billing?cancelled=1",
    )
    if url is None:
        return CheckoutResponse(
            checkout_url=None,
            message="Billing is not configured. Contact your administrator.",
        )
    return CheckoutResponse(checkout_url=url)


@router.post("/portal", response_model=PortalResponse, dependencies=[can_manage_company])
async def create_portal(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortalResponse:
    company_id = get_current_company_id(request)
    company = await db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    url = await BillingService.create_portal_session(
        company_id=company_id,
        company_name=company.name,
        admin_email=current_user.user.email,
        return_url=f"{_frontend_url()}/billing",
    )
    if url is None:
        return PortalResponse(
            portal_url=None,
            message="Billing is not configured. Contact your administrator.",
        )
    return PortalResponse(portal_url=url)


@router.post(
    "/webhook",
    include_in_schema=False,
    status_code=200,
    response_model=None,
)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Receive and process Stripe webhook events."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    event = BillingService.construct_event(payload, sig)
    if event is None:
        raise HTTPException(status_code=400, detail="Invalid webhook signature or Stripe not configured")

    event_type = event.get("type", "")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        company_id_str = (session.get("metadata") or {}).get("company_id")
        plan_tier = (session.get("metadata") or {}).get("plan_tier", "pro")
        if company_id_str:
            try:
                cid = UUID(company_id_str)
                await UsageService(db).upsert_plan(
                    company_id=cid,
                    plan_tier=plan_tier,
                )
                await db.commit()
            except Exception:  # noqa: BLE001
                pass

    return {"received": True}
