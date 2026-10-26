from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import AuditLog


def filter_logs(params):
    """Apply ?user, ?action, ?model, ?date_from, ?date_to. Raises ValidationError on bad input."""
    qs = AuditLog.objects.select_related("user")
    user = (params.get("user") or "").strip()
    if user:
        cond = Q(user__username__iexact=user)
        if user.isdigit():
            cond |= Q(user_id=int(user))
        qs = qs.filter(cond)
    action = (params.get("action") or "").strip().upper()
    if action:
        if action not in AuditLog.Action.values:
            raise ValidationError({"action": "Unknown action."})
        qs = qs.filter(action=action)
    model = (params.get("model") or "").strip()
    if model:
        qs = qs.filter(model_name__iexact=model)
    for key, lookup in (("date_from", "timestamp__date__gte"), ("date_to", "timestamp__date__lte")):
        value = (params.get(key) or "").strip()
        if value:
            try:
                qs = qs.filter(**{lookup: date.fromisoformat(value)})
            except ValueError:
                raise ValidationError({key: "Use YYYY-MM-DD."})
    return qs.order_by("-timestamp", "-id")
