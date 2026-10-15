"""Trazabilidad del agente (ADR-076, CONTRACT-020): traza por nodo, logs, vistas y comando."""

import json
import logging
import os
import subprocess
import sys
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from apps.ai.agent import runner
from apps.ai.agent.trace import describe, format_step, traced
from apps.ai.models import AIDecision

pytestmark = pytest.mark.django_db
LIST = reverse("ai:trace_list")


@pytest.fixture(autouse=True)
def fresh_graph():
    runner.reset()
    yield
    runner.reset()


@pytest.fixture
def student(make_user):
    return make_user("ana", role="Usuario", external_id="EST-0001")


@pytest.fixture
def supervisor(client, make_user):
    make_user("sup", role="Supervisor")
    client.login(username="sup", password="Clave-Segura-2026")
    return client


def run(text, user=None, **kw):
    return runner.run_agent(text=text, user=user, **kw)


# --- Traza persistida ------------------------------------------------------------------------


def test_trace_has_one_step_per_node_without_response_text(student):
    r = run("¿Cuánto debo?", student)
    trace = r.decision.trace
    assert [s["node"] for s in trace] == r.path
    first = trace[0]["data"]
    assert first["message"] == "¿Cuánto debo?" and first["channel"] == "WEB"
    tool = next(s for s in trace if s["node"] == "call_tool")
    assert tool["data"]["tool_calls"] == [{"tool": "get_debt", "ok": True}]
    assert tool["data"]["response_chars"] == len(r.response)
    assert "390" not in json.dumps(trace)  # la respuesta (deuda) no se guarda en la traza
    assert all(s["ms"] >= 0 and s["at"] for s in trace)
    assert r.decision.duration_ms is not None


def test_llm_calls_are_recorded_inside_their_node(student):
    r = run("algo rarísimo #fallo-llm", student)  # primario, reintento y respaldo fallan
    llm = next(s for s in r.decision.trace if s["node"] == "classify_llm")
    assert len(llm["llm_calls"]) == 3
    assert not any(c["success"] for c in llm["llm_calls"])
    assert {"provider", "model", "operation", "latency_ms", "error_code"} <= set(
        llm["llm_calls"][0]
    )
    assert "llm_calls" not in r.decision.trace[0]


def test_resume_extends_trace(student, make_user):
    reviewer = make_user("sup", role="Supervisor")
    r = run("certificado y contraseña", student)
    assert r.decision.trace[-1]["node"] == "request_review"
    decision = runner.resume_agent(r.ticket, actor=reviewer, action="accept")
    nodes = [s["node"] for s in decision.trace]
    assert nodes[-2:] == ["human_review", "apply_review"]
    assert nodes.count("request_review") == 1
    review = next(s for s in decision.trace if s["node"] == "human_review")
    assert review["data"]["review"]["action"] == "accept"


def test_fallback_trace_records_error(student, monkeypatch):
    from apps.ai.agent import nodes

    def boom(state):
        raise RuntimeError("bug")

    monkeypatch.setattr(nodes, "decide_autonomy", boom)
    runner.reset()
    r = run("Olvidé mi contraseña", student)
    [step] = r.decision.trace
    assert step["node"] == "agent_error" and step["data"]["errors"] == ["RuntimeError: bug"]


# --- Logs -----------------------------------------------------------------------------------


@pytest.fixture
def trace_log(caplog):
    """El logger `apps` no propaga a la raíz (LOGGING): se engancha el capturador directo."""
    logger = logging.getLogger("apps.ai.agent.trace")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="apps.ai.agent.trace")
    yield caplog
    logger.removeHandler(caplog.handler)


def test_each_node_and_run_summary_are_logged(student, trace_log):
    r = run("certificado y contraseña", student)
    lines = [rec.getMessage() for rec in trace_log.records if rec.name == "apps.ai.agent.trace"]
    assert all(line.startswith(f"[{r.thread_id}]") for line in lines)
    assert any("classify_rules" in line for line in lines)
    assert any("⏸ en espera de revisión humana" in line for line in lines)
    assert "revisión pendiente" in lines[-1] and "fin" in lines[-1]


