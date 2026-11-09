"""Email backend that sends through Brevo's HTTPS API.

Hosts such as Render's free plan block outbound SMTP ports, so plain SMTP
cannot deliver OTP and notification emails there. This backend uses HTTPS
(port 443) instead and needs no extra Python packages.
Set BREVO_API_KEY, and set DEFAULT_FROM_EMAIL to a sender verified in Brevo.
"""
import json
import logging
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


def _address(value):
    name, email = parseaddr(value)
    data = {"email": email}
    if name:
        data["name"] = name
    return data


class BrevoEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, api_key=None, timeout=None, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = api_key or getattr(settings, "BREVO_API_KEY", "")
        self.timeout = timeout or getattr(settings, "EMAIL_TIMEOUT", None) or 15

    def build_payload(self, message):
        payload = {
            "sender": _address(message.from_email or settings.DEFAULT_FROM_EMAIL),
            "to": [_address(a) for a in message.to],
            "subject": message.subject,
            "textContent": message.body or " ",
        }
        if message.cc:
            payload["cc"] = [_address(a) for a in message.cc]
        if message.bcc:
            payload["bcc"] = [_address(a) for a in message.bcc]
        if message.reply_to:
            payload["replyTo"] = _address(message.reply_to[0])
        for content, mimetype in getattr(message, "alternatives", []) or []:
            if mimetype == "text/html":
                payload["htmlContent"] = content
        return payload

    def _send(self, message):
        if not message.recipients():
            return False
        request = urllib.request.Request(
            BREVO_SEND_URL,
            data=json.dumps(self.build_payload(message)).encode(),
            headers={
                "api-key": self.api_key,
                "accept": "application/json",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return 200 <= response.status < 300

    def send_messages(self, email_messages):
        if not self.api_key:
            if self.fail_silently:
                return 0
            raise ValueError("BREVO_API_KEY is not set.")
        sent = 0
        for message in email_messages:
            try:
                if self._send(message):
                    sent += 1
            except (urllib.error.URLError, OSError) as exc:
                detail = ""
                if isinstance(exc, urllib.error.HTTPError):
                    detail = exc.read().decode(errors="replace")[:500]
                logger.error("Brevo email send failed: %s %s", exc, detail)
                if not self.fail_silently:
                    raise
        return sent
