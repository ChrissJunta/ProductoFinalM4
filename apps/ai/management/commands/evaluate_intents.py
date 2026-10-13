"""Métricas base del clasificador sobre el dataset etiquetado (BE-T17).

python manage.py evaluate_intents            # conjunto de prueba
python manage.py evaluate_intents --split dev --errors
python manage.py evaluate_intents --agent    # + latencia P50/P95/P99 del grafo completo
"""

import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test import override_settings

from apps.ai.evaluation.dataset import load_dataset
from apps.ai.evaluation.metrics import evaluate
from apps.ai.evaluation.pipelines import make_rules_then_llm, rules


class Rollback(Exception):
    pass


class Command(BaseCommand):
    help = "Calcula Accuracy y Macro F1 de reglas y de reglas + LLM sobre el dataset."

    def add_arguments(self, parser):
        parser.add_argument("--split", choices=["dev", "test", "all"], default="test")
        parser.add_argument("--errors", action="store_true", help="Lista los ejemplos fallados.")
        parser.add_argument(
            "--agent", action="store_true", help="Ejecuta el grafo completo y mide latencias."
        )

    def handle(self, *args, split, errors, agent=False, **options):
        examples = load_dataset(None if split == "all" else split)
        self.stdout.write(f"Dataset: {len(examples)} ejemplos ({split}).")
        try:
            # Las llamadas al LLM registran AIUsage: la evaluación no deja rastro en la base.
            with transaction.atomic():
                for name, predict in (("reglas", rules), ("reglas + LLM", make_rules_then_llm())):
                    report = evaluate(examples, predict)
                    acc, f1 = report.accuracy, report.macro_f1
                    self.stdout.write(f"{name:<13} accuracy {acc:.3f} · macro F1 {f1:.3f}")
                    if errors:
                        for text, expected, got in report.errors:
                            self.stdout.write(f"    {expected:<22} → {got:<22} «{text}»")
                if agent:
                    self._agent_benchmark(examples)
                raise Rollback
        except Rollback:
            pass

    def _agent_benchmark(self, examples):
        """Benchmark IA (BE-T20): latencia de extremo a extremo y aciertos del agente."""
        from apps.ai.agent import runner

        user = get_user_model().objects.create_user("benchmark-ia", external_id="EST-BENCH")
        latencies, hits = [], 0
        with override_settings(AGENT_CHECKPOINTER="memory"):
            runner.reset()
            for example in examples:
                start = time.perf_counter()
                result = runner.run_agent(text=example.text, user=user)
                latencies.append((time.perf_counter() - start) * 1000)
                hits += (result.intent_code or "UNKNOWN_REQUEST") == example.intent
            runner.reset()
        ordered = sorted(latencies)

        def pct(p):
            return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]

        self.stdout.write(
            f"agente        accuracy {hits / len(examples):.3f} · latencia ms "
            f"P50 {pct(50):.0f} · P95 {pct(95):.0f} · P99 {pct(99):.0f}"
        )
