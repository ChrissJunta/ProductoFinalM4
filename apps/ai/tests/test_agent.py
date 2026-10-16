"""BE-T18A: grafo agéntico LangGraph (SPEC §46A.9) con FakeLLMProvider e InMemorySaver."""

from datetime import date
from io import StringIO

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.urls import reverse

from apps.ai.agent import runner
from apps.ai.agent.graph import GRAPH_VERSION
from apps.ai.agent.tools import READ_TOOLS, ToolNotAllowed, run_read_tool
from apps.ai.models import AIDecision, AIUsage
from apps.ai.providers import LLMResponse
from apps.ai.providers.fake import FakeLLMProvider
from apps.helpdesk.models import Alert, Area, AuditLog, Ticket
from apps.integrations.institutional.local import LocalProvider

pytestmark = pytest.mark.django_db

WEDNESDAY = date(2026, 10, 14)


@pytest.fixture(autouse=True)
def fresh_graph():
    runner.reset()
    yield
    runner.reset()


@pytest.fixture
def student(make_user):
    return make_user("ana", role="Usuario", external_id="EST-0001")


@pytest.fixture
def on_wednesday(monkeypatch):
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: WEDNESDAY)


def run(text, user=None, **kw):
    return runner.run_agent(text=text, user=user, **kw)


# --- Rutas N0–N4 -----------------------------------------------------------------------------


def test_n0_rules_resolve_without_llm(student):
    r = run("¿Cuánto debo?", student)
    assert r.level == "N0" and "USD 390.00" in r.response
    assert "classify_llm" not in r.path and AIUsage.objects.count() == 0
    d = r.decision
    assert (d.operation, d.graph_version, d.node_path, d.thread_id) == (
        "AGENT_RUN", GRAPH_VERSION, r.path, r.thread_id,
    )  # fmt: skip
    assert d.parsed_output["tool_calls"] == [{"tool": "get_debt", "ok": True}]
    assert d.prompt_version is None and not d.requires_human


def test_n0_via_llm_when_rules_do_not_resolve(student, monkeypatch):
    payload = (
        '{"intent": "CHECK_DEBT", "category": "FINANCIAL", "subcategory": "DEBT",'
        ' "priority": "MEDIUM", "summary": "s", "requires_human": false, "confidence": 0.9}'
    )
    monkeypatch.setattr(FakeLLMProvider, "classify", lambda self, t, c=None: LLMResponse(payload))
    r = run("frase que ninguna regla reconoce", student)
    assert r.path == [
        "load_context", "classify_rules", "classify_llm", "validate_output", "decide_autonomy",
        "check_auth", "call_tool", "respond",
    ]  # fmt: skip
    assert r.level == "N0" and "USD 390.00" in r.response


def test_llm_classifies_what_rules_miss(student):
    r = run("no logro acceder a la biblioteca digital", student)
    assert r.path[:4] == ["load_context", "classify_rules", "classify_llm", "validate_output"]
    assert r.source == "LLM" and r.ticket is not None
    assert r.decision.prompt_version.purpose == "CLASSIFY"
    assert r.decision.raw_output.startswith("{")


def test_n1_template(student):
    r = run("¿Cuáles son los requisitos?")
    assert r.level == "N1" and r.path[-1] == "respond_template" and r.ticket is None


def test_n2_ticket_with_category_from_catalog(student):
    r = run("Mi nota de Cálculo está incorrecta", student)
    t = r.ticket
    assert (r.level, t.category.code, t.subcategory.code, t.assigned_area.code) == (
        "N2", "ACADEMIC", "GRADES", "ACADEMIC",
    )  # fmt: skip
    assert r.path[-3:] == ["create_ticket", "route_ticket", "respond_ticket"]
    assert not r.pending_review and t.classification_source == "RULES"


def test_n4_ambiguous_pauses_for_human_review(student):
    r = run("certificado y contraseña", student)
    assert (r.level, r.pending_review) == ("N4", True)
    assert r.decision.requires_human and r.decision.pending_review
    assert r.ticket.alerts.get().alert_type == Alert.Type.HUMAN_REVIEW
    assert r.ticket.classification_source == ""
    assert "Un agente la revisará" in r.response  # el usuario no queda esperando


# --- Fallos del LLM (CA-007) ---------------------------------------------------------------


def test_ca007_llm_error_retry_fallback_then_human(student):
    r = run("algo rarísimo #fallo-llm", student)
    assert r.level == "N4" and r.pending_review and r.ticket is not None
    assert AIUsage.objects.filter(success=False).count() == 3  # primario, reintento, respaldo
    assert any("LLM no disponible" in e for e in r.errors)
    assert r.ticket.intent.code == "UNKNOWN_REQUEST"


