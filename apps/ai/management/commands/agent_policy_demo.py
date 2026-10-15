"""Historial de demostración para comprobar las decisiones propias del agente (ADR-077).

Crea revisiones humanas y tickets con SLA vencido marcados como demo, de modo que la
próxima evaluación dispare D1, D2, D3 y D5 (y D4 con --llm-failures). Solo desarrollo.

    python manage.py agent_policy_demo
    python manage.py evaluate_agent_policies
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.ai.models import AIDecision, AIUsage, Operation
from apps.automation.models import Intent
from apps.helpdesk.models import Ticket
from apps.helpdesk.tickets import TicketService

DEMO = {"demo": "agent_policy_demo"}
D3_MESSAGES = [
    "Requiero el documento de egresado para un trabajo",
    "Pido mi acta de egresado por favor",
    "Necesito algo que diga que soy egresado de la carrera",
]


class Command(BaseCommand):
    help = "Genera historial demo para que el agente tome las decisiones D1–D5."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Permite DEBUG=False.")
        parser.add_argument(
            "--llm-failures",
            action="store_true",
            help="Agrega fallas recientes del LLM (D4 lo pausará 15 minutos).",
        )

    def handle(self, *args, force=False, llm_failures=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError("Solo en desarrollo (DEBUG=True) o con --force.")
        user = get_user_model().objects.filter(username="usuario").first()
        if user is None:
            raise CommandError("Ejecute primero `python manage.py seed_demo`.")
        with transaction.atomic():
            self._reviews("PASSWORD_PROBLEM", accepted=10)  # D1
            self._reviews("ENROLLMENT_PROBLEM", accepted=3, corrected=2)  # D2
            self._corrections(user)  # D3
            self._breached(user, "CERTIFICATE_REQUEST", 5)  # D5
            if llm_failures:
                for _ in range(6):  # D4
                    AIUsage.objects.create(
                        provider="demo", model_name="demo", operation=Operation.CLASSIFY,
                        success=False, error_code="DEMO",
                    )  # fmt: skip
        self.stdout.write(self.style.SUCCESS("Historial demo creado:"))
        self.stdout.write("  D1 PASSWORD_PROBLEM: 10 revisiones aceptadas")
        self.stdout.write("  D2 ENROLLMENT_PROBLEM: 5 revisiones, 2 corregidas")
        self.stdout.write("  D3 CERTIFICATE_REQUEST: 3 mensajes corregidos con «egresado»")
        self.stdout.write("  D5 CERTIFICATE_REQUEST: 5 tickets con SLA vencido")
        if llm_failures:
            self.stdout.write("  D4 LLM: 6 llamadas fallidas en la última hora")
        self.stdout.write("Ahora: python manage.py evaluate_agent_policies")

    def _reviews(self, code, *, accepted=0, corrected=0):
        now = timezone.now()
        for index in range(accepted + corrected):
            fixed = index >= accepted
            AIDecision.objects.create(
                operation=Operation.AGENT_RUN,
                intent_code=code,
                autonomy_level="N3",
                classification_source="LLM",
                requires_human=True,
                accepted=True,
                corrected=fixed,
                reviewed_at=now,
                parsed_output={**DEMO, **({"corrected_to": "UNKNOWN_REQUEST"} if fixed else {})},
                thread_id="demo",
            )

    def _corrections(self, user):
        unknown = Intent.objects.get(code="UNKNOWN_REQUEST")
        for text in D3_MESSAGES:
            ticket = TicketService.create(
                user=user, subject="Solicitud no identificada", description=text, intent=unknown
            )
            AIDecision.objects.create(
                operation=Operation.AGENT_RUN,
                ticket=ticket,
                intent_code="UNKNOWN_REQUEST",
                autonomy_level="N4",
                requires_human=True,
                accepted=True,
                corrected=True,
                reviewed_at=timezone.now(),
                parsed_output={**DEMO, "corrected_to": "CERTIFICATE_REQUEST"},
                thread_id="demo",
            )

    def _breached(self, user, code, count):
        intent = Intent.objects.get(code=code)
        for index in range(count):
            ticket = TicketService.create(
                user=user,
                subject=f"{intent.name} (demo SLA)",
                description="Ticket demo con SLA vencido.",
                intent=intent,
            )
            Ticket.objects.filter(pk=ticket.pk).update(
                sla_due_at=timezone.now() - timedelta(hours=index + 1)
            )
