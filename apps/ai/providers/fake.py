"""FakeLLMProvider: proveedor determinístico para desarrollo, CI y demo (SPEC §42.1).

No llama a ninguna red. Imita a un LLM con coincidencia aproximada de raíces de
palabras (tolera conjugaciones y sinónimos parciales que las reglas exactas no
cubren). Su salida pasa por la misma validación que la de un proveedor real.

Para demostrar CA-007 a mano, un mensaje que contenga `#fallo-llm` simula una
caída del proveedor, y `#salida-invalida` una respuesta que no cumple el contrato.
"""

import json
import re

from apps.automation.intents import normalize

from .base import LLMError, LLMProvider, LLMResponse

FAIL_MARKER = "#fallo-llm"
INVALID_MARKER = "#salida-invalida"
STEM = 5
STOPWORDS = {
    "para", "pero", "porque", "como", "cual", "cuales", "cuando", "donde", "este", "esta",
    "esto", "estos", "esas", "esos", "tengo", "tiene", "quiero", "necesito", "puedo", "hola",
    "buenas", "buenos", "favor", "gracias", "sobre", "desde", "hasta", "tardes", "noches",
    "dias", "mucho", "mucha", "ayuda", "ayudar", "saber", "consulta", "consultar",
}  # fmt: skip
URGENT = ("urgente", "urgencia", "inmediato", "hoy mismo")


def _stems(text):
    return {w[:STEM] for w in normalize(text).split() if len(w) >= 4 and w not in STOPWORDS}


def _tokens(text):
    return len(text.split())


class FakeLLMProvider(LLMProvider):
    name = "fake"
    default_model = "fake-1"

    def _check(self, text):
        if FAIL_MARKER in text:
            raise LLMError("Fallo simulado del proveedor (FakeLLMProvider).")

    def _reply(self, prompt, payload):
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return LLMResponse(text, input_tokens=_tokens(prompt), output_tokens=_tokens(text))

    def classify(self, text, context=None):
        self._check(text)
        if INVALID_MARKER in text:
            return self._reply(text, "Creo que es sobre notas, pero no estoy seguro.")
        context = context or {}
        words = _stems(text)
        scores = []
        for intent in context.get("intents", []):
            vocab = _stems(f"{intent['name']} {intent.get('keywords', '')}")
            scores.append((len(words & vocab), intent))
        scores.sort(key=lambda s: (-s[0], s[1]["code"]))
        best, runner = (scores + [(0, None), (0, None)])[:2]
        if not best[0]:
            code, confidence = "UNKNOWN_REQUEST", 0.40
        else:
            code = best[1]["code"]
            margin = best[0] - runner[0]
            confidence = 0.60 if margin == 0 else min(0.95, 0.70 + 0.10 * margin)
        cat, sub = context.get("intent_categories", {}).get(code, (None, None))
        level = next((i["level"] for i in context.get("intents", []) if i["code"] == code), "N4")
        priority = "HIGH" if any(u in normalize(text) for u in URGENT) else "MEDIUM"
        return self._reply(
            text,
            {
                "intent": code,
                "category": cat,
                "subcategory": sub,
                "priority": priority,
                "summary": f"Solicitud del usuario: {text.strip()[:160]}",
                "requires_human": level not in ("N0", "N1"),
                "confidence": round(confidence, 2),
            },
        )

    def extract(self, text, schema):
        self._check(text)
        found = {
            "ticket_code": re.search(r"\bHD-\d{4}-\d{6}\b", text, re.IGNORECASE),
            "amount": re.search(r"(?<![\d-])\d+[.,]\d{2}\b", text),
            "date": re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", text),
        }
        out = {}
        for field in schema:
            m = found.get(field)
            value = m.group(0) if m else None
            if field == "ticket_code" and value:
                value = value.upper()
            if field == "amount" and value:
                value = value.replace(",", ".")
            out[field] = value
        return self._reply(text, out)

    def summarize(self, messages):
        joined = " ".join(m.strip() for m in messages if m and m.strip())
        self._check(joined)
        first = [re.split(r"(?<=[.!?])\s", m.strip())[0] for m in messages if m and m.strip()]
        return self._reply(joined, " / ".join(first)[:400])

    def generate_response(self, context):
        template = context.get("template", "")
        self._check(template)
        return self._reply(template, template)
