"""Evaluación periódica del SLA (SPEC §34.2, §38.1). Cron cada 5 minutos.

Para cada ticket abierto con plazo de resolución:
- consumido >= SLA_WARNING_RATIO → alerta SLA_WARNING;
- vencido → alerta SLA_BREACHED (cierra la de aviso) y escalamiento automático
  (filas 6 y 10 de §32.1) si el estado lo permite.

Idempotente: una alerta abierta por tipo y ticket; el escalamiento se vuelve a
validar bajo bloqueo en `workflow.transition`.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.helpdesk import alerts, sla, workflow
from apps.helpdesk.models import Alert, Ticket

S = Ticket.Status
AUTO_ESCALATE_FROM = {S.ASSIGNED, S.IN_PROGRESS}


class Command(BaseCommand):
    help = "Genera alertas de SLA y escala automáticamente los tickets vencidos."

    def handle(self, *args, **options):
        now = timezone.now()
        counts = {"warning": 0, "breached": 0, "escalated": 0}
        tickets = (
            Ticket.objects.exclude(status__in=sla.FINISHED)
            .filter(sla_due_at__isnull=False)
            .select_related("category")
            .order_by("sla_due_at")
        )
        for ticket in tickets.iterator():
            status = sla.sla_status(ticket, now)
            if status.state == sla.SLAState.BREACHED:
                due = timezone.localtime(ticket.sla_due_at)
                _, created = alerts.open_alert(
                    ticket,
                    Alert.Type.SLA_BREACHED,
                    severity=Alert.Severity.CRITICAL,
                    message=f"SLA vencido el {due:%Y-%m-%d %H:%M}.",
                )
                alerts.resolve_alerts(ticket, [Alert.Type.SLA_WARNING])
                counts["breached"] += created
                if ticket.status in AUTO_ESCALATE_FROM:
                    try:
                        workflow.transition(
                            ticket, S.ESCALATED, actor=None, reason="SLA de resolución vencido."
                        )
                        counts["escalated"] += 1
                    except workflow.TransitionError:
                        pass  # el estado cambió mientras tanto
            elif status.state == sla.SLAState.WARNING:
                _, created = alerts.open_alert(
                    ticket,
                    Alert.Type.SLA_WARNING,
                    severity=Alert.Severity.WARNING,
                    message=f"SLA por vencer: quedan {status.remaining_minutes} min.",
                )
                counts["warning"] += created
        self.stdout.write(
            self.style.SUCCESS(
                "Alertas nuevas: {warning} por vencer, {breached} vencidas; "
                "tickets escalados: {escalated}".format(**counts)
            )
        )
