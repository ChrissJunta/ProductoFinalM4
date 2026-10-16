"""ConversationService (SPEC §33, BE-T05): mensajes del ticket e histórico omnicanal.

Web y WhatsApp escriben en el mismo ticket: cada mensaje del usuario se asocia
a su `Conversation` del canal correspondiente, y el histórico del ticket los
muestra juntos en orden cronológico (SPEC §14).
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.roles import Role, get_role

from . import queries, workflow
from .models import Conversation, Ticket, TicketMessage
from .tickets import TicketService

S = Ticket.Status
CLOSED_FOR_MESSAGES = {S.CLOSED, S.CANCELLED}


class MessageError(workflow.TransitionError):
    message = "No fue posible enviar el mensaje."


class MessageForbidden(workflow.TransitionForbidden):
    pass


def get_conversation(user, channel=Ticket.Channel.WEB):
    """Conversación activa del usuario en el canal (una por canal)."""
    conversation, _ = Conversation.objects.get_or_create(user=user, channel=channel, is_active=True)
    return conversation


def sender_type_for(ticket, user):
    """USER si es el solicitante; AGENT si es personal de atención con acceso al ticket."""
    if ticket.user_id == user.pk:
        return TicketMessage.SenderType.USER
    role = get_role(user)
    if role == Role.SUPERVISOR or (role == Role.AGENTE and queries.can_view_ticket(user, ticket)):
        return TicketMessage.SenderType.AGENT
    return None  # Administrador y terceros no escriben en tickets (ADR-023)


def can_reply(ticket, user):
    return ticket.status not in CLOSED_FOR_MESSAGES and sender_type_for(ticket, user) is not None


@transaction.atomic
def add_message(
    ticket,
    author,
    content,
    *,
    attachment=None,
    request_info=False,
    channel=Ticket.Channel.WEB,
    external_message_id="",
):
    """Registra un mensaje y aplica sus efectos sobre el ticket.

    - Primera respuesta del personal → `first_response_at`.
    - Respuesta del solicitante en WAITING_USER → IN_PROGRESS (§32.1 fila 8).
    - `request_info` (solo personal) → mensaje de solicitud e IN_PROGRESS → WAITING_USER.
    """
    ticket = Ticket.objects.select_for_update(of=("self",)).get(pk=ticket.pk)
    sender_type = sender_type_for(ticket, author)
    if sender_type is None:
        raise MessageForbidden()
    if ticket.status in CLOSED_FOR_MESSAGES:
        raise MessageError("El ticket está cerrado: reábralo para continuar la conversación.")
    content = (content or "").strip()
    if not content:
        raise MessageError("El mensaje no puede estar vacío.")
    is_staff = sender_type == TicketMessage.SenderType.AGENT
    if request_info and not is_staff:
        raise MessageForbidden()

    conversation = None
    if not is_staff:
        conversation = get_conversation(author, channel)
        conversation.active_ticket = ticket
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=["active_ticket", "last_message_at"])

    kind = TicketMessage.MessageType
    message = TicketMessage.objects.create(
        ticket=ticket,
        conversation=conversation,
        sender_type=sender_type,
        sender=author,
        message_type=kind.INFO_REQUEST if request_info else kind.TEXT,
        content=content,
        external_message_id=external_message_id,
    )
    if attachment is not None:
        TicketService.add_attachment(ticket, attachment, uploaded_by=author, message=message)

    if is_staff and ticket.first_response_at is None:
        ticket.first_response_at = message.created_at
    ticket.save(update_fields=["first_response_at", "updated_at"])

    if is_staff:
        # Ticket nacido en WhatsApp o Telegram: la respuesta del personal sale por ese canal.
        from apps.integrations.telegram.processing import notify_ticket_reply as notify_telegram
        from apps.integrations.whatsapp.processing import notify_ticket_reply

        notify_ticket_reply(message)
        notify_telegram(message)
    if request_info:
        workflow.transition(ticket, S.WAITING_USER, actor=author, reason="Solicitud de información")
    elif not is_staff and ticket.status == S.WAITING_USER:
        workflow.transition(ticket, S.IN_PROGRESS, actor=author, reason="El usuario respondió.")
    return message


def timeline(ticket):
    """Mensajes y cambios de estado del ticket, en orden cronológico (SPEC §14, FE-005)."""
    messages = (
        ticket.messages.select_related("sender", "conversation")
        .prefetch_related("attachments")
        .all()
    )
    history = ticket.status_history.select_related("actor").all()
    items = [
        {"kind": "message", "created_at": m.created_at, "message": m, "channel": m.channel}
        for m in messages
    ] + [{"kind": "status", "created_at": h.created_at, "entry": h} for h in history]
    return sorted(items, key=lambda item: item["created_at"])
