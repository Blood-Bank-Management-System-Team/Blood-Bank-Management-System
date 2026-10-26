import logging

from .middleware import get_client_ip, get_current_request, get_current_user
from .models import AuditLog

logger = logging.getLogger(__name__)


def log_action(action, model_name="", object_id="", description="", user=None, request=None):
    """Write an audit row. Never raises: auditing must not break the main action."""
    try:
        request = request or get_current_request()
        if user is None:
            user = get_current_user()
        AuditLog.objects.create(
            user=user if user is not None and user.is_authenticated else None,
            action=action,
            model_name=model_name,
            object_id=str(object_id) if object_id is not None else "",
            description=(description or "")[:255],
            ip_address=get_client_ip(request),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audit log write failed: %s", exc)
