import logging

from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save

from .audit import log_action
from .models import AuditLog

logger = logging.getLogger(__name__)

# model label -> fields compared for UPDATE logs (None = every concrete field)
AUDITED_MODELS = {
    "donors.DonorProfile": None,
    "donors.DonationRecord": None,
    "inventory.BloodUnit": None,
    "inventory.BloodStock": None,
    "bloodrequests.BloodRequest": None,
    "users.User": ("role", "is_active"),
}
STATUS_ACTIONS = {
    "approved": AuditLog.Action.APPROVE,
    "rejected": AuditLog.Action.REJECT,
    "fulfilled": AuditLog.Action.FULFIL,
}
IGNORED_FIELDS = {"updated_at", "created_at", "password", "last_login"}


def _snapshot(instance, fields):
    if fields is None:
        fields = [f.name for f in instance._meta.concrete_fields if f.name not in IGNORED_FIELDS]
    return {name: getattr(instance, name, None) for name in fields}


def _pre_save(sender, instance, raw=False, **kwargs):
    instance._audit_old = None
    if raw or instance.pk is None:
        return
    try:
        old = sender._default_manager.filter(pk=instance.pk).first()
        if old is not None:
            instance._audit_old = _snapshot(old, AUDITED_MODELS[instance._meta.label])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audit pre_save failed: %s", exc)


def _post_save(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    try:
        label = instance._meta.label
        name = sender.__name__
        if created:
            if label != "users.User":  # users: only role/active changes are audited
                log_action(AuditLog.Action.CREATE, name, instance.pk, f"Created {name} #{instance.pk}")
            return
        old = getattr(instance, "_audit_old", None)
        if old is None:
            return
        new = _snapshot(instance, AUDITED_MODELS[label])
        changed = [f for f in new if new[f] != old.get(f)]
        if not changed:
            return
        action = AuditLog.Action.UPDATE
        if label == "bloodrequests.BloodRequest" and "status" in changed:
            action = STATUS_ACTIONS.get(str(new["status"]), action)
        if label == "users.User":
            detail = ", ".join(f"{f}: {old[f]} -> {new[f]}" for f in changed)
        elif action != AuditLog.Action.UPDATE:
            detail = f"status: {old['status']} -> {new['status']}"
        else:
            detail = "changed " + ", ".join(changed)
        log_action(action, name, instance.pk, f"{name} #{instance.pk} {detail}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audit post_save failed: %s", exc)


def _post_delete(sender, instance, **kwargs):
    try:
        name = sender.__name__
        log_action(AuditLog.Action.DELETE, name, instance.pk, f"Deleted {name} #{instance.pk}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audit post_delete failed: %s", exc)


def _on_login(sender, request, user, **kwargs):
    log_action(
        AuditLog.Action.LOGIN, "User", user.pk, f"User {user.get_username()} logged in",
        user=user, request=request,
    )


def _on_login_failed(sender, credentials, request=None, **kwargs):
    # only the username is read from the credentials; the password is never touched
    username = str((credentials or {}).get("username", ""))[:150]
    log_action(AuditLog.Action.LOGIN_FAILED, "User", "", f"Failed login for username '{username}'", request=request)


def connect_signals():
    for label in AUDITED_MODELS:
        try:
            model = apps.get_model(label)
        except LookupError:
            continue
        uid = f"audit-{label}"
        pre_save.connect(_pre_save, sender=model, dispatch_uid=f"{uid}-pre")
        post_save.connect(_post_save, sender=model, dispatch_uid=f"{uid}-post")
        if label != "users.User":
            post_delete.connect(_post_delete, sender=model, dispatch_uid=f"{uid}-del")
    user_logged_in.connect(_on_login, dispatch_uid="audit-login")
    user_login_failed.connect(_on_login_failed, dispatch_uid="audit-login-failed")
