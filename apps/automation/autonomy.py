"""Autonomy Engine (SPEC §31, BE-T14): decide el nivel N0–N4.

La decisión es determinística (catálogo `Intent.automation_level` + confianza):
el LLM nunca elige el nivel. Desde BE-T18A la ejecución de cada nivel la
orquesta el grafo LangGraph (`apps.ai.agent`, SPEC §46A): `determine_autonomy`
es el nodo `decide_autonomy`.
"""

from .models import AutomationLevel, IntentAction

L = AutomationLevel
A = IntentAction.ActionType

MIN_CONFIDENCE = 0.70  # por debajo → N4 (SPEC §46)
REVIEW_CONFIDENCE = 0.85  # 0.70–0.849 → revisión humana antes de N2/N3 (SPEC §46A.4)
MAX_MESSAGE_LENGTH = 5000  # = Ticket.description


def active_action(intent):
    if intent is None:
        return None
    return intent.actions.filter(is_active=True).first()


def determine_autonomy(intent, confidence, action=None):
    """Nivel N0–N4 para una intención ya clasificada."""
    if intent is None or confidence < MIN_CONFIDENCE:
        return L.N4
    level = intent.automation_level
    # Sin acción automática válida no se responde solo: baja a ticket (SPEC §31.1).
    if level == L.N0 and (action is None or action.action_type != A.PROVIDER_QUERY):
        return L.N3
    if level == L.N1 and (
        action is None
        or action.action_type != A.TEMPLATE_RESPONSE
        or not action.response_template.strip()
    ):
        return L.N3
    return level
