import hashlib
import secrets

from django.db import models
from django.utils import timezone

from drf_spectacular.extensions import OpenApiAuthenticationExtension

from rest_framework.authentication import (
    BaseAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed


class HospitalPartnerAPIKey(models.Model):
    """API credentials for external hospital integrations."""

    name = models.CharField(max_length=150)
    key_prefix = models.CharField(
        max_length=12,
        unique=True,
        db_index=True,
    )
    key_hash = models.CharField(
        max_length=64,
        unique=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Hospital partner API key"
        verbose_name_plural = "Hospital partner API keys"

    @staticmethod
    def hash_key(raw_key):
        """Return the SHA-256 hash of an API key."""
        return hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()

    @classmethod
    def issue_key(cls, name):
        """Create a key and return it once; store only its hash."""
        raw_key = secrets.token_urlsafe(32)
        prefix = raw_key[:12]

        record = cls.objects.create(
            name=name,
            key_prefix=prefix,
            key_hash=cls.hash_key(raw_key),
        )

        return record, raw_key

    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"


class PartnerPrincipal:
    """Minimal authenticated identity for an external hospital partner."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, partner_key):
        self.partner_key = partner_key
        self.pk = None
        self.id = None
        self.username = partner_key.name
        self.role = "HOSPITAL"
        self.is_superuser = False
        self.is_staff = False

    def __str__(self):
        return self.username


class HospitalPartnerAPIKeyAuthentication(BaseAuthentication):
    """Authenticate using Authorization: Api-Key <key>."""

    keyword = b"Api-Key"

    def authenticate(self, request):
        # Preferred header for Swagger and external integrations.
        raw_key = request.headers.get("X-API-Key")

        # Preserve existing Authorization: Api-Key <key> support.
        if not raw_key:
            header = get_authorization_header(request).split()

            if not header or header[0].lower() != self.keyword.lower():
                return None

            if len(header) != 2:
                raise AuthenticationFailed(
                    "Invalid API key authorization header."
                )

            try:
                raw_key = header[1].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise AuthenticationFailed("Invalid API key.") from exc

        prefix = raw_key[:12]
        key_hash = HospitalPartnerAPIKey.hash_key(raw_key)

        try:
            partner_key = HospitalPartnerAPIKey.objects.get(
                key_prefix=prefix,
                key_hash=key_hash,
                is_active=True,
            )
        except HospitalPartnerAPIKey.DoesNotExist as exc:
            raise AuthenticationFailed(
                "Invalid or inactive API key."
            ) from exc

        HospitalPartnerAPIKey.objects.filter(
            pk=partner_key.pk
        ).update(last_used_at=timezone.now())

        return PartnerPrincipal(partner_key), raw_key


class HospitalPartnerAPIKeyScheme(OpenApiAuthenticationExtension):
    target_class = (
        "users.partner_auth.HospitalPartnerAPIKeyAuthentication"
    )
    name = "HospitalPartnerApiKey"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Enter your hospital partner API key.",
        }