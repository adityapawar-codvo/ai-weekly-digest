"""Sends the built email via the Brevo transactional email API."""

import logging

import requests

from core import config

logger = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


class MailerError(Exception):
    pass


def send(email: dict, recipients: list[str], *, bcc: bool = True) -> dict:
    """Sends `email` ({subject, html, text}) to `recipients`.

    If DRY_RUN is truthy, recipients are always overridden to [MAINTAINER_EMAIL],
    regardless of what's passed in. Raises MailerError on a non-2xx response —
    callers are responsible for not letting that crash unrelated pipeline stages.
    """
    if config.DRY_RUN:
        logger.info("DRY_RUN active — overriding recipients to MAINTAINER_EMAIL only")
        recipients = [config.MAINTAINER_EMAIL]
        bcc = False

    if not recipients:
        raise MailerError("No recipients configured for send().")

    payload = {
        "sender": {"name": config.SENDER_NAME, "email": config.SENDER_EMAIL},
        "subject": email["subject"],
        "htmlContent": email["html"],
        "textContent": email["text"],
    }

    if bcc and len(recipients) > 1:
        # BCC everyone so the test group can't see each other's addresses; Brevo
        # still requires a "to" — send that copy to the sender itself.
        payload["to"] = [{"email": config.SENDER_EMAIL}]
        payload["bcc"] = [{"email": addr} for addr in recipients]
    else:
        payload["to"] = [{"email": addr} for addr in recipients]

    headers = {
        "api-key": config.BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    resp = requests.post(BREVO_URL, headers=headers, json=payload, timeout=30)
    if resp.status_code not in (200, 201):
        raise MailerError(f"Brevo send failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    logger.info("Sent email to %d recipient(s), messageId=%s", len(recipients), data.get("messageId"))
    return data
