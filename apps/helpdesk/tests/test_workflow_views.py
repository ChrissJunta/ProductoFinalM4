"""Vistas de acciones de estado (CONTRACT-006)."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.helpdesk.models import Area, Ticket
from apps.helpdesk.tickets import TicketService

pytestmark = pytest.mark.django_db

S = Ticket.Status


@pytest.fixture
def owner(make_user):
    return make_user("owner", role="Usuario")


@pytest.fixture
def agent(make_user):
    return make_user("agent", role="Agente")


@pytest.fixture
def ticket(owner, agent):
    t = TicketService.create(user=owner, subject="s", description="d")
    Ticket.objects.filter(pk=t.pk).update(
        status=S.IN_PROGRESS, assigned_user=agent, assigned_area=Area.objects.get(code="IT")
    )
    t.refresh_from_db()
    return t


def _messages(response):
    return [str(m) for m in response.wsgi_request._messages]


def test_generic_status_endpoint(client, agent, ticket):
    client.force_login(agent)
    response = client.post(
        reverse("helpdesk:ticket_status", args=[ticket.ticket_code]),
        {"to_status": "WAITING_USER", "version": ticket.version},
    )
    assert response.status_code == 302
    ticket.refresh_from_db()
    assert ticket.status == S.WAITING_USER
    assert _messages(response) == [
        f"Ticket {ticket.ticket_code}: estado cambiado a Esperando usuario."
    ]


def test_named_resolve_with_reason(client, agent, ticket):
    client.force_login(agent)
    client.post(
        reverse("helpdesk:ticket_resolve", args=[ticket.ticket_code]),
        {"version": ticket.version, "reason": "Se corrigió la nota."},
    )
    ticket.refresh_from_db()
    assert ticket.status == S.RESOLVED
    assert ticket.status_history.last().reason == "Se corrigió la nota."


def test_missing_reason_shows_error(client, agent, ticket):
    client.force_login(agent)
    response = client.post(
        reverse("helpdesk:ticket_resolve", args=[ticket.ticket_code]), {"version": ticket.version}
    )
    assert response.status_code == 302
    assert _messages(response) == ["Debe indicar un motivo para este cambio de estado."]
    ticket.refresh_from_db()
    assert ticket.status == S.IN_PROGRESS


def test_stale_version_message(client, agent, ticket):
    client.force_login(agent)
    response = client.post(
        reverse("helpdesk:ticket_status", args=[ticket.ticket_code]),
        {"to_status": "WAITING_USER", "version": ticket.version - 1 or 99},
    )
    assert _messages(response) == ["El ticket fue actualizado por otro usuario."]


def test_role_not_allowed_is_403(client, owner, ticket):
    client.force_login(owner)
    response = client.post(
        reverse("helpdesk:ticket_resolve", args=[ticket.ticket_code]),
        {"version": ticket.version, "reason": "x"},
    )
    assert response.status_code == 403


def test_other_user_cannot_touch_ticket(client, make_user, ticket):
    client.force_login(make_user("intruso", role="Usuario"))
    response = client.post(
        reverse("helpdesk:ticket_cancel", args=[ticket.ticket_code]),
        {"version": ticket.version, "reason": "x"},
    )
    assert response.status_code == 404  # ticket no visible: no se revela que existe


def test_agent_from_other_area_cannot_touch_ticket(client, make_user, ticket):
    other = make_user("finanzas", role="Agente")
    Area.objects.get(code="FINANCE").agents.add(other)
    client.force_login(other)
    response = client.post(
        reverse("helpdesk:ticket_status", args=[ticket.ticket_code]),
        {"to_status": "WAITING_USER", "version": ticket.version},
    )
    assert response.status_code == 404


def test_confirm_and_reject_require_resolved(client, owner, ticket):
    """«Rechazar resolución» no puede usarse para otra transición hacia IN_PROGRESS."""
    Ticket.objects.filter(pk=ticket.pk).update(status=S.WAITING_USER)
    ticket.refresh_from_db()
    client.force_login(owner)
    response = client.post(
        reverse("helpdesk:ticket_reject_resolution", args=[ticket.ticket_code]),
        {"version": ticket.version, "reason": "x"},
    )
    assert _messages(response) == ["El ticket no admite ese cambio de estado."]
    ticket.refresh_from_db()
    assert ticket.status == S.WAITING_USER


def test_owner_confirms_resolution(client, owner, ticket):
    Ticket.objects.filter(pk=ticket.pk).update(status=S.RESOLVED)
    ticket.refresh_from_db()
    client.force_login(owner)
    client.post(
        reverse("helpdesk:ticket_confirm", args=[ticket.ticket_code]), {"version": ticket.version}
    )
    ticket.refresh_from_db()
    assert ticket.status == S.CLOSED


@pytest.mark.parametrize(
    "data",
    [
        {"to_status": "NOPE", "version": 1},
        {"to_status": "CLOSED"},
        {"to_status": "CLOSED", "version": "x"},
    ],
)
def test_bad_request(client, agent, ticket, data):
    client.force_login(agent)
    url = reverse("helpdesk:ticket_status", args=[ticket.ticket_code])
    assert client.post(url, data).status_code == 400


def test_safe_next_is_respected_and_external_ignored(client, agent, ticket):
    client.force_login(agent)
    url = reverse("helpdesk:ticket_status", args=[ticket.ticket_code])
    r1 = client.post(
        url, {"to_status": "WAITING_USER", "version": ticket.version, "next": "/inicio/"}
    )
    assert r1.url == "/inicio/"
    ticket.refresh_from_db()
    r2 = client.post(
        url,
        {"to_status": "IN_PROGRESS", "version": ticket.version, "next": "https://evil.example/"},
    )
    assert r2.url == reverse("helpdesk:ticket_detail", args=[ticket.ticket_code])  # CR-005


def test_get_not_allowed_and_login_required(client, agent, ticket):
    url = reverse("helpdesk:ticket_resolve", args=[ticket.ticket_code])
    assert client.post(url, {"version": 1}).status_code == 302  # a login
    client.force_login(agent)
    assert client.get(url).status_code == 405


def test_unknown_ticket_404(client, agent):
    client.force_login(agent)
    url = reverse("helpdesk:ticket_status", args=["HD-2026-999999"])
    assert client.post(url, {"to_status": "CLOSED", "version": 1}).status_code == 404


def test_csrf_required(agent, ticket):
    client = Client(enforce_csrf_checks=True)
    client.force_login(agent)
    url = reverse("helpdesk:ticket_status", args=[ticket.ticket_code])
    assert client.post(url, {"to_status": "WAITING_USER", "version": 1}).status_code == 403
