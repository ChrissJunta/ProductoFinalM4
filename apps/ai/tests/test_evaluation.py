"""BE-T17: dataset etiquetado y métricas base (Accuracy, Macro F1)."""

from collections import Counter
from io import StringIO

import pytest
from django.core.management import call_command

from apps.ai.evaluation.base_phrases import BASES
from apps.ai.evaluation.dataset import Example, informal, load_dataset
from apps.ai.evaluation.metrics import evaluate
from apps.ai.evaluation.pipelines import make_rules_then_llm, rules
from apps.ai.models import AIUsage
from apps.automation.models import Intent


def test_dataset_covers_catalog_with_20_examples_each():
    counts = Counter(e.intent for e in load_dataset())
    assert len(counts) == 20 and min(counts.values()) >= 20
    assert len(load_dataset("dev")) == 280 and len(load_dataset("test")) == 120


@pytest.mark.django_db
def test_dataset_matches_intent_catalog():
    assert set(BASES) == set(Intent.objects.values_list("code", flat=True))


def test_dev_and_test_do_not_share_base_phrases():
    dev = {e.text for e in load_dataset("dev")}
    test = {e.text for e in load_dataset("test")}
    assert not dev & test
    assert all(len(set(bases)) == 10 for bases in BASES.values())


def test_informal_variant():
    assert informal("¿Cuánto debo?", 0) == "Hola, cuanto debo"
    assert informal("Olvidé mi contraseña", 5) == "Buenas, olvide mi contrasena por favor"


def test_metrics():
    ex = [Example("a", "X", "dev"), Example("b", "X", "dev"), Example("c", "Y", "dev")]
    report = evaluate(ex, {"a": "X", "b": "Y", "c": "Y"}.get)
    assert report.total == 3 and report.accuracy == pytest.approx(2 / 3)
    # X: p=1 r=.5 f1=.667 · Y: p=.5 r=1 f1=.667
    assert report.macro_f1 == pytest.approx(2 / 3)
    assert report.errors == [("b", "X", "Y")]
    empty = evaluate([], lambda t: t)
    assert (empty.accuracy, empty.macro_f1) == (0.0, 0.0)
    assert evaluate([Example("a", "X", "dev")], lambda t: "Z").per_label["X"] == (0.0, 0.0, 0.0, 1)


@pytest.mark.django_db
def test_baseline_on_held_out_test_split():
    """Línea base registrada (TEST-RUN-010). Sirve de alarma ante regresiones."""
    test = load_dataset("test")
    base = evaluate(test, rules)
    hybrid = evaluate(test, make_rules_then_llm())
    assert base.accuracy >= 0.65 and base.macro_f1 >= 0.65
    assert hybrid.accuracy >= base.accuracy  # el LLM solo actúa donde las reglas no resuelven


@pytest.mark.django_db
def test_hybrid_survives_llm_failure(monkeypatch):
    from apps.ai.providers import LLMError
    from apps.ai.providers.fake import FakeLLMProvider

    def down(self, text, context=None):
        raise LLMError("x")

    monkeypatch.setattr(FakeLLMProvider, "classify", down)
    predict = make_rules_then_llm()
    assert predict("zzz") == "UNKNOWN_REQUEST"
    assert predict("certificado y contraseña") == "UNKNOWN_REQUEST"  # ambiguo: no se consulta


@pytest.mark.django_db
def test_evaluate_command_leaves_no_usage_rows():
    out = StringIO()
    call_command("evaluate_intents", "--split", "test", "--errors", stdout=out)
    text = out.getvalue()
    assert "120 ejemplos" in text and "reglas + LLM" in text and "macro F1" in text
    assert AIUsage.objects.count() == 0
