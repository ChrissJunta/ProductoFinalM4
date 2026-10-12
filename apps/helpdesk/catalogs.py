"""Escritura de catálogos (Area, Category, Subcategory).

Toda creación, modificación o (des)activación de un catálogo pasa por aquí para
que quede auditada en la misma transacción. Lo usan el admin de Django y, más
adelante, las vistas de administración de FE-T09.
"""

from django.db import transaction

from . import audit
from .audit import Action


@transaction.atomic
def save_catalog_item(instance, *, actor):
    """Crea o actualiza un elemento de catálogo y registra el cambio.

    Si no cambió ningún campo auditado, guarda sin generar registro.
    """
    fields = instance.audit_fields
    if instance.pk is None:
        instance.full_clean()
        instance.save()
        audit.record(Action.CREATE, instance, actor=actor, new=audit.snapshot(instance, fields))
        return instance

    current = type(instance).objects.select_for_update().get(pk=instance.pk)
    previous = audit.snapshot(current, fields)
    instance.full_clean()
    instance.save()
    new = audit.snapshot(instance, fields)
    if new != previous:
        changed = {k: v for k, v in new.items() if previous.get(k) != v}
        prev_changed = {k: previous[k] for k in changed}
        audit.record(Action.UPDATE, instance, actor=actor, previous=prev_changed, new=changed)
    return instance


@transaction.atomic
def set_active(instance, active, *, actor):
    """Activa o desactiva lógicamente un elemento de catálogo (nunca se borra)."""
    instance = type(instance).objects.select_for_update().get(pk=instance.pk)
    if instance.is_active == active:
        return instance
    instance.is_active = active
    instance.save(update_fields=["is_active", "updated_at"])
    audit.record(
        Action.ACTIVATE if active else Action.DEACTIVATE,
        instance,
        actor=actor,
        previous={"is_active": not active},
        new={"is_active": active},
    )
    return instance
