"""Procesamiento del bot de Telegram (ADR-080), separado de WhatsApp.

- `ingest_update(update)`: guarda cada mensaje privado en IntegrationInbox
  (provider=TELEGRAM, idempotente por `update_id`).
- `process_inbox()` / `process_outbox()`: solo elementos de Telegram, con reintento y
  backoff exponencial.
- Un mensaje: `/start <código>` o un código → vinculación; respuesta a un ticket que espera
  al usuario → conversación del ticket; si no → agente LangGraph con la identidad del chat
  vinculado. La respuesta sale por IntegrationOutbox.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.automation.intents import normalize
from apps.helpdesk import conversations
from apps.helpdesk.models import Ticket

from ..models import IntegrationInbox, IntegrationOutbox, Provider
from . import linking
from .client import TelegramError, get_client

logger = logging.getLogger(__name__)
TG = Provider.TELEGRAM
CHANNEL = Ticket.Channel.TELEGRAM
BATCH = 50
WELCOME = (
    "¡Hola! Soy el asistente de la Mesa de Ayuda de la Universidad Indoamérica. Escríbeme tu "
    "consulta (horario, notas, deuda, trámites…). Para ver tus datos personales, vincula tu "
    "cuenta: genera un código en el portal (Perfil → Telegram) y envíamelo aquí."
)
HELP = (
    "Esto es lo que puedo hacer por ti (usa los botones o escríbeme con tus palabras):\n"
    "• Horario, notas, asignaturas, matrícula y deuda (requieren vincular tu cuenta).\n"
    "• Estado de tus solicitudes («Mis solicitudes» o el código HD-…).\n"
    "• Requisitos de trámites, fechas académicas y teléfonos de contacto.\n"
    "• Registrar una solicitud: descríbeme tu problema («Olvidé mi contraseña»…).\n"
    "Te avisaré aquí cuando tus solicitudes cambien de estado.\n"
    "Para vincular tu cuenta: Perfil → Telegram en el portal."
)
# Menú de opciones (teclado de Telegram): cada botón envía una pregunta que el agente entiende.
MENU = [
    ["¿Cuál es mi horario de hoy?", "¿Cuáles son mis notas?"],
    ["¿Cuánto debo?", "Mis asignaturas"],
    ["Mis solicitudes", "¿Estoy matriculado?"],
    ["Requisitos de trámites", "Fechas académicas"],
    ["Teléfono de contacto", "Ayuda"],
]
MENU_WORDS = {"ayuda", "menu", "opciones", "que puedes hacer", "que puedo hacer"}
KEYBOARD = {
    "keyboard": [[{"text": label} for label in row] for row in MENU],
    "resize_keyboard": True,
    "is_persistent": True,
    "input_field_placeholder": "Escribe tu consulta o elige una opción",
}
UNSUPPORTED = "Por ahora solo puedo leer mensajes de texto. Escríbeme tu consulta, por favor."
GROUPS = "Solo atiendo en chats privados para proteger tus datos."


def backoff(attempts):
    return timedelta(minutes=2 ** max(attempts - 1, 0))


# --- Entrada --------------------------------------------------------------------------------


def ingest_update(update):
    """Guarda un update de la Bot API. Devuelve True si es nuevo."""
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    if "update_id" not in update or "id" not in chat:
        return False
    payload = {
        "update_id": update["update_id"],
        "chat_id": str(chat["id"]),
        "chat_type": chat.get("type", ""),
        "text": message.get("text"),
        "date": message.get("date"),
    }
    _, created = IntegrationInbox.objects.get_or_create(
        provider=TG, external_event_id=str(update["update_id"]), defaults={"payload_json": payload}
    )
    return created


def enqueue_text(chat_id, text, *, menu=False):
    payload = {"type": "text", "text": text}
    if menu:
        payload["reply_markup"] = KEYBOARD
    return IntegrationOutbox.objects.create(
        provider=TG, destination=str(chat_id), payload_json=payload
    )


def _reply(chat_id, text, *, menu=False):
    enqueue_text(chat_id, text, menu=menu)
    return text


def handle_message(item):
    """Procesa un mensaje entrante. Devuelve el texto respondido (o None si se ignora)."""
    data = item.payload_json
    chat_id = data.get("chat_id")
    if not chat_id:
        return None
    if data.get("chat_type") != "private":
        return _reply(chat_id, GROUPS)
    text = (data.get("text") or "").strip()
    if not text:
        return _reply(chat_id, UNSUPPORTED)

    if text.startswith("/"):
        command, _, argument = text.partition(" ")
        command = command.split("@")[0].lower()
        if command == "/start":
            if linking.looks_like_code(argument):  # enlace t.me/<bot>?start=<código>
                return _reply(chat_id, linking.redeem(argument, chat_id)[1], menu=True)
            return _reply(chat_id, f"{WELCOME}\n\n{HELP}", menu=True)
        return _reply(chat_id, HELP, menu=True)  # /menu, /ayuda y cualquier otro comando

    if normalize(text) in MENU_WORDS:
        return _reply(chat_id, HELP, menu=True)

    if linking.looks_like_code(text):
        return _reply(chat_id, linking.redeem(text, chat_id)[1], menu=True)

    user = linking.linked_user(chat_id)
    if user is not None and (ticket := _ticket_waiting_for(user)):
        conversations.add_message(
            ticket, user, text, channel=CHANNEL, external_message_id=item.external_event_id
        )
        return _reply(chat_id, f"Recibimos tu respuesta en la solicitud {ticket.ticket_code}.")

    from apps.ai.agent.runner import run_agent  # import diferido: ai depende de integrations

    result = run_agent(text=text, user=user, channel=CHANNEL, is_verified=user is not None)
    return _reply(chat_id, result.response)


def _ticket_waiting_for(user):
    """Solo cuenta como respuesta un ticket de esta conversación o nacido en Telegram: el que
    espera respuesta en la web se contesta en la web, y una consulta nueva va al agente."""
    conversation = conversations.get_conversation(user, CHANNEL)
    ticket = conversation.active_ticket
    if ticket and ticket.status == Ticket.Status.WAITING_USER:
        return ticket
    return (
        Ticket.objects.filter(user=user, status=Ticket.Status.WAITING_USER, channel=CHANNEL)
        .order_by("-updated_at")
        .first()
    )


# --- Colas ----------------------------------------------------------------------------------


def _due(model, now):
    return (
        model.objects.filter(provider=TG, status="PENDING")
        .exclude(next_attempt_at__gt=now)
        .order_by("id")
        .select_for_update(skip_locked=True)[:BATCH]
    )


def _fail(item, exc, now):
    item.attempts += 1
    item.last_error = f"{exc.__class__.__name__}: {exc}"[:2000]
    if item.attempts >= settings.INTEGRATION_MAX_ATTEMPTS:
        item.status = "FAILED"
        item.next_attempt_at = None
        logger.error("Telegram %s falló definitivamente: %s", item.pk, item.last_error)
    else:
        item.next_attempt_at = now + backoff(item.attempts)


def process_inbox(now=None):
    """Procesa los mensajes de Telegram pendientes. Devuelve (procesados, fallidos)."""
    done = failed = 0
    with transaction.atomic():
        for item in list(_due(IntegrationInbox, now or timezone.now())):
            try:
                with transaction.atomic():
                    reply = handle_message(item)
            except Exception as exc:  # el mensaje no se pierde: reintento con backoff
                logger.exception("Error procesando Telegram %s", item.pk)
                _fail(item, exc, now or timezone.now())
                failed += 1
            else:
                item.status = item.Status.DONE if reply is not None else item.Status.IGNORED
                item.processed_at = timezone.now()
                item.attempts += 1
                done += 1
            item.save()
    return done, failed


def process_outbox(now=None, client=None):
    """Envía las respuestas pendientes de Telegram. Devuelve (enviados, fallidos)."""
    client = client or get_client()
    sent = failed = 0
    with transaction.atomic():
        for item in list(_due(IntegrationOutbox, now or timezone.now())):
            try:
                item.external_message_id = client.send_text(
                    item.destination,
                    item.payload_json.get("text", ""),
                    reply_markup=item.payload_json.get("reply_markup"),
                )
            except TelegramError as exc:
                _fail(item, exc, now or timezone.now())
                failed += 1
            else:
                item.status = item.Status.SENT
                item.sent_at = timezone.now()
                item.attempts += 1
                sent += 1
            item.save()
    return sent, failed
