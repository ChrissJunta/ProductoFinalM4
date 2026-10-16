"""Máquina de estados de tickets (SPEC §32.1 y §32.2).

La tabla `TRANSITIONS` es la única fuente de verdad: toda transición que no
figura en ella está prohibida. `transition()` es el único punto que cambia
`Ticket.status`; valida, actualiza, registra historial, audita y confirma en
una sola transacción.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.accounts.roles import Role, get_role

from . import alerts, audit, queries
from .models import Alert, Ticket, TicketMessage, TicketStatusHistory

S = Ticket.Status


class Actor:
    """Quién puede ejecutar una transición (columna «Rol permitido» de §32.1)."""

    SYSTEM = "SYSTEM"  # proceso backend (routing, SLA, comandos); nunca el LLM
    OWNER = "OWNER"  # el solicitante del ticket («Usuario (propio)»)
    AGENT = "AGENT"  # cualquier Agente
    ASSIGNED_AGENT = "ASSIGNED_AGENT"  # el Agente responsable del ticket
    SUPERVISOR = "SUPERVISOR"


@dataclass(frozen=True)
class Rule:
    actors: frozenset
    reason_required: bool = False


def _rule(*actors, reason_required=False):
    return Rule(frozenset(actors), reason_required)


A = Actor
TRANSITIONS = {
    (S.NEW, S.CLASSIFIED): _rule(A.SYSTEM, A.AGENT, A.SUPERVISOR),  # 1
    (S.NEW, S.CANCELLED): _rule(A.OWNER, A.SUPERVISOR, reason_required=True),  # 2
    (S.CLASSIFIED, S.ASSIGNED): _rule(A.SYSTEM, A.AGENT, A.SUPERVISOR),  # 3
    (S.CLASSIFIED, S.CANCELLED): _rule(A.OWNER, A.SUPERVISOR, reason_required=True),  # 4
    (S.ASSIGNED, S.IN_PROGRESS): _rule(A.ASSIGNED_AGENT, A.SUPERVISOR),  # 5
    (S.ASSIGNED, S.ESCALATED): _rule(
        A.ASSIGNED_AGENT, A.SUPERVISOR, A.SYSTEM, reason_required=True
    ),  # 6
    (S.IN_PROGRESS, S.WAITING_USER): _rule(A.ASSIGNED_AGENT, A.SUPERVISOR),  # 7
    (S.WAITING_USER, S.IN_PROGRESS): _rule(A.OWNER, A.AGENT, A.SUPERVISOR),  # 8
    (S.WAITING_USER, S.CANCELLED): _rule(A.SYSTEM),  # 9
    (S.IN_PROGRESS, S.ESCALATED): _rule(
        A.ASSIGNED_AGENT, A.SUPERVISOR, A.SYSTEM, reason_required=True
    ),  # 10
    # 11: el motivo es el mensaje de resolución; también se publica en la conversación.
    (S.IN_PROGRESS, S.RESOLVED): _rule(A.ASSIGNED_AGENT, A.SUPERVISOR, reason_required=True),
    (S.ESCALATED, S.ASSIGNED): _rule(A.SUPERVISOR),  # 12
    (S.ESCALATED, S.IN_PROGRESS): _rule(A.SUPERVISOR),  # 13
    (S.RESOLVED, S.CLOSED): _rule(A.OWNER, A.SYSTEM),  # 14
    (S.RESOLVED, S.IN_PROGRESS): _rule(A.OWNER, reason_required=True),  # 15
    (S.CLOSED, S.REOPENED): _rule(A.OWNER, A.SUPERVISOR),  # 16
    (S.REOPENED, S.ASSIGNED): _rule(A.SYSTEM, A.SUPERVISOR),  # 17
}


class TransitionError(Exception):
    """Error de transición con mensaje apto para mostrar al usuario (SPEC §19)."""

    message = "No fue posible cambiar el estado del ticket."

    def __init__(self, message=None):
        super().__init__(message or self.message)
        self.message = message or self.message


class InvalidTransition(TransitionError):
    message = "El ticket no admite ese cambio de estado."


class TransitionForbidden(TransitionError, PermissionDenied):
    message = "No tiene permisos para realizar esta acción."


class ReasonRequired(TransitionError):
    message = "Debe indicar un motivo para este cambio de estado."


class StaleTicket(TransitionError):
    message = "El ticket fue actualizado por otro usuario."


def actor_kinds(ticket, user):
    """Categorías de §32.1 que cumple `user` respecto a `ticket` (None = sistema)."""
    if user is None:
        return {Actor.SYSTEM}
    kinds = set()
    if user.is_authenticated and ticket.user_id == user.pk:
        kinds.add(Actor.OWNER)
    role = get_role(user)
    if role == Role.AGENTE and queries.can_view_ticket(user, ticket):
        # Un agente solo actúa sobre tickets de sus áreas, asignados a él o sin área (BE-T04).
        kinds.add(Actor.AGENT)
        if ticket.assigned_user_id == user.pk:
            kinds.add(Actor.ASSIGNED_AGENT)
    elif role == Role.SUPERVISOR:
        kinds.add(Actor.SUPERVISOR)
    return kinds


def _condition_error(ticket, target, now):
    """Condiciones de la columna «Disparador / condición» que dependen de datos."""
    if target == S.ASSIGNED and not (ticket.assigned_area_id or ticket.assigned_user_id):
        return "Asigne un área o un responsable antes de marcar el ticket como asignado."
    if (ticket.status, target) == (S.CLOSED, S.REOPENED):
        limit = timedelta(days=settings.REOPEN_WINDOW_DAYS)
        if ticket.closed_at is None or now - ticket.closed_at > limit:
            return f"Solo puede reabrirse dentro de {settings.REOPEN_WINDOW_DAYS} días del cierre."
    return None


def allowed_targets(ticket, user):
    """Estados a los que `user` puede llevar `ticket` ahora (para mostrar solo acciones válidas)."""
    kinds = actor_kinds(ticket, user)
    now = timezone.now()
    return [
        target
        for (source, target), rule in TRANSITIONS.items()
        if source == ticket.status
        and rule.actors & kinds
        and _condition_error(ticket, target, now) is None
    ]


def _apply_side_effects(ticket, target, now):
    if target == S.ASSIGNED:
        if (
            ticket.status == S.REOPENED
            and ticket.assigned_user
            and not ticket.assigned_user.is_active
        ):
            # 17: vuelve al último responsable solo si sigue activo; si no, queda el área.
            ticket.assigned_user = None
        ticket.assigned_at = now
    elif target == S.RESOLVED:
        ticket.resolved_at = now
    elif target == S.CLOSED:
        ticket.closed_at = now
    elif target == S.REOPENED:
        ticket.resolved_at = None
        ticket.closed_at = None
    elif (ticket.status, target) == (S.RESOLVED, S.IN_PROGRESS):
        ticket.resolved_at = None  # 15: rechazo; el SLA original se conserva


@transaction.atomic
def transition(ticket, target, *, actor=None, reason="", expected_version=None):
    """Cambia el estado de `ticket` a `target` según §32.1.

    `actor=None` significa «Sistema». `expected_version` es la versión que leyó
    la UI; si no coincide, se rechaza (bloqueo optimista, SPEC §26).
    Devuelve el ticket actualizado.
    """
    # Se bloquea solo la fila del ticket: PostgreSQL no admite FOR UPDATE sobre el
    # lado nullable del OUTER JOIN que genera select_related("assigned_user").
    locked = (
        Ticket.objects.select_for_update(of=("self",))
        .select_related("assigned_user")
        .get(pk=ticket.pk)
    )
    if expected_version is not None and locked.version != expected_version:
        raise StaleTicket()

    rule = TRANSITIONS.get((locked.status, target))
    if rule is None:
        raise InvalidTransition()
    if not rule.actors & actor_kinds(locked, actor):
        raise TransitionForbidden()
    reason = (reason or "").strip()
    if rule.reason_required and not reason:
        raise ReasonRequired()
    now = timezone.now()
    condition_error = _condition_error(locked, target, now)
    if condition_error:
        raise InvalidTransition(condition_error)

    previous = locked.status
    _apply_side_effects(locked, target, now)
    locked.status = target
    locked.version += 1
    locked.save()

    TicketStatusHistory.objects.create(
        ticket=locked, previous_status=previous, new_status=target, actor=actor, reason=reason
    )
    if target == S.RESOLVED and actor is not None:
        # Fila 11: el mensaje de resolución se publica en la conversación del ticket.
        TicketMessage.objects.create(
            ticket=locked,
            sender_type=TicketMessage.SenderType.AGENT,
            sender=actor,
            message_type=TicketMessage.MessageType.RESOLUTION,
            content=reason,
        )
        if locked.first_response_at is None:
            Ticket.objects.filter(pk=locked.pk).update(first_response_at=now)
            locked.first_response_at = now
    _sync_alerts(locked, previous, target, reason)
    # Aviso proactivo al usuario con Telegram vinculado (ADR-081); va por la cola de salida.
    from apps.integrations.telegram.notifications import notify_status_change

    notify_status_change(locked, previous, target, actor=actor, reason=reason)
    audit.record(
        audit.Action.STATUS_CHANGE,
        locked,
        actor=actor,
        previous={"status": previous},
        new={"status": target},
        metadata={"reason": reason} if reason else None,
    )
    return locked


FINISHED = {S.RESOLVED, S.CLOSED, S.CANCELLED}


def _sync_alerts(ticket, previous, target, reason):
    """Alertas ligadas al estado (SPEC §32.1 nota sobre filas 6 y 10, FE-007)."""
    if target == S.ESCALATED:
        alerts.open_alert(
            ticket,
            Alert.Type.ESCALATED,
            severity=Alert.Severity.WARNING,
            message=f"Ticket escalado: {reason}"[:255],
        )
    elif previous == S.ESCALATED:
        alerts.resolve_alerts(ticket, [Alert.Type.ESCALATED])
    if previous == S.NEW:
        # Un humano ya triageó el ticket (asignó, pidió datos…): la revisión N4 está hecha.
        alerts.resolve_alerts(ticket, [Alert.Type.HUMAN_REVIEW])
    if target in FINISHED:
        alerts.resolve_alerts(ticket)


def record_initial_status(ticket, actor):
    """Primera entrada del historial (— → NEW). La llama `TicketService.create`."""
    TicketStatusHistory.objects.create(ticket=ticket, new_status=ticket.status, actor=actor)
