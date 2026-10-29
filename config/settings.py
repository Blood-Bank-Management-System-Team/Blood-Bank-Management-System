"""Django settings for the Blood Bank Management System (BBMS)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me-in-env-0123456789")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

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

if os.environ.get("DB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "bbms"),
            "USER": os.environ.get("DB_USER", "bbms"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ["DB_HOST"],
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

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

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# Configurable operational rules (not hard-coded in feature logic).
BBMS_MIN_DONATION_INTERVAL_DAYS = int(os.environ.get("BBMS_MIN_DONATION_INTERVAL_DAYS", "90"))
BBMS_MIN_DONOR_AGE = int(os.environ.get("BBMS_MIN_DONOR_AGE", "18"))
BBMS_MAX_DONOR_AGE = int(os.environ.get("BBMS_MAX_DONOR_AGE", "65"))
BBMS_MIN_DONOR_WEIGHT_KG = int(os.environ.get("BBMS_MIN_DONOR_WEIGHT_KG", "50"))

# BB-31: API Documentation
SPECTACULAR_SETTINGS = {
    "TITLE": "Blood Bank Management System API",
    "DESCRIPTION": "API documentation for the Blood Bank Management System (BBMS).",
    "VERSION": "1.0.0",
    "REDOC_DIST": "https://cdn.jsdelivr.net/npm/redoc@2.1.5",
}

# BB-30 (notifications) / BB-27 (email OTP): Email configuration
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "noreply@bbms.local",
)

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