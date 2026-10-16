"""Avisos proactivos por Telegram (ADR-081): el usuario con el chat vinculado recibe los
cambios de estado y los mensajes del personal de TODAS sus solicitudes.

No se avisa lo que hace el propio usuario ni el paso interno «Clasificado». La solicitud
de información llega como mensaje del personal (no se repite como cambio de estado).
"""

from apps.helpdesk.models import Ticket, TicketMessage

from . import processing, resolution

S = Ticket.Status
PORTAL_HINT = "Responde desde el portal (Mis tickets)."


def _area(ticket):
    return ticket.assigned_area.name if ticket.assigned_area_id else "Atención General"


def status_text(ticket, previous, target, reason):
    head = f"[{ticket.ticket_code}] «{ticket.subject}»"
    reason = (reason or "").strip()
    if target == S.ASSIGNED:
        return f"{head}: tu solicitud fue asignada al área {_area(ticket)}."
    if target == S.IN_PROGRESS:
        if previous == S.RESOLVED:
            return f"{head}: retomamos la atención de tu solicitud."
        return f"{head}: estamos atendiendo tu solicitud."
    if target == S.ESCALATED:
        return f"{head}: tu solicitud fue escalada para darle prioridad."
    if target == S.RESOLVED:
        detail = f" {reason}" if reason else ""
        return (
            f"{head}: tu solicitud fue resuelta.{detail}\n"
            "¿Quedó resuelta? Responde con los botones (o desde el portal, Mis tickets)."
        )
    if target == S.CLOSED:
        return f"{head}: tu solicitud quedó cerrada." + (f" {reason}" if reason else "")
    if target == S.CANCELLED:
        return f"{head}: tu solicitud fue cancelada." + (f" Motivo: {reason}" if reason else "")
    if target == S.REOPENED:
        return f"{head}: tu solicitud fue reabierta."
    return None  # NEW, CLASSIFIED (interno) y WAITING_USER (llega como mensaje del personal)


def _linked_owner(ticket, actor):
    user = ticket.user
    if not user.is_active or not user.is_telegram_linked:
        return None
    if actor is not None and actor.pk == user.pk:  # lo hizo el propio usuario
        return None
    return user


def notify_status_change(ticket, previous, target, *, actor=None, reason=""):
    """Lo llama `helpdesk.workflow.transition` en cada cambio de estado."""
    user = _linked_owner(ticket, actor)
    text = status_text(ticket, previous, target, reason) if user else None
    if text is None:
        return None
    # Resuelta: botones para confirmar (cierra) o rechazar (vuelve a atención), ADR-082.
    markup = resolution.buttons(ticket) if target == S.RESOLVED else None
    return processing.enqueue_text(user.telegram_chat_id, text[:4096], reply_markup=markup)


def notify_staff_message(message):
    """Mensaje del personal en cualquier solicitud del usuario vinculado."""
    if message.sender_type != TicketMessage.SenderType.AGENT:
        return None
    ticket = message.ticket
    user = _linked_owner(ticket, message.sender)
    if user is None:
        return None
    text = f"[{ticket.ticket_code}] {message.content}"
    if ticket.channel != Ticket.Channel.TELEGRAM:  # se contesta donde nació la solicitud
        text += f"\n{PORTAL_HINT}"
    item = processing.enqueue_text(user.telegram_chat_id, text[:4096])
    # Archivos del mensaje (p. ej. el certificado de Secretaría): se envían como documentos.
    for attachment in message.attachments.all():
        processing.enqueue(
            user.telegram_chat_id,
            {
                "type": "document",
                "attachment_id": attachment.pk,
                "caption": f"[{ticket.ticket_code}] {attachment.original_name}",
            },
        )
    return item
