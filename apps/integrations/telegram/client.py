"""Clientes de la Bot API de Telegram (ADR-080). El bot usa `get_client()`.

El token forma parte de la URL de la Bot API: nunca se escribe en logs ni en errores
(`_safe` lo reemplaza por «***»).
"""

import json
import urllib.error
import urllib.request
import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

API = "https://api.telegram.org"


class TelegramError(Exception):
    """Fallo de la Bot API: el worker reintenta con backoff."""


class SimulatedTelegramClient:
    """No contacta a Telegram: registra el envío con un id ficticio (pruebas y demo sin red)."""

    name = "simulated"
    fail_chats = set()  # pruebas: chats que simulan un fallo de envío

    def send_text(self, chat_id, text):
        if str(chat_id) in self.fail_chats:
            raise TelegramError("Fallo simulado de envío.")
        return f"tg.SIM.{uuid.uuid4().hex[:12]}"

    def get_updates(self, offset=None, timeout=0):
        return []

    def get_me(self):
        return {"username": settings.TELEGRAM_BOT_USERNAME, "simulated": True}

    def delete_webhook(self):
        return True


class BotAPIClient:
    """Bot API real con long polling (`getUpdates`): no necesita URL pública."""

    name = "bot"

    def __init__(self, token=None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        if not self.token:
            raise ImproperlyConfigured("TELEGRAM_MODE=bot requiere TELEGRAM_BOT_TOKEN en .env.")

    def _safe(self, text):
        return str(text).replace(self.token, "***")

    def _call(self, method, payload=None, timeout=15):
        request = urllib.request.Request(
            f"{API}/bot{self.token}/{method}",
            data=json.dumps(payload or {}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read()).get("description", "")
            except (ValueError, OSError):
                pass
            raise TelegramError(self._safe(f"{method}: HTTP {exc.code} {detail}")) from None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise TelegramError(self._safe(f"{method}: {exc}")) from None
        if not data.get("ok"):
            raise TelegramError(self._safe(f"{method}: {data.get('description', 'error')}"))
        return data["result"]

    def send_text(self, chat_id, text):
        result = self._call("sendMessage", {"chat_id": chat_id, "text": text[:4096]})
        return str(result.get("message_id", ""))

    def get_updates(self, offset=None, timeout=0):
        payload = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        return self._call("getUpdates", payload, timeout=timeout + 10)

    def get_me(self):
        return self._call("getMe")

    def delete_webhook(self):
        return self._call("deleteWebhook")


def get_client():
    if settings.TELEGRAM_MODE == "simulated":
        return SimulatedTelegramClient()
    if settings.TELEGRAM_MODE == "bot":
        return BotAPIClient()
    raise ImproperlyConfigured(f"TELEGRAM_MODE desconocido: {settings.TELEGRAM_MODE!r}.")
