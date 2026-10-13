"""Clientes de salida (SPEC §35 «Salida»). El worker usa `get_client()`."""

import json
import urllib.error
import urllib.request
import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class SendError(Exception):
    """Fallo de envío: el worker reintenta con backoff."""


class SimulatedClient:
    """No envía nada: registra el mensaje como enviado con un id ficticio (ADR-049)."""

    name = "simulated"
    fail_destinations = set()  # pruebas: números que simulan un fallo de envío

    def send_text(self, to, text):
        if to in self.fail_destinations:
            raise SendError("Fallo simulado de envío.")
        return f"wamid.SIM.{uuid.uuid4().hex[:16]}"


class CloudAPIClient:
    """Meta WhatsApp Cloud API. Requiere credenciales; no se usa en el MVP."""

    name = "cloud"
    timeout = 10

    def __init__(self):
        if not (settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID):
            raise ImproperlyConfigured("WHATSAPP_MODE=cloud requiere token y phone number id.")

    def send_text(self, to, text):
        url = (
            f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/"
            f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        )
        body = json.dumps(
            {
                "messaging_product": "whatsapp",
                "to": to.lstrip("+"),
                "type": "text",
                "text": {"body": text[:4096]},
            }
        ).encode()
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise SendError(f"Cloud API: {exc}") from exc
        try:
            return data["messages"][0]["id"]
        except (KeyError, IndexError, TypeError) as exc:
            raise SendError("Cloud API: respuesta inesperada.") from exc


def get_client():
    if settings.WHATSAPP_MODE == "simulated":
        return SimulatedClient()
    if settings.WHATSAPP_MODE == "cloud":
        return CloudAPIClient()
    raise ImproperlyConfigured(f"WHATSAPP_MODE desconocido: {settings.WHATSAPP_MODE!r}.")
