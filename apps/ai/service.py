"""AIService (SPEC §33, BE-T17/BE-T18): única puerta al LLM.

- Cadena de continuidad (SPEC §46): primario → reintento → respaldo → error
  `AIUnavailable` (quien llama deriva a humano; la solicitud no se pierde).
- Cada intento queda en `AIUsage`.
- Toda salida se valida contra el contrato y los catálogos (SPEC §44) antes de
  usarse; el LLM nunca escribe en la base (SPEC §45).
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings

from apps.automation.catalog import INTENT_CATEGORY
from apps.automation.models import Intent
from apps.helpdesk.models import Category, Subcategory, Ticket

from . import circuit
from .agent.trace import record_llm_call
from .models import AIModelConfig, AIPromptVersion, AIUsage, Operation
from .providers import LLMError, get_llm_provider

CONTRACT_KEYS = {
    "intent": str,
    "category": (str, type(None)),
    "subcategory": (str, type(None)),
    "priority": str,
    "summary": str,
    "requires_human": bool,
    "confidence": (int, float),
}
EXTRACT_TYPES = {"str", "int", "decimal", "date"}


class AIUnavailable(Exception):
    """Primario, reintentos y respaldo fallaron (SPEC §46: → humano)."""


class AIInvalidOutput(Exception):
    """La salida no cumple el contrato (SPEC §44). Se guarda la salida cruda para auditoría."""

    def __init__(self, message, raw=""):
        super().__init__(message)
        self.raw = raw


@dataclass(frozen=True)
class Classification:
    intent: Intent
    category: Category | None
    subcategory: Subcategory | None
    priority: str
    summary: str
    requires_human: bool
    confidence: float
    raw: str = ""
    parsed: dict = field(default_factory=dict)


def _parse_json(raw):
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        # Modelos locales a veces rodean el JSON con texto: se toma el primer objeto completo.
        start = text.find("{")
        try:
            data, _ = json.JSONDecoder().raw_decode(text[start:]) if start >= 0 else (None, 0)
        except ValueError:
            data = None
        if data is None:
            raise AIInvalidOutput("La salida no es JSON.", raw) from None
    if not isinstance(data, dict):
        raise AIInvalidOutput("La salida JSON no es un objeto.", raw)
    return data


def validate_classification(raw):
    """Valida JSON, esquema, catálogos, tipos y rangos (SPEC §44)."""
    data = _parse_json(raw)
    missing = set(CONTRACT_KEYS) - set(data)
    if missing:
        raise AIInvalidOutput(f"Faltan campos: {', '.join(sorted(missing))}.", raw)
    for key, types in CONTRACT_KEYS.items():
        # bool es subclase de int: se exige bool solo donde corresponde.
        if not isinstance(data[key], types) or isinstance(data[key], bool) != (types is bool):
            raise AIInvalidOutput(f"Tipo inválido en «{key}».", raw)
    confidence = float(data["confidence"])
    if not 0 <= confidence <= 1:
        raise AIInvalidOutput("La confianza debe estar entre 0 y 1.", raw)
    intent = Intent.objects.filter(code=data["intent"], is_active=True).first()
    if intent is None:
        raise AIInvalidOutput(f"Intención desconocida: {data['intent']!r}.", raw)
    category = subcategory = None
    if data["category"]:
        category = Category.objects.filter(code=data["category"], is_active=True).first()
        if category is None:
            raise AIInvalidOutput(f"Categoría desconocida: {data['category']!r}.", raw)
    if data["subcategory"]:
        if category is None:
            raise AIInvalidOutput("Subcategoría sin categoría.", raw)
        subcategory = Subcategory.objects.filter(
            category=category, code=data["subcategory"], is_active=True
        ).first()
        if subcategory is None:
            raise AIInvalidOutput(f"Subcategoría inválida: {data['subcategory']!r}.", raw)
    if data["priority"] not in Ticket.Priority.values:
        raise AIInvalidOutput(f"Prioridad inválida: {data['priority']!r}.", raw)
    summary = data["summary"].strip()[: settings.AI_SUMMARY_MAX_CHARS]
    return Classification(
        intent=intent,
        category=category,
        subcategory=subcategory,
        priority=data["priority"],
        summary=summary,
        # El catálogo manda: una intención que exige humano no se relaja por el LLM.
        requires_human=data["requires_human"] or intent.requires_human,
        confidence=confidence,
        raw=raw,
        parsed={**data, "summary": summary, "confidence": confidence},
    )


def _coerce(value, kind):
    if value is None:
        return None
    try:
        if kind == "str":
            return str(value)[:500]
        if kind == "int":
            return int(value)
        if kind == "decimal":
            return Decimal(str(value))
        if kind == "date":
            if isinstance(value, str) and "/" in value:
                d, m, y = value.split("/")
                return date(int(y), int(m), int(d))
            return date.fromisoformat(str(value))
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise AIInvalidOutput(f"Valor inválido para tipo {kind}: {value!r}.") from exc
    raise ValueError(kind)  # pragma: no cover - el esquema ya se validó


def classification_context():
    """Catálogo que se entrega al LLM: solo códigos y nombres, nunca datos personales."""
    intents = [
        {"code": i.code, "name": i.name, "keywords": i.keywords, "level": i.automation_level}
        for i in Intent.objects.filter(is_active=True)
    ]
    return {"intents": intents, "intent_categories": INTENT_CATEGORY}


class AIService:
    def __init__(self, *, ticket=None, message=None):
        self.ticket, self.message = ticket, message
        self.last_provider = None

    @staticmethod
    def prompt_for(operation):
        return AIPromptVersion.objects.filter(purpose=operation, is_active=True).first()

    @staticmethod
    def chain(operation):
        """[(proveedor, intentos)] según AIModelConfig del proveedor configurado."""
        configs = AIModelConfig.objects.filter(
            provider=settings.LLM_PROVIDER, purpose=operation, is_active=True
        )
        primary = configs.filter(is_primary=True).first()
        fallback = configs.filter(is_fallback=True).first()
        chain = [
            (
                get_llm_provider(model_name=primary.model_name if primary else None),
                1 + settings.AI_MAX_RETRIES,
            )
        ]
        if fallback:
            chain.append((get_llm_provider(model_name=fallback.model_name), 1))
        elif (
            settings.LLM_FALLBACK_PROVIDER
            and settings.LLM_FALLBACK_PROVIDER != settings.LLM_PROVIDER
        ):
            chain.append((get_llm_provider(settings.LLM_FALLBACK_PROVIDER), 1))
        return chain

    def _call(self, operation, method, *args):
        if not circuit.allow():  # D4: el agente pausó el LLM por fallas repetidas
            raise AIUnavailable("LLM en pausa por fallas repetidas (decisión D4)")
        errors = []
        for provider, attempts in self.chain(operation):
            for _ in range(attempts):
                start = time.monotonic()
                try:
                    response = getattr(provider, method)(*args)
                except LLMError as exc:
                    self._usage(provider, operation, start, None, exc.code)
                    errors.append(f"{provider.model_name}: {exc}")
                    continue
                self._usage(provider, operation, start, response, "")
                self.last_provider = provider
                circuit.after_call(True)
                return response
        circuit.after_call(False)
        raise AIUnavailable("; ".join(errors))

    def _usage(self, provider, operation, start, response, error_code):
        tokens_in = response.input_tokens if response else 0
        tokens_out = response.output_tokens if response else 0
        cin, cout = provider.cost_per_1k
        record_llm_call(
            provider=provider.name,
            model=provider.model_name,
            operation=operation,
            latency_ms=int((time.monotonic() - start) * 1000),
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            success=response is not None,
            error_code=error_code,
        )
        AIUsage.objects.create(
            ticket=self.ticket,
            message=self.message,
            provider=provider.name,
            model_name=provider.model_name,
            operation=operation,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            latency_ms=int((time.monotonic() - start) * 1000),
            estimated_cost=Decimal(str(round((tokens_in * cin + tokens_out * cout) / 1000, 6))),
            success=response is not None,
            error_code=error_code,
        )

    # --- Operaciones (SPEC §33) ----------------------------------------------------------

    def classify(self, text, context=None):
        context = dict(context or classification_context())
        prompt = self.prompt_for(Operation.CLASSIFY)
        if prompt is not None:
            context.setdefault("prompt_template", prompt.template)
        response = self._call(Operation.CLASSIFY, "classify", text, context)
        return validate_classification(response.text)

    def extract(self, text, schema):
        """`schema`: {campo: "str" | "int" | "decimal" | "date"}. Devuelve solo esos campos."""
        unknown = set(schema.values()) - EXTRACT_TYPES
        if unknown:
            raise ValueError(f"Tipos no soportados: {unknown}")
        response = self._call(Operation.EXTRACT, "extract", text, schema)
        data = _parse_json(response.text)
        return {name: _coerce(data.get(name), kind) for name, kind in schema.items()}

    def summarize(self, messages):
        response = self._call(Operation.SUMMARIZE, "summarize", list(messages))
        return response.text.strip()[: settings.AI_SUMMARY_MAX_CHARS]

    def generate_response(self, template, facts=None):
        """Reformula una plantilla N1 sin añadir hechos (SPEC §31.1).

        Si la reformulación introduce cifras que no estaban en la plantilla o en
        `facts`, o el proveedor falla, se devuelve la plantilla original.
        """
        try:
            response = self._call(
                Operation.GENERATE_RESPONSE,
                "generate_response",
                {"template": template, "facts": facts or {}},
            )
        except AIUnavailable:
            return template
        text = response.text.strip()
        allowed = set(re.findall(r"\d+", f"{template} {json.dumps(facts or {})}"))
        if not text or set(re.findall(r"\d+", text)) - allowed:
            return template
        return text