def test_invalid_llm_output_goes_to_human(student):
    r = run("algo rarísimo #salida-invalida", student)
    assert r.level == "N4" and r.pending_review
    assert r.decision.raw_output.startswith("Creo que")  # salida cruda auditada


def test_low_llm_confidence_goes_to_human(student):
    r = run("zzz qqq", student)  # fake: UNKNOWN_REQUEST con 0.40
    assert "validate_output" in r.path and r.level == "N4" and r.pending_review
    assert r.intent_code is None


def test_medium_llm_confidence_creates_ticket_and_review(student, monkeypatch):
    payload = (
        '{"intent": "PASSWORD_PROBLEM", "category": "TECHNICAL", "subcategory": "PASSWORD",'
        ' "priority": "MEDIUM", "summary": "s", "requires_human": true, "confidence": 0.75}'
    )
    monkeypatch.setattr(FakeLLMProvider, "classify", lambda self, t, c=None: LLMResponse(payload))
    r = run("algo no reconocido por reglas", student)
    assert (r.level, r.intent_code, r.pending_review) == ("N3", "PASSWORD_PROBLEM", True)
    assert r.ticket.assigned_area.code == "IT" and r.ticket.classification_source == "LLM"


def test_graph_crash_never_loses_request(student, monkeypatch):
    def boom(state):
        raise RuntimeError("bug")

    from apps.ai.agent import nodes

    monkeypatch.setattr(nodes, "decide_autonomy", boom)
    runner.reset()
    r = run("Olvidé mi contraseña", student)
    assert r.path == ["agent_error"] and r.ticket is not None
    assert r.ticket.alerts.get().alert_type == Alert.Type.HUMAN_REVIEW
    assert r.errors == ["RuntimeError: bug"]
    anonymous = run("Olvidé mi contraseña")
    assert anonymous.ticket is None and "identificarte" in anonymous.response


def test_step_limit_falls_back(student, settings):
    settings.AGENT_MAX_STEPS = 3
    r = run("Olvidé mi contraseña", student)
    assert r.path == ["agent_error"] and "GraphRecursionError" in r.errors[0]
    assert r.ticket is not None


# --- Autenticación y herramientas ------------------------------------------------------------


def test_unverified_sender_never_reaches_call_tool(student):
    r = run("¿Cuánto debo?", student, channel="WHATSAPP", is_verified=False)
    assert "call_tool" not in r.path and r.path[-1] == "respond_link_instructions"
    assert "390" not in r.response
    assert run("¿Cuánto debo?").path[-1] == "respond_link_instructions"


def test_anonymous_ticket_intent_gets_instructions():
    r = run("Olvidé mi contraseña")
    assert r.ticket is None and r.path[-1] == "respond_link_instructions"


def test_provider_failure_becomes_ticket(student, monkeypatch):
    monkeypatch.setattr(LocalProvider, "get_debt", lambda self, user: 1 / 0)
    r = run("¿Cuánto debo?", student)
    assert r.ticket is not None and "No pudimos consultar" in r.response
    assert r.decision.parsed_output["tool_calls"][0] == {"tool": "get_debt", "ok": False}


def test_write_tools_are_not_exposed():
    assert "create_ticket" not in READ_TOOLS and "route_ticket" not in READ_TOOLS
    assert set(READ_TOOLS) == {
        "get_schedule", "get_grades", "get_debt", "get_enrollment", "get_subjects",
        "get_ticket_status",
    }  # fmt: skip


def test_read_tool_validation(student):
    with pytest.raises(ToolNotAllowed):
        run_read_tool("create_ticket", user_id=student.pk, channel="WEB")
    with pytest.raises(ToolNotAllowed):
        run_read_tool("get_debt", user_id=student.pk, channel="WEB", args={"user_id": 99})
    with pytest.raises(ToolNotAllowed):
        run_read_tool("get_debt", user_id=None, channel="WEB")
    with pytest.raises(ToolNotAllowed):
        run_read_tool("get_ticket_status", user_id=student.pk, channel="WEB",
                      args={"ticket_code": "' OR 1=1"})  # fmt: skip
    with pytest.raises(ToolNotAllowed):
        run_read_tool("get_schedule", user_id=student.pk, channel="WEB", args={"date": "ayer"})


# --- Memoria de conversación (CA-010) ----------------------------------------------------------


def test_ca010_contextual_follow_up(student, on_wednesday):
    first = run("¿Cuál es mi horario de hoy?", student)
    assert "Tu horario de hoy (miércoles 14/10/2026)" in first.response
    follow = run("¿Y mañana?", student)
    assert (follow.intent_code, follow.level) == ("CHECK_SCHEDULE", "N0")
    assert "Tu horario de mañana (jueves 15/10/2026)" in follow.response
    assert "09:00–11:00 Programación I" in follow.response


