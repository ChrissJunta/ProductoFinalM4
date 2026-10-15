"""Estado del grafo (SPEC §46A.3).

Solo tipos serializables (el checkpointer lo persiste) y sin datos sensibles
completos: la respuesta con notas/deuda vive en `response`, no en campos aparte.
"""

import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict, total=False):
    thread_id: str
    user_id: int | None
    channel: str  # WEB | WHATSAPP
    is_verified: bool
    message: str
    intent: str | None
    entities: dict
    candidates: list[str]
    confidence: float | None
    classification_source: str  # RULES | LLM | HUMAN
    classification_valid: bool  # False si la salida del LLM no se acepta (SPEC §46)
    category: str | None
    subcategory: str | None
    summary: str
    llm_raw: str
    autonomy_level: str | None  # N0..N4
    needs_review: bool
    tool_calls: Annotated[list[dict], operator.add]
    ticket_id: int | None
    ticket_code: str | None
    response: str | None
    attempts: int
    errors: Annotated[list[str], operator.add]
    requires_human: bool
    review: dict | None
    node_path: Annotated[list[str], operator.add]
    disambiguation: list[str] | None  # candidatos del empate que razonó el LLM (CR-009)
    policy: dict | None  # política de la intención aplicada en decide_autonomy (ADR-077)
    trace: Annotated[list[dict], operator.add]  # pasos resumidos (ADR-076)
