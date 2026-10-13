"""BE-T16 / BE-T17 / BE-T18: proveedor LLM, AIService, validación, reintento y respaldo."""

import json
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.ai.models import AIModelConfig, AIPromptVersion, AIUsage
from apps.ai.providers import LLMError, LLMProvider, LLMResponse, get_llm_provider
from apps.ai.providers.fake import FakeLLMProvider
from apps.ai.service import (
    AIInvalidOutput,
    AIService,
    AIUnavailable,
    classification_context,
    validate_classification,
)

pytestmark = pytest.mark.django_db

VALID = {
    "intent": "GRADE_DISCREPANCY",
    "category": "ACADEMIC",
    "subcategory": "GRADES",
    "priority": "MEDIUM",
    "summary": "El usuario reporta una posible inconsistencia en su calificación.",
    "requires_human": True,
    "confidence": 0.91,
}


def raw(**changes):
    return json.dumps({**VALID, **changes})


# --- Selección de proveedor (BE-T16) ----------------------------------------------------


def test_provider_by_configuration(settings):
    assert isinstance(get_llm_provider(), FakeLLMProvider)
    assert get_llm_provider(model_name="x").model_name == "x"
    settings.LLM_PROVIDER = "inexistente"
    with pytest.raises(ImproperlyConfigured):
        get_llm_provider()


def test_initial_config_has_primary_and_fallback_per_operation():
    for purpose in ("CLASSIFY", "EXTRACT", "SUMMARIZE", "GENERATE_RESPONSE"):
        chain = AIService.chain(purpose)
        assert [(p.model_name, n) for p, n in chain] == [("fake-1", 2), ("fake-1-respaldo", 1)]
        assert AIService.prompt_for(purpose).version == 1
    assert AIPromptVersion.objects.count() == 4


def test_chain_without_config_uses_provider_default():
    AIModelConfig.objects.filter(purpose="SUMMARIZE").update(is_active=False)
    chain = AIService.chain("SUMMARIZE")
    assert [(p.model_name, n) for p, n in chain] == [("fake-1", 2)]


def test_contract_is_abstract():
    with pytest.raises(TypeError):
        LLMProvider()


# --- Validación del contrato (SPEC §44) ---------------------------------------------------


def test_valid_classification():
    c = validate_classification(raw())
    assert (c.intent.code, c.category.code, c.subcategory.code) == (
        "GRADE_DISCREPANCY", "ACADEMIC", "GRADES",
    )  # fmt: skip
    assert (c.priority, c.confidence, c.requires_human) == ("MEDIUM", 0.91, True)
    fenced = f"```json\n{raw(category=None, subcategory=None)}\n```"
    assert validate_classification(fenced).category is None


def test_catalog_requires_human_wins_over_llm():
    assert validate_classification(raw(requires_human=False)).requires_human is True


@pytest.mark.parametrize(
    "bad",
    [
        "no es json",
        "[1, 2]",
        json.dumps({k: v for k, v in VALID.items() if k != "priority"}),
        raw(intent="BORRAR_NOTAS"),
        raw(category="X"),
        raw(subcategory="DEBT"),  # no pertenece a ACADEMIC
        raw(category=None),  # subcategoría sin categoría
        raw(priority="URGENTE"),
        raw(confidence=1.5),
        raw(confidence="alta"),
        raw(confidence=True),
        raw(requires_human="sí"),
        raw(summary=3),
    ],
)
def test_invalid_outputs_are_rejected(bad):
    with pytest.raises(AIInvalidOutput) as exc:
        validate_classification(bad)
    assert exc.value.raw == bad


def test_inactive_intent_is_rejected(make_user):
    from apps.automation.models import Intent

    Intent.objects.filter(code="GRADE_DISCREPANCY").update(is_active=False)
    with pytest.raises(AIInvalidOutput):
        validate_classification(raw())


def test_summary_is_truncated(settings):
    settings.AI_SUMMARY_MAX_CHARS = 10
    assert validate_classification(raw(summary="x" * 50)).summary == "x" * 10


# --- Fake + AIService ---------------------------------------------------------------------


def test_classify_with_fake_tolerates_wording_rules_miss():
    service = AIService()
    c = service.classify("no logro ingresar a la plataforma virtual")
    assert c.intent.code == "ACCESS_PROBLEM" and c.category.code == "TECHNICAL"
    usage = AIUsage.objects.get()
    assert (usage.operation, usage.success, usage.model_name) == ("CLASSIFY", True, "fake-1")
    assert usage.input_tokens > 0 and usage.output_tokens > 0


def test_fake_unknown_and_urgent():
    unknown = AIService().classify("zzz qqq")
    assert (unknown.intent.code, unknown.confidence) == ("UNKNOWN_REQUEST", 0.40)
    assert AIService().classify("urgente: no puedo ingresar a la plataforma").priority == "HIGH"


