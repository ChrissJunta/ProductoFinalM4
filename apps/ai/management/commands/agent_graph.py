"""Regenera el diagrama del grafo del agente (SPEC §46A.8): docs/agent_graph.md."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ai.agent.graph import GRAPH_VERSION, build_graph

DOC = Path(settings.BASE_DIR) / "docs" / "agent_graph.md"


def render():
    mermaid = build_graph().get_graph().draw_mermaid().strip()
    return (
        "# Grafo del agente de atención (LangGraph)\n\n"
        f"Versión del grafo: **{GRAPH_VERSION}** · generado con "
        "`python manage.py agent_graph` (no editar a mano).\n\n"
        "Fuente: `apps/ai/agent/graph.py`. Las líneas punteadas son aristas condicionales.\n\n"
        f"```mermaid\n{mermaid}\n```\n"
    )


class Command(BaseCommand):
    help = "Escribe docs/agent_graph.md con el diagrama Mermaid del grafo actual."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check", action="store_true", help="Falla si el archivo no está al día."
        )

    def handle(self, *args, check=False, **options):
        content = render()
        if check:
            current = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
            if current != content:
                raise SystemExit(
                    "docs/agent_graph.md desactualizado: ejecute manage.py agent_graph"
                )
            self.stdout.write("Diagrama al día.")
            return
        DOC.parent.mkdir(exist_ok=True)
        DOC.write_text(content, encoding="utf-8")
        self.stdout.write(f"Escrito {DOC} (v{GRAPH_VERSION}).")
