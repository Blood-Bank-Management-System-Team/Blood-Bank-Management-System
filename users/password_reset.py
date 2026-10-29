
import hashlib
import hmac
import secrets

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail


OTP_LENGTH = 6
OTP_TIMEOUT_SECONDS = 600
OTP_MAX_ATTEMPTS = 5
RESET_GRANT_TIMEOUT_SECONDS = 300


def _email_key(email):
    normalized_email = email.strip().lower()
    digest = hashlib.sha256(normalized_email.encode()).hexdigest()
    return f"bbms:password-reset:{digest}"


def _otp_hash(otp):
    return hmac.new(
        settings.SECRET_KEY.encode(),
        otp.encode(),
        hashlib.sha256,
    ).hexdigest()


def _grant_key(token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    return f"bbms:password-reset-grant:{digest}"


def request_password_reset(email):
    """Send an OTP for an unambiguous, registered email address."""
    from .models import User

    matches = User.objects.filter(email__iexact=email.strip())

    if matches.count() != 1:
        return False

    user = matches.first()
    otp = f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"

    cache.set(
        _email_key(email),
        {
            "user_id": user.pk,
            "otp_hash": _otp_hash(otp),
            "attempts": 0,
        },
        timeout=OTP_TIMEOUT_SECONDS,
    )

    send_mail(
        subject="BBMS Password Reset OTP",
        message=(
            f"Your Blood Bank Management System password reset OTP is {otp}.\n"
            "It expires in 10 minutes. If you did not request this, ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return True


def verify_password_reset_otp(email, otp):
    """Verify an OTP once and return a short-lived reset grant."""
    from .models import User

    key = _email_key(email)
    record = cache.get(key)

    if not record:
        return None

    if record["attempts"] >= OTP_MAX_ATTEMPTS:
        cache.delete(key)
        return None

    if not isinstance(otp, str) or len(otp) != OTP_LENGTH or not otp.isdigit():
        record["attempts"] += 1
    else:
        if hmac.compare_digest(_otp_hash(otp), record["otp_hash"]):
        # Continue with the existing successful-verification logic.
            pass
        else:
            record["attempts"] += 1

    if record["attempts"] >= OTP_MAX_ATTEMPTS:
        cache.delete(key)
        return None

    if not isinstance(otp, str) or len(otp) != OTP_LENGTH or not otp.isdigit():
        cache.set(key, record, timeout=OTP_TIMEOUT_SECONDS)
        return None

    if not hmac.compare_digest(_otp_hash(otp), record["otp_hash"]):
        cache.set(key, record, timeout=OTP_TIMEOUT_SECONDS)
        return None

    user = User.objects.filter(
        pk=record["user_id"],
        email__iexact=email.strip(),
    ).first()

    if not user:
        cache.delete(key)
        return None

    # Consume the OTP immediately so it cannot be verified again.
    cache.delete(key)

    grant = secrets.token_urlsafe(32)
    cache.set(
        _grant_key(grant),
        {"user_id": user.pk},
        timeout=RESET_GRANT_TIMEOUT_SECONDS,
    )
    return grant


def consume_password_reset_grant(token):
    """Consume a reset grant and return its user, or None if invalid."""
    from .models import User

    if not token:
        return None

    key = _grant_key(token)
    record = cache.get(key)

    if not record:
        return None

    # Delete before returning so the grant cannot be reused sequentially.
    cache.delete(key)
    return User.objects.filter(pk=record["user_id"]).first()


def clear_password_reset(email):
    cache.delete(_email_key(email))


def get_password_reset_grant_user(token):
    """Return the user for a valid reset grant without consuming it."""
    from .models import User

    if not token:
        return None

    record = cache.get(_grant_key(token))

    if not record:
        return None

    return User.objects.filter(pk=record["user_id"]).first()