def test_context_has_no_personal_data():
    ctx = classification_context()
    assert {"code", "name", "keywords", "level"} == set(ctx["intents"][0])
    assert ctx["intent_categories"]["CHECK_DEBT"] == ("FINANCIAL", "DEBT")


def test_retry_then_fallback_then_unavailable(monkeypatch):
    calls = []

    def flaky(self, text, context=None):
        calls.append(self.model_name)
        raise LLMError("caído")

    monkeypatch.setattr(FakeLLMProvider, "classify", flaky)
    with pytest.raises(AIUnavailable, match="fake-1-respaldo"):
        AIService().classify("hola")
    assert calls == ["fake-1", "fake-1", "fake-1-respaldo"]  # primario + reintento + respaldo
    assert set(AIUsage.objects.values_list("success", "error_code")) == {(False, "LLM_ERROR")}
    assert AIUsage.objects.count() == 3


def test_fallback_answers_when_primary_fails(monkeypatch):
    real = FakeLLMProvider.classify

    def primary_down(self, text, context=None):
        if self.model_name == "fake-1":
            raise LLMError("caído")
        return real(self, text, context)

    monkeypatch.setattr(FakeLLMProvider, "classify", primary_down)
    service = AIService()
    assert service.classify("olvidé mi contraseña").intent.code == "PASSWORD_PROBLEM"
    assert service.last_provider.model_name == "fake-1-respaldo"
    assert AIUsage.objects.filter(success=False).count() == 2


def test_failure_markers_for_manual_demo():
    with pytest.raises(AIUnavailable):
        AIService().classify("mis notas #fallo-llm")
    with pytest.raises(AIInvalidOutput):
        AIService().classify("mis notas #salida-invalida")


def test_extract():
    out = AIService().extract(
        "Pagué 350,50 el 12/10/2026, mi ticket hd-2026-000003",
        {"ticket_code": "str", "amount": "decimal", "date": "date", "otro": "int"},
    )
    assert out == {
        "ticket_code": "HD-2026-000003",
        "amount": Decimal("350.50"),
        "date": date(2026, 10, 12),
        "otro": None,
    }
    with pytest.raises(ValueError):
        AIService().extract("x", {"a": "lista"})


def test_extract_rejects_bad_types(monkeypatch):
    monkeypatch.setattr(
        FakeLLMProvider, "extract", lambda self, t, s: LLMResponse('{"n": "abc", "d": "ayer"}')
    )
    with pytest.raises(AIInvalidOutput):
        AIService().extract("x", {"n": "int"})
    with pytest.raises(AIInvalidOutput):
        AIService().extract("x", {"d": "date"})
    monkeypatch.setattr(
        FakeLLMProvider, "extract", lambda self, t, s: LLMResponse('{"d": "2026-01-02", "s": 5}')
    )
    assert AIService().extract("x", {"d": "date", "s": "str"}) == {"d": date(2026, 1, 2), "s": "5"}


def test_summarize(settings):
    text = AIService().summarize(["No veo mi nota. Ayer estaba.", "", "Ya revisé el portal."])
    assert text == "No veo mi nota. / Ya revisé el portal."
    settings.AI_SUMMARY_MAX_CHARS = 5
    assert len(AIService().summarize(["abcdefghij"])) == 5


def test_generate_response_never_adds_facts(monkeypatch):
    template = "Atención de 08:00 a 17:00 en la oficina A."
    assert AIService().generate_response(template) == template

    monkeypatch.setattr(
        FakeLLMProvider, "generate_response",
        lambda self, ctx: LLMResponse("¡Hola! Atendemos de 08:00 a 17:00 en la oficina A."),
    )  # fmt: skip
    assert AIService().generate_response(template).startswith("¡Hola!")

    monkeypatch.setattr(
        FakeLLMProvider, "generate_response",
        lambda self, ctx: LLMResponse("Atendemos de 08:00 a 20:00 y el sábado."),
    )  # fmt: skip
    assert AIService().generate_response(template) == template  # cifra inventada → plantilla

    def down(self, ctx):
        raise LLMError("x")

    monkeypatch.setattr(FakeLLMProvider, "generate_response", down)
    assert AIService().generate_response(template) == template


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_ai_migrations_are_reversible_with_existing_decisions():
    from django.core.management import call_command

    from apps.ai.models import AIDecision

    AIDecision.objects.create(
        operation="AGENT_RUN", prompt_version=AIService.prompt_for("CLASSIFY")
    )
    call_command("migrate", "ai", "0001", verbosity=0)
    assert AIDecision.objects.get().prompt_version is None  # la decisión se conserva
    call_command("migrate", "ai", "zero", verbosity=0)
    call_command("migrate", verbosity=0)
    assert AIPromptVersion.objects.count() == 4 and AIModelConfig.objects.count() == 8
