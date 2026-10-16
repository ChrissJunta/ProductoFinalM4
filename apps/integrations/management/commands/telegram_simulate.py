"""Simula un mensaje al bot de Telegram sin red (ADR-080) y muestra la respuesta.

python manage.py telegram_simulate 123456 "¿Cuánto debo?"
python manage.py telegram_simulate 123456 "/start 482913"   # vinculación por código
python manage.py telegram_simulate 123456 --boton close:HD-2026-000008   # pulsar un botón
"""

import time

from django.core.management.base import BaseCommand

from apps.integrations.models import IntegrationOutbox, Provider
from apps.integrations.telegram import processing
from apps.integrations.telegram.client import SimulatedTelegramClient


class Command(BaseCommand):
    help = "Envía un mensaje simulado al bot de Telegram y muestra la respuesta."

    def add_arguments(self, parser):
        parser.add_argument("chat_id", help="Id del chat (cualquier número).")
        parser.add_argument("message", nargs="?", default="")
        parser.add_argument("--boton", help="Simula pulsar un botón (callback_data).")

    def handle(self, *args, chat_id, message, boton=None, **options):
        update_id = int(time.time() * 1000)
        chat = {"chat": {"id": chat_id, "type": "private"}}
        if boton:
            update = {"callback_query": {"id": "sim", "data": boton, "message": chat}}
        else:
            update = {"message": {**chat, "text": message}}
        processing.ingest_update({"update_id": update_id, **update})
        last = IntegrationOutbox.objects.order_by("-id").values_list("id", flat=True).first() or 0
        processing.process_inbox()
        processing.process_outbox(client=SimulatedTelegramClient())
        replies = IntegrationOutbox.objects.filter(
            id__gt=last, provider=Provider.TELEGRAM, destination=str(chat_id)
        )
        for reply in replies:
            payload = reply.payload_json
            if payload.get("type") == "callback_answer":
                continue
            text = payload.get("text") or f"📎 {payload.get('caption', '')}"
            self.stdout.write(f"← {reply.destination} [{reply.status}]\n{text}")
