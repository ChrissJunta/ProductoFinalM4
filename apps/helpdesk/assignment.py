"""Asignación y reasignación de tickets (BE-T06, SPEC §33 TicketService).

Quién puede asignar:
- Supervisor: cualquier área activa y cualquier agente de esa área.
- Agente: solo dentro de sus áreas (tomar el ticket o pasarlo a un compañero
  del área), y solo tickets que puede ver. No puede mover tickets a otras áreas.
- Usuario y Administrador: no asignan (ADR-023).

Un ticket escalado solo lo reasigna el Supervisor (§32.1 fila 12). Tras asignar,
el estado avanza a ASSIGNED si estaba en NEW, CLASSIFIED, REOPENED o ESCALATED.
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.roles import Role, get_role

from . import audit, queries, workflow
from .models import Area, Ticket

S = Ticket.Status
FINISHED = {S.RESOLVED, S.CLOSED, S.CANCELLED}
ADVANCE_TO_ASSIGNED = {
    S.NEW: [S.CLASSIFIED, S.ASSIGNED],
    S.CLASSIFIED: [S.ASSIGNED],
    S.REOPENED: [S.ASSIGNED],
    S.ESCALATED: [S.ASSIGNED],
}


def assignable_areas(ticket, user):
    """Áreas (con sus agentes) a las que `user` puede asignar `ticket`. Vacío si no puede."""
    if ticket.status in FINISHED:
        return Area.objects.none()
    role = get_role(user)
    areas = Area.objects.filter(is_active=True).prefetch_related("agents")
    if role == Role.SUPERVISOR:
        return areas
    if (
        role == Role.AGENTE
        and ticket.status != S.ESCALATED
        and queries.can_view_ticket(user, ticket)
    ):
        return areas.filter(agents=user)
    return Area.objects.none()


def assign_options(ticket, user):
    """Contexto para la UI de asignación (CONTRACT-012): qué puede elegir el usuario."""
    areas = [
        {
            "id": area.pk,
            "name": area.name,
            "agents": [
                {"id": a.pk, "name": a.get_full_name() or a.username}
                for a in sorted(area.agents.all(), key=lambda a: a.username)
                if a.is_active
            ],
        }
        for area in assignable_areas(ticket, user)
    ]
    return {
        "can_assign": bool(areas),
        "areas": areas,
        "current_area_id": ticket.assigned_area_id,
        "current_assignee_id": ticket.assigned_user_id,
    }


def _step_actor(ticket, target, actor):
    """El propio usuario si la tabla §32.1 se lo permite; si no, el sistema."""
    rule = workflow.TRANSITIONS[(ticket.status, target)]
    if rule.actors & workflow.actor_kinds(ticket, actor):
        return actor
    if workflow.Actor.SYSTEM in rule.actors:
        return None
    raise workflow.TransitionForbidden()


@transaction.atomic
def assign(ticket, *, actor, area, assignee=None, expected_version=None):
    """Asigna área y, opcionalmente, responsable. Audita y avanza el estado."""
    locked = Ticket.objects.select_for_update(of=("self",)).get(pk=ticket.pk)
    if expected_version is not None and locked.version != expected_version:
        raise workflow.StaleTicket()
    if locked.status in FINISHED:
        raise workflow.InvalidTransition(
            "No se puede asignar un ticket resuelto, cerrado o cancelado."
        )
    allowed = assignable_areas(locked, actor)
    if not allowed.exists():
        raise workflow.TransitionForbidden()
    if area is None or not allowed.filter(pk=area.pk).exists():
        raise workflow.TransitionForbidden()
    if assignee is not None and not (
        assignee.is_active and area.agents.filter(pk=assignee.pk).exists()
    ):
        raise workflow.InvalidTransition("El responsable debe ser un agente activo del área.")

    previous = {
        "assigned_area_id": locked.assigned_area_id,
        "assigned_user_id": locked.assigned_user_id,
    }
    new = {"assigned_area_id": area.pk, "assigned_user_id": assignee.pk if assignee else None}
    if previous != new:
        locked.assigned_area = area
        locked.assigned_user = assignee
        if assignee is not None and previous["assigned_user_id"] != assignee.pk:
            locked.assigned_at = timezone.now()
        locked.version += 1
        locked.save()
        reassign = previous["assigned_user_id"] is not None
        action = audit.Action.REASSIGN if reassign else audit.Action.ASSIGN
        audit.record(action, locked, actor=actor, previous=previous, new=new)

    # Aunque área y responsable no cambien (p. ej. el área ya venía de la categoría),
    # confirmar la asignación avanza el estado.

    for target in ADVANCE_TO_ASSIGNED.get(locked.status, []):
        locked = workflow.transition(
            locked, target, actor=_step_actor(locked, target, actor), reason="Asignación"
        )
    return locked
