"""Azure Communication Services — email sending.

Usage::

    from app.services.email import get_email_service, EmailService

    svc = get_email_service()
    await svc.send_invitation(
        to="new.user@example.com",
        invited_by="Admin User",
        company_name="Acme Corp",
        role="qa",
        accept_url="https://app.kaats.kiu.ai/accept-invite?token=...",
        expires_hours=48,
    )

The service degrades gracefully when ACS is not configured (dev/local):
it logs the email body instead of sending.
"""

from __future__ import annotations

from functools import lru_cache

import structlog

log = structlog.get_logger(__name__)

# ACS SDK is an optional dependency in dev environments.
try:
    from azure.communication.email import EmailClient as _AcsEmailClient

    _ACS_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    _ACS_AVAILABLE = False


class EmailService:
    def __init__(self, connection_string: str | None, sender: str | None) -> None:
        self._sender = sender or "noreply@kaats.kiu.ai"
        self._client: _AcsEmailClient | None = None

        if connection_string and _ACS_AVAILABLE:
            try:
                self._client = _AcsEmailClient.from_connection_string(connection_string)
                log.info("email_service.initialized", sender=self._sender)
            except Exception as exc:  # noqa: BLE001
                log.warning("email_service.init_failed", error=str(exc))

    # ── Public API ────────────────────────────────────────────────────────────

    async def send_invitation(
        self,
        *,
        to: str,
        invited_by: str,
        company_name: str,
        role: str,
        accept_url: str,
        expires_hours: int = 48,
    ) -> None:
        subject = f"You've been invited to join {company_name} on KAATS"
        html = _invitation_html(
            invited_by=invited_by,
            company_name=company_name,
            role=role,
            accept_url=accept_url,
            expires_hours=expires_hours,
        )
        plain = _invitation_plain(
            invited_by=invited_by,
            company_name=company_name,
            role=role,
            accept_url=accept_url,
            expires_hours=expires_hours,
        )
        await self._send(to=to, subject=subject, html=html, plain=plain)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _send(self, *, to: str, subject: str, html: str, plain: str) -> None:
        if self._client is None:
            # Dev fallback — log instead of send
            log.info(
                "email_service.dev_send",
                to=to,
                subject=subject,
                body_preview=plain[:200],
            )
            return

        message = {
            "senderAddress": self._sender,
            "recipients": {"to": [{"address": to}]},
            "content": {
                "subject": subject,
                "html": html,
                "plainText": plain,
            },
        }
        try:
            poller = self._client.begin_send(message)
            result = poller.result()
            log.info(
                "email_service.sent",
                to=to,
                subject=subject,
                message_id=result.get("id"),
            )
        except Exception as exc:  # noqa: BLE001
            log.error("email_service.send_failed", to=to, error=str(exc))
            raise


# ── Template helpers ──────────────────────────────────────────────────────────


def _invitation_html(
    *,
    invited_by: str,
    company_name: str,
    role: str,
    accept_url: str,
    expires_hours: int,
) -> str:
    role_display = role.replace("_", " ").title()
    return f"""<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; color: #333; max-width: 600px; margin: auto; padding: 24px;">
  <h1 style="font-size: 24px; margin-bottom: 8px;">You're invited to KAATS</h1>
  <p><strong>{invited_by}</strong> has invited you to join
     <strong>{company_name}</strong> as a <strong>{role_display}</strong>.</p>
  <p>Click the button below to accept your invitation. This link expires in
     <strong>{expires_hours} hours</strong>.</p>
  <p style="margin: 32px 0;">
    <a href="{accept_url}"
       style="background:#4F46E5;color:#fff;padding:12px 24px;border-radius:6px;
              text-decoration:none;font-weight:600;">
      Accept Invitation
    </a>
  </p>
  <p style="font-size: 12px; color: #888;">
    Or paste this link into your browser:<br>
    <a href="{accept_url}" style="color: #4F46E5;">{accept_url}</a>
  </p>
  <hr style="border:none;border-top:1px solid #eee;margin-top:40px;">
  <p style="font-size:12px;color:#aaa;">
    KAATS — KIU AI Agentic Test System.
    If you did not expect this invitation, you can safely ignore this email.
  </p>
</body>
</html>"""


def _invitation_plain(
    *,
    invited_by: str,
    company_name: str,
    role: str,
    accept_url: str,
    expires_hours: int,
) -> str:
    role_display = role.replace("_", " ").title()
    return (
        f"You're invited to KAATS\n\n"
        f"{invited_by} has invited you to join {company_name} as a {role_display}.\n\n"
        f"Accept your invitation (expires in {expires_hours} hours):\n{accept_url}\n\n"
        f"If you did not expect this invitation, you can safely ignore this email."
    )


# ── Singleton ─────────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_email_service() -> EmailService:
    from app.config import get_settings

    settings = get_settings()
    return EmailService(
        connection_string=getattr(settings, "acs_connection_string", None),
        sender=getattr(settings, "acs_sender_address", None),
    )
