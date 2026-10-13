"""Worker de integraciones (SPEC §38): inbox y outbox de WhatsApp con reintentos.

python manage.py process_integration_queue            # una pasada (cron cada minuto)
python manage.py process_integration_queue --loop     # continuo, en desarrollo
"""

import argparse
import time

from django.core.management.base import BaseCommand

from apps.integrations.whatsapp.processing import process_inbox, process_outbox


class Command(BaseCommand):
    help = "Procesa IntegrationInbox e IntegrationOutbox (reintentos con backoff)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Ejecución continua.")
        parser.add_argument("--interval", type=float, default=5.0, help="Segundos entre pasadas.")
        parser.add_argument("--max-loops", type=int, default=0, help=argparse.SUPPRESS)

    def handle(self, *args, loop=False, interval=5.0, max_loops=0, **options):
        passes = 0
        while True:
            done, failed_in = process_inbox()
            sent, failed_out = process_outbox()
            if done or failed_in or sent or failed_out or not loop:
                self.stdout.write(
                    f"Entrada: {done} procesados, {failed_in} con error · "
                    f"Salida: {sent} enviados, {failed_out} con error"
                )
            passes += 1
            if not loop or (max_loops and passes >= max_loops):
                return
            time.sleep(interval)  # pragma: no cover - solo modo continuo real
