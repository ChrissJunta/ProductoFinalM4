"""Muestra en consola cómo procesó el agente sus últimos mensajes (ADR-076).

python manage.py agent_trace                 # las 5 últimas ejecuciones
python manage.py agent_trace --last 20
python manage.py agent_trace --id 42         # una ejecución
python manage.py agent_trace --ticket HD-2026-000034
python manage.py agent_trace --id 42 --json  # traza completa en JSON
"""

import json

from django.core.management.base import BaseCommand, CommandError

from apps.ai import traces
from apps.ai.agent.trace import format_step


class Command(BaseCommand):
    help = "Muestra la traza nodo por nodo de las ejecuciones del agente."

    def add_arguments(self, parser):
        parser.add_argument("--last", type=int, default=5, help="Cantidad de ejecuciones.")
        parser.add_argument("--id", type=int, help="Id de la ejecución (AIDecision).")
        parser.add_argument("--ticket", help="Código del ticket.")
        parser.add_argument(
            "--json", action="store_true", dest="as_json", help="Salida JSON completa."
        )

    def handle(self, *args, last, id=None, ticket=None, as_json=False, **options):
        qs = traces.runs()
        if id is not None:
            qs = qs.filter(pk=id)
        if ticket:
            qs = qs.filter(ticket__ticket_code=ticket)
        decisions = list(qs.order_by("-created_at", "-id")[: max(last, 1)])
        if not decisions:
            raise CommandError("No hay ejecuciones del agente con esos criterios.")
        if as_json:
            self.stdout.write(_dumps([traces.export(d) for d in decisions]))
            return
        for decision in reversed(decisions):
            self._print(decision)

    def _print(self, decision):
        run = traces.row(decision)
        header = (
            f"#{run['id']} {decision.created_at:%Y-%m-%d %H:%M:%S} · "
            f"{run['user'].username if run['user'] else 'anónimo'} · {run['channel']} · "
            f"nivel {run['autonomy_level'] or '—'} · intent {run['intent_code'] or '—'}"
        )
        if run["duration_ms"] is not None:
            header += f" · {run['duration_ms']} ms"
        self.stdout.write(self.style.MIGRATE_HEADING(header))
        if run["message"]:
            self.stdout.write(f"  mensaje: {run['message']}")
        if decision.trace:
            for index, step in enumerate(decision.trace, start=1):
                self.stdout.write(f"  {index:>2}. {format_step(step)}")
        else:
            self.stdout.write(f"  ruta: {' → '.join(decision.node_path or [])}")
        if run["ticket_code"]:
            self.stdout.write(f"  ticket: {run['ticket_code']}")
        if run["pending_review"]:
            self.stdout.write(self.style.WARNING("  revisión humana pendiente"))
        for error in decision.errors or []:
            self.stdout.write(self.style.ERROR(f"  error: {error}"))
        self.stdout.write("")


def _dumps(data):
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)
