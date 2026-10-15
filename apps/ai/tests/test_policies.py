"""Decisiones propias del agente (ADR-077): métricas, D1–D5, aprobación, reversión y efecto."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from apps.ai import circuit, policies
from apps.ai.agent import runner
from apps.ai.agent.trace import format_step
from apps.ai.models import AgentPolicyDecision, AIDecision, AIUsage, LLMCircuit
from apps.ai.service import AIService, AIUnavailable
from apps.automation.models import Intent, IntentPolicy
from apps.helpdesk.models import AuditLog, Ticket
from apps.helpdesk.tickets import TicketService

pytestmark = pytest.mark.django_db
K = AgentPolicyDecision.Kind
S = AgentPolicyDecision.Status
LIST = reverse("ai:policy_list")


@pytest.fixture(autouse=True)
def fresh_graph():
    runner.reset()
    yield
    runner.reset()


@pytest.fixture
def student(make_user):
    return make_user("ana", role="Usuario", external_id="EST-0001")


@pytest.fixture
def sup(make_user):
    return make_user("sup", role="Supervisor")


def intent(code):
    return Intent.objects.get(code=code)


def reviews(code, *, accepted=0, corrected=0, rejected=0, when=None):
    when = when or timezone.now()
    for kind, count in (("ok", accepted), ("fix", corrected), ("no", rejected)):
        for _ in range(count):
            d = AIDecision.objects.create(
                operation="AGENT_RUN",
                intent_code=code,
                accepted=kind != "no",
                corrected=kind == "fix",
                reviewed_at=when,
                requires_human=True,
            )
            AIDecision.objects.filter(pk=d.pk).update(created_at=when)


def corrected_ticket(user, text, to):
    ticket = TicketService.create(user=user, subject="s", description=text)
    AIDecision.objects.create(
        operation="AGENT_RUN",
        ticket=ticket,
        intent_code="UNKNOWN_REQUEST",
        accepted=True,
        corrected=True,
        parsed_output={"corrected_to": to},
    )


def breached(user, code, count, resolved_late=False):
    for i in range(count):
        t = TicketService.create(user=user, subject="s", description="d", intent=intent(code))
        due = timezone.now() - timedelta(hours=i + 2)
        Ticket.objects.filter(pk=t.pk).update(
            sla_due_at=due, resolved_at=due + timedelta(hours=1) if resolved_late else None
        )


def kinds(items):
    return sorted(i["kind"] if isinstance(i, dict) else i.kind for i in items)


# --- Métricas y decisiones ----------------------------------------------------------------


def test_metrics_count_reviews_and_sla(student):
    reviews("PASSWORD_PROBLEM", accepted=3, corrected=1, rejected=1)
    reviews("PASSWORD_PROBLEM", accepted=5, when=timezone.now() - timedelta(days=60))  # fuera
    breached(student, "CERTIFICATE_REQUEST", 2, resolved_late=True)
    t = TicketService.create(
        user=student, subject="s", description="d", intent=intent("CERTIFICATE_REQUEST")
    )
    Ticket.objects.filter(pk=t.pk).update(
        sla_due_at=timezone.now() + timedelta(days=1), resolved_at=timezone.now()
    )
    rows = {r["code"]: r for r in policies.intent_metrics()}
    pw = rows["PASSWORD_PROBLEM"]
    assert (pw["reviewed"], pw["accepted"], pw["corrected"], pw["rejected"]) == (5, 3, 1, 1)
    assert pw["accept_rate"] == 0.6 and pw["error_rate"] == 0.4
    cert = rows["CERTIFICATE_REQUEST"]
    assert (cert["sla_decided"], cert["sla_breached"]) == (3, 2)
    assert rows["CHECK_DEBT"]["accept_rate"] is None


def test_evaluate_takes_all_five_decisions(student):
    reviews("PASSWORD_PROBLEM", accepted=10)
    reviews("ENROLLMENT_PROBLEM", accepted=3, corrected=2)
    for text in ("documento de egresado", "acta de egresado ya", "soy egresado de aqui"):
        corrected_ticket(student, text, "CERTIFICATE_REQUEST")
    breached(student, "CERTIFICATE_REQUEST", 5)
    for _ in range(6):
        AIUsage.objects.create(provider="x", model_name="x", operation="CLASSIFY", success=False)
    assert kinds(policies.evaluate(dry_run=True)) == sorted(
        [K.TRUST_UP, K.TRUST_DOWN, K.KEYWORDS, K.PRIORITY_UP, K.LLM_PAUSE]
    )
    assert not AgentPolicyDecision.objects.exists()  # dry-run no guarda
    created = {d.kind: d for d in policies.evaluate()}
    assert {k: d.status for k, d in created.items()} == {
        K.TRUST_UP: S.PROPOSED, K.KEYWORDS: S.PROPOSED, K.PRIORITY_UP: S.PROPOSED,
        K.TRUST_DOWN: S.APPLIED, K.LLM_PAUSE: S.APPLIED,
    }  # fmt: skip
    assert created[K.KEYWORDS].change == {"add": ["egresado"]}
    assert created[K.PRIORITY_UP].change["priority"] == "MEDIUM"
    assert created[K.TRUST_UP].evidence["accepted"] == 10
    assert intent("ENROLLMENT_PROBLEM").policy.review_mode == "ALWAYS"
    assert circuit.state().state == LLMCircuit.State.OPEN
    assert AuditLog.objects.filter(action="POLICY_APPLY", actor_type="AI").count() == 2
    assert policies.evaluate() == []  # nada repetido: pendientes, ya aplicadas o en pausa
    assert policies.summary()["proposed"] == 3


def test_guardrails(student):
    reviews("GENERAL_COMPLAINT", accepted=20)  # N4: nunca pierde la revisión
    reviews("UNKNOWN_REQUEST", corrected=10)  # N4: D2 no aplica
    reviews("CHECK_DEBT", corrected=10)  # N0: sin tickets que revisar
    breached(student, "PAYMENT_NOT_REFLECTED", 6)  # su routing ya es Alta: tope
    reviews("PASSWORD_PROBLEM", accepted=9)  # bajo el mínimo de revisiones
    reviews("ACCESS_PROBLEM", accepted=8, corrected=2)  # 80 % < 90 %
    assert policies.evaluate(dry_run=True) == []


def test_reviews_count_from_last_policy_change():
    reviews("PASSWORD_PROBLEM", accepted=10, when=timezone.now() - timedelta(days=2))
    IntentPolicy.objects.create(intent=intent("PASSWORD_PROBLEM"))
    assert policies.evaluate(dry_run=True) == []


def test_keywords_skip_known_other_and_rejected_words(student, sup):
    for text in ("constancia egresado", "constancia egresado", "egresado constancia matricula"):
        corrected_ticket(student, text, "CERTIFICATE_REQUEST")  # constancia ya es suya
    for text in ("contrasena papel", "contrasena papel", "contrasena papel"):
        corrected_ticket(student, text, "ACCESS_PROBLEM")  # contrasena es de otra intención
    corrected_ticket(student, "egresado", "NO_EXISTE")
    proposals = {d.intent.code: d.change["add"] for d in policies.evaluate()}
    assert proposals == {"CERTIFICATE_REQUEST": ["egresado"], "ACCESS_PROBLEM": ["papel"]}
    for d in AgentPolicyDecision.objects.filter(status=S.PROPOSED):
        policies.reject(d, sup, "no")
    assert policies.evaluate() == []  # lo rechazado no se vuelve a proponer


# --- Aprobación, rechazo y reversión ----------------------------------------------------------


def test_approve_and_revert_each_kind(student, sup):
    reviews("PASSWORD_PROBLEM", accepted=10)
    for text in ("acta egresado", "egresado ya", "soy egresado"):
        corrected_ticket(student, text, "CERTIFICATE_REQUEST")
    breached(student, "CERTIFICATE_REQUEST", 5)
    created = {d.kind: d for d in policies.evaluate()}
    for d in created.values():
        policies.approve(d, sup, "ok")
    cert = intent("CERTIFICATE_REQUEST")
    assert "egresado" in cert.keywords.splitlines()
    assert cert.policy.priority_override == "MEDIUM"
    assert intent("PASSWORD_PROBLEM").policy.review_mode == "SKIP"
    assert AuditLog.objects.filter(entity_type="automation.intent", actor=sup).exists()
    with pytest.raises(ValidationError):
        policies.approve(created[K.TRUST_UP], sup)  # ya aplicada
    for d in created.values():
        policies.revert(d, sup, "deshacer")
    cert.refresh_from_db()
    assert "egresado" not in cert.keywords
    assert cert.policy.priority_override == ""
    assert intent("PASSWORD_PROBLEM").policy.review_mode == "DEFAULT"
    assert {d.status for d in AgentPolicyDecision.objects.all()} == {S.REVERTED}
    with pytest.raises(ValidationError):
        policies.revert(created[K.TRUST_UP], sup)


def test_reject_and_superseded_revert(sup):
    reviews("PASSWORD_PROBLEM", accepted=10)
    [up] = policies.evaluate()
    policies.approve(up, sup)
    reviews("PASSWORD_PROBLEM", corrected=5, when=timezone.now() + timedelta(seconds=1))
    [down] = policies.evaluate()  # D2 automática sobre la política que dejó D1
    assert down.kind == K.TRUST_DOWN and down.change["previous"] == "SKIP"
    with pytest.raises(ValidationError):
        policies.revert(up, sup)  # otra decisión posterior ya la cambió
    with pytest.raises(ValidationError):
        policies.reject(down, sup)  # no está propuesta
    proposal = policies.record(
        kind=K.PRIORITY_UP, intent=intent("CHECK_DEBT"), summary="s", evidence={},
        change={"priority": "HIGH", "previous": ""},
    )  # fmt: skip
    proposal = policies.reject(proposal, sup, "no")
    assert proposal.status == S.REJECTED and proposal.note == "no"
    applied = policies.record(
        kind=K.PRIORITY_UP, intent=intent("CHECK_DEBT"), summary="s", evidence={},
        change={"priority": "HIGH", "previous": ""},
    )  # fmt: skip
    policies.approve(applied, sup)
    IntentPolicy.objects.filter(intent__code="CHECK_DEBT").update(priority_override="LOW")
    with pytest.raises(ValidationError):
        policies.revert(applied, sup)


# --- D4: interruptor del LLM ------------------------------------------------------------------


def test_circuit_pauses_probes_and_resumes(student, sup, settings):
    settings.AGENT_POLICY = {**settings.AGENT_POLICY, "llm_min_calls": 3}
    with pytest.raises(AIUnavailable):  # 3 intentos fallidos → pausa automática
        AIService().classify("x #fallo-llm")
    pause = AgentPolicyDecision.objects.get(kind=K.LLM_PAUSE)
    assert pause.status == S.APPLIED and pause.evidence["failed"] == 3
    usage = AIUsage.objects.count()
    with pytest.raises(AIUnavailable, match="en pausa"):
        AIService().classify("hola")  # en pausa: ni siquiera se llama
    assert AIUsage.objects.count() == usage
    r = runner.run_agent(text="no logro acceder a la biblioteca digital", user=student)
    assert r.level == "N4" and any("en pausa" in e for e in r.errors)

    later = timezone.now() + timedelta(minutes=16)
    assert circuit.allow(later)
    circuit.after_call(False, now=later)  # la prueba falló: se extiende
    assert circuit.state().retry_at > later
    LLMCircuit.objects.update(retry_at=timezone.now() - timedelta(seconds=1))
    AIService().classify("algo no reconocido")  # la prueba responde → se reactiva
    assert circuit.state().state == LLMCircuit.State.CLOSED
    resume = AgentPolicyDecision.objects.get(kind=K.LLM_RESUME)
    assert resume.status == S.APPLIED and resume.auto
    policies.revert(resume, sup)  # revertir la reactivación = volver a pausar
    assert circuit.state().state == LLMCircuit.State.OPEN
    policies.revert(pause, sup)
    assert circuit.allow()


def test_circuit_ignores_low_volume():
    AIUsage.objects.create(provider="x", model_name="x", operation="CLASSIFY", success=False)
    circuit.after_call(False)
    assert circuit.check() is None and circuit.allow()
    assert circuit.failure_stats()["failure_rate"] == 1.0


# --- Efecto en el agente --------------------------------------------------------------------


def test_review_policy_changes_agent_route(student, monkeypatch):
    IntentPolicy.objects.create(intent=intent("ENROLLMENT_PROBLEM"), review_mode="ALWAYS")
    r = runner.run_agent(text="No puedo matricularme", user=student)
    assert r.pending_review and r.path[-1] == "request_review"
    step = next(s for s in r.decision.trace if s["node"] == "decide_autonomy")
    assert step["data"]["policy"] == {"review_mode": "ALWAYS"}

    IntentPolicy.objects.create(intent=intent("ACCESS_PROBLEM"), review_mode="SKIP")
    monkeypatch.setattr(policies.random, "random", lambda: 0.99)
    skipped = runner.run_agent(text="no logro acceder a la biblioteca digital", user=student)
    assert skipped.level == "N3" and not skipped.pending_review  # 0.80 sin revisión
    monkeypatch.setattr(policies.random, "random", lambda: 0.01)
    sampled = runner.run_agent(text="no logro acceder a la biblioteca digital", user=student)
    assert sampled.pending_review  # muestreo de control
    step = next(s for s in sampled.decision.trace if s["node"] == "decide_autonomy")
    assert "política=SKIP muestreo" in format_step(step)


def test_policy_does_not_touch_n0_or_n4(student):
    IntentPolicy.objects.create(intent=intent("CHECK_DEBT"), review_mode="ALWAYS")
    assert runner.run_agent(text="¿Cuánto debo?", user=student).level == "N0"
    assert policies.review_decision(intent("GENERAL_COMPLAINT"), "N4", True) == (True, None)


def test_priority_override_only_raises(student):
    cert = intent("CERTIFICATE_REQUEST")
    IntentPolicy.objects.create(intent=cert, priority_override="HIGH")
    t = TicketService.create(user=student, subject="s", description="d", intent=cert)
    assert t.priority == "HIGH"
    IntentPolicy.objects.filter(intent=cert).update(priority_override="LOW")
    pay = intent("PAYMENT_NOT_REFLECTED")
    IntentPolicy.objects.create(intent=pay, priority_override="LOW")
    t2 = TicketService.create(user=student, subject="s", description="d", intent=pay)
    assert t2.priority == "HIGH"  # el routing ya era Alta: no baja


# --- Vistas -----------------------------------------------------------------------------------


def test_policy_views(client, make_user, sup):
    assert client.get(LIST).status_code == 302
    make_user("ana", role="Usuario")
    client.login(username="ana", password="Clave-Segura-2026")
    assert client.get(LIST).status_code == 403
    client.logout()
    client.login(username="sup", password="Clave-Segura-2026")
    page = client.get(LIST)
    assert page.status_code == 200 and page.context["summary"]["proposed"] == 0
    assert len(page.context["metrics"]) == Intent.objects.filter(is_active=True).count()
    r = client.post(reverse("ai:policy_evaluate"), follow=True)
    assert "Sin decisiones nuevas" in r.content.decode()
    reviews("PASSWORD_PROBLEM", accepted=10)
    r = client.post(reverse("ai:policy_evaluate"), follow=True)
    assert "1 decisiones nuevas" in r.content.decode()
    d = AgentPolicyDecision.objects.get()
    url = reverse("ai:policy_decide", args=[d.pk])
    assert "Acción inválida" in client.post(url, {"action": "x"}, follow=True).content.decode()
    client.post(url, {"action": "approve", "note": "va"})
    d.refresh_from_db()
    assert d.status == S.APPLIED and d.decided_by.username == "sup" and d.note == "va"
    err = client.post(url, {"action": "approve"}, follow=True).content.decode()
    assert "Solo se puede aprobar" in err
    assert client.get(LIST, {"status": "APPLIED"}).context["decisions"][0] == d
    assert not client.get(LIST, {"status": "REJECTED"}).context["decisions"]
    client.post(url, {"action": "revert"})
    d.refresh_from_db()
    assert d.status == S.REVERTED


# --- Comandos ---------------------------------------------------------------------------------


def _cmd(name, *args):
    out = StringIO()
    call_command(name, *args, stdout=out)
    return out.getvalue()


def test_evaluate_command():
    assert "sin revisiones" in _cmd("evaluate_agent_policies")
    reviews("PASSWORD_PROBLEM", accepted=10)
    out = _cmd("evaluate_agent_policies", "--dry-run")
    assert "[simulación] D1" in out and not AgentPolicyDecision.objects.exists()
    out = _cmd("evaluate_agent_policies")
    assert "→ Propuesta" in out and "PASSWORD_PROBLEM" in out
    assert "Sin decisiones nuevas" in _cmd("evaluate_agent_policies")
    policies.approve(AgentPolicyDecision.objects.get(), None)
    assert "política=SKIP" in _cmd("evaluate_agent_policies")


def test_demo_command(settings, make_user):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        _cmd("agent_policy_demo")
    with pytest.raises(CommandError):
        _cmd("agent_policy_demo", "--force")  # sin usuario demo
    make_user("usuario", role="Usuario")
    _cmd("agent_policy_demo", "--force", "--llm-failures")
    assert kinds(policies.evaluate()) == sorted(
        [K.TRUST_UP, K.TRUST_DOWN, K.KEYWORDS, K.PRIORITY_UP, K.LLM_PAUSE]
    )
    settings.DEBUG = True
    assert "D4" not in _cmd("agent_policy_demo")
