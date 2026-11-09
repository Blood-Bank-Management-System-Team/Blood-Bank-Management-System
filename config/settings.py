"""Django settings for the Blood Bank Management System (BBMS)."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .deploy import add_render_hostname, database_config

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


_DEV_SECRET_KEY = "dev-insecure-key-change-me-in-env-0123456789"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _DEV_SECRET_KEY)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# Full origins including the scheme, e.g. https://bbms.example.com
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
# Render sets this to the service's public host name.
add_render_hostname(os.environ, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS)

if not DEBUG and (SECRET_KEY in ("", "change-me", _DEV_SECRET_KEY) or len(SECRET_KEY) < 32):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a real secret (at least 32 characters) "
        "when DJANGO_DEBUG is False."
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "users",
    "donors",
    "inventory",
    "bloodrequests",
    "camps",
    "notifications",
    "reports",
    "drf_spectacular",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "reports.middleware.CurrentUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# DATABASE_URL (e.g. from Neon) wins; otherwise DB_* for Postgres; otherwise SQLite.
DATABASES = {"default": database_config(os.environ, BASE_DIR)}

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# BB-33: Multilingual UI configuration
LANGUAGE_CODE = "en"

LANGUAGES = [
    ("en", "English"),
    ("hi", "Hindi"),
]

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# WhiteNoise serves the collected files in production; in DEBUG it falls back to the finders.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "users.partner_auth.HospitalPartnerAPIKeyAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# HTTPS hardening (DEV-14). Only active when DEBUG is False, so local dev and CI are unchanged.
# Each switch can be overridden from the environment.
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", True)
    if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", True):
        # The TLS-terminating reverse proxy must set X-Forwarded-Proto.
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
    # Health checks (container healthcheck, deploy smoke test) must work without a redirect.
    SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# Configurable operational rules (not hard-coded in feature logic).
BBMS_MIN_DONATION_INTERVAL_DAYS = int(os.environ.get("BBMS_MIN_DONATION_INTERVAL_DAYS", "90"))
BBMS_MIN_DONOR_AGE = int(os.environ.get("BBMS_MIN_DONOR_AGE", "18"))
BBMS_MAX_DONOR_AGE = int(os.environ.get("BBMS_MAX_DONOR_AGE", "65"))
BBMS_MIN_DONOR_WEIGHT_KG = int(os.environ.get("BBMS_MIN_DONOR_WEIGHT_KG", "50"))

# BB-30 (notifications) / BB-27 (email OTP): Email configuration
# Delivery is picked from the environment, in this order:
#   1. EMAIL_BACKEND, if set explicitly.
#   2. BREVO_API_KEY -> Brevo's HTTPS API. Use this on Render's free plan,
#      which blocks outbound SMTP ports 25, 465 and 587.
#   3. EMAIL_HOST -> plain SMTP (e.g. smtp.gmail.com with an app password).
#   4. Otherwise the console backend: emails (and OTPs) print in the server terminal.
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "15"))

if os.environ.get("EMAIL_BACKEND"):
    EMAIL_BACKEND = os.environ["EMAIL_BACKEND"]
elif BREVO_API_KEY:
    EMAIL_BACKEND = "users.email_backends.BrevoEmailBackend"
elif EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "noreply@bbms.local",
)

# One cache shared by every server process. The default per-process memory
# cache lost OTPs whenever the dev server reloaded, and under gunicorn's
# multiple workers an OTP stored by one worker was invisible to the others.
# The table is created by users/migrations/0003_create_cache_table.py.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "bbms_cache",
    }
}

PASSWORD_RESET_TIMEOUT = 600  # 10 minutes

# BB-31: API Documentation
SPECTACULAR_SETTINGS = {
    "TITLE": "Blood Bank Management System API",
    "DESCRIPTION": (
        "API documentation for the Blood Bank Management System (BBMS). "
        "External hospital partners can authenticate using their API key "
        "in the Authorization header: Api-Key <key>."
    ),
    "VERSION": "1.0.0",
    "REDOC_DIST": "https://cdn.jsdelivr.net/npm/redoc@2.1.5",
    "ENUM_NAME_OVERRIDES": {
        "UserRoleEnum": "users.models.User.Role",
        "SelfRegisterRoleEnum": [("DONOR", "Donor")],
    },
    "COMPONENTS": {
        "securitySchemes": {
            "HospitalPartnerApiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Enter: Api-Key <your-partner-api-key>",
            },
        },
    },
}