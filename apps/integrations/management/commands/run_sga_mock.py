"""Levanta el SGA simulado para probar `INSTITUTIONAL_PROVIDER=sga` en desarrollo.

python manage.py run_sga_mock --port 8099
# en otra terminal: INSTITUTIONAL_PROVIDER=sga SGA_BASE_URL=http://127.0.0.1:8099 ...
"""

import time

from django.core.management.base import BaseCommand

from apps.integrations.institutional import sga_mock


class Command(BaseCommand):
    help = "Servidor HTTP simulado del SGA (solo desarrollo y pruebas)."

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, default=8099)
        parser.add_argument("--token", default="")
        parser.add_argument("--seconds", type=float, default=0, help="0 = hasta Ctrl+C.")

    def handle(self, *args, port, token, seconds, **options):
        server = sga_mock.start(port=port, token=token)
        self.stdout.write(f"SGA simulado en {server.url} (Ctrl+C para salir).")
        try:
            if seconds:
                time.sleep(seconds)
            else:  # pragma: no cover - interactivo
                while True:
                    time.sleep(3600)
        except KeyboardInterrupt:  # pragma: no cover - interactivo
            pass
        finally:
            server.shutdown()
            self.stdout.write("SGA simulado detenido.")
