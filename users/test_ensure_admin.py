from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from users.models import User

ENV = {
    "DJANGO_SUPERUSER_USERNAME": "firstadmin",
    "DJANGO_SUPERUSER_PASSWORD": "Initial-Pass-123",
    "DJANGO_SUPERUSER_EMAIL": "admin@example.com",
}


class EnsureAdminTests(TestCase):
    def run_command(self):
        call_command("ensure_admin", stdout=StringIO())

    def test_creates_admin_once(self):
        with patch.dict("os.environ", ENV):
            self.run_command()
            self.run_command()
        self.assertEqual(User.objects.filter(username="firstadmin").count(), 1)
        user = User.objects.get(username="firstadmin")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.email, "admin@example.com")
        self.assertTrue(user.check_password("Initial-Pass-123"))

    def test_does_not_change_existing_user(self):
        User.objects.create_user(
            username="firstadmin", password="Original-Pass-456", role=User.Role.DONOR
        )
        with patch.dict("os.environ", ENV):
            self.run_command()
        user = User.objects.get(username="firstadmin")
        self.assertTrue(user.check_password("Original-Pass-456"))
        self.assertEqual(user.role, User.Role.DONOR)
        self.assertFalse(user.is_superuser)

    def test_skips_when_env_not_set(self):
        with patch.dict("os.environ", {"DJANGO_SUPERUSER_USERNAME": "", "DJANGO_SUPERUSER_PASSWORD": ""}):
            self.run_command()
        self.assertFalse(User.objects.exists())
