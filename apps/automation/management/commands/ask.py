"""Prueba el agente de atención desde consola (BE-T14).

    python manage.py ask usuario "¿cuánto debo?"
    python manage.py ask --anonymous "¿cuáles son los requisitos?" --channel WHATSAPP

Usa el mismo `AutomationService.handle_message` que la web: si la intención es
N2–N4 crea un ticket real.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.automation.services import AutomationService
from apps.helpdesk.models import Ticket


class Command(BaseCommand):
    help = "Envía un mensaje al Autonomy Engine y muestra la decisión y la respuesta."

    def add_arguments(self, parser):
        parser.add_argument("username", nargs="?", help="Usuario remitente.")
        parser.add_argument("message", help="Texto del mensaje.")
        parser.add_argument("--channel", choices=Ticket.Channel.values, default="WEB")
        parser.add_argument(
            "--anonymous", action="store_true", help="Remitente no identificado (SPEC §35.1)."
        )

    def handle(self, *args, username=None, message, channel, anonymous, **options):
        user = None
        if not anonymous:
            if not username:
                raise CommandError("Indique el usuario o use --anonymous.")
            user = get_user_model().objects.filter(username=username).first()
            if user is None:
                raise CommandError(f"No existe el usuario {username!r}.")
        result = AutomationService.handle_message(text=message, user=user, channel=channel)
        self.stdout.write(
            f"Intención: {result.intent_code or '—'} · nivel {result.level} · "
            f"confianza {result.confidence:.2f} · origen {result.source}"
        )
        self.stdout.write(f"Ruta: {' → '.join(result.path)}")
        if result.ticket:
            self.stdout.write(f"Ticket: {result.ticket.ticket_code}")
        self.stdout.write("")
        self.stdout.write(result.response)
