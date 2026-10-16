"""Proveedor compatible con la API de OpenAI (ADR-069): servidor vLLM con Qwen3-8B.

Habla `POST {LLM_BASE_URL}/chat/completions` con la biblioteca estándar (sin SDK).
Sirve para cualquier servidor compatible (vLLM, OpenAI, etc.). Solo se envía el
texto del mensaje y el catálogo de intenciones; nunca notas, deuda ni datos del
usuario (SPEC §42.1).
"""

import json
import re
import urllib.error
import urllib.request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import LLMError, LLMProvider, LLMResponse, LLMTimeout

THINK = re.compile(r"<think>.*?</think>", re.S)

SYSTEM_EXTRACT = (
    "Extrae del mensaje SOLO los campos pedidos y responde únicamente con un objeto JSON. "
    "Usa null si el dato no aparece; no lo deduzcas."
)
SYSTEM_SUMMARY = (
    "Resume la conversación para un agente de mesa de ayuda universitaria en máximo 500 "
    "caracteres, en español, sin incluir notas, montos ni datos personales."
)
SYSTEM_REPHRASE = (
    "Reformula el texto oficial en tono cordial y breve, en español. No añadas hechos, cifras, "
    "fechas, teléfonos ni enlaces que no estén en el texto. Responde solo con el texto final."
)


def auth_headers():
    return {"Authorization": f"Bearer {settings.LLM_API_KEY or 'no-se-necesita'}"}


def strip_thinking(text):
    return THINK.sub("", text or "").strip()


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compat"

    def __init__(self, model_name=None):
        super().__init__(model_name=model_name or settings.LLM_MODEL)
        if not settings.LLM_BASE_URL:
            raise ImproperlyConfigured("LLM_PROVIDER=openai_compat requiere LLM_BASE_URL.")
        self.base_url = settings.LLM_BASE_URL.rstrip("/")

    # --- Transporte ------------------------------------------------------------------------

    def _chat(self, system, user, *, temperature=0.1, max_tokens=400):
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if settings.LLM_CHAT_TEMPLATE_KWARGS:  # vLLM + Qwen3: «thinking mode» por configuración
            payload["chat_template_kwargs"] = {"enable_thinking": settings.LLM_ENABLE_THINKING}
        # Opciones propias de cada servidor; nunca reemplazan modelo ni mensajes.
        payload.update(
            {k: v for k, v in settings.LLM_EXTRA_BODY.items() if k not in ("model", "messages")}
        )
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", **auth_headers()},
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.LLM_TIMEOUT) as response:
                data = json.loads(response.read())
        except TimeoutError as exc:
            raise LLMTimeout(f"El servidor LLM no respondió en {settings.LLM_TIMEOUT} s.") from exc
        except urllib.error.HTTPError as exc:
            raise LLMError(f"Servidor LLM respondió {exc.code}.") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise LLMError(f"Servidor LLM no disponible: {exc}") from exc
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Respuesta del servidor LLM con formato inesperado.") from exc
        usage = data.get("usage") or {}
        return LLMResponse(
            strip_thinking(text),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
        )

    # --- Contrato (SPEC §42) ----------------------------------------------------------------

    def classify(self, text, context=None):
        context = context or {}
        catalog = "\n".join(
            f"- {i['code']}: {i['name']} (nivel {i['level']})" for i in context.get("intents", [])
        )
        categories = json.dumps(context.get("intent_categories", {}), ensure_ascii=False)
        template = context.get("prompt_template") or "{catalog}\n\nMensaje: {message}"
        system = template.replace(
            "{catalog}", f"{catalog}\n\nCategorías por intención: {categories}"
        )
        system = system.replace("{message}", "(el mensaje va en el turno del usuario)")
        if candidates := context.get("candidates"):
            hint = (
                f"Las reglas dudan entre: {', '.join(candidates)}. Elige la que corresponda; "
                "si el mensaje pide varias cosas distintas, usa confianza menor a 0.7."
            )
            system = (
                system.replace("{candidates}", hint)
                if "{candidates}" in system
                else f"{system}\n\n{hint}"
            )
        system = system.replace("{candidates}", "")
        return self._chat(system, text, max_tokens=300)

    def extract(self, text, schema):
        fields = ", ".join(f"{k} ({v})" for k, v in schema.items())
        return self._chat(f"{SYSTEM_EXTRACT} Campos: {fields}.", text, max_tokens=200)

    def summarize(self, messages):
        joined = "\n".join(f"- {m}" for m in messages if m)
        return self._chat(SYSTEM_SUMMARY, joined, temperature=0.2, max_tokens=250)

    def generate_response(self, context):
        return self._chat(
            SYSTEM_REPHRASE, context.get("template", ""), temperature=0.3, max_tokens=300
        )
