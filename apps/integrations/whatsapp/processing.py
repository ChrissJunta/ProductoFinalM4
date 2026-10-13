"""Inbox/Outbox y worker (SPEC §35-§38, BE-T12).

- `ingest(payload)`: guarda cada mensaje del webhook en IntegrationInbox (idempotente).
- `process_inbox()` / `process_outbox()`: lotes con `select_for_update(skip_locked=True)`,
  reintento con backoff exponencial (1, 2, 4, 8 min) y FAILED tras el máximo de intentos.
- Un mensaje entrante: código de vinculación → BE-T11A; respuesta a un ticket que espera
  al usuario → conversación del ticket; si no → agente LangGraph con la identidad
  verificada del número (SPEC §35.1). La respuesta sale por IntegrationOutbox.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.helpdesk import conversations
from apps.helpdesk.models import Ticket

from ..models import IntegrationInbox, IntegrationOutbox, Provider
from . import linking
from .client import SendError, get_client

logger = logging.getLogger(__name__)
WA = Provider.WHATSAPP
BATCH = 50
UNSUPPORTED = "Por ahora solo puedo leer mensajes de texto. Escríbeme tu consulta, por favor."


def normalize_phone(raw):
    digits = "".join(c for c in str(raw) if c.isdigit())
    return f"+{digits}" if digits else ""


def backoff(attempts):
    return timedelta(minutes=2 ** max(attempts - 1, 0))


# --- Entrada --------------------------------------------------------------------------------


def iter_messages(payload):
    """Mensajes del formato de Meta: entry[].changes[].value.messages[]."""
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            yield from value.get("messages") or []


def ingest(payload):
    """Guarda los mensajes del evento. Devuelve (nuevos, duplicados)."""
    new = duplicated = 0
    for message in iter_messages(payload):
        message_id = message.get("id")
        if not message_id:
            continue
        _, created = IntegrationInbox.objects.get_or_create(
            provider=WA, external_event_id=message_id, defaults={"payload_json": message}
        )
        new, duplicated = (new + 1, duplicated) if created else (new, duplicated + 1)
    return new, duplicated


def enqueue_text(destination, text):
    return IntegrationOutbox.objects.create(
        provider=WA, destination=destination, payload_json={"type": "text", "text": text}
    )


def handle_message(item):
    """Procesa un mensaje entrante. Devuelve el texto respondido (o None si se ignora)."""
    message = item.payload_json
    phone = normalize_phone(message.get("from"))
    if not phone:
        return None
    if message.get("type") != "text":
        enqueue_text(phone, UNSUPPORTED)
        return UNSUPPORTED
    text = ((message.get("text") or {}).get("body") or "").strip()
    if not text:
        return None

    if linking.looks_like_code(text):
        _, reply = linking.redeem(text, phone)
        enqueue_text(phone, reply)
        return reply

    user = linking.verified_user(phone)
    if user is not None and (ticket := _ticket_waiting_for(user)):
        conversations.add_message(
            ticket, user, text, channel=Ticket.Channel.WHATSAPP,
            external_message_id=item.external_event_id,
        )  # fmt: skip
        reply = f"Recibimos tu respuesta en la solicitud {ticket.ticket_code}. ¡Gracias!"
        enqueue_text(phone, reply)
        return reply

    from apps.ai.agent.runner import run_agent  # import diferido: ai depende de integrations

    result = run_agent(
        text=text, user=user, channel=Ticket.Channel.WHATSAPP, is_verified=user is not None
    )
    enqueue_text(phone, result.response)
    return result.response


def _ticket_waiting_for(user):
    conversation = conversations.get_conversation(user, Ticket.Channel.WHATSAPP)
    ticket = conversation.active_ticket
    if ticket and ticket.status == Ticket.Status.WAITING_USER:
        return ticket
    return (
        Ticket.objects.filter(user=user, status=Ticket.Status.WAITING_USER)
        .order_by("-updated_at")
        .first()
    )


def _due(queryset, now):
    return (
        queryset.filter(status="PENDING")
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
        logger.error("Integración %s falló definitivamente: %s", item.pk, item.last_error)
    else:
        item.next_attempt_at = now + backoff(item.attempts)


def process_inbox(now=None):
    """Procesa entradas pendientes. Devuelve (procesadas, fallidas)."""
    done = failed = 0
    with transaction.atomic():
        items = list(_due(IntegrationInbox.objects.all(), now or timezone.now()))
        for item in items:
            try:
                with transaction.atomic():
                    reply = handle_message(item)
            except Exception as exc:  # el mensaje no se pierde: reintento con backoff
                logger.exception("Error procesando inbox %s", item.pk)
                _fail(item, exc, now or timezone.now())
                failed += 1
            else:
                item.status = item.Status.DONE if reply is not None else item.Status.IGNORED
                item.processed_at = timezone.now()
                item.attempts += 1
                done += 1
            item.save()
    return done, failed


def process_outbox(now=None):
    """Envía salientes pendientes. Devuelve (enviados, fallidos)."""
    client = get_client()
    sent = failed = 0
    with transaction.atomic():
        items = list(_due(IntegrationOutbox.objects.all(), now or timezone.now()))
        for item in items:
            try:
                item.external_message_id = client.send_text(
                    item.destination, item.payload_json.get("text", "")
                )
            except SendError as exc:
                _fail(item, exc, now or timezone.now())
                failed += 1
            else:
                item.status = item.Status.SENT
                item.sent_at = timezone.now()
                item.attempts += 1
                sent += 1
            item.save()
    return sent, failed


def notify_ticket_reply(message):
    """Respuesta del personal en un ticket de WhatsApp → al número verificado del usuario."""
    ticket = message.ticket
    user = ticket.user
    if ticket.channel != Ticket.Channel.WHATSAPP or not user.is_phone_verified:
        return None
    text = f"[{ticket.ticket_code}] {message.content}"
    return enqueue_text(user.phone, text[:4096])
