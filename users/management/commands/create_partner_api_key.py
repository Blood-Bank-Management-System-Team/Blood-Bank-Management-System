from django.core.management.base import BaseCommand, CommandError

from users.partner_auth import HospitalPartnerAPIKey


class Command(BaseCommand):
    help = "Create an API key for an external hospital partner."

    def add_arguments(self, parser):
        parser.add_argument(
            "name",
            type=str,
            help="Name identifying the external hospital partner.",
        )

    def handle(self, *args, **options):
        name = options["name"].strip()

        if not name:
            raise CommandError("Partner name cannot be empty.")

        _, raw_key = HospitalPartnerAPIKey.issue_key(name)

        self.stdout.write(
            self.style.SUCCESS(
                f"API key created for {name}:\n{raw_key}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Save this key securely. It will not be displayed again."
            )
        )
