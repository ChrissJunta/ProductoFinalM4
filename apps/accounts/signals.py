"""Auditoría de accesos (ADR-074): ingresos, fallos, salidas y cambios de contraseña
quedan en `AuditLog` con la IP de origen. Nunca se registra la contraseña."""

from django.contrib.auth import signals as auth_signals
from django.dispatch import receiver

from . import ratelimit

ENTITY_TYPE = "accounts.user"


class Action:
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGIN_LOCKED = "LOGIN_LOCKED"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    PASSWORD_RESET = "PASSWORD_RESET"


SELF = object()


def record_access(action, *, user=None, actor=SELF, request=None, username="", **metadata):
    """Registro de acceso. `user` es la cuenta afectada (puede no existir en un fallo);
    el actor es la propia cuenta salvo que se indique otro (`None` = sistema)."""
    from apps.helpdesk.models import AuditLog

    if request is not None:
        metadata["ip"] = ratelimit.client_ip(request)
        metadata["user_agent"] = request.META.get("HTTP_USER_AGENT", "")[:200]
    if username:
        metadata["username"] = username[:150]
    actor = user if actor is SELF else actor
    return AuditLog.objects.create(
        actor_type=AuditLog.ActorType.USER if actor else AuditLog.ActorType.SYSTEM,
        actor=actor,
        action=action,
        entity_type=ENTITY_TYPE,
        entity_id=str(user.pk) if user else "",
        metadata_json=metadata,
    )


@receiver(auth_signals.user_logged_in)
def on_login(sender, request, user, **kwargs):
    record_access(Action.LOGIN, user=user, request=request)


@receiver(auth_signals.user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        record_access(Action.LOGOUT, user=user, request=request)


@receiver(auth_signals.user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    record_access(
        Action.LOGIN_FAILED, request=request, username=str(credentials.get("username", ""))
    )
