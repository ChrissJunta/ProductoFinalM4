"""Contrato LLMProvider (SPEC §42).

Los proveedores devuelven texto crudo (`LLMResponse.text`): validar la salida es
responsabilidad de `AIService` (SPEC §44), nunca del proveedor.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMError(Exception):
    """Fallo del proveedor (red, timeout, cuota, 5xx). Se reintenta y luego se usa el respaldo."""

    code = "LLM_ERROR"


class LLMTimeout(LLMError):
    code = "LLM_TIMEOUT"


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(ABC):
    name = "abstract"
    default_model = ""
    # Costo por 1K tokens (entrada, salida) para AIUsage.estimated_cost.
    cost_per_1k = (0.0, 0.0)

    def __init__(self, model_name=None):
        self.model_name = model_name or self.default_model

    @abstractmethod
    def classify(self, text, context=None) -> LLMResponse:
        """JSON con el contrato de SPEC §44."""

    @abstractmethod
    def extract(self, text, schema) -> LLMResponse:
        """JSON con los campos de `schema` (nombre → tipo)."""

    @abstractmethod
    def summarize(self, messages) -> LLMResponse: ...

    @abstractmethod
    def generate_response(self, context) -> LLMResponse:
        """Reformula `context["template"]` sin añadir hechos (SPEC §31.1)."""

    def answer(self, text) -> LLMResponse:
        """Respuesta breve a un saludo o pregunta general (ADR-083)."""
        raise NotImplementedError
