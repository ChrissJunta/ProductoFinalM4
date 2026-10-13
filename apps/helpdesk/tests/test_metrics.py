"""BE-T10: métricas operativas contra cálculos manuales de referencia (CONTRACT-017)."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.ai.models import AIDecision, AIUsage
from apps.helpdesk import metrics
from apps.helpdesk.models import AuditLog, Category, Ticket, TicketStatusHistory
from apps.helpdesk.tickets import TicketService

pytestmark = pytest.mark.django_db

DAY = date(2026, 10, 5)


def at(day, hour, minute=0):
    return timezone.make_aware(datetime(day.year, day.month, day.day, hour, minute))


@pytest.fixture
def data(make_user):
    """Cuatro tickets con tiempos conocidos (creados el 5/10 a las 08:00)."""
    user = make_user("u")
    fin, tech = Category.objects.get(code="FINANCIAL"), Category.objects.get(code="TECHNICAL")
    created = at(DAY, 8)
    spec = [
        # categoría, canal, estado, 1.ª resp. (min), resuelto (min), vence 1.ª resp., vence resol.
        (fin, "WEB", "CLOSED", 30, 120, 60, 240),  # cumple ambos
        (fin, "WHATSAPP", "RESOLVED", 90, 300, 60, 240),  # incumple ambos
        (tech, "WEB", "IN_PROGRESS", 10, None, 60, 240),  # resolución vencida sin resolver
        (None, "WEB", "NEW", None, None, None, None),  # sin SLA
    ]
    tickets = []
    for category, channel, status, first, resolved, due_first, due_res in spec:
        t = TicketService.create(
            user=user, subject="s", description="d", category=category, channel=channel
        )
        Ticket.objects.filter(pk=t.pk).update(
            created_at=created,
            status=status,
            first_response_at=created + timedelta(minutes=first) if first else None,
            resolved_at=created + timedelta(minutes=resolved) if resolved else None,
            first_response_due_at=created + timedelta(minutes=due_first) if due_first else None,
            sla_due_at=created + timedelta(minutes=due_res) if due_res else None,
        )
        tickets.append(t)
    return tickets


def compute(**kw):
    return metrics.compute(DAY, DAY, now=at(DAY, 23), **kw)


def test_totals_and_status(data):
    m = compute()
    assert (m["total"], m["open"], m["resolved"], m["closed"], m["cancelled"]) == (4, 2, 1, 1, 0)
    statuses = {row["status"]: row["count"] for row in m["by_status"]}
    assert (statuses["NEW"], statuses["IN_PROGRESS"], statuses["REOPENED"]) == (1, 1, 0)


def test_sla_reference_values(data):
    m = compute()
    # Resolución: cumple 1 (120 ≤ 240); incumple 2 (300 > 240 y otro vencido sin resolver).
    assert m["sla_resolution"] == {
        "within": 1, "breached": 2, "pending": 0, "no_sla": 1, "compliance_pct": 33.3,
    }  # fmt: skip
    # Primera respuesta: 30 y 10 cumplen; 90 incumple.
    assert m["sla_first_response"] == {
        "within": 2, "breached": 1, "pending": 0, "no_sla": 1, "compliance_pct": 66.7,
    }  # fmt: skip


def test_pending_when_not_yet_due(data):
    m = metrics.compute(DAY, DAY, now=at(DAY, 9))  # 60 min después: aún no vence la resolución
    assert m["sla_resolution"]["pending"] == 1 and m["sla_resolution"]["breached"] == 1


def test_times_reference_values(data):
    m = compute()
    assert m["first_response_minutes"] == {"count": 3, "avg": 43.3, "median": 30.0, "p90": 90.0}
    assert m["resolution_minutes"] == {"count": 2, "avg": 210.0, "median": 210.0, "p90": 300.0}


def test_breakdowns(data):
    m = compute()
    by_cat = {row["label"]: row for row in m["by_category"]}
    assert (
        by_cat["Financiero"]["total"] == 2
        and by_cat["Financiero"]["sla_resolution"]["compliance_pct"] == 50.0
    )
    assert by_cat["Sin categoría"]["total"] == 1
    by_channel = {row["id"]: row["total"] for row in m["by_channel"]}
    assert by_channel == {"WEB": 3, "WHATSAPP": 1}
    assert {row["label"] for row in m["by_channel"]} == {"Web", "WhatsApp"}
    by_area = {row["label"]: row["total"] for row in m["by_area"]}
    assert by_area == {"Tesorería y Finanzas": 2, "Soporte Tecnológico": 1, "Sin área": 1}
    assert m["by_area"][0]["label"] == "Tesorería y Finanzas"  # ordenado por volumen


def test_filters(data):
    fin = Category.objects.get(code="FINANCIAL")
    assert compute(category=fin)["total"] == 2
    assert compute(channel="WHATSAPP")["total"] == 1
    assert compute(area=fin.default_area)["total"] == 2
    assert metrics.compute(DAY + timedelta(days=1), DAY + timedelta(days=2))["total"] == 0


def test_period_uses_local_dates(data, settings):
    # 23:30 locales del día anterior no entran en el periodo del día.
    t = data[0]
    Ticket.objects.filter(pk=t.pk).update(created_at=at(DAY - timedelta(days=1), 23, 30))
    assert compute()["total"] == 3
    assert metrics.compute(DAY - timedelta(days=1), DAY)["total"] == 4


def test_reassignments_and_reopenings(data):
    t = data[0]
    AuditLog.objects.create(
        actor_type="SYSTEM", action="REASSIGN", entity_type="helpdesk.ticket", entity_id=str(t.pk)
    )
    TicketStatusHistory.objects.create(ticket=t, previous_status="CLOSED", new_status="REOPENED")
    m = compute()
    assert (m["reassignments"], m["reopenings"]) == (1, 1)


def test_empty_period():
    m = metrics.compute(DAY, DAY)
    assert m["total"] == 0 and m["sla_resolution"]["compliance_pct"] is None
    assert m["first_response_minutes"] == {"count": 0, "avg": None, "median": None, "p90": None}
    assert m["by_area"] == [] and m["ai"]["automation_pct"] is None


def test_ai_metrics(data):
    when = at(DAY, 10)
    for level, extra in (
        ("N0", {}),
        ("N0", {}),
        ("N3", {}),
        ("N4", {"requires_human": True, "errors": ["Salida LLM inválida: x"]}),
    ):
        d = AIDecision.objects.create(
            operation="AGENT_RUN", autonomy_level=level, channel="WEB", **extra
        )
        AIDecision.objects.filter(pk=d.pk).update(created_at=when)
    AIDecision.objects.filter(autonomy_level="N3").update(
        requires_human=True, accepted=True, corrected=True
    )
    for ok, ms in ((True, 100), (True, 300), (False, 0)):
        u = AIUsage.objects.create(
            provider="fake", model_name="m", operation="CLASSIFY", success=ok, latency_ms=ms,
            estimated_cost=Decimal("0.001"),
        )  # fmt: skip
        AIUsage.objects.filter(pk=u.pk).update(created_at=when)
    ai = compute()["ai"]
    assert (ai["runs"], ai["automation_pct"]) == (4, 50.0)
    assert [r["count"] for r in ai["by_level"]] == [2, 0, 0, 1, 1]
    assert (ai["llm_calls"], ai["llm_failures"], ai["invalid_outputs"]) == (3, 1, 1)
    assert (ai["pending_reviews"], ai["reviewed"], ai["corrected"]) == (1, 1, 1)
    assert ai["latency_ms"]["median"] == 200.0 and ai["estimated_cost"] == Decimal("0.003")
    assert metrics.ai_metrics(DAY, DAY, channel="WHATSAPP")["runs"] == 0


def test_default_period():
    assert metrics.default_period(date(2026, 10, 30)) == (date(2026, 10, 1), date(2026, 10, 30))


# --- Vista (CONTRACT-017) -------------------------------------------------------------------


def test_view_supervisor_only(client, make_user):
    url = reverse("helpdesk:metrics")
    for role in ("Usuario", "Agente", "Administrador"):
        client.force_login(make_user(role, role=role))
        assert client.get(url).status_code == 403
    client.force_login(make_user("sup", role="Supervisor"))
    r = client.get(url)
    assert r.status_code == 200 and r.context["metrics"]["total"] == 0
    assert r.context["period"]["date_to"] == timezone.localdate()


def test_view_filters_and_errors(client, make_user, data):
    client.force_login(make_user("sup", role="Supervisor"))
    url = reverse("helpdesk:metrics")
    r = client.get(url, {"date_from": "2026-10-05", "date_to": "2026-10-05", "channel": "WEB"})
    assert r.context["metrics"]["total"] == 3
    bad = client.get(url, {"date_from": "2026-10-06", "date_to": "2026-10-05"})
    assert bad.context["metrics"] is None and "date_to" in bad.context["form"].errors
    long = client.get(url, {"date_from": "2025-01-01", "date_to": "2026-10-05"})
    assert long.context["metrics"] is None
    only_from = client.get(url, {"date_from": "2026-10-05"})
    assert only_from.context["period"]["date_from"] == date(2026, 10, 5)