def test_traced_node_logs_and_reraises_errors(trace_log):
    def broken(state):
        raise ValueError("x")

    with pytest.raises(ValueError):
        traced("demo", broken)({"thread_id": "t1"})
    assert "[t1] demo ✗ ValueError: x" in trace_log.text


def test_format_step_and_describe():
    step = {
        "node": "call_tool",
        "ms": 2.5,
        "data": {
            "confidence": 0.5,
            "tool_calls": [{"tool": "get_debt", "ok": False}],
            "errors": ["get_debt: ProviderError"],
        },
        "llm_calls": [{"model": "m", "latency_ms": 7, "success": False, "error_code": "timeout"}],
    }
    line = format_step(step)
    assert "herramienta=get_debt ✗" in line and "llm=m 7 ms ✗ timeout" in line
    assert "conf=0.50" in line and "error=get_debt: ProviderError" in line
    [described] = describe([step, {"node": "misterioso", "ms": 1}])[:1]
    assert described["stage"] == "accion" and described["has_error"]
    unknown = describe([{"node": "misterioso", "ms": 1}])[0]
    assert unknown["stage"] == "otro" and unknown["offset_ms"] == 0


def test_log_file_setting_creates_directory(tmp_path):
    target = tmp_path / "nuevo" / "agent.log"
    code = (
        "from config.settings import base;"
        "print(base.LOGGING['handlers']['file']['filename'], base.LOG_FILE.parent.exists())"
    )
    env = {**os.environ, "DJANGO_SECRET_KEY": "x", "LOG_FILE": str(target)}
    out = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    ).stdout
    assert out.split() == [str(target), "True"]


# --- Vistas ---------------------------------------------------------------------------------


def test_trace_views_require_supervisor_or_admin(client, make_user):
    assert client.get(LIST).status_code == 302  # sin sesión → login
    make_user("ana", role="Usuario")
    client.login(username="ana", password="Clave-Segura-2026")
    assert client.get(LIST).status_code == 403
    client.logout()
    make_user("jefe", role="Administrador")
    client.login(username="jefe", password="Clave-Segura-2026")
    assert client.get(LIST).status_code == 200


def test_trace_list_rows_and_filters(supervisor, student):
    debt = run("¿Cuánto debo?", student)
    review = run("certificado y contraseña", student)
    failed = run("algo rarísimo #fallo-llm", student)
    page = supervisor.get(LIST)
    rows = page.context["runs"]
    assert [r["id"] for r in rows] == [failed.decision.pk, review.decision.pk, debt.decision.pk]
    first = rows[-1]
    assert first["message"] == "¿Cuánto debo?" and first["steps"] == len(debt.path)
    assert not first["used_llm"] and not first["has_errors"]

    def ids(**params):
        return {r["id"] for r in supervisor.get(LIST, params).context["runs"]}

    assert ids(level="N0") == {debt.decision.pk}
    assert ids(status="pending") == {review.decision.pk, failed.decision.pk}
    assert ids(status="errors") == {failed.decision.pk}
    assert ids(status="llm") == {failed.decision.pk}
    assert ids(status="ticket") == {review.decision.pk, failed.decision.pk}
    assert ids(q=review.ticket.ticket_code) == {review.decision.pk}
    assert ids(q="CHECK_DEBT") == {debt.decision.pk}
    assert ids(source="RULES", channel="WEB") == {debt.decision.pk}
    today = timezone.localdate()
    assert len(ids(date_from=today, date_to=today)) == 3
    assert ids(date_from=today + timedelta(days=1)) == set()
    invalid = supervisor.get(LIST, {"level": "N9"})
    assert invalid.context["form"].errors and len(invalid.context["runs"]) == 3


