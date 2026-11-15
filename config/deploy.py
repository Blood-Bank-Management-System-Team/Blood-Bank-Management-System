"""Environment-driven deployment helpers used by settings.py (kept separate so they can be unit tested)."""
import re
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

_POSTGRES_SCHEMES = ("postgres", "postgresql")
_URL_IN_TEXT = re.compile(r"postgres(?:ql)?://[^\s'\"]+")


def _extract_url(value):
    """Pull the connection URL out of common copy-paste wrappers.

    Dashboards often copy a snippet rather than the bare URL, e.g.
    psql 'postgresql://...', DATABASE_URL="postgresql://..." or a quoted value.
    """
    match = _URL_IN_TEXT.search(value)
    return match.group(0) if match else value


def _describe(value):
    """Describe a bad value without revealing any secret in it."""
    head = re.sub(r"[A-Za-z0-9]", "x", value[:12])
    return f"got {len(value)} characters starting with {head!r}"


def _parse_database_url(url):
    url = _extract_url(url)
    parts = urlsplit(url)
    if parts.scheme not in _POSTGRES_SCHEMES:
        raise ImproperlyConfigured(
            "DATABASE_URL must be a postgresql:// (or postgres://) connection string; "
            + _describe(url)
            + "."
        )
    if not parts.hostname:
        raise ImproperlyConfigured("DATABASE_URL has no host name.")
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parts.path.lstrip("/")),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname,
        "PORT": str(parts.port or 5432),
    }
    options = dict(parse_qsl(parts.query))
    if options:
        config["OPTIONS"] = options
    # Neon's pooled endpoint ("-pooler" in the host) is PgBouncer in transaction mode,
    # which cannot keep server-side cursors open across statements.
    if "-pooler" in parts.hostname:
        config["DISABLE_SERVER_SIDE_CURSORS"] = True
    return config


def database_config(env, base_dir):
    """Build DATABASES["default"].

    Order: DATABASE_URL, then the DB_* variables (Postgres), then SQLite.
    """
    url = env.get("DATABASE_URL", "").strip()
    if url:
        config = _parse_database_url(url)
    elif env.get("DB_HOST"):
        config = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env.get("DB_NAME", "bbms"),
            "USER": env.get("DB_USER", "bbms"),
            "PASSWORD": env.get("DB_PASSWORD", ""),
            "HOST": env["DB_HOST"],
            "PORT": env.get("DB_PORT", "5432"),
        }
        if env.get("DB_SSLMODE"):
            config["OPTIONS"] = {"sslmode": env["DB_SSLMODE"]}
    else:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": base_dir / "db.sqlite3",
        }

    # Reuse connections, but ping them first: Neon suspends idle computes, which
    # silently drops connections that are still open on our side.
    config["CONN_MAX_AGE"] = int(env.get("CONN_MAX_AGE", "60"))
    config["CONN_HEALTH_CHECKS"] = True
    return config


def add_render_hostname(env, allowed_hosts, csrf_trusted_origins):
    """Allow the host name Render assigns (RENDER_EXTERNAL_HOSTNAME), without duplicates."""
    host = env.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if not host:
        return
    if host not in allowed_hosts:
        allowed_hosts.append(host)
    origin = f"https://{host}"
    if origin not in csrf_trusted_origins:
        csrf_trusted_origins.append(origin)
