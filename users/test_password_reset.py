
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from users.password_reset import (
    RESET_GRANT_TIMEOUT_SECONDS,
    OTP_MAX_ATTEMPTS,
    OTP_TIMEOUT_SECONDS,
    _email_key,
    _grant_key,
    _otp_hash,
    consume_password_reset_grant,
    get_password_reset_grant_user,
    request_password_reset,
    verify_password_reset_otp,
)

User = get_user_model()
STRONG_PASSWORD = "Str0ng-Pass#2024"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PasswordResetServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="resetuser",
            email="reset@example.com",
            password=STRONG_PASSWORD,
        )

    def tearDown(self):
        cache.clear()

    def request_otp(self):
        self.assertTrue(request_password_reset(self.user.email))
        record = cache.get(_email_key(self.user.email))
        return record

    def test_registered_email_sends_otp(self):
        self.request_otp()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn("OTP", mail.outbox[0].subject)

    def test_unknown_email_does_not_send_email(self):
        result = request_password_reset("unknown@example.com")

        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)

    def test_correct_otp_returns_grant_and_consumes_otp(self):
        record = self.request_otp()

        # The OTP is stored as a hash, not as plaintext.
        self.assertNotIn("otp", record)

        # Generate a known OTP and store its hash for this test.
        otp = "123456"
        cache.set(
            _email_key(self.user.email),
            {
                "user_id": self.user.pk,
                "otp_hash": _otp_hash(otp),
                "attempts": 0,
            },
            timeout=OTP_TIMEOUT_SECONDS,
        )

        grant = verify_password_reset_otp(self.user.email, otp)

        self.assertIsNotNone(grant)
        self.assertIsNone(cache.get(_email_key(self.user.email)))
        self.assertEqual(
            get_password_reset_grant_user(grant),
            self.user,
        )

    def test_wrong_otp_is_rejected(self):
        self.request_otp()

        grant = verify_password_reset_otp(
            self.user.email,
            "000000",
        )

        self.assertIsNone(grant)

    def test_otp_is_rejected_after_maximum_failed_attempts(self):
        self.request_otp()

        for _ in range(OTP_MAX_ATTEMPTS):
            self.assertIsNone(
                verify_password_reset_otp(
                    self.user.email,
                    "000000",
                )
            )

        self.assertIsNone(cache.get(_email_key(self.user.email)))

    def test_otp_cannot_be_reused(self):
        otp = "123456"

        cache.set(
            _email_key(self.user.email),
            {
                "user_id": self.user.pk,
                "otp_hash": _otp_hash(otp),
                "attempts": 0,
            },
            timeout=OTP_TIMEOUT_SECONDS,
        )

        grant = verify_password_reset_otp(self.user.email, otp)

        self.assertIsNotNone(grant)
        self.assertIsNone(
            verify_password_reset_otp(self.user.email, otp)
        )

    def test_reset_grant_cannot_be_consumed_twice(self):
        grant = "test-reset-grant"

        cache.set(
            _grant_key(grant),
            {"user_id": self.user.pk},
            timeout=RESET_GRANT_TIMEOUT_SECONDS,
        )

        first_user = consume_password_reset_grant(grant)
        second_user = consume_password_reset_grant(grant)

        self.assertEqual(first_user, self.user)
        self.assertIsNone(second_user)

    def test_missing_grant_is_rejected(self):
        self.assertIsNone(get_password_reset_grant_user(""))
        self.assertIsNone(
            get_password_reset_grant_user("nonexistent-token")
        )


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PasswordResetViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="webreset",
            email="webreset@example.com",
            password=STRONG_PASSWORD,
        )

    def tearDown(self):
        cache.clear()

    def test_request_page_loads(self):
        response = self.client.get(
            reverse("password-reset-request")
        )
        self.assertEqual(response.status_code, 200)

    def test_verify_page_redirects_without_requested_email(self):
        response = self.client.get(
            reverse("password-reset-verify")
        )

        self.assertRedirects(
            response,
            reverse("password-reset-request"),
        )

    def test_new_password_page_redirects_without_grant(self):
        response = self.client.get(
            reverse("password-reset-new-password")
        )

        self.assertRedirects(
            response,
            reverse("password-reset-request"),
        )

    def test_password_reset_flow(self):
        # Request an OTP.
        response = self.client.post(
            reverse("password-reset-request"),
            {"email": self.user.email},
        )
        self.assertRedirects(
            response,
            reverse("password-reset-verify"),
        )
        self.assertEqual(len(mail.outbox), 1)

        # Retrieve the OTP from the test email.
        message = mail.outbox[0].body
        import re

        match = re.search(r"\b(\d{6})\b", message)
        self.assertIsNotNone(match)
        otp = match.group(1)

        # Verify the OTP.
        response = self.client.post(
            reverse("password-reset-verify"),
            {
                "email": self.user.email,
                "otp": otp,
            },
        )
        self.assertRedirects(
            response,
            reverse("password-reset-new-password"),
        )

        # Set a new password.
        new_password = "N3w-Strong-Password#2026"
        response = self.client.post(
            reverse("password-reset-new-password"),
            {
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )

        self.assertRedirects(response, reverse("login"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.check_password(STRONG_PASSWORD))

        # Confirm the new password works for login.
        login_response = self.client.post(
            reverse("login"),
            {
                "username": self.user.username,
                "password": new_password,
            },
        )
        self.assertEqual(login_response.status_code, 302)