def test_trace_list_paginates(supervisor, settings):
    for _ in range(26):
        AIDecision.objects.create(operation="AGENT_RUN", thread_id="run-x")
    AIDecision.objects.create(operation="CLASSIFY")  # no es una ejecución del agente
    page = supervisor.get(LIST, {"page": 2})
    assert page.context["page_obj"].paginator.count == 26 and len(page.context["runs"]) == 1
    assert "page" not in page.context["querystring"]


def test_trace_detail_and_json(supervisor, student):
    r = run("algo rarísimo #fallo-llm", student)
    url = reverse("ai:trace_detail", args=[r.decision.pk])
    page = supervisor.get(url)
    assert page.status_code == 200 and page.context["has_trace"]
    steps = page.context["steps"]
    assert [s["node"] for s in steps] == r.path
    assert steps[1]["offset_ms"] == steps[0]["ms"]
    assert len(page.context["llm_calls"]) == 3 and page.context["llm_failures"] == 3
    assert page.context["review"]["pending"]
    assert b"classify_llm" in page.content
    data = supervisor.get(reverse("ai:trace_json", args=[r.decision.pk]))
    assert data["Content-Disposition"] == f'attachment; filename="traza-{r.decision.pk}.json"'
    body = data.json()
    assert body["thread_id"] == r.thread_id and body["review"]["pending"] is True
    assert [s["node"] for s in body["trace"]] == r.path


def test_trace_detail_reviewed_and_legacy(supervisor, student, make_user):
    r = run("certificado y contraseña", student)
    runner.resume_agent(
        r.ticket, actor=make_user("rev", role="Supervisor"), action="correct",
        intent_code="CERTIFICATE_REQUEST",
    )  # fmt: skip
    page = supervisor.get(reverse("ai:trace_detail", args=[r.decision.pk]))
    assert page.context["review"]["corrected_to"] == "CERTIFICATE_REQUEST"
    assert b"Corregida a" in page.content
    legacy = AIDecision.objects.create(
        operation="AGENT_RUN", node_path=["load_context", "classify_rules"]
    )
    old = supervisor.get(reverse("ai:trace_detail", args=[legacy.pk]))
    assert not old.context["has_trace"] and b"load_context" in old.content
    other = AIDecision.objects.create(operation="CLASSIFY")
    assert supervisor.get(reverse("ai:trace_detail", args=[other.pk])).status_code == 404


def test_ticket_detail_lists_agent_runs_for_supervisor(client, student, make_user):
    r = run("certificado y contraseña", student)
    url = reverse("helpdesk:ticket_detail", args=[r.ticket.ticket_code])
    make_user("sup", role="Supervisor")
    client.login(username="sup", password="Clave-Segura-2026")
    [entry] = client.get(url).context["agent_traces"]
    assert entry["id"] == r.decision.pk and entry["autonomy_level"] == "N4"
    client.logout()
    client.login(username="ana", password="Clave-Segura-2026")
    assert client.get(url).context["agent_traces"] == []


# --- Comando --------------------------------------------------------------------------------


def _trace_cmd(*args):
    out = StringIO()
    call_command("agent_trace", *args, stdout=out)
    return out.getvalue()


def test_agent_trace_command(student):
    with pytest.raises(CommandError):
        _trace_cmd()
    debt = run("¿Cuánto debo?", student)
    review = run("algo rarísimo #fallo-llm", student)
    out = _trace_cmd()
    assert out.index(f"#{debt.decision.pk}") < out.index(f"#{review.decision.pk}")
    assert "mensaje: ¿Cuánto debo?" in out and "herramienta=get_debt" in out
    assert "revisión humana pendiente" in out and "error: LLM no disponible" in out
    assert f"ticket: {review.ticket.ticket_code}" in out
    only = _trace_cmd("--ticket", review.ticket.ticket_code)
    assert f"#{debt.decision.pk}" not in only
    data = json.loads(_trace_cmd("--id", str(debt.decision.pk), "--json"))
    assert data[0]["intent"] == "CHECK_DEBT"
    legacy = AIDecision.objects.create(operation="AGENT_RUN", node_path=["load_context"])
    assert "ruta: load_context" in _trace_cmd("--id", str(legacy.pk))
