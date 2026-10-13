"""Lectura de tickets: visibilidad por rol, filtros y paginación (BE-T04).

Visibilidad (control horizontal, SPEC §48):
- Usuario: solo sus tickets.
- Agente: tickets asignados a él, tickets de sus áreas (`Area.agents`, CR-003) y
  tickets sin área (cola de triaje, para poder clasificarlos: §32.1 fila 1).
- Supervisor y Administrador: todos (el Administrador solo consulta, ADR-023).
- Cualquier rol ve además los tickets que él mismo creó.
"""

from datetime import date

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.accounts.roles import Role, get_role

from . import sla
from .models import Alert, Ticket

S = Ticket.Status
PAGE_SIZE = 20


def visible_tickets(user):
    if not user.is_authenticated:
        return Ticket.objects.none()
    role = get_role(user)
    qs = Ticket.objects.all()
    if role in (Role.SUPERVISOR, Role.ADMINISTRADOR):
        return qs
    own = Q(user=user)
    if role == Role.AGENTE:
        return qs.filter(
            own
            | Q(assigned_user=user)
            | Q(assigned_area__agents=user)
            | Q(assigned_area__isnull=True)
        ).distinct()
    return qs.filter(own)


def can_view_ticket(user, ticket):
    return visible_tickets(user).filter(pk=ticket.pk).exists()


def get_visible_ticket_or_404(user, code):
    from django.shortcuts import get_object_or_404

    return get_object_or_404(visible_tickets(user), ticket_code=code)


# --- Filtros -------------------------------------------------------------------------

SORTS = {
    "-created_at": ("-created_at", "-id"),
    "created_at": ("created_at", "id"),
    "-updated_at": ("-updated_at", "-id"),
    "sla_due_at": ("sla_due_at", "id"),
}


def _parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def apply_filters(qs, params, user):
    """Aplica los filtros de FE-004 / FE-006. Ignora valores inválidos.

    Devuelve (queryset, filtros_aplicados) para que la plantilla los conserve.
    """
    applied = {}

    status = params.get("status", "")
    if status == "OPEN":
        qs = qs.exclude(status__in=sla.FINISHED)
        applied["status"] = status
    elif status == "FINISHED":
        qs = qs.filter(status__in=sla.FINISHED)
        applied["status"] = status
    elif status in S.values:
        qs = qs.filter(status=status)
        applied["status"] = status

    priority = params.get("priority", "")
    if priority in Ticket.Priority.values:
        qs = qs.filter(priority=priority)
        applied["priority"] = priority

    for field in ("category", "area"):
        pk = _int(params.get(field))
        if pk is not None:
            qs = qs.filter(**{"assigned_area_id" if field == "area" else "category_id": pk})
            applied[field] = pk

    assignee = params.get("assignee", "")
    if assignee == "me":
        qs = qs.filter(assigned_user=user)
        applied["assignee"] = assignee
    elif assignee == "none":
        qs = qs.filter(assigned_user__isnull=True)
        applied["assignee"] = assignee
    elif _int(assignee) is not None:
        qs = qs.filter(assigned_user_id=int(assignee))
        applied["assignee"] = int(assignee)

    date_from, date_to = _parse_date(params.get("date_from")), _parse_date(params.get("date_to"))
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
        applied["date_from"] = date_from.isoformat()
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
        applied["date_to"] = date_to.isoformat()

    sla_filter = params.get("sla", "")
    if sla_filter in (sla.SLAState.WARNING, sla.SLAState.BREACHED):
        now = timezone.now()
        open_qs = qs.exclude(status__in=sla.FINISHED)
        if sla_filter == sla.SLAState.BREACHED:
            qs = open_qs.filter(sla_due_at__lte=now)
        else:
            # «Por vencer»: con alerta SLA_WARNING abierta (la crea check_sla) y aún no vencido.
            warning = Alert.objects.filter(
                ticket=OuterRef("pk"), alert_type=Alert.Type.SLA_WARNING, status=Alert.Status.OPEN
            )
            qs = open_qs.filter(Exists(warning), sla_due_at__gt=now)
        applied["sla"] = sla_filter

    text = (params.get("q") or "").strip()
    if text:
        qs = qs.filter(Q(ticket_code__iexact=text) | Q(subject__icontains=text))
        applied["q"] = text

    sort = params.get("sort", "-created_at")
    if sort not in SORTS:
        sort = "-created_at"
    qs = qs.order_by(*SORTS[sort])
    applied["sort"] = sort
    return qs, applied


def with_related(qs):
    return qs.select_related("user", "category", "subcategory", "assigned_area", "assigned_user")


def ticket_rows(tickets, now=None):
    """Filas para listados: el ticket y su estado SLA (sin consultas por fila)."""
    now = now or timezone.now()
    index = sla.policy_index()
    return [{"ticket": t, "sla": sla.sla_status(t, now, policies=index)} for t in tickets]


RECENT_LIMIT = 5


def dashboard(user):
    """Contexto del inicio (FE-002 / CONTRACT-013): últimos tickets y resumen por estado."""
    visible = visible_tickets(user)
    if get_role(user) != Role.USUARIO:
        # Para el personal, «recientes» son los suyos o asignados a él, no toda la cola.
        visible = visible.filter(Q(user=user) | Q(assigned_user=user))
    recent = with_related(visible.order_by("-updated_at", "-id"))[:RECENT_LIMIT]
    return {
        "recent_rows": ticket_rows(recent),
        "summary": {
            "open": visible.exclude(status__in=sla.FINISHED).count(),
            "waiting_user": visible.filter(status=S.WAITING_USER).count(),
            "resolved": visible.filter(status=S.RESOLVED).count(),
        },
    }
