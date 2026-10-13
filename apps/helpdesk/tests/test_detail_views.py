"""Vistas de BE-T05/BE-T06 y del inicio: CONTRACT-010 a CONTRACT-013."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.helpdesk.models import Area, Ticket
from apps.helpdesk.tickets import TicketService

from .factories import upload

pytestmark = pytest.mark.django_db

S = Ticket.Status


@pytest.fixture
def p(make_user):
    agent = make_user("agent", role="Agente")
    Area.objects.get(code="IT").agents.add(agent)
    return {
        "owner": make_user("owner", role="Usuario"),
        "agent": agent,
        "sup": make_user("sup", role="Supervisor"),
        "other": make_user("other", role="Usuario"),
    }


@pytest.fixture
def ticket(p):
    t = TicketService.create(user=p["owner"], subject="Nota", description="d", attachment=upload())
    Ticket.objects.filter(pk=t.pk).update(
        status=S.IN_PROGRESS, assigned_area=Area.objects.get(code="IT"), assigned_user=p["agent"]
    )
    t.refresh_from_db()
    return t


def detail(client, ticket):
    return client.get(reverse("helpdesk:ticket_detail", args=[ticket.ticket_code]))


# --- Detalle (CONTRACT-010) -------------------------------------------------------------


def test_detail_context_for_agent(client, p, ticket):
    client.force_login(p["agent"])
    r = detail(client, ticket)
    assert r.status_code == 200
    ctx = r.context
    assert ctx["ticket"] == ticket and ctx["sla"].state in ("OK", "WARNING", "BREACHED")
    assert ctx["is_owner"] is False and ctx["can_reply"] is True and ctx["can_request_info"] is True
    targets = {a["target"]: a for a in ctx["actions"]}
    assert set(targets) == {S.WAITING_USER, S.ESCALATED, S.RESOLVED}
    assert (
        targets[S.RESOLVED]["url"].endswith("/resolve/") and targets[S.RESOLVED]["reason_required"]
    )
    assert targets[S.WAITING_USER]["generic"] is True
    assert ctx["assign"]["can_assign"] and ctx["assign"]["current_assignee_id"] == p["agent"].pk
    assert [i["kind"] for i in ctx["timeline"]][0] == "status"
    assert list(ctx["attachments"]) == list(ticket.attachments.all())


def test_detail_context_for_owner(client, p, ticket):
    Ticket.objects.filter(pk=ticket.pk).update(status=S.RESOLVED)
    client.force_login(p["owner"])
    ctx = detail(client, ticket).context
    labels = {a["label"] for a in ctx["actions"]}
    assert labels == {"Confirmar solución", "Rechazar solución"}
    assert ctx["is_owner"] and ctx["can_reply"] and not ctx["can_request_info"]
    assert ctx["assign"]["can_assign"] is False


def test_detail_hidden_from_others(client, p, ticket):
    client.force_login(p["other"])
    assert detail(client, ticket).status_code == 404


def test_detail_requires_login(client, ticket):
    assert detail(client, ticket).status_code == 302


# --- Mensajes (CONTRACT-011) --------------------------------------------------------------


def test_post_message_with_attachment(client, p, ticket):
    client.force_login(p["owner"])
    r = client.post(
        reverse("helpdesk:ticket_message", args=[ticket.ticket_code]),
        {"content": "Adjunto comprobante", "attachment": upload("c.pdf")},
    )
    assert r.status_code == 302 and r.url == reverse(
        "helpdesk:ticket_detail", args=[ticket.ticket_code]
    )
    m = ticket.messages.get()
    assert m.content == "Adjunto comprobante" and m.attachments.count() == 1


def test_post_message_request_info(client, p, ticket):
    client.force_login(p["agent"])
    client.post(
        reverse("helpdesk:ticket_message", args=[ticket.ticket_code]),
        {"content": "¿Su número de cédula?", "request_info": "on"},
    )
    ticket.refresh_from_db()
    assert ticket.status == S.WAITING_USER


@pytest.mark.parametrize(
    "data,error",
    [
        ({"content": ""}, "Este campo es obligatorio."),
        ({"content": "x", "attachment": upload("x.exe", b"MZ")}, "Tipo de archivo no permitido"),
    ],
)
def test_post_message_errors(client, p, ticket, data, error):
    client.force_login(p["owner"])
    r = client.post(reverse("helpdesk:ticket_message", args=[ticket.ticket_code]), data)
    msgs = [str(m) for m in r.wsgi_request._messages]
    assert len(msgs) == 1 and msgs[0].startswith(error)
    assert not ticket.messages.exists()


def test_post_message_on_closed_ticket(client, p, ticket):
    Ticket.objects.filter(pk=ticket.pk).update(status=S.CLOSED)
    client.force_login(p["owner"])
    r = client.post(reverse("helpdesk:ticket_message", args=[ticket.ticket_code]), {"content": "x"})
    assert [str(m) for m in r.wsgi_request._messages] == [
        "El ticket está cerrado: reábralo para continuar la conversación."
    ]


def test_owner_cannot_request_info_via_post(client, p, ticket):
    client.force_login(p["owner"])
    r = client.post(
        reverse("helpdesk:ticket_message", args=[ticket.ticket_code]),
        {"content": "x", "request_info": "on"},
    )
    assert r.status_code == 403


def test_message_requires_csrf(p, ticket):
    c = Client(enforce_csrf_checks=True)
    c.force_login(p["owner"])
    r = c.post(reverse("helpdesk:ticket_message", args=[ticket.ticket_code]), {"content": "x"})
    assert r.status_code == 403


# --- Asignación (CONTRACT-012) -------------------------------------------------------------


def test_assign_via_post(client, p, make_user):
    t = TicketService.create(user=p["owner"], subject="s", description="d")
    client.force_login(p["sup"])
    r = client.post(
        reverse("helpdesk:ticket_assign", args=[t.ticket_code]),
        {"version": t.version, "area": Area.objects.get(code="IT").pk, "assignee": p["agent"].pk},
    )
    assert r.status_code == 302
    t.refresh_from_db()
    assert (t.assigned_user, t.status) == (p["agent"], S.ASSIGNED)
    assert [str(m) for m in r.wsgi_request._messages] == [f"Ticket {t.ticket_code} asignado."]


def test_assign_errors(client, p, ticket):
    client.force_login(p["sup"])
    url = reverse("helpdesk:ticket_assign", args=[ticket.ticket_code])
    it = Area.objects.get(code="IT").pk
    assert client.post(url, {"version": 1}).status_code == 400
    assert client.post(url, {"version": 1, "area": it, "assignee": 99999}).status_code == 400
    r = client.post(url, {"version": 99, "area": it})
    assert [str(m) for m in r.wsgi_request._messages] == [
        "El ticket fue actualizado por otro usuario."
    ]


def test_assign_forbidden_for_owner(client, p, ticket):
    client.force_login(p["owner"])
    r = client.post(
        reverse("helpdesk:ticket_assign", args=[ticket.ticket_code]),
        {"version": ticket.version, "area": Area.objects.get(code="IT").pk},
    )
    assert r.status_code == 403


# --- Inicio (CONTRACT-013) ---------------------------------------------------------------


def test_home_dashboard_for_user(client, p, ticket):
    for i in range(6):
        TicketService.create(user=p["owner"], subject=f"t{i}", description="d")
    TicketService.create(user=p["other"], subject="ajeno", description="d")
    client.force_login(p["owner"])
    ctx = client.get(reverse("accounts:home")).context
    assert len(ctx["recent_rows"]) == 5
    assert all(r["ticket"].user == p["owner"] for r in ctx["recent_rows"])
    assert ctx["summary"] == {"open": 7, "waiting_user": 0, "resolved": 0}


def test_home_dashboard_for_agent_shows_own_work(client, p, ticket):
    TicketService.create(user=p["other"], subject="cola", description="d")  # visible, no asignado
    client.force_login(p["agent"])
    ctx = client.get(reverse("accounts:home")).context
    assert [r["ticket"].subject for r in ctx["recent_rows"]] == ["Nota"]
