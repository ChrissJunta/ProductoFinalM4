"""Trazabilidad del agente (ADR-076): qué hizo cada nodo, cuánto tardó y qué llamadas al
LLM ocurrieron dentro de él.

Cada nodo del grafo se envuelve con `traced`, que:
- mide la duración del nodo,
- recoge las llamadas al LLM hechas por `AIService` mientras corre (vía `contextvars`),
- añade un paso resumido a `state["trace"]` (persistido en `AIDecision.trace`), y
- escribe una línea en el logger `apps.ai.agent.trace` (consola o archivo, ver `LOGGING`).

El resumen solo guarda datos de decisión (intención, confianza, nivel, herramienta, ticket,
errores) y la longitud de la respuesta, nunca su contenido: las respuestas pueden traer
notas o deudas (SPEC §46A.3). El mensaje del usuario se guarda recortado en el primer paso.
"""

import contextvars
import logging
import time

from django.utils import timezone
from langgraph.errors import GraphInterrupt

logger = logging.getLogger("apps.ai.agent.trace")

MESSAGE_PREVIEW = 300
SUMMARY_PREVIEW = 200
SAFE_KEYS = (
    "intent",
    "confidence",
    "classification_source",
    "classification_valid",
    "candidates",
    "category",
    "subcategory",
    "autonomy_level",
    "needs_review",
    "requires_human",
    "ticket_code",
    "attempts",
    "is_verified",
)

_llm_calls = contextvars.ContextVar("agent_llm_calls", default=None)


def record_llm_call(**call):
    """Lo invoca `AIService` por cada intento; fuera de un nodo trazado no hace nada."""
    calls = _llm_calls.get()
    if calls is not None:
        calls.append(call)


def summarize(update):
    data = {key: update[key] for key in SAFE_KEYS if key in update}
    if update.get("entities"):
        data["entities"] = update["entities"]
    for key in ("tool_calls", "errors"):
        if update.get(key):
            data[key] = update[key]
    if update.get("response"):
        data["response_chars"] = len(update["response"])
    if update.get("summary"):
        data["summary"] = update["summary"][:SUMMARY_PREVIEW]
    if update.get("review"):
        data["review"] = update["review"]
    if update.get("policy"):
        data["policy"] = update["policy"]
    if update.get("disambiguation"):
        data["disambiguation"] = update["disambiguation"]
    return data


def traced(name, fn):
    def node(state):
        calls = []
        token = _llm_calls.set(calls)
        started_at, start = timezone.now(), time.monotonic()
        thread = state.get("thread_id", "?")
        try:
            update = fn(state)
        except GraphInterrupt:
            logger.info("[%s] %s ⏸ en espera de revisión humana", thread, name)
            raise
        except Exception as exc:
            logger.error("[%s] %s ✗ %s: %s", thread, name, exc.__class__.__name__, exc)
            raise
        finally:
            _llm_calls.reset(token)
        step = {
            "node": name,
            "at": started_at.isoformat(),
            "ms": round((time.monotonic() - start) * 1000, 1),
            "data": summarize(update),
        }
        if name == "load_context":
            step["data"]["message"] = state.get("message", "")[:MESSAGE_PREVIEW]
            step["data"]["channel"] = state.get("channel")
        if calls:
            step["llm_calls"] = calls
        logger.info("[%s] %s", thread, format_step(step))
        return {**update, "trace": [step]}

    node.__name__ = name
    return node


def format_step(step):
    """Línea legible de un paso: `classify_rules 2.1 ms · intent=GET_DEBT conf=0.90`."""
    data = step.get("data", {})
    parts = [f"{step['node']} {step['ms']} ms"]
    labels = (
        ("intent", "intent"),
        ("confidence", "conf"),
        ("classification_source", "origen"),
        ("autonomy_level", "nivel"),
        ("ticket_code", "ticket"),
        ("response_chars", "respuesta"),
    )
    details = []
    for key, label in labels:
        if data.get(key) is not None:
            value = data[key]
            details.append(f"{label}={value:.2f}" if key == "confidence" else f"{label}={value}")
    for call in data.get("tool_calls", []):
        details.append(f"herramienta={call.get('tool')}{'' if call.get('ok', True) else ' ✗'}")
    for call in step.get("llm_calls", []):
        status = "ok" if call.get("success") else f"✗ {call.get('error_code')}"
        details.append(f"llm={call.get('model')} {call.get('latency_ms')} ms {status}")
    if tie := data.get("disambiguation"):
        details.append(f"desambigua={'|'.join(tie)}")
    if policy := data.get("policy"):
        sampled = " muestreo" if policy.get("sampled") else ""
        details.append(f"política={policy['review_mode']}{sampled}")
    for error in data.get("errors", []):
        details.append(f"error={error}")
    if details:
        parts.append(" ".join(details))
    return " · ".join(parts)


def log_run(state, duration_ms, pending):
    path = " → ".join(state.get("node_path") or [])
    logger.info(
        "[%s] fin %.1f ms · nivel=%s intent=%s ticket=%s%s · %s",
        state.get("thread_id"),
        duration_ms,
        state.get("autonomy_level") or "—",
        state.get("intent") or "—",
        state.get("ticket_code") or "—",
        " · revisión pendiente" if pending else "",
        path,
    )


# Etapa y descripción de cada nodo para la vista de trazas (CONTRACT-020).
NODE_INFO = {
    "load_context": ("percepcion", "Carga usuario, verificación y memoria de la conversación"),
    "classify_rules": ("razonamiento", "Clasifica por reglas y palabras clave"),
    "classify_llm": ("razonamiento", "Clasifica con el LLM (las reglas no resolvieron)"),
    "validate_output": ("razonamiento", "Valida la salida del LLM y su confianza"),
    "decide_autonomy": ("decision", "Decide el nivel de autonomía (N0–N4)"),
    "check_auth": ("decision", "Verifica si la consulta exige identidad confirmada"),
    "respond_link_instructions": ("respuesta", "Pide iniciar sesión o vincular WhatsApp"),
    "call_tool": ("accion", "Consulta el sistema institucional (solo lectura)"),
    "respond": ("respuesta", "Responde con el resultado de la consulta"),
    "respond_template": ("respuesta", "Responde con la plantilla de la intención"),
    "create_ticket": ("accion", "Crea el ticket"),
    "route_ticket": ("accion", "Registra el área y la regla de routing"),
    "respond_ticket": ("respuesta", "Confirma el ticket al usuario"),
    "request_review": ("revision", "Abre la alerta de revisión humana"),
    "human_review": ("revision", "Recibe la decisión del revisor"),
    "apply_review": ("revision", "Aplica la decisión humana"),
    "agent_error": ("error", "Fallo del agente: se registró el ticket de respaldo"),
}


def describe(steps):
    """Pasos enriquecidos para la vista: etapa, descripción y desfase desde el inicio."""
    out, offset = [], 0.0
    for index, step in enumerate(steps, start=1):
        stage, description = NODE_INFO.get(step.get("node"), ("otro", step.get("node", "")))
        out.append(
            {
                **step,
                "index": index,
                "stage": stage,
                "description": description,
                "offset_ms": round(offset, 1),
                "has_error": bool(step.get("data", {}).get("errors"))
                or any(not c.get("success", True) for c in step.get("llm_calls", [])),
            }
        )
        offset += step.get("ms") or 0
    return out
