from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.helpdesk import alerts, workflow
from apps.helpdesk.models import Alert, Area, Ticket
from apps.helpdesk.tickets import TicketService

pytestmark = pytest.mark.django_db

S = Ticket.Status
TZ = ZoneInfo("America/Guayaquil")


def at(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 10, day, h, m, tzinfo=TZ)


@pytest.fixture(autouse=True)
def calendar(settings):
    settings.TIME_ZONE = "America/Guayaquil"
    settings.BUSINESS_HOURS = {"weekdays": [0, 1, 2, 3, 4], "start": "08:00", "end": "17:00"}
    settings.HOLIDAYS = []


@pytest.fixture
def clock(monkeypatch):
    """Reloj controlable: clock.set(at(...))."""

    class Clock:
        now = at(12, "08:00")

        def set(self, value):
            self.now = value

    c = Clock()
    monkeypatch.setattr(timezone, "now", lambda: c.now)
    return c


@pytest.fixture
def agent(make_user):
    return make_user("agent", role="Agente")


@pytest.fixture
def ticket(make_user, agent, clock):
    # Creado el lunes 12 a las 08:00 → MEDIUM vence el lunes 19 a las 11:00 (2880 min laborables).
    t = TicketService.create(user=make_user("owner"), subject="s", description="d")
    Ticket.objects.filter(pk=t.pk).update(
        status=S.IN_PROGRESS, assigned_user=agent, assigned_area=Area.objects.get(code="IT")
    )
    t.refresh_from_db()
    return t


def run():
    out = StringIO()
    call_command("check_sla", stdout=out)
    return out.getvalue()


def open_types(ticket):
    return set(ticket.alerts.filter(status=Alert.Status.OPEN).values_list("alert_type", flat=True))


def test_no_alert_while_in_time(ticket, clock):
    clock.set(at(15, "16:00"))  # 73 %
    run()
    assert open_types(ticket) == set()


def test_warning_alert_when_approaching(ticket, clock):
    clock.set(at(16, "16:00"))  # 92 %
    output = run()
    assert open_types(ticket) == {Alert.Type.SLA_WARNING}
    alert = ticket.alerts.get()
    assert alert.severity == Alert.Severity.WARNING
    assert "quedan" in alert.message
    assert "1 por vencer" in output


def test_breach_alert_and_auto_escalation(ticket, clock):
    clock.set(at(16, "16:00"))
    run()
    clock.set(at(19, "12:00"))
    output = run()

    ticket.refresh_from_db()
    assert ticket.status == S.ESCALATED
    assert open_types(ticket) == {Alert.Type.SLA_BREACHED, Alert.Type.ESCALATED}
    assert ticket.alerts.get(alert_type=Alert.Type.SLA_WARNING).status == Alert.Status.RESOLVED
    entry = ticket.status_history.last()
    assert (entry.actor, entry.reason) == (None, "SLA de resolución vencido.")
    assert "1 vencidas" in output and "tickets escalados: 1" in output


def test_check_sla_is_idempotent(ticket, clock):
    clock.set(at(19, "12:00"))
    run()
    second = run()
    assert ticket.alerts.filter(alert_type=Alert.Type.SLA_BREACHED).count() == 1
    assert "0 vencidas" in second and "tickets escalados: 0" in second


@pytest.mark.parametrize("status", [S.NEW, S.WAITING_USER])
def test_breach_without_escalation_when_state_does_not_allow_it(ticket, clock, status):
    Ticket.objects.filter(pk=ticket.pk).update(status=status)
    clock.set(at(19, "12:00"))
    run()
    ticket.refresh_from_db()
    assert ticket.status == status
    assert open_types(ticket) == {Alert.Type.SLA_BREACHED}


@pytest.mark.parametrize("status", [S.RESOLVED, S.CLOSED, S.CANCELLED])
def test_finished_tickets_are_ignored(ticket, clock, status):
    Ticket.objects.filter(pk=ticket.pk).update(status=status)
    clock.set(at(19, "12:00"))
    run()
    assert not ticket.alerts.exists()


# --- Alertas ligadas al workflow ---------------------------------------------------------


