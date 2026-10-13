"""Cálculo de SLA (SPEC §34).

Los plazos se cuentan en minutos corridos (24×7) o solo dentro del calendario
laboral (`settings.BUSINESS_HOURS`, `settings.HOLIDAYS`, zona `TIME_ZONE`),
según `SLAPolicy.business_hours_only`.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from .models import SLAPolicy, Ticket

MAX_DAYS_SCAN = 366 * 3  # protección ante un calendario sin días laborables


# --- Calendario laboral ----------------------------------------------------------


def _calendar():
    hours = settings.BUSINESS_HOURS
    return (
        ZoneInfo(settings.TIME_ZONE),
        set(hours["weekdays"]),
        time.fromisoformat(hours["start"]),
        time.fromisoformat(hours["end"]),
        {date.fromisoformat(d) for d in settings.HOLIDAYS},
    )


def _business_window(day, cal):
    """(inicio, fin) laborables de `day` en hora local, o None si no es laborable."""
    tz, weekdays, start, end, holidays = cal
    if day.weekday() not in weekdays or day in holidays:
        return None
    return datetime.combine(day, start, tzinfo=tz), datetime.combine(day, end, tzinfo=tz)


def add_business_minutes(start, minutes):
    """Instante en que se cumplen `minutes` laborables contados desde `start`."""
    cal = _calendar()
    cursor = start.astimezone(cal[0])
    remaining = timedelta(minutes=minutes)
    for _ in range(MAX_DAYS_SCAN):
        window = _business_window(cursor.date(), cal)
        if window:
            window_start, window_end = window
            cursor = max(cursor, window_start)
            if cursor < window_end:
                available = window_end - cursor
                if remaining <= available:
                    return cursor + remaining
                remaining -= available
        next_day = cursor.date() + timedelta(days=1)
        cursor = datetime.combine(next_day, time.min, tzinfo=cal[0])
    raise ValueError("El calendario laboral no tiene días hábiles suficientes.")


def business_minutes_between(start, end):
    """Minutos laborables entre `start` y `end` (0 si end <= start)."""
    if end <= start:
        return 0
    cal = _calendar()
    start, end = start.astimezone(cal[0]), end.astimezone(cal[0])
    total = timedelta()
    day = start.date()
    for _ in range(MAX_DAYS_SCAN):
        if day > end.date():
            break
        window = _business_window(day, cal)
        if window:
            overlap = min(end, window[1]) - max(start, window[0])
            if overlap > timedelta():
                total += overlap
        day += timedelta(days=1)
    return int(total.total_seconds() // 60)


def add_minutes(start, minutes, business_hours_only):
    if business_hours_only:
        return add_business_minutes(start, minutes)
    return start + timedelta(minutes=minutes)


def minutes_between(start, end, business_hours_only):
    if business_hours_only:
        return business_minutes_between(start, end)
    return max(0, int((end - start).total_seconds() // 60))


# --- Políticas y plazos ------------------------------------------------------------


def policy_index():
    """Políticas activas indexadas por (category_id, prioridad), para listados sin N+1."""
    return {(p.category_id, p.priority): p for p in SLAPolicy.objects.filter(is_active=True)}


def policy_for(category, priority, policies=None):
    """Política activa de la categoría; si no hay, la general (sin categoría).

    `policies` (de `policy_index()`) evita consultar la BD por cada ticket.
    """
    if policies is not None:
        category_id = getattr(category, "pk", None)
        specific = policies.get((category_id, priority)) if category_id else None
        return specific or policies.get((None, priority))
    qs = SLAPolicy.objects.filter(is_active=True, priority=priority)
    if category is not None:
        specific = qs.filter(category=category).first()
        if specific:
            return specific
    return qs.filter(category__isnull=True).first()


def apply_due_dates(ticket):
    """Fija `first_response_due_at` y `sla_due_at` desde la creación del ticket.

    No guarda: lo llama `TicketService.create` antes de guardar. Si no existe
    política aplicable, los plazos quedan vacíos (el ticket no tiene SLA).
    """
    policy = policy_for(ticket.category, ticket.priority)
    if policy is None:
        ticket.first_response_due_at = ticket.sla_due_at = None
        return None
    start = ticket.created_at or timezone.now()
    ticket.first_response_due_at = add_minutes(
        start, policy.first_response_minutes, policy.business_hours_only
    )
    ticket.sla_due_at = add_minutes(start, policy.resolution_minutes, policy.business_hours_only)
    return policy


# --- Estado del SLA de un ticket ---------------------------------------------------


class SLAState:
    NONE = "NONE"  # sin política aplicable
    OK = "OK"
    WARNING = "WARNING"  # consumido >= SLA_WARNING_RATIO
    BREACHED = "BREACHED"  # vencido
    STOPPED = "STOPPED"  # ticket resuelto, cerrado o cancelado


FINISHED = {Ticket.Status.RESOLVED, Ticket.Status.CLOSED, Ticket.Status.CANCELLED}


@dataclass(frozen=True)
class SLAStatus:
    state: str
    due_at: datetime | None
    remaining_minutes: int | None  # negativo si está vencido
    consumed_ratio: float | None


def sla_status(ticket, now=None, policies=None):
    """Estado del SLA de resolución, con los mismos criterios que `check_sla`."""
    if ticket.sla_due_at is None:
        return SLAStatus(SLAState.NONE, None, None, None)
    if ticket.status in FINISHED:
        return SLAStatus(SLAState.STOPPED, ticket.sla_due_at, None, None)

    now = now or timezone.now()
    policy = policy_for(ticket.category, ticket.priority, policies)
    business = policy.business_hours_only if policy else False
    total = minutes_between(ticket.created_at, ticket.sla_due_at, business)
    consumed = minutes_between(ticket.created_at, now, business)
    ratio = consumed / total if total else 1.0

    if now >= ticket.sla_due_at:
        remaining = -minutes_between(ticket.sla_due_at, now, business)
        return SLAStatus(SLAState.BREACHED, ticket.sla_due_at, remaining, ratio)
    remaining = minutes_between(now, ticket.sla_due_at, business)
    state = SLAState.WARNING if ratio >= settings.SLA_WARNING_RATIO else SLAState.OK
    return SLAStatus(state, ticket.sla_due_at, remaining, ratio)
