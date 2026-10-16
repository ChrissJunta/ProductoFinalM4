"""CONTRACT-023: aviso emergente al personal cuando llega un ticket por Telegram."""

import time

import pytest
from django.urls import reverse

from apps.accounts.middleware import BACKGROUND_HEADER, LAST_ACTIVITY_KEY
from apps.helpdesk.models import Area, Ticket
from apps.helpdesk.tickets import TicketService

pytestmark = pytest.mark.django_db

FEED = reverse("helpdesk:new_tickets_feed")
TELEGRAM = Ticket.Channel.TELEGRAM


def telegram_ticket(user, subject="Certificado de matrícula", channel=TELEGRAM):
    return TicketService.create(user=user, subject=subject, description="d", channel=channel)


def poll(client, after=None):
    params = {} if after is None else {"after": after}
    return client.get(FEED, params, headers={BACKGROUND_HEADER: "1"})


def test_first_poll_only_returns_the_starting_point(client, make_user):
    old = telegram_ticket(make_user("ana", role="Usuario"))
    client.force_login(make_user("sup", role="Supervisor"))
    data = poll(client).json()
    assert data == {"last_id": old.pk, "tickets": []}


def test_new_telegram_ticket_is_announced(client, make_user):
    student = make_user("ana", role="Usuario", first_name="Ana", last_name="Paz")
    client.force_login(make_user("sup", role="Supervisor"))
    start = poll(client).json()["last_id"]
    telegram_ticket(student, channel=Ticket.Channel.WEB)  # la web no avisa
    ticket = telegram_ticket(student)
    data = poll(client, start).json()
    assert data["last_id"] == ticket.pk
    assert data["tickets"] == [
        {
            "code": ticket.ticket_code,
            "subject": "Certificado de matrícula",
            "channel": "Telegram",
            "priority": ticket.get_priority_display(),
            "user": "Ana Paz",
            "created_at": ticket.created_at.isoformat(),
            "url": reverse("helpdesk:ticket_detail", args=[ticket.ticket_code]),
        }
    ]
    assert poll(client, data["last_id"]).json()["tickets"] == []


def test_agent_only_sees_tickets_of_their_areas(client, make_user):
    agent = make_user("tomas", role="Agente")
    client.force_login(agent)
    start = poll(client).json()["last_id"]
    mine, other = Area.objects.all()[:2]
    other.agents.add(agent)
    ticket = telegram_ticket(make_user("ana", role="Usuario"))
    Ticket.objects.filter(pk=ticket.pk).update(assigned_area=mine)
    assert poll(client, start).json()["tickets"] == []
    mine.agents.add(agent)
    assert [t["code"] for t in poll(client, start).json()["tickets"]] == [ticket.ticket_code]


def test_channels_are_configurable(client, make_user, settings):
    settings.NEW_TICKET_ALERT_CHANNELS = ["TELEGRAM", "WHATSAPP"]
    client.force_login(make_user("sup", role="Supervisor"))
    start = poll(client).json()["last_id"]
    telegram_ticket(make_user("ana", role="Usuario"), channel=Ticket.Channel.WHATSAPP)
    assert poll(client, start).json()["tickets"][0]["channel"] == "WhatsApp"


def test_bad_after_and_limit(client, make_user):
    client.force_login(make_user("sup", role="Supervisor"))
    student = make_user("ana", role="Usuario")
    for n in range(7):
        telegram_ticket(student, subject=f"Solicitud {n}")
    assert poll(client, "x").json()["tickets"] == []
    tickets = poll(client, 0).json()["tickets"]
    assert [t["subject"] for t in tickets] == [f"Solicitud {n}" for n in range(6, 1, -1)]


def test_students_cannot_poll(client, make_user):
    client.force_login(make_user("ana", role="Usuario"))
    assert poll(client).status_code == 403
    client.logout()
    assert poll(client).status_code == 302


def test_popup_script_only_for_staff(client, make_user):
    client.force_login(make_user("ana", role="Usuario"))
    assert b"mesa-ticket-alerts" not in client.get(reverse("accounts:home")).content
    client.force_login(make_user("tomas", role="Agente"))
    html = client.get(reverse("accounts:home")).content.decode()
    assert f'data-feed-url="{FEED}"' in html and 'data-poll-seconds="15"' in html
    assert "js/new-ticket-alerts.js" in html


def test_polling_does_not_keep_idle_session_alive(client, make_user, settings):
    settings.SESSION_IDLE_TIMEOUT = 600
    client.force_login(make_user("sup", role="Supervisor"))
    session = client.session
    stale = int(time.time()) - 300
    session[LAST_ACTIVITY_KEY] = stale
    session.save()
    assert poll(client).status_code == 200
    assert client.session[LAST_ACTIVITY_KEY] == stale
    session = client.session
    session[LAST_ACTIVITY_KEY] = int(time.time()) - 700
    session.save()
    assert poll(client).status_code == 302  # vencida: el script deja de consultar
