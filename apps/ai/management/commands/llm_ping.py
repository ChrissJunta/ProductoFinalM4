"""Diagnóstico del servidor LLM (ADR-069): conectividad, modelo y una clasificación real.

LLM_PROVIDER=openai_compat LLM_BASE_URL=http://172.16.8.69:8000/v1 python manage.py llm_ping
python manage.py llm_ping --text "no logro entrar al aula virtual"
"""

import json
import time
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.ai.service import AIInvalidOutput, AIService, AIUnavailable


class Rollback(Exception):
    pass


class Command(BaseCommand):
    help = "Comprueba el servidor LLM configurado y hace una clasificación de prueba."

    def add_arguments(self, parser):
        parser.add_argument("--text", default="Ya pagué la matrícula y sigue apareciendo la deuda")

    def handle(self, *args, text, **options):
        self.stdout.write(f"LLM_PROVIDER={settings.LLM_PROVIDER} · modelo {settings.LLM_MODEL}")
        if settings.LLM_PROVIDER == "openai_compat":
            url = settings.LLM_BASE_URL.rstrip("/") + "/models"
            try:
                with urllib.request.urlopen(url, timeout=settings.LLM_TIMEOUT) as response:
                    models = [m.get("id") for m in json.loads(response.read()).get("data", [])]
            except Exception as exc:  # noqa: BLE001 - diagnóstico para el usuario
                raise CommandError(f"No se pudo contactar {url}: {exc}") from exc
            self.stdout.write(f"Servidor OK · modelos: {', '.join(filter(None, models)) or '—'}")
        start = time.monotonic()
        try:
            with transaction.atomic():  # AIUsage de la prueba no queda registrado
                result = AIService().classify(text)
                raise Rollback
        except Rollback:
            pass
        except (AIUnavailable, AIInvalidOutput) as exc:
            raise CommandError(f"Clasificación fallida: {exc}") from exc
        ms = (time.monotonic() - start) * 1000
        self.stdout.write(
            f"«{text}» → {result.intent.code} · confianza {result.confidence:.2f} · "
            f"prioridad {result.priority} · {ms:.0f} ms"
        )
