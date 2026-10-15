"""ADR-069: adaptador compatible con OpenAI (vLLM + Qwen3-8B) contra un servidor simulado."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command

from apps.ai.models import AIUsage
from apps.ai.providers import LLMError, LLMTimeout, get_llm_provider
from apps.ai.providers.openai_compat import OpenAICompatibleProvider, strip_thinking
from apps.ai.service import AIInvalidOutput, AIService

pytestmark = pytest.mark.django_db

GOOD = {
    "intent": "PAYMENT_NOT_REFLECTED", "category": "FINANCIAL", "subcategory": "PAYMENTS",
    "priority": "HIGH", "summary": "Pago no reflejado.", "requires_human": True,
    "confidence": 0.92,
}  # fmt: skip


class FakeVLLM(BaseHTTPRequestHandler):
    """Imita /v1/models y /v1/chat/completions de vLLM."""

    def log_message(self, *args):
        pass

    def _json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        self._json(200, {"data": [{"id": "Qwen/Qwen3-8B-AWQ"}]})

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(body)
        mode = self.server.mode
        if mode == "500":
            return self._json(500, {"error": "boom"})
        if mode == "slow":
            time.sleep(0.5)
        if mode == "garbage":
            return self._json(200, {"nope": 1})
        content = self.server.content
        self._json(200, {
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 40},
        })  # fmt: skip


@pytest.fixture
def vllm(settings):
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeVLLM)
    server.requests, server.mode = [], "ok"
    server.content = "<think>\n\n</think>\n\n" + json.dumps(GOOD)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings.LLM_PROVIDER = "openai_compat"
    settings.LLM_BASE_URL = f"http://127.0.0.1:{server.server_address[1]}/v1"
    settings.LLM_TIMEOUT = 2
    settings.LLM_FALLBACK_PROVIDER = ""
    yield server
    server.shutdown()


def test_classify_against_vllm(vllm):
    result = AIService().classify("Ya pagué y sigue la deuda")
    assert (result.intent.code, result.priority, result.confidence) == (
        "PAYMENT_NOT_REFLECTED", "HIGH", 0.92,
    )  # fmt: skip
    request = vllm.requests[0]
    assert request["model"] == "Qwen/Qwen3-8B-AWQ"
    assert request["chat_template_kwargs"] == {"enable_thinking": False}
    system, user = request["messages"]
    assert user == {"role": "user", "content": "Ya pagué y sigue la deuda"}
    assert "PAYMENT_NOT_REFLECTED" in system["content"] and "Devuelve SOLO" in system["content"]
    usage = AIUsage.objects.get()
    assert (usage.provider, usage.input_tokens, usage.output_tokens) == ("openai_compat", 120, 40)


def test_json_wrapped_in_prose_is_accepted(vllm):
    vllm.content = "Claro, aquí está:\n```json\n" + json.dumps(GOOD) + "\n```\nSaludos."
    assert AIService().classify("x").intent.code == "PAYMENT_NOT_REFLECTED"
    vllm.content = "Respuesta: " + json.dumps(GOOD) + " fin"
    assert AIService().classify("x").intent.code == "PAYMENT_NOT_REFLECTED"
    vllm.content = "no sé"
    with pytest.raises(AIInvalidOutput):
        AIService().classify("x")


def test_thinking_flag(vllm, settings):
    settings.LLM_ENABLE_THINKING = True
    AIService().classify("x")
    assert vllm.requests[0]["chat_template_kwargs"] == {"enable_thinking": True}
    assert strip_thinking("<think>razono\nmucho</think>  hola") == "hola"


def test_errors_map_to_llm_errors(vllm, settings):
    provider = get_llm_provider()
    vllm.mode = "500"
    with pytest.raises(LLMError, match="500"):
        provider.classify("x", {})
    vllm.mode = "garbage"
    with pytest.raises(LLMError, match="formato"):
        provider.classify("x", {})
    vllm.mode = "slow"
    settings.LLM_TIMEOUT = 0.1
    with pytest.raises(LLMTimeout):
        provider.classify("x", {})
    settings.LLM_BASE_URL = "http://127.0.0.1:9/v1"
    with pytest.raises(LLMError, match="no disponible"):
        get_llm_provider().classify("x", {})


def test_fallback_provider_when_server_down(vllm, settings):
    vllm.mode = "500"
    settings.LLM_FALLBACK_PROVIDER = "fake"
    service = AIService()
    assert service.classify("olvidé mi contraseña").intent.code == "PASSWORD_PROBLEM"
    assert service.last_provider.name == "fake"
    assert list(AIUsage.objects.values_list("provider", "success").order_by("id")) == [
        ("openai_compat", False), ("openai_compat", False), ("fake", True),
    ]  # fmt: skip


def test_other_operations(vllm):
    vllm.content = '{"ticket_code": "HD-2026-000001", "amount": "10.50"}'
    out = AIService().extract("x", {"ticket_code": "str", "amount": "decimal"})
    assert out["ticket_code"] == "HD-2026-000001"
    vllm.content = "Resumen breve."
    assert AIService().summarize(["a", "b"]) == "Resumen breve."
    template = "Atendemos de 08:00 a 17:00."
    vllm.content = "¡Hola! Atendemos de 08:00 a 17:00."
    assert AIService().generate_response(template).startswith("¡Hola!")
    vllm.content = "Atendemos 24 horas."  # cifra inventada → plantilla original
    assert AIService().generate_response(template) == template
    assert "08:00" in vllm.requests[-1]["messages"][1]["content"]


def test_requires_base_url(settings):
    settings.LLM_PROVIDER, settings.LLM_BASE_URL = "openai_compat", ""
    with pytest.raises(ImproperlyConfigured):
        OpenAICompatibleProvider()


def test_agent_uses_vllm_when_rules_do_not_resolve(vllm, make_user):
    from apps.ai.agent import runner

    runner.reset()
    vllm.content = json.dumps({**GOOD, "intent": "ACCESS_PROBLEM", "category": "TECHNICAL",
                               "subcategory": "ACCESS", "confidence": 0.9})  # fmt: skip
    r = runner.run_agent(text="la biblioteca digital me rebota", user=make_user("ana"))
    assert r.source == "LLM" and r.ticket.assigned_area.code == "IT"
    runner.reset()


def test_llm_ping_command(vllm, settings):
    out = StringIO()
    call_command("llm_ping", stdout=out)
    text = out.getvalue()
    assert "Servidor OK · modelos: Qwen/Qwen3-8B-AWQ" in text and "PAYMENT_NOT_REFLECTED" in text
    assert AIUsage.objects.count() == 0  # la prueba no deja rastro
    vllm.content = "no sé"
    with pytest.raises(CommandError):
        call_command("llm_ping", stdout=StringIO())
    settings.LLM_BASE_URL = "http://127.0.0.1:9/v1"
    with pytest.raises(CommandError, match="No se pudo contactar"):
        call_command("llm_ping", stdout=StringIO())


def test_llm_ping_with_fake(settings):
    out = StringIO()
    call_command("llm_ping", "--text", "olvidé mi contraseña", stdout=out)
    assert "PASSWORD_PROBLEM" in out.getvalue()


def test_tie_candidates_and_v2_criteria_reach_the_prompt(vllm):
    """CR-009: en un empate el agente le pide al LLM desambiguar entre los candidatos."""
    AIService().classify(
        "certificado o contraseña", candidates=["CERTIFICATE_REQUEST", "PASSWORD_PROBLEM"]
    )
    system = vllm.requests[0]["messages"][0]["content"]
    assert "Las reglas dudan entre: CERTIFICATE_REQUEST, PASSWORD_PROBLEM" in system
    assert "consulta informativa (nivel N1)" in system and "{candidates}" not in system
    AIService().classify("Ya pagué y sigue la deuda")
    assert "Las reglas dudan" not in vllm.requests[1]["messages"][0]["content"]


def test_hint_appended_when_template_has_no_placeholder(vllm):
    from apps.ai.models import AIPromptVersion

    AIPromptVersion.objects.filter(purpose="CLASSIFY", is_active=True).update(
        template="Catálogo: {catalog}"
    )
    AIService().classify("x", candidates=["A_B", "C_D"])
    system = vllm.requests[0]["messages"][0]["content"]
    assert system.startswith("Catálogo:") and "Las reglas dudan entre: A_B, C_D." in system
