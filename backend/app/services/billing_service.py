"""Stripe billing service.

Wraps the Stripe Python SDK for:
- Creating / fetching Stripe Customer records per company
- Creating Checkout Sessions (subscribe / upgrade)
- Creating Customer Portal sessions (manage subscription / invoices)
- Handling Stripe webhook events (subscription.updated, invoice.payment_succeeded, etc.)

All Stripe calls are conditional on stripe_secret_key being set; if absent, methods
return None so the app stays functional without billing configured.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

log = structlog.get_logger(__name__)

# Lazy import so the app starts without stripe installed if unused.
try:
    import stripe as _stripe_module
except ImportError:  # pragma: no cover
    _stripe_module = None  # type: ignore[assignment]


def _get_stripe():  # type: ignore[return]
    from app.config import get_settings

    settings = get_settings()
    if _stripe_module is None:
        raise RuntimeError("stripe package not installed")
    if not settings.stripe_secret_key:
        return None
    _stripe_module.api_key = settings.stripe_secret_key
    return _stripe_module


class BillingService:
    """Thin façade over the Stripe API. All methods return None when Stripe is unconfigured."""

    # ── Customer ──────────────────────────────────────────────────────────────

    @staticmethod
    async def get_or_create_customer(
        company_id: uuid.UUID,
        company_name: str,
        admin_email: str,
    ) -> str | None:
        """Return existing or newly created Stripe customer ID. None if Stripe is off."""
        stripe = _get_stripe()
        if stripe is None:
            return None
        try:
            existing = stripe.Customer.search(query=f'metadata["company_id"]:"{company_id}"')
            if existing.data:
                return existing.data[0].id
            customer = stripe.Customer.create(
                name=company_name,
                email=admin_email,
                metadata={"company_id": str(company_id)},
            )
            return customer.id
        except Exception as exc:  # noqa: BLE001
            log.exception(
                "billing.customer.create_failed", company_id=str(company_id), error=str(exc)
            )
            return None

    # ── Checkout ──────────────────────────────────────────────────────────────

    @staticmethod
    async def create_checkout_session(
        *,
        company_id: uuid.UUID,
        company_name: str,
        admin_email: str,
        plan_tier: str,
        success_url: str,
        cancel_url: str,
    ) -> str | None:
        """Create a Stripe Checkout session. Returns the session URL or None."""
        stripe = _get_stripe()
        if stripe is None:
            return None
        from app.config import get_settings

        settings = get_settings()

        price_id = (
            settings.stripe_price_enterprise
            if plan_tier == "enterprise"
            else settings.stripe_price_pro
        )
        if not price_id:
            log.warning("billing.checkout.no_price_id", plan_tier=plan_tier)
            return None

        customer_id = await BillingService.get_or_create_customer(
            company_id, company_name, admin_email
        )
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                mode="subscription",
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"company_id": str(company_id), "plan_tier": plan_tier},
            )
            return session.url
        except Exception as exc:  # noqa: BLE001
            log.exception("billing.checkout.failed", company_id=str(company_id), error=str(exc))
            return None

    # ── Customer portal ───────────────────────────────────────────────────────

    @staticmethod
    async def create_portal_session(
        *,
        company_id: uuid.UUID,
        company_name: str,
        admin_email: str,
        return_url: str,
    ) -> str | None:
        stripe = _get_stripe()
        if stripe is None:
            return None
        customer_id = await BillingService.get_or_create_customer(
            company_id, company_name, admin_email
        )
        if customer_id is None:
            return None
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            return session.url
        except Exception as exc:  # noqa: BLE001
            log.exception("billing.portal.failed", company_id=str(company_id), error=str(exc))
            return None

    # ── Webhook handler ───────────────────────────────────────────────────────

    @staticmethod
    def construct_event(payload: bytes, sig_header: str) -> Any | None:
        """Verify Stripe webhook signature and parse event. Returns None on failure."""
        stripe = _get_stripe()
        if stripe is None:
            return None
        from app.config import get_settings

        secret = get_settings().stripe_webhook_secret
        if not secret:
            return None
        try:
            return stripe.Webhook.construct_event(payload, sig_header, secret)
        except Exception as exc:  # noqa: BLE001
            log.warning("billing.webhook.invalid_signature", error=str(exc))
            return None