def test_manual_escalation_opens_alert_and_leaving_closes_it(ticket, agent, make_user):
    workflow.transition(ticket, S.ESCALATED, actor=agent, reason="Necesita Finanzas")
    alert = ticket.alerts.get(alert_type=Alert.Type.ESCALATED)
    assert alert.status == Alert.Status.OPEN
    assert alert.message == "Ticket escalado: Necesita Finanzas"

    workflow.transition(ticket, S.IN_PROGRESS, actor=make_user("sup", role="Supervisor"))
    alert.refresh_from_db()
    assert alert.status == Alert.Status.RESOLVED
    assert alert.resolved_at is not None


def test_resolving_ticket_closes_its_alerts(ticket, agent, clock):
    clock.set(at(16, "16:00"))
    run()
    workflow.transition(ticket, S.RESOLVED, actor=agent, reason="Listo")
    assert open_types(ticket) == set()


def test_open_alert_is_unique_per_type(ticket):
    a1, created1 = alerts.open_alert(
        ticket, Alert.Type.SLA_WARNING, severity=Alert.Severity.WARNING, message="x"
    )
    a2, created2 = alerts.open_alert(
        ticket, Alert.Type.SLA_WARNING, severity=Alert.Severity.WARNING, message="y"
    )
    assert (created1, created2) == (True, False)
    assert a1 == a2


def test_open_alert_handles_race(ticket, monkeypatch):
    """Si otro proceso inserta la alerta entre la consulta y el INSERT, se reutiliza."""
    existing = Alert.objects.create(
        ticket=ticket, alert_type=Alert.Type.SLA_WARNING, severity="WARNING", message="otro proceso"
    )
    real_filter = Alert.objects.filter
    calls = {"n": 0}

    def filter_hiding_first(*args, **kwargs):
        calls["n"] += 1
        qs = real_filter(*args, **kwargs)
        return qs.none() if calls["n"] == 1 else qs

    monkeypatch.setattr(Alert.objects, "filter", filter_hiding_first)
    alert, created = alerts.open_alert(
        ticket, Alert.Type.SLA_WARNING, severity=Alert.Severity.WARNING, message="x"
    )
    assert (alert, created) == (existing, False)


# --- Vista de alertas (CONTRACT-007) -------------------------------------------------------


@pytest.fixture
def alerts_data(ticket, make_user):
    other = TicketService.create(user=make_user("owner2"), subject="s", description="d")
    alerts.open_alert(ticket, Alert.Type.SLA_BREACHED, severity="CRITICAL", message="vencido")
    alerts.open_alert(other, Alert.Type.SLA_WARNING, severity="WARNING", message="por vencer")
    resolved, _ = alerts.open_alert(other, Alert.Type.ESCALATED, severity="WARNING", message="esc")
    alerts.resolve_alerts(other, [Alert.Type.ESCALATED])
    return ticket, other


def test_alert_list_for_supervisor(client, make_user, alerts_data):
    client.force_login(make_user("sup", role="Supervisor"))
    response = client.get(reverse("helpdesk:alert_list"))
    assert response.status_code == 200
    ctx = response.context
    assert {a.message for a in ctx["alerts"]} == {"vencido", "por vencer"}  # OPEN por defecto
    assert ctx["filters"] == {"status": "OPEN", "type": ""}
    assert ctx["open_counts"] == {"SLA_WARNING": 1, "SLA_BREACHED": 1, "ESCALATED": 0,
                                  "HUMAN_REVIEW": 0}  # fmt: skip
    assert ctx["page_obj"].number == 1


@pytest.mark.parametrize(
    "params,messages",
    [
        ({"type": "SLA_BREACHED"}, {"vencido"}),
        ({"status": "RESOLVED"}, {"esc"}),
        ({"status": "ALL"}, {"vencido", "por vencer", "esc"}),
        ({"status": "NOPE", "type": "NOPE"}, {"vencido", "por vencer", "esc"}),
    ],
)
def test_alert_list_filters(client, make_user, alerts_data, params, messages):
    client.force_login(make_user("sup", role="Supervisor"))
    response = client.get(reverse("helpdesk:alert_list"), params)
    assert {a.message for a in response.context["alerts"]} == messages


@pytest.mark.parametrize("role", ["Usuario", "Agente", "Administrador"])
def test_alert_list_forbidden_for_other_roles(client, make_user, role):
    client.force_login(make_user("x", role=role))
    assert client.get(reverse("helpdesk:alert_list")).status_code == 403


def test_alert_list_requires_login(client):
    assert client.get(reverse("helpdesk:alert_list")).status_code == 302
