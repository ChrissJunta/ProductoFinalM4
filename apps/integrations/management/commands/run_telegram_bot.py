"""Bot de Telegram con long polling (ADR-080): no necesita URL pública.

    python manage.py run_telegram_bot          # queda escuchando (Ctrl+C para salir)
    python manage.py run_telegram_bot --once   # una vuelta (pruebas)

Requiere en .env: TELEGRAM_MODE=bot y TELEGRAM_BOT_TOKEN=<token de @BotFather>.
"""

import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.integrations.telegram import processing
from apps.integrations.telegram.client import TelegramError, get_client

RETRY_SECONDS = 5


class Command(BaseCommand):
    help = "Ejecuta el bot de Telegram (long polling) y procesa sus colas."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Una sola vuelta.")

    def handle(self, *args, once=False, **options):
        client = get_client()
        try:
            me = client.get_me()
            client.delete_webhook()  # con webhook activo, getUpdates no funciona
        except TelegramError as exc:
            raise CommandError(f"No se pudo conectar con Telegram: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(f"Bot @{me.get('username')} escuchando ({settings.TELEGRAM_MODE}).")
        )
        offset = None
        while True:
            try:
                offset = self._tick(client, offset, 0 if once else settings.TELEGRAM_POLL_TIMEOUT)
            except TelegramError as exc:
                self.stderr.write(f"Telegram no disponible: {exc}. Reintento en {RETRY_SECONDS} s.")
                if once:
                    raise CommandError(str(exc)) from exc
                time.sleep(RETRY_SECONDS)
            except KeyboardInterrupt:
                self.stdout.write("Bot detenido.")
                return
            if once:
                return

    def _tick(self, client, offset, timeout):
        updates = client.get_updates(offset=offset, timeout=timeout)
        for update in updates:
            processing.ingest_update(update)
            offset = max(offset or 0, update["update_id"] + 1)
        done, failed = processing.process_inbox()
        sent, send_failed = processing.process_outbox(client=client)
        if updates or done or sent or failed or send_failed:
            self.stdout.write(
                f"Recibidos {len(updates)} · procesados {done} · enviados {sent}"
                + (f" · fallidos {failed + send_failed}" if failed or send_failed else "")
            )
        return offset
