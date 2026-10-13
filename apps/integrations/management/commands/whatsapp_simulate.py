"""Simulador de WhatsApp (ADR-049): envía al webhook un evento con el formato de Meta,
firmado con WHATSAPP_APP_SECRET, procesa la cola y muestra la respuesta.

    python manage.py whatsapp_simulate +593991234567 "¿Cuánto debo?"
    python manage.py whatsapp_simulate +593991234567 "123456"     # código de vinculación
"""

import json
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.urls import reverse

from apps.integrations.models import IntegrationOutbox
from apps.integrations.whatsapp.processing import normalize_phone, process_inbox, process_outbox
from apps.integrations.whatsapp.signature import sign


def meta_payload(phone, text, message_id=None):
    """Evento `messages` de WhatsApp Cloud API (estructura pública de Meta)."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "SIMULATED",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "SIMULADO", "phone_number_id": "SIM"},
                    "contacts": [{"wa_id": phone.lstrip("+"), "profile": {"name": "Simulado"}}],
                    "messages": [{
                        "from": phone.lstrip("+"),
                        "id": message_id or f"wamid.SIM.{uuid.uuid4().hex}",
                        "timestamp": "0",
                        "type": "text",
                        "text": {"body": text},
                    }],
                },
            }],
        }],
    }  # fmt: skip


class Command(BaseCommand):
    help = "Simula un mensaje entrante de WhatsApp de punta a punta (webhook → worker → salida)."

    def add_arguments(self, parser):
        parser.add_argument("phone", help="Número E.164, p. ej. +593991234567.")
        parser.add_argument("message")
        parser.add_argument("--message-id", help="Repetir un id prueba la idempotencia.")

    def handle(self, *args, phone, message, message_id=None, **options):
        phone = normalize_phone(phone)
        body = json.dumps(meta_payload(phone, message, message_id)).encode()
        host = next((h for h in settings.ALLOWED_HOSTS if h and h[0] not in "*."), "localhost")
        response = Client(SERVER_NAME=host).post(
            reverse("integrations:whatsapp_webhook"),
            data=body,
            content_type="application/json",
            headers={"X-Hub-Signature-256": sign(body)},
        )
        if response.status_code != 200:
            raise CommandError(f"El webhook respondió {response.status_code}: {response.content!r}")
        self.stdout.write(f"Webhook: {response.json()}")
        last = IntegrationOutbox.objects.order_by("-id").values_list("id", flat=True).first() or 0
        process_inbox()
        process_outbox()
        for out in IntegrationOutbox.objects.filter(id__gt=last, destination=phone):
            self.stdout.write(f"← {out.destination} [{out.status}]\n{out.payload_json['text']}")
