import os

from django.core.management.base import BaseCommand

from users.models import User


class Command(BaseCommand):
    help = (
        "Create the first admin from DJANGO_SUPERUSER_USERNAME / _PASSWORD / _EMAIL. "
        "Does nothing if those are unset or the user already exists (the password of an "
        "existing user is never changed)."
    )

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()

        if not username or not password:
            self.stdout.write("ensure_admin: DJANGO_SUPERUSER_USERNAME/PASSWORD not set, skipping.")
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(f"ensure_admin: user '{username}' already exists, leaving it unchanged.")
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            role=User.Role.ADMIN,
        )
        self.stdout.write(self.style.SUCCESS(f"ensure_admin: created admin '{username}'."))
