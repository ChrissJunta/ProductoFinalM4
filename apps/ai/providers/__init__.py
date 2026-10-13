"""Selección del proveedor LLM por configuración (SPEC §42.1, ADR-010)."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import LLMError, LLMProvider, LLMResponse, LLMTimeout
from .fake import FakeLLMProvider
from .openai_compat import OpenAICompatibleProvider

# ADR-010 → ADR-069: servidor vLLM (Qwen3-8B) con API compatible con OpenAI.
REGISTRY = {"fake": FakeLLMProvider, "openai_compat": OpenAICompatibleProvider}

__all__ = ["LLMError", "LLMProvider", "LLMResponse", "LLMTimeout", "get_llm_provider"]


def get_llm_provider(name=None, model_name=None):
    name = name or settings.LLM_PROVIDER
    try:
        cls = REGISTRY[name]
    except KeyError:
        raise ImproperlyConfigured(
            f"LLM_PROVIDER desconocido: {name!r}. Disponibles: {', '.join(REGISTRY)}."
        ) from None
    return cls(model_name=model_name)
