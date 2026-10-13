"""Cierre y cancelación automáticos (SPEC §32.1 filas 9 y 14, §38.1).

- RESOLVED sin confirmación durante AUTO_CLOSE_DAYS → CLOSED.
- WAITING_USER sin respuesta durante WAITING_USER_TIMEOUT_DAYS → CANCELLED.

Pensado para cron cada hora. Es idempotente: cada ticket se vuelve a validar
bajo bloqueo dentro de `workflow.transition`, así que dos ejecuciones
solapadas no duplican cambios.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from apps.helpdesk import workflow
from apps.helpdesk.models import Ticket, TicketStatusHistory

S = Ticket.Status

RULES = [
    # (estado actual, días, estado destino, motivo)
    (S.RESOLVED, "AUTO_CLOSE_DAYS", S.CLOSED, "Cierre automático: el usuario no respondió."),
    (
        S.WAITING_USER,
        "WAITING_USER_TIMEOUT_DAYS",
        S.CANCELLED,
        "Cancelación automática: sin respuesta del usuario.",
    ),
]


def stale_tickets(status, days, now):
    """Tickets en `status` desde hace más de `days` días (según su último ingreso al estado)."""
    entered_at = (
        TicketStatusHistory.objects.filter(ticket=OuterRef("pk"), new_status=status)
        .order_by("-created_at", "-id")
        .values("created_at")[:1]
    )
    return (
        Ticket.objects.filter(status=status)
        .annotate(entered_at=Subquery(entered_at))
        .filter(entered_at__lte=now - timedelta(days=days))
        .order_by("entered_at")
    )


class Command(BaseCommand):
    help = "Cierra tickets resueltos sin confirmación y cancela los que esperan al usuario."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Solo muestra lo que se haría, sin cambiar nada."
        )

    def handle(self, *args, dry_run=False, **options):
        now = timezone.now()
        total = 0
        for status, setting_name, target, reason in RULES:
            days = getattr(settings, setting_name)
            for ticket in stale_tickets(status, days, now):
                if dry_run:
                    self.stdout.write(f"[dry-run] {ticket.ticket_code}: {status} → {target}")
                    total += 1
                    continue
                try:
                    workflow.transition(ticket, target, actor=None, reason=reason)
                except workflow.TransitionError as exc:
                    # Otro proceso lo cambió entre la consulta y el bloqueo: se omite.
                    self.stdout.write(f"Omitido {ticket.ticket_code}: {exc.message}")
                    continue
                total += 1
                self.stdout.write(f"{ticket.ticket_code}: {status} → {target}")
        self.stdout.write(self.style.SUCCESS(f"Tickets procesados: {total}"))
