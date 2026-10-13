"""Clasificadores evaluados: solo reglas, y reglas + LLM (el orden de SPEC §30)."""

from apps.automation.intents import identify_intent

from ..service import AIInvalidOutput, AIService, AIUnavailable, classification_context

UNKNOWN = "UNKNOWN_REQUEST"


def rules(text):
    match = identify_intent(text)
    return match.intent.code if match.intent else UNKNOWN


def make_rules_then_llm():
    context = classification_context()
    service = AIService()

    def predict(text):
        match = identify_intent(text)
        if match.intent:
            return match.intent.code
        if match.ambiguous:  # empate: lo decide un humano, no el LLM (ADR-042)
            return UNKNOWN
        try:
            return service.classify(text, context).intent.code
        except (AIUnavailable, AIInvalidOutput):
            return UNKNOWN

    return predict
