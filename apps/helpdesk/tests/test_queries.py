"""BE-T04: visibilidad por rol, filtros, pestañas y paginación."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.helpdesk import alerts, queries
from apps.helpdesk.models import Alert, Area, Category, Ticket
from apps.helpdesk.tickets import TicketService

pytestmark = pytest.mark.django_db

S = Ticket.Status


@pytest.fixture
def world(make_user):
    """Escenario: dos áreas con sus agentes y tickets de distintos dueños."""
    u = {
        "ana": make_user("ana", role="Usuario"),
        "beto": make_user("beto", role="Usuario"),
        "agent_it": make_user("agent_it", role="Agente"),
        "agent_fin": make_user("agent_fin", role="Agente"),
        "sup": make_user("sup", role="Supervisor"),
        "admin": make_user("admin", role="Administrador"),
    }
    Area.objects.get(code="IT").agents.add(u["agent_it"])
    Area.objects.get(code="FINANCE").agents.add(u["agent_fin"])
    tech, fin = Category.objects.get(code="TECHNICAL"), Category.objects.get(code="FINANCIAL")

    def make(owner, subject, category=None, **update):
        t = TicketService.create(user=owner, subject=subject, description="d", category=category)
        if update:
            Ticket.objects.filter(pk=t.pk).update(**update)
            t.refresh_from_db()
        return t

    t = {
        "ana_it": make(u["ana"], "Ana sin acceso", tech),
        "ana_fin": make(u["ana"], "Ana pago", fin, status=S.IN_PROGRESS),
        "beto_none": make(u["beto"], "Beto sin categoría"),
        "beto_fin_assigned_it": make(
            u["beto"], "Beto deuda", fin, assigned_user=u["agent_it"], status=S.ASSIGNED
        ),
        "beto_closed": make(u["beto"], "Beto cerrado", tech, status=S.CLOSED),
    }
    return u, t


def codes(qs):
    return {t.subject for t in qs}


# --- Visibilidad por rol (criterio de aceptación) ---------------------------------------


@pytest.mark.parametrize(
    "who,expected",
    [
        ("ana", {"Ana sin acceso", "Ana pago"}),
        ("beto", {"Beto sin categoría", "Beto deuda", "Beto cerrado"}),
        # Agente de IT: su área (IT) + asignados a él (aunque sean de Finanzas) + sin área.
        ("agent_it", {"Ana sin acceso", "Beto cerrado", "Beto deuda", "Beto sin categoría"}),
        ("agent_fin", {"Ana pago", "Beto deuda", "Beto sin categoría"}),
        ("sup", "ALL"),
        ("admin", "ALL"),
    ],
)
def test_visibility_by_role(world, who, expected):
    users, tickets = world
    visible = codes(queries.visible_tickets(users[who]))
    if expected == "ALL":
        expected = {t.subject for t in tickets.values()}
    assert visible == expected


def test_agent_without_areas_sees_only_triage_and_assigned(world, make_user):
    users, tickets = world
    lonely = make_user("lonely", role="Agente")
    assert codes(queries.visible_tickets(lonely)) == {"Beto sin categoría"}


def test_agent_sees_own_tickets_even_outside_area(world):
    users, tickets = world
    own = TicketService.create(
        user=users["agent_fin"],
        subject="Mi propio problema",
        description="d",
        category=Category.objects.get(code="TECHNICAL"),
    )
    assert own in queries.visible_tickets(users["agent_fin"])


def test_anonymous_sees_nothing():
    from django.contrib.auth.models import AnonymousUser

    assert not queries.visible_tickets(AnonymousUser()).exists()


def test_no_duplicates_when_several_rules_match(world):
    users, tickets = world
    Area.objects.get(code="FINANCE").agents.add(users["agent_it"])  # asignado + área
    qs = queries.visible_tickets(users["agent_it"])
    assert qs.count() == len(set(qs.values_list("pk", flat=True)))


# --- Filtros ------------------------------------------------------------------------------


def _filter(user, **params):
    qs, applied = queries.apply_filters(queries.visible_tickets(user), params, user)
    return codes(qs), applied


def test_filter_status(world):
    users, _ = world
    assert _filter(users["sup"], status="CLOSED")[0] == {"Beto cerrado"}
    assert "Beto cerrado" not in _filter(users["sup"], status="OPEN")[0]
    assert _filter(users["sup"], status="FINISHED")[0] == {"Beto cerrado"}


def test_filter_priority_category_area(world):
    users, tickets = world
    Ticket.objects.filter(pk=tickets["ana_fin"].pk).update(priority="HIGH")
    fin = Category.objects.get(code="FINANCIAL")
    assert _filter(users["sup"], priority="HIGH")[0] == {"Ana pago"}
    assert _filter(users["sup"], category=str(fin.pk))[0] == {"Ana pago", "Beto deuda"}
    area = Area.objects.get(code="IT")
    assert _filter(users["sup"], area=str(area.pk))[0] == {"Ana sin acceso", "Beto cerrado"}


def test_filter_assignee(world):
    users, _ = world
    assert _filter(users["agent_it"], assignee="me")[0] == {"Beto deuda"}
    assert "Beto deuda" not in _filter(users["sup"], assignee="none")[0]
    assert _filter(users["sup"], assignee=str(users["agent_it"].pk))[0] == {"Beto deuda"}


def test_filter_dates(world):
    users, tickets = world
    old = timezone.now() - timedelta(days=10)
    Ticket.objects.filter(pk=tickets["ana_it"].pk).update(created_at=old)
    today = timezone.localdate().isoformat()
    assert "Ana sin acceso" not in _filter(users["sup"], date_from=today)[0]
    assert _filter(users["sup"], date_to=(old.date()).isoformat())[0] == {"Ana sin acceso"}


def test_filter_sla(world):
    users, tickets = world
    now = timezone.now()
    Ticket.objects.filter(pk=tickets["ana_fin"].pk).update(sla_due_at=now - timedelta(hours=1))
    Ticket.objects.filter(pk=tickets["beto_closed"].pk).update(sla_due_at=now - timedelta(hours=1))
    alerts.open_alert(tickets["ana_it"], Alert.Type.SLA_WARNING, severity="WARNING", message="x")
    assert _filter(users["sup"], sla="BREACHED")[0] == {"Ana pago"}  # el cerrado no cuenta
    assert _filter(users["sup"], sla="WARNING")[0] == {"Ana sin acceso"}


def test_text_search(world):
    users, tickets = world
    assert _filter(users["sup"], q="deuda")[0] == {"Beto deuda"}
    assert _filter(users["sup"], q=tickets["ana_it"].ticket_code)[0] == {"Ana sin acceso"}


def test_invalid_filters_are_ignored(world):
    users, tickets = world
    result, applied = _filter(
        users["sup"],
        status="NOPE",
        priority="X",
        category="abc",
        area="",
        assignee="x",
        date_from="ayer",
        sla="RARO",
        sort="DROP TABLE",
    )
    assert result == {t.subject for t in tickets.values()}
    assert applied == {"sort": "-created_at"}


def test_sorting(world):
    users, _ = world
    qs, _ = queries.apply_filters(
        queries.visible_tickets(users["sup"]), {"sort": "created_at"}, None
    )
    created = [t.created_at for t in qs]
    assert created == sorted(created)


def test_ticket_rows_without_n_plus_one(world, django_assert_max_num_queries):
    users, _ = world
    qs = queries.with_related(queries.visible_tickets(users["sup"]))
    with django_assert_max_num_queries(2):  # tickets + políticas SLA
        rows = queries.ticket_rows(qs)
        [(r["ticket"].category, r["ticket"].assigned_user, r["sla"].state) for r in rows]


# --- Vista de listado (CONTRACT-008) ------------------------------------------------------


def test_ticket_list_for_user(client, world):
    users, _ = world
    client.force_login(users["ana"])
    response = client.get(reverse("helpdesk:ticket_list"))
    assert response.status_code == 200
    ctx = response.context
    assert {r["ticket"].subject for r in ctx["rows"]} == {"Ana sin acceso", "Ana pago"}
    assert {"ticket", "sla"} == set(ctx["rows"][0])
    assert ctx["filters"] == {"sort": "-created_at"}
    assert ("OPEN", "Abiertos") in ctx["status_choices"]


def test_ticket_list_filters_from_querystring(client, world):
    users, _ = world
    client.force_login(users["beto"])
    response = client.get(reverse("helpdesk:ticket_list"), {"status": "CLOSED"})
    assert [r["ticket"].subject for r in response.context["rows"]] == ["Beto cerrado"]
    assert response.context["filters"]["status"] == "CLOSED"


def test_ticket_list_pagination(client, make_user):
    user = make_user("muchos")
    for i in range(queries.PAGE_SIZE + 3):
        TicketService.create(user=user, subject=f"t{i}", description="d")
    client.force_login(user)
    page1 = client.get(reverse("helpdesk:ticket_list"))
    page2 = client.get(reverse("helpdesk:ticket_list"), {"page": 2})
    assert len(page1.context["rows"]) == queries.PAGE_SIZE
    assert len(page2.context["rows"]) == 3
    assert page1.context["page_obj"].has_next()


def test_ticket_list_requires_login(client):
    assert client.get(reverse("helpdesk:ticket_list")).status_code == 302


# --- Bandeja del agente (CONTRACT-009) -------------------------------------------------------


def test_inbox_default_tab_is_mine(client, world):
    users, _ = world
    client.force_login(users["agent_it"])
    response = client.get(reverse("helpdesk:agent_inbox"))
    ctx = response.context
    assert ctx["tab"] == "mine"
    assert [r["ticket"].subject for r in ctx["rows"]] == ["Beto deuda"]
    assert ctx["filters"]["sort"] == "sla_due_at"
    tabs = {t["key"]: t["count"] for t in ctx["tabs"]}
    assert tabs["mine"] == 1
    assert tabs["history"] is None
    assert list(tabs) == [
        "mine",
        "unassigned",
        "in_progress",
        "waiting_user",
        "due_soon",
        "overdue",
        "history",
    ]
    assert set(ctx["assignees"]) == {users["agent_it"], users["agent_fin"]}


@pytest.mark.parametrize(
    "tab,expected",
    [
        ("unassigned", {"Ana sin acceso", "Beto sin categoría"}),
        ("history", {"Beto cerrado"}),
        ("in_progress", set()),
        ("desconocida", {"Beto deuda"}),  # vuelve a «mine»
    ],
)
def test_inbox_tabs(client, world, tab, expected):
    users, _ = world
    client.force_login(users["agent_it"])
    response = client.get(reverse("helpdesk:agent_inbox"), {"tab": tab})
    assert {r["ticket"].subject for r in response.context["rows"]} == expected


def test_inbox_extra_filters_override_tab(client, world):
    users, _ = world
    client.force_login(users["sup"])
    response = client.get(
        reverse("helpdesk:agent_inbox"), {"tab": "unassigned", "status": "IN_PROGRESS"}
    )
    assert {r["ticket"].subject for r in response.context["rows"]} == {"Ana pago"}


@pytest.mark.parametrize("role", ["Usuario", "Administrador"])
def test_inbox_forbidden_for_other_roles(client, make_user, role):
    client.force_login(make_user("x", role=role))
    assert client.get(reverse("helpdesk:agent_inbox")).status_code == 403