def test_context_expires_and_is_per_channel(student, on_wednesday):
    from apps.helpdesk.conversations import get_conversation

    run("¿Cuál es mi horario de hoy?", student)
    assert run("¿Y mañana?", student, channel="WHATSAPP").intent_code != "CHECK_SCHEDULE"
    conv = get_conversation(student, "WEB")
    conv.last_message_at = conv.last_message_at.replace(year=2020)
    conv.save()
    assert run("¿Y mañana?", student).intent_code != "CHECK_SCHEDULE"


def test_schedule_for_day_without_classes(student, monkeypatch):
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: date(2026, 10, 15))
    r = run("mi horario pasado mañana", student)
    assert r.response == "No tienes clases registradas el sábado 17/10/2026."


# --- Revisión humana: interrupt y reanudación -------------------------------------------------


@pytest.fixture
def reviewer(make_user):
    sup = make_user("sup", role="Supervisor")
    return sup


def test_resume_accept(student, reviewer):
    r = run("certificado y contraseña", student)
    decision = runner.resume_agent(r.ticket, actor=reviewer, action="accept")
    assert decision.accepted is True and not decision.corrected
    assert decision.node_path[-2:] == ["human_review", "apply_review"]
    assert r.ticket.alerts.get().status == Alert.Status.RESOLVED
    with pytest.raises(ValidationError):
        runner.resume_agent(r.ticket, actor=reviewer, action="accept")  # ya no hay pendiente


def test_resume_correct_reroutes_and_audits(student, reviewer):
    r = run("certificado y contraseña", student)
    decision = runner.resume_agent(
        r.ticket, actor=reviewer, action="correct", intent_code="PASSWORD_PROBLEM"
    )
    t = Ticket.objects.get(pk=r.ticket.pk)
    assert (t.intent.code, t.assigned_area.code, t.classification_source) == (
        "PASSWORD_PROBLEM", "IT", "HUMAN",
    )  # fmt: skip
    assert (t.category.code, t.subcategory.code, t.version) == ("TECHNICAL", "PASSWORD", 2)
    assert decision.corrected and decision.corrected_by == reviewer
    assert decision.parsed_output["corrected_to"] == "PASSWORD_PROBLEM"
    assert AuditLog.objects.filter(
        entity_type="helpdesk.ticket", entity_id=str(t.pk), action="UPDATE"
    ).exists()


def test_resume_reject_and_validation(student, reviewer):
    r = run("certificado y contraseña", student)
    with pytest.raises(ValidationError):
        runner.resume_agent(r.ticket, actor=reviewer, action="borrar")
    with pytest.raises(ValidationError):
        runner.resume_agent(r.ticket, actor=reviewer, action="correct", intent_code="NOPE")
    decision = runner.resume_agent(r.ticket, actor=reviewer, action="reject")
    assert decision.accepted is False
    assert Ticket.objects.get(pk=r.ticket.pk).intent.code == "UNKNOWN_REQUEST"


def test_correct_only_while_new(student, reviewer, make_user):
    from apps.helpdesk import assignment

    r = run("certificado y contraseña", student)
    agent = make_user("ag", role="Agente")
    Area.objects.get(code="SERVICE").agents.add(agent)
    assignment.assign(r.ticket, actor=reviewer, area=r.ticket.assigned_area, assignee=agent)
    with pytest.raises(ValidationError):
        runner.resume_agent(
            r.ticket, actor=reviewer, action="correct", intent_code="PASSWORD_PROBLEM"
        )
    assert runner.resume_agent(r.ticket, actor=agent, action="accept").accepted


def test_review_permissions(student, make_user):
    r = run("certificado y contraseña", student)
    for user in (
        student,
        make_user("adm", role="Administrador"),
        make_user("other", role="Agente"),
    ):
        with pytest.raises(PermissionDenied):
            runner.resume_agent(r.ticket, actor=user, action="accept")


def test_resume_without_checkpoint_still_applies(student, reviewer):
    r = run("certificado y contraseña", student)
    runner.reset()  # memoria perdida (reinicio del proceso)
    decision = runner.resume_agent(r.ticket, actor=reviewer, action="accept")
    assert decision.accepted and "Hilo no disponible para reanudar." in decision.errors


def test_new_message_does_not_discard_pending_review(student, reviewer):
    """CR-008: cada mensaje usa su propio hilo; la revisión pendiente sigue reanudable."""
    r = run("certificado y contraseña", student)
    run("¿Cuánto debo?", student)
    decision = runner.resume_agent(r.ticket, actor=reviewer, action="accept")
    assert decision.node_path[-1] == "apply_review"


