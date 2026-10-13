"""BE-T05: mensajes, efectos sobre el ticket e histórico omnicanal."""

import pytest
from django.core.exceptions import ValidationError

from apps.helpdesk import conversations, workflow
from apps.helpdesk.models import Area, Conversation, Ticket, TicketMessage
from apps.helpdesk.tickets import TicketService

from .factories import upload

pytestmark = pytest.mark.django_db

S = Ticket.Status
MT = TicketMessage.MessageType


@pytest.fixture
def people(make_user):
    agent = make_user("agent", role="Agente")
    Area.objects.get(code="IT").agents.add(agent)
    return {
        "owner": make_user("owner", role="Usuario"),
        "agent": agent,
        "sup": make_user("sup", role="Supervisor"),
        "admin": make_user("admin", role="Administrador"),
        "other": make_user("other", role="Usuario"),
    }


@pytest.fixture
def ticket(people):
    t = TicketService.create(user=people["owner"], subject="s", description="d")
    Ticket.objects.filter(pk=t.pk).update(
        status=S.IN_PROGRESS,
        assigned_area=Area.objects.get(code="IT"),
        assigned_user=people["agent"],
    )
    t.refresh_from_db()
    return t


def test_owner_message_goes_to_web_conversation(ticket, people):
    m = conversations.add_message(ticket, people["owner"], "  Hola  ")
    assert (m.sender_type, m.content, m.channel) == ("USER", "Hola", "WEB")
    conv = Conversation.objects.get(user=people["owner"], channel="WEB")
    assert m.conversation == conv
    assert conv.active_ticket == ticket and conv.last_message_at is not None


def test_staff_message_sets_first_response_once(ticket, people):
    first = conversations.add_message(ticket, people["agent"], "Estamos revisando")
    ticket.refresh_from_db()
    assert first.sender_type == "AGENT" and first.conversation is None
    assert ticket.first_response_at == first.created_at
    conversations.add_message(ticket, people["sup"], "Seguimiento")
    ticket.refresh_from_db()
    assert ticket.first_response_at == first.created_at


def test_owner_message_does_not_count_as_first_response(ticket, people):
    conversations.add_message(ticket, people["owner"], "Hola")
    ticket.refresh_from_db()
    assert ticket.first_response_at is None


def test_request_info_moves_to_waiting_and_reply_resumes(ticket, people):
    m = conversations.add_message(
        ticket, people["agent"], "Envíe su comprobante", request_info=True
    )
    ticket.refresh_from_db()
    assert m.message_type == MT.INFO_REQUEST
    assert ticket.status == S.WAITING_USER

    conversations.add_message(ticket, people["owner"], "Adjunto", attachment=upload())
    ticket.refresh_from_db()
    assert ticket.status == S.IN_PROGRESS  # §32.1 fila 8
    entry = ticket.status_history.last()
    assert (entry.actor, entry.reason) == (people["owner"], "El usuario respondió.")


def test_message_attachment_is_linked(ticket, people):
    m = conversations.add_message(ticket, people["owner"], "Va el PDF", attachment=upload("r.pdf"))
    att = m.attachments.get()
    assert att.ticket == ticket and att.original_name == "r.pdf"


def test_invalid_attachment_rolls_back_message(ticket, people):
    with pytest.raises(ValidationError):
        conversations.add_message(ticket, people["owner"], "x", attachment=upload("a.exe", b"MZ"))
    assert not TicketMessage.objects.exists()


@pytest.mark.parametrize("who", ["admin", "other"])
def test_forbidden_authors(ticket, people, who):
    with pytest.raises(conversations.MessageForbidden):
        conversations.add_message(ticket, people[who], "x")


def test_agent_outside_area_cannot_write(ticket, make_user):
    outsider = make_user("fin", role="Agente")
    Area.objects.get(code="FINANCE").agents.add(outsider)
    with pytest.raises(conversations.MessageForbidden):
        conversations.add_message(ticket, outsider, "x")


def test_owner_cannot_request_info(ticket, people):
    with pytest.raises(conversations.MessageForbidden):
        conversations.add_message(ticket, people["owner"], "x", request_info=True)


@pytest.mark.parametrize("status", [S.CLOSED, S.CANCELLED])
def test_no_messages_on_closed_tickets(ticket, people, status):
    Ticket.objects.filter(pk=ticket.pk).update(status=status)
    with pytest.raises(conversations.MessageError):
        conversations.add_message(ticket, people["owner"], "x")
    assert not conversations.can_reply(Ticket.objects.get(pk=ticket.pk), people["owner"])


def test_empty_message_rejected(ticket, people):
    with pytest.raises(conversations.MessageError):
        conversations.add_message(ticket, people["owner"], "   ")


def test_resolution_is_published_in_conversation(ticket, people):
    workflow.transition(ticket, S.RESOLVED, actor=people["agent"], reason="Nota corregida")
    m = ticket.messages.get()
    assert (m.message_type, m.content, m.sender) == (
        MT.RESOLUTION,
        "Nota corregida",
        people["agent"],
    )
    ticket.refresh_from_db()
    assert ticket.first_response_at is not None


def test_whatsapp_and_web_share_ticket_history(ticket, people):
    """Criterio de aceptación BE-T05: Web y WhatsApp comparten ticket e histórico."""
    conversations.add_message(ticket, people["owner"], "Desde la web")
    conversations.add_message(ticket, people["owner"], "Desde WhatsApp", channel="WHATSAPP")
    conversations.add_message(ticket, people["agent"], "Respuesta del agente")
    items = [i for i in conversations.timeline(ticket) if i["kind"] == "message"]
    assert [(i["message"].content, i["channel"]) for i in items] == [
        ("Desde la web", "WEB"),
        ("Desde WhatsApp", "WHATSAPP"),
        ("Respuesta del agente", "WEB"),
    ]
    assert Conversation.objects.filter(user=people["owner"]).count() == 2


def test_timeline_mixes_messages_and_status_in_order(ticket, people):
    conversations.add_message(ticket, people["agent"], "Necesito datos", request_info=True)
    kinds = [i["kind"] for i in conversations.timeline(ticket)]
    assert kinds[0] == "status"  # creación (— → NEW)
    assert kinds[-2:] == ["message", "status"]  # mensaje y luego IN_PROGRESS → WAITING_USER


def test_external_message_id_is_unique(ticket, people):
    from django.db import IntegrityError

    conversations.add_message(
        ticket, people["owner"], "a", channel="WHATSAPP", external_message_id="wamid.1"
    )
    with pytest.raises(IntegrityError):
        conversations.add_message(
            ticket, people["owner"], "b", channel="WHATSAPP", external_message_id="wamid.1"
        )
