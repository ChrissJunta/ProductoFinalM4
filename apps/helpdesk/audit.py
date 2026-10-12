"""Servicio de auditoría (SPEC §26 `AuditLog`).

Uso: `audit.record(Action.UPDATE, instancia, actor=request.user, previous=..., new=...)`.
"""

from .models import AuditLog


class Action:
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    ACTIVATE = "ACTIVATE"
    DEACTIVATE = "DEACTIVATE"


def entity_type_of(instance):
    return instance._meta.label_lower  # p. ej. "helpdesk.area"


def snapshot(instance, fields):
    """Copia serializable de los campos auditados de una instancia."""
    return {field: getattr(instance, field) for field in fields}


def record(
    action, instance, *, actor=None, actor_type=None, previous=None, new=None, metadata=None
):
    """Crea un registro de auditoría inmutable.

    Si no se indica `actor_type`, se infiere: USER si hay actor, SYSTEM si no.
    Debe llamarse dentro de la misma transacción que el cambio auditado.
    """
    if actor is not None and not actor.is_authenticated:
        actor = None
    if actor_type is None:
        actor_type = AuditLog.ActorType.USER if actor else AuditLog.ActorType.SYSTEM
    return AuditLog.objects.create(
        actor_type=actor_type,
        actor=actor,
        action=action,
        entity_type=entity_type_of(instance),
        entity_id=str(instance.pk),
        previous_value_json=previous,
        new_value_json=new,
        metadata_json=metadata or {},
    )
