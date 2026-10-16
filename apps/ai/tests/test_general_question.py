"""ADR-083: saludos y preguntas generales los responde el LLM, sin crear ticket."""

import pytest

from apps.ai.agent import runner
from apps.ai.models import AIUsage
from apps.ai.providers import LLMError, LLMResponse
from apps.ai.providers.fake import FakeLLMProvider
from apps.ai.service import AIService, AIUnavailable
from apps.automation import responses
from apps.automation.autonomy import determine_autonomy
from apps.automation.models import Intent, IntentAction
from apps.helpdesk.models import Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fresh_graph():
    runner.reset()
    yield
    runner.reset()


@pytest.fixture
def student(make_user):
    return make_user("ana", role="Usuario", external_id="EST-0001")


def run(text, user=None):
    return runner.run_agent(text=text, user=user)


def test_greeting_is_answered_by_the_llm_without_ticket(student):
    r = run("Hola, buenas tardes", student)
    assert (r.intent_code, r.level, r.ticket) == ("GENERAL_QUESTION", "N1", None)
    assert "classify_llm" not in r.path and r.path[-1] == "respond_template"
    assert "Mesa de Ayuda" in r.response
    assert AIUsage.objects.filter(operation="GENERATE_RESPONSE", success=True).exists()
    assert not Ticket.objects.exists()


def test_general_question_is_classified_by_llm_and_answered(student, monkeypatch):
    monkeypatch.setattr(
        FakeLLMProvider,
        "answer",
        lambda self, text: LLMResponse("La fotosíntesis es el proceso de las plantas…"),
    )
    r = run("¿Qué es la fotosíntesis?", student)
    assert (r.intent_code, r.source, r.level) == ("GENERAL_QUESTION", "LLM", "N1")
    assert r.response.startswith("La fotosíntesis") and not Ticket.objects.exists()


def test_llm_down_answers_template_and_still_no_ticket(student, monkeypatch):
    def down(self, text):
        raise LLMError("sin red")

    monkeypatch.setattr(FakeLLMProvider, "answer", down)
    r = run("hola", student)
    template = IntentAction.objects.get(intent__code="GENERAL_QUESTION").response_template
    assert (r.level, r.response, r.ticket) == ("N1", template, None)
    step = next(s for s in r.decision.trace if s["node"] == "respond_template")
    assert step["data"]["errors"][0].startswith("LLM no disponible")


def test_without_template_uses_general_fallback(student, monkeypatch):
    IntentAction.objects.filter(intent__code="GENERAL_QUESTION").update(response_template="")
    monkeypatch.setattr(FakeLLMProvider, "answer", lambda self, t: LLMResponse("   "))
    assert run("gracias", student).response == responses.GENERAL_FALLBACK


def test_answer_is_capped(settings, monkeypatch):
    settings.AI_ANSWER_MAX_CHARS = 10
    monkeypatch.setattr(FakeLLMProvider, "answer", lambda self, t: LLMResponse("x" * 50))
    assert AIService().answer("¿algo?") == "x" * 10
    monkeypatch.setattr(FakeLLMProvider, "answer", lambda self, t: LLMResponse(""))
    with pytest.raises(AIUnavailable):
        AIService().answer("¿algo?")


def test_unrecognized_request_still_creates_ticket(student):
    r = run("necesito ayuda con algo", student)
    assert r.ticket is not None and r.ticket.intent.code == "UNKNOWN_REQUEST"


def test_llm_answer_action_is_valid_n1():
    intent = Intent.objects.get(code="GENERAL_QUESTION")
    action = intent.actions.get(is_active=True)
    assert action.action_type == IntentAction.ActionType.LLM_ANSWER
    assert determine_autonomy(intent, 0.9, action) == "N1"
    assert determine_autonomy(intent, 0.6, action) == "N4"
