"""Confirmar o rechazar una solución desde Telegram (ADR-082).

Cuando una solicitud pasa a «Resuelto», el aviso trae dos botones. «Sí, está resuelto»
cierra la solicitud en el acto (fila 14 de §32.1, actor = el propio usuario). «No, sigue
el problema» pide el motivo (obligatorio, fila 15): el siguiente mensaje del chat se usa
como motivo y la solicitud vuelve a «En proceso».

Solo actúa el dueño de la solicitud con el chat vinculado y solo si sigue «Resuelto».
"""

from django.core.cache import cache

from apps.helpdesk import workflow
from apps.helpdesk.models import Ticket

from . import linking

CONFIRM, REJECT = "close", "reject"
PENDING_SECONDS = 30 * 60
NOT_YOURS = "No encontramos esa solicitud entre las tuyas, o ya no está resuelta."


def buttons(ticket):
    code = ticket.ticket_code
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Sí, está resuelto", "callback_data": f"{CONFIRM}:{code}"},
                {"text": "❌ No, sigue el problema", "callback_data": f"{REJECT}:{code}"},
            ]
        ]
    }


def _pending_key(chat_id):
    return f"telegram:reject:{chat_id}"


def _resolved_ticket(user, code):
    if user is None:
        return None
    return Ticket.objects.filter(user=user, ticket_code=code, status=Ticket.Status.RESOLVED).first()


def handle_button(chat_id, data):
    """Botón pulsado. Devuelve el texto respondido."""
    from .processing import _reply, enqueue

    action, _, code = (data.get("data") or "").partition(":")
    if data.get("callback_id"):  # quita el «cargando» del botón en el celular
        enqueue(chat_id, {"type": "callback_answer", "callback_id": data["callback_id"]})
    user = linking.linked_user(chat_id)
    ticket = _resolved_ticket(user, code)
    if ticket is None or action not in (CONFIRM, REJECT):
        return _reply(chat_id, NOT_YOURS)
    if action == CONFIRM:
        workflow.transition(
            ticket, Ticket.Status.CLOSED, actor=user, reason="Solución confirmada por Telegram."
        )
        return _reply(chat_id, f"¡Gracias! Cerramos tu solicitud {code}.")
    cache.set(_pending_key(chat_id), code, PENDING_SECONDS)
    return _reply(
        chat_id,
        f"Lamentamos que {code} no haya quedado resuelta. Cuéntanos en tu próximo mensaje "
        "qué sigue fallando y la volvemos a atender.",
    )


def take_reject_reason(chat_id, user, text):
    """Si el chat está rechazando una solución, `text` es el motivo. Devuelve la respuesta
    o None si no había un rechazo pendiente."""
    code = cache.get(_pending_key(chat_id))
    if not code:
        return None
    cache.delete(_pending_key(chat_id))
    ticket = _resolved_ticket(user, code)
    if ticket is None:
        return None  # ya no está resuelta: el mensaje sigue su curso normal
    workflow.transition(ticket, Ticket.Status.IN_PROGRESS, actor=user, reason=text[:500])
    return f"Recibido. Retomamos la atención de {code} y te avisaremos por aquí."
