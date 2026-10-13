"""Calendario laboral y plazos SLA (SPEC §34). Fechas: 2026-10-09 es viernes, 10 sábado,
12 lunes. Horario 08:00–17:00 (9 h = 540 min por día) en America/Guayaquil (UTC-5, sin DST)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.helpdesk import catalogs, sla
from apps.helpdesk.models import Category, SLAPolicy, Ticket
from apps.helpdesk.tickets import TicketService

TZ = ZoneInfo("America/Guayaquil")


@pytest.fixture(autouse=True)
def calendar(settings):
    settings.TIME_ZONE = "America/Guayaquil"
    settings.BUSINESS_HOURS = {"weekdays": [0, 1, 2, 3, 4], "start": "08:00", "end": "17:00"}
    settings.HOLIDAYS = []


def at(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 10, day, h, m, tzinfo=TZ)


# --- add_business_minutes -----------------------------------------------------------


@pytest.mark.parametrize(
    "start,minutes,expected",
    [
        (at(12, "09:00"), 60, at(12, "10:00")),  # dentro del día
        (at(12, "16:30"), 60, at(13, "08:30")),  # cruza el fin de jornada
        (at(12, "06:00"), 30, at(12, "08:30")),  # antes de abrir
        (at(12, "20:00"), 30, at(13, "08:30")),  # después de cerrar
        (at(9, "16:00"), 120, at(12, "09:00")),  # viernes → lunes
        (at(10, "11:00"), 15, at(12, "08:15")),  # sábado → lunes
        (at(12, "08:00"), 540, at(12, "17:00")),  # exactamente un día
        (at(12, "08:00"), 2880, at(19, "11:00")),  # 2880 min = 5 días (2700) + 180 min
        (at(12, "10:00"), 0, at(12, "10:00")),
    ],
)
def test_add_business_minutes(start, minutes, expected):
    assert sla.add_business_minutes(start, minutes) == expected


def test_add_business_minutes_skips_holidays(settings):
    settings.HOLIDAYS = ["2026-10-12"]
    assert sla.add_business_minutes(at(9, "16:30"), 60) == at(13, "08:30")


def test_add_business_minutes_accepts_utc_input():
    start_utc = at(12, "09:00").astimezone(ZoneInfo("UTC"))
    assert sla.add_business_minutes(start_utc, 60) == at(12, "10:00")


def test_calendar_without_business_days_fails(settings):
    settings.BUSINESS_HOURS = {"weekdays": [], "start": "08:00", "end": "17:00"}
    with pytest.raises(ValueError):
        sla.add_business_minutes(at(12, "09:00"), 10)


# --- business_minutes_between ---------------------------------------------------------


@pytest.mark.parametrize(
    "start,end,expected",
    [
        (at(12, "09:00"), at(12, "10:30"), 90),
        (at(9, "16:00"), at(12, "09:00"), 120),  # fin de semana no cuenta
        (at(12, "18:00"), at(13, "07:00"), 0),  # noche
        (at(12, "08:00"), at(16, "17:00"), 540 * 5),
        (at(12, "10:00"), at(12, "09:00"), 0),  # rango invertido
    ],
)
def test_business_minutes_between(start, end, expected):
    assert sla.business_minutes_between(start, end) == expected


def test_add_and_between_are_inverse():
    start = at(9, "15:17")
    for minutes in (1, 59, 540, 1000, 4320):
        assert (
            sla.business_minutes_between(start, sla.add_business_minutes(start, minutes)) == minutes
        )


def test_24x7_mode():
    start = at(10, "23:00")  # sábado de noche
    assert sla.add_minutes(start, 120, business_hours_only=False) == at(11, "01:00")
    assert sla.minutes_between(start, at(11, "01:00"), business_hours_only=False) == 120


# --- Políticas y plazos del ticket ------------------------------------------------------

pytestmark = pytest.mark.django_db


def test_initial_policies_match_spec():
    rows = {
        p.priority: (p.first_response_minutes, p.resolution_minutes, p.business_hours_only)
        for p in SLAPolicy.objects.filter(category__isnull=True)
    }
    assert rows == {
        "LOW": (480, 4320, True),
        "MEDIUM": (240, 2880, True),
        "HIGH": (60, 1440, True),
        "CRITICAL": (15, 240, True),
    }


def test_category_policy_overrides_general(make_user):
    admin = make_user("admin", role="Administrador")
    category = Category.objects.get(code="FINANCIAL")
    catalogs.save_catalog_item(
        SLAPolicy(
            category=category,
            priority="MEDIUM",
            first_response_minutes=30,
            resolution_minutes=60,
            business_hours_only=False,
        ),
        actor=admin,
    )
    assert sla.policy_for(category, "MEDIUM").resolution_minutes == 60
    assert (
        sla.policy_for(Category.objects.get(code="ACADEMIC"), "MEDIUM").resolution_minutes == 2880
    )
    assert sla.policy_for(None, "MEDIUM").category is None


def test_inactive_policy_is_ignored(make_user):
    admin = make_user("admin", role="Administrador")
    catalogs.set_active(SLAPolicy.objects.get(category=None, priority="MEDIUM"), False, actor=admin)
    assert sla.policy_for(None, "MEDIUM") is None


def test_ticket_gets_due_dates_on_creation(make_user, monkeypatch):
    created = at(9, "16:00")  # viernes
    monkeypatch.setattr(timezone, "now", lambda: created)
    ticket = TicketService.create(user=make_user(), subject="s", description="d")
    assert ticket.created_at == created
    assert ticket.first_response_due_at == sla.add_business_minutes(created, 240)
    assert ticket.first_response_due_at == at(12, "11:00")
    assert ticket.sla_due_at == sla.add_business_minutes(created, 2880)


def test_ticket_without_policy_has_no_sla(make_user):
    SLAPolicy.objects.update(is_active=False)
    ticket = TicketService.create(user=make_user(), subject="s", description="d")
    assert ticket.sla_due_at is None
    assert sla.sla_status(ticket).state == sla.SLAState.NONE


def test_policy_constraints(make_user):
    from django.core.exceptions import ValidationError

    admin = make_user("admin", role="Administrador")
    with pytest.raises(ValidationError):  # resolución < primera respuesta
        catalogs.save_catalog_item(
            SLAPolicy(priority="LOW", first_response_minutes=100, resolution_minutes=50),
            actor=admin,
        )
    with pytest.raises(ValidationError):  # ya existe una general activa para MEDIUM
        catalogs.save_catalog_item(
            SLAPolicy(priority="MEDIUM", first_response_minutes=1, resolution_minutes=2),
            actor=admin,
        )


# --- sla_status ---------------------------------------------------------------------------


@pytest.fixture
def ticket(make_user, monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: at(12, "08:00"))
    t = TicketService.create(user=make_user(), subject="s", description="d")  # MEDIUM: 2880 min
    monkeypatch.undo()
    return t


@pytest.mark.parametrize(
    "now,state",
    [
        (at(12, "09:00"), sla.SLAState.OK),
        (at(15, "16:00"), sla.SLAState.OK),  # 2100/2880 = 73 %
        (at(16, "16:00"), sla.SLAState.WARNING),  # 2640/2880 = 92 %
        (at(19, "11:00"), sla.SLAState.BREACHED),  # vence justo (lunes siguiente 11:00)
        (at(19, "12:00"), sla.SLAState.BREACHED),
    ],
)
def test_sla_status(ticket, now, state):
    assert sla.sla_status(ticket, now).state == state


def test_sla_status_values(ticket):
    status = sla.sla_status(ticket, at(12, "10:00"))
    assert status.due_at == ticket.sla_due_at
    assert status.remaining_minutes == 2880 - 120
    assert status.consumed_ratio == pytest.approx(120 / 2880)
    late = sla.sla_status(ticket, at(19, "12:00"))
    assert late.remaining_minutes == -60


def test_warning_threshold(ticket, settings):
    warn_at = sla.add_business_minutes(ticket.created_at, int(2880 * settings.SLA_WARNING_RATIO))
    assert sla.sla_status(ticket, warn_at - timedelta(minutes=1)).state == sla.SLAState.OK
    assert sla.sla_status(ticket, warn_at).state == sla.SLAState.WARNING


@pytest.mark.parametrize(
    "status", [Ticket.Status.RESOLVED, Ticket.Status.CLOSED, Ticket.Status.CANCELLED]
)
def test_sla_stops_when_finished(ticket, status):
    ticket.status = status
    assert sla.sla_status(ticket, at(19, "09:00")).state == sla.SLAState.STOPPED
