"""Selección del proveedor LLM por configuración (SPEC §42.1, ADR-010)."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import LLMError, LLMProvider, LLMResponse, LLMTimeout
from .fake import FakeLLMProvider

# Al decidir ADR-010 se registra aquí el proveedor real; el negocio no cambia.
REGISTRY = {"fake": FakeLLMProvider}

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
