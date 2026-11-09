import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.cache import caches
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase, TestCase, override_settings

from users.email_backends import BREVO_SEND_URL, BrevoEmailBackend


def fake_response(status=201):
    response = MagicMock()
    response.status = status
    response.__enter__.return_value = response
    return response


@override_settings(BREVO_API_KEY="test-key", DEFAULT_FROM_EMAIL="BBMS <bank@example.com>")
class BrevoEmailBackendTests(SimpleTestCase):
    def test_sends_message_over_https_api(self):
        message = EmailMessage("Your OTP", "OTP is 123456", to=["donor@example.com"])
        with patch("urllib.request.urlopen", return_value=fake_response()) as urlopen:
            sent = BrevoEmailBackend().send_messages([message])

        self.assertEqual(sent, 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, BREVO_SEND_URL)
        self.assertEqual(request.get_header("Api-key"), "test-key")
        payload = json.loads(request.data)
        self.assertEqual(payload["sender"], {"email": "bank@example.com", "name": "BBMS"})
        self.assertEqual(payload["to"], [{"email": "donor@example.com"}])
        self.assertEqual(payload["subject"], "Your OTP")
        self.assertEqual(payload["textContent"], "OTP is 123456")

    def test_includes_html_alternative(self):
        message = EmailMultiAlternatives("Hi", "plain", to=["a@example.com"])
        message.attach_alternative("<p>html</p>", "text/html")
        payload = BrevoEmailBackend().build_payload(message)
        self.assertEqual(payload["htmlContent"], "<p>html</p>")

    def test_api_error_raises_unless_fail_silently(self):
        error = urllib.error.HTTPError(BREVO_SEND_URL, 401, "Unauthorized", {}, BytesIO(b"bad key"))
        message = EmailMessage("s", "b", to=["a@example.com"])
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(urllib.error.HTTPError):
                BrevoEmailBackend().send_messages([message])
        error = urllib.error.HTTPError(BREVO_SEND_URL, 401, "Unauthorized", {}, BytesIO(b"bad key"))
        with patch("urllib.request.urlopen", side_effect=error):
            self.assertEqual(BrevoEmailBackend(fail_silently=True).send_messages([message]), 0)

    @override_settings(BREVO_API_KEY="")
    def test_missing_api_key_is_reported(self):
        with self.assertRaises(ValueError):
            BrevoEmailBackend().send_messages([EmailMessage("s", "b", to=["a@example.com"])])


class SharedCacheTests(TestCase):
    def test_otp_cache_is_shared_between_processes(self):
        # A per-process memory cache loses OTPs across gunicorn workers and dev-server reloads.
        self.assertEqual(
            settings.CACHES["default"]["BACKEND"],
            "django.core.cache.backends.db.DatabaseCache",
        )
        caches["default"].set("bbms:test", "value", 30)
        self.assertEqual(caches["default"].get("bbms:test"), "value")