# --- Vista de revisión (CONTRACT-015) -------------------------------------------------------


def test_review_view_and_detail_context(client, student, reviewer):
    r = run("certificado y contraseña", student)
    code = r.ticket.ticket_code
    client.force_login(reviewer)
    ctx = client.get(reverse("helpdesk:ticket_detail", args=[code])).context["ai_review"]
    assert ctx["candidates"] == ["CERTIFICATE_REQUEST", "PASSWORD_PROBLEM"]
    assert ctx["can_correct"] and ("PASSWORD_PROBLEM", "Problema de contraseña") in ctx["intents"]
    url = reverse("ai:ticket_review", args=[code])
    bad = client.post(url, {"action": "x"})
    assert bad.status_code == 302
    bad = client.post(url, {"action": "correct", "intent": "NOPE"})
    assert bad.status_code == 302 and AIDecision.objects.get(pk=r.decision.pk).accepted is None
    ok = client.post(url, {"action": "correct", "intent": "PASSWORD_PROBLEM"})
    assert ok.status_code == 302 and ok.url == reverse("helpdesk:ticket_detail", args=[code])
    detail = client.get(reverse("helpdesk:ticket_detail", args=[code]))
    assert detail.context["ai_review"] is None


def test_review_view_permissions(client, student, make_user):
    r = run("certificado y contraseña", student)
    url = reverse("ai:ticket_review", args=[r.ticket.ticket_code])
    client.force_login(student)
    assert (
        client.get(reverse("helpdesk:ticket_detail", args=[r.ticket.ticket_code])).context[
            "ai_review"
        ]
        is None
    )
    assert client.post(url, {"action": "accept"}).status_code == 403
    client.force_login(make_user("other", role="Agente"))
    assert client.post(url, {"action": "accept"}).status_code == 404  # no visible


# --- Diagrama y checkpointer PostgreSQL --------------------------------------------------------


def test_graph_diagram_is_up_to_date():
    out = StringIO()
    call_command("agent_graph", "--check", stdout=out)
    assert "al día" in out.getvalue()


def test_agent_graph_command_check_detects_drift(tmp_path, monkeypatch):
    from apps.ai.management.commands import agent_graph

    monkeypatch.setattr(agent_graph, "DOC", tmp_path / "docs" / "agent_graph.md")
    with pytest.raises(SystemExit):
        call_command("agent_graph", "--check")
    call_command("agent_graph", stdout=StringIO())
    call_command("agent_graph", "--check", stdout=StringIO())


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_postgres_checkpointer_persists_pause_and_resume(settings, make_user):
    settings.AGENT_CHECKPOINTER = "postgres"
    runner.reset()
    student = make_user("pg", role="Usuario")
    sup = make_user("pgsup", role="Supervisor")
    r = run("certificado y contraseña", student)
    runner.reset()  # «reinicio»: el hilo pausado se recupera de PostgreSQL
    decision = runner.resume_agent(r.ticket, actor=sup, action="accept")
    # el empate pasó por el LLM, que tampoco estaba seguro (CR-009)
    assert decision.node_path[-1] == "apply_review" and decision.errors == ["LLM: confianza baja"]


# --- CR-009: el empate de reglas lo razona el agente con el LLM --------------------------------


def test_rule_tie_is_disambiguated_by_llm(student, monkeypatch):
    seen = {}

    def classify(self, text, context=None):
        seen["candidates"] = (context or {}).get("candidates")
        return LLMResponse(
            '{"intent": "CERTIFICATE_REQUEST", "category": "ACADEMIC", "subcategory": '
            '"CERTIFICATES", "priority": "MEDIUM", "summary": "s", "requires_human": true, '
            '"confidence": 0.9}'
        )

    monkeypatch.setattr(FakeLLMProvider, "classify", classify)
    r = run("certificado y contraseña", student)
    assert seen["candidates"] == ["CERTIFICATE_REQUEST", "PASSWORD_PROBLEM"]
    assert r.path[:4] == ["load_context", "classify_rules", "classify_llm", "validate_output"]
    assert (r.intent_code, r.level, r.pending_review) == ("CERTIFICATE_REQUEST", "N3", False)
    step = next(s for s in r.decision.trace if s["node"] == "classify_llm")
    assert step["data"]["disambiguation"] == ["CERTIFICATE_REQUEST", "PASSWORD_PROBLEM"]
    assert r.decision.prompt_version.version == 3


def test_fake_llm_only_chooses_among_candidates():
    from apps.ai.service import AIService

    result = AIService().classify(
        "no puedo ingresar a mi correo", candidates=["PASSWORD_PROBLEM", "CHECK_CONTACT"]
    )
    assert result.intent.code in ("PASSWORD_PROBLEM", "CHECK_CONTACT")
