"""El agente revisa sus métricas y toma decisiones propias (ADR-077). Programarlo a diario:

python manage.py evaluate_agent_policies            # decide y aplica/propone
python manage.py evaluate_agent_policies --dry-run  # solo muestra qué decidiría
"""

from django.core.management.base import BaseCommand

from apps.ai import policies
from apps.ai.models import AgentPolicyDecision


class Command(BaseCommand):
    help = "Evalúa las métricas del agente y registra sus decisiones (D1–D5)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No guarda nada.")

    def handle(self, *args, dry_run=False, **options):
        rows = [
            r
            for r in policies.intent_metrics()
            if r["reviewed"]
            or r["sla_decided"]
            or r["review_mode"] != "DEFAULT"
            or r["priority_override"]
        ]
        self.stdout.write(self.style.MIGRATE_HEADING("Métricas por intención"))
        for r in rows:
            self.stdout.write(
                f"  {r['code']:<22} {r['level']} revisiones={r['reviewed']} "
                f"aceptadas={r['accepted']} corregidas={r['corrected']} "
                f"rechazadas={r['rejected']} sla={r['sla_breached']}/{r['sla_decided']} "
                f"política={r['review_mode']}"
                + (f" prioridad≥{r['priority_override']}" if r["priority_override"] else "")
            )
        if not rows:
            self.stdout.write("  (sin revisiones, tickets con SLA ni políticas en la ventana)")
        result = policies.evaluate(dry_run=dry_run)
        self.stdout.write(self.style.MIGRATE_HEADING("Decisiones"))
        if not result:
            self.stdout.write("  Sin decisiones nuevas.")
        for item in result:
            if dry_run:
                kind = AgentPolicyDecision.Kind(item["kind"]).label
                self.stdout.write(f"  [simulación] {kind}: {item['summary']}")
            else:
                self.stdout.write(
                    f"  #{item.pk} {item.get_kind_display()} → {item.get_status_display()}: "
                    f"{item.summary}"
                )
