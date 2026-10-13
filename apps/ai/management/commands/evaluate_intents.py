"""Métricas base del clasificador sobre el dataset etiquetado (BE-T17).

python manage.py evaluate_intents            # conjunto de prueba
python manage.py evaluate_intents --split dev --errors
"""

from django.core.management.base import BaseCommand
from django.db import transaction

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

    def handle(self, *args, split, errors, **options):
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
                raise Rollback
        except Rollback:
            pass
