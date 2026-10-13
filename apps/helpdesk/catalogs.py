"""Escritura de catálogos (Area, Category, Subcategory).

Toda creación, modificación o (des)activación de un catálogo pasa por aquí para
que quede auditada en la misma transacción. Lo usan el admin de Django y, más
adelante, las vistas de administración de FE-T09.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.roles import Role, get_role

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


@transaction.atomic
def set_area_agents(area, agents, *, actor):
    """Define qué agentes atienden un área (CR-003) y audita el cambio.

    Solo admite usuarios activos del grupo Agente.
    """
    agents = list(agents)
    invalid = [a.username for a in agents if not a.is_active or get_role(a) != Role.AGENTE]
    if invalid:
        raise ValidationError({"agents": f"No son agentes activos: {', '.join(invalid)}."})

    before = sorted(area.agents.values_list("pk", flat=True))
    area.agents.set(agents)
    after = sorted(a.pk for a in agents)
    if before != after:
        audit.record(
            Action.UPDATE,
            area,
            actor=actor,
            previous={"agent_ids": before},
            new={"agent_ids": after},
        )
    return area
