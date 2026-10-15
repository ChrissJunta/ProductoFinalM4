"""Grafo del agente (SPEC §46A.4). Modificar el comportamiento del agente =
modificar este archivo: nodos, aristas y condiciones.

Todo cambio de nodos o aristas exige subir `GRAPH_VERSION`, un CHANGE REQUEST
en progress.md, pruebas de las rutas afectadas y regenerar el diagrama
(`python manage.py agent_graph` → docs/agent_graph.md).
"""

from langgraph.graph import END, START, StateGraph

from apps.automation.models import AutomationLevel, Intent

from . import nodes
from .state import AgentState
from .trace import traced

GRAPH_VERSION = "1.1.0"
L = AutomationLevel


def after_rules(state):
    if state.get("intent"):
        return "decide_autonomy"
    # Sin coincidencias o con empate entre intenciones, el agente razona con el LLM
    # (CR-009): si el LLM tampoco está seguro (< 0.70), validate_output lo lleva a N4.
    return "classify_llm"


def after_decision(state):
    level = state["autonomy_level"]
    if level == L.N0:
        return "check_auth"
    if level == L.N1:
        return "respond_template"
    return "create_ticket" if state.get("user_id") else "respond_link_instructions"


def after_auth(state):
    intent = Intent.objects.filter(code=state.get("intent")).first()
    if intent and intent.requires_authentication and not state.get("is_verified"):
        return "respond_link_instructions"
    return "call_tool"


def after_tool(state):
    if state.get("response"):
        return "respond"
    # El proveedor falló: la solicitud se convierte en ticket (SPEC §46A.4).
    return "create_ticket" if state.get("user_id") else "respond_link_instructions"


def after_ticket_response(state):
    return "request_review" if state.get("needs_review") else END


def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    for name in (
        "load_context", "classify_rules", "classify_llm", "validate_output",
        "decide_autonomy", "check_auth", "respond_link_instructions", "call_tool",
        "respond", "respond_template", "create_ticket", "route_ticket", "respond_ticket",
        "request_review", "human_review", "apply_review",
    ):  # fmt: skip
        g.add_node(name, traced(name, getattr(nodes, name)))

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "classify_rules")
    g.add_conditional_edges("classify_rules", after_rules, ["decide_autonomy", "classify_llm"])
    g.add_edge("classify_llm", "validate_output")
    g.add_edge("validate_output", "decide_autonomy")
    g.add_conditional_edges(
        "decide_autonomy",
        after_decision,
        ["check_auth", "respond_template", "create_ticket", "respond_link_instructions"],
    )
    g.add_conditional_edges("check_auth", after_auth, ["respond_link_instructions", "call_tool"])
    g.add_conditional_edges(
        "call_tool", after_tool, ["respond", "create_ticket", "respond_link_instructions"]
    )
    g.add_edge("create_ticket", "route_ticket")
    g.add_edge("route_ticket", "respond_ticket")
    g.add_conditional_edges("respond_ticket", after_ticket_response, ["request_review", END])
    g.add_edge("request_review", "human_review")
    g.add_edge("human_review", "apply_review")
    for terminal in ("respond", "respond_template", "respond_link_instructions", "apply_review"):
        g.add_edge(terminal, END)
    return g.compile(checkpointer=checkpointer)
