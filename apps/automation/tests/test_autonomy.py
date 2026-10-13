"""BE-T14: Autonomy Engine N0–N4 (SPEC §31) sobre LocalProvider (BE-T15)."""

from datetime import date
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.automation.autonomy import determine_autonomy
from apps.automation.models import Intent, IntentAction
from apps.automation.services import AutomationService
from apps.helpdesk import assignment, catalogs
from apps.helpdesk.models import Alert, Area, Category, Ticket
from apps.helpdesk.tickets import TicketService
from apps.integrations.institutional.local import LocalProvider

pytestmark = pytest.mark.django_db

WEDNESDAY = date(2026, 10, 14)


@pytest.fixture
def student(make_user):
    return make_user("ana", role="Usuario", external_id="EST-0001")


@pytest.fixture
def on_wednesday(monkeypatch):
    monkeypatch.setattr(
        "apps.integrations.institutional.local.timezone.localdate", lambda: WEDNESDAY
    )


def ask(text, user=None, channel="WEB"):
    return AutomationService.handle_message(text=text, user=user, channel=channel)


# --- N0: consultas estructuradas (CA-001 a CA-003) ---------------------------------------


def test_ca001_schedule(student, on_wednesday):
    r = ask("¿Cuál es mi horario de hoy?", student)
    assert (r.intent_code, r.level, r.ticket) == ("CHECK_SCHEDULE", "N0", None)
    assert "miércoles 14/10/2026" in r.response
    assert "07:00–09:00 Cálculo I (A-201)" in r.response
    assert r.path == [
        "load_context", "classify_rules", "decide_autonomy", "check_auth", "call_tool", "respond",
    ]  # fmt: skip
    assert Ticket.objects.count() == 0


def test_ca002_grades(student):
    r = ask("quiero ver mis notas", student)
    assert (r.intent_code, r.level) == ("CHECK_GRADE", "N0")
    assert "periodo 2026-2" in r.response and "Programación I: 8.50 (En curso)" in r.response


def test_ca003_debt_web_detail_and_whatsapp_minimized(student):
    web = ask("¿Cuánto debo?", student)
    assert "USD 390.00" in web.response and "Matrícula 2026-2: 350.00" in web.response
    wa = ask("¿Cuánto debo?", student, channel="WHATSAPP")
    assert "USD 390.00" in wa.response and "Matrícula" not in wa.response  # SPEC §35.1


def test_other_n0_queries(student, make_user):
    assert "Ingeniería de Software: Matriculado" in ask("¿estoy matriculado?", student).response
    assert "13 créditos" in ask("qué materias tengo", student).response
    eva = make_user("eva", role="Usuario", external_id="EST-0002")
    assert ask("cuánto debo", eva).response == "No tienes valores pendientes de pago."


def test_empty_results(student, monkeypatch):
    monkeypatch.setattr(
        "apps.integrations.institutional.local.timezone.localdate", lambda: date(2026, 10, 18)
    )
    assert ask("mi horario", student).response == "Hoy no tienes clases registradas."
    monkeypatch.setattr(LocalProvider, "get_grades", lambda self, user, period=None: [])
    monkeypatch.setattr(LocalProvider, "get_subjects", lambda self, user, period=None: [])
    assert "No hay notas" in ask("mis notas", student).response
    assert "No tienes asignaturas" in ask("mis materias", student).response


def test_n0_requires_authentication():
    r = ask("¿Cuánto debo?")
    assert r.path[-2:] == ["check_auth", "respond_link_instructions"]
    assert "Perfil → WhatsApp" in r.response and "390" not in r.response
    assert Ticket.objects.count() == 0


def test_provider_failure_creates_ticket(student, monkeypatch):
    def boom(self, user, period=None):
        raise ConnectionError("SGA caído")

    monkeypatch.setattr(LocalProvider, "get_grades", boom)
    r = ask("mis notas", student)
    assert r.path[-4:-2] == ["call_tool", "create_ticket"] and r.ticket is not None
    assert r.errors == ["get_grades: ProviderError"]
    assert (r.level, r.ticket.intent.code, r.ticket.user) == ("N3", "CHECK_GRADE", student)
    assert "No pudimos consultar" in r.response and r.ticket.ticket_code in r.response


def test_provider_failure_with_human_review_fallback(student, monkeypatch):
    IntentAction.objects.filter(intent__code="CHECK_GRADE").update(fallback_action="HUMAN_REVIEW")
    monkeypatch.setattr(LocalProvider, "get_grades", lambda *a, **k: 1 / 0)
    r = ask("mis notas", student)
    assert r.level == "N4"
    assert r.ticket.alerts.get().alert_type == Alert.Type.HUMAN_REVIEW


def test_student_without_institutional_record_gets_ticket(make_user):
    r = ask("mis notas", make_user("nuevo", role="Usuario"))
    assert r.ticket is not None and r.errors == ["get_grades: StudentNotFound"]


# --- CHECK_TICKET (CA-009) ---------------------------------------------------------------


def test_ca009_ticket_status_only_own_tickets(student, make_user):
    mine = TicketService.create(user=student, subject="Acceso", description="d")
    other = TicketService.create(user=make_user("otro"), subject="Ajeno", description="d")
    r = ask(f"¿Cómo va {mine.ticket_code}?", student)
    assert (r.intent_code, r.level) == ("CHECK_TICKET", "N0")
    assert f"{mine.ticket_code} «Acceso»: Nuevo" in r.response
    leaked = ask(f"estado de {other.ticket_code}", student)
    assert "No encontramos" in leaked.response and "Ajeno" not in leaked.response


def test_ticket_status_lists_open_tickets(student):
    assert ask("seguimiento de mi solicitud", student).response == "No tienes solicitudes abiertas."
    t = TicketService.create(user=student, subject="Primero", description="d",
                             category=Category.objects.get(code="FINANCIAL"))  # fmt: skip
    r = ask("seguimiento de mi solicitud", student)
    assert f"{t.ticket_code} «Primero»: Nuevo, área {t.assigned_area.name}" in r.response


# --- N1: conocimiento autorizado -----------------------------------------------------------


def test_n1_template_without_authentication():
    r = ask("¿Cuáles son los requisitos?")
    template = IntentAction.objects.get(intent__code="CHECK_REQUIREMENTS").response_template
    assert (r.level, r.response, r.ticket) == ("N1", template.strip(), None)
    assert r.path[-1] == "respond_template"


def test_n1_without_template_falls_to_ticket(student):
    IntentAction.objects.filter(intent__code="CHECK_CONTACT").update(is_active=False)
    r = ask("necesito un contacto", student)
    assert r.level == "N3" and r.ticket.intent.code == "CHECK_CONTACT"


# --- N2 / N3: ticket ------------------------------------------------------------------------


def test_ca004_grade_discrepancy_is_n2(student):
    r = ask("Mi nota de Cálculo I está incorrecta, debería ser 8", student)
    t = r.ticket
    assert (r.intent_code, r.level, r.requires_human) == ("GRADE_DISCREPANCY", "N2", True)
    assert (t.assigned_area.code, t.priority, t.status, t.channel) == (
        "ACADEMIC", "MEDIUM", "NEW", "WEB",
    )  # fmt: skip
    assert (t.classification_source, float(t.classification_score)) == ("RULES", 0.9)
    assert t.description.startswith("Mi nota de Cálculo I")
    assert "validará" in r.response and t.ticket_code in r.response
    assert not t.alerts.exists()  # confianza alta: sin revisión previa


def test_ca005_payment_not_reflected(student):
    r = ask("Ya pagué la matrícula y sigue apareciendo la deuda", student, channel="WHATSAPP")
    assert (r.ticket.assigned_area.code, r.ticket.priority, r.ticket.channel) == (
        "FINANCE", "HIGH", "WHATSAPP",
    )  # fmt: skip


def test_n3_routes_ticket(student):
    r = ask("Olvidé mi contraseña", student)
    assert (r.level, r.ticket.assigned_area.code) == ("N3", "IT")
    assert "derivamos al área" in r.response
    assert r.path[-3:] == ["create_ticket", "route_ticket", "respond_ticket"]


def test_ticket_actions_need_identified_sender():
    r = ask("Olvidé mi contraseña")  # no requiere autenticación, pero sí identificar al autor
    assert r.ticket is None and "identificarte" in r.response


# --- N4: revisión humana (CA-006) -------------------------------------------------------------


def test_ca006_ambiguous_request_goes_to_human_review(student):
    r = ask("certificado y contraseña", student)
    assert (r.level, r.intent_code) == ("N4", None)
    t = r.ticket
    assert (t.intent.code, t.assigned_area.code, t.classification_source) == (
        "UNKNOWN_REQUEST", "SERVICE", "",
    )  # fmt: skip
    alert = t.alerts.get()
    assert alert.alert_type == "HUMAN_REVIEW" and "CERTIFICATE_REQUEST" in alert.message
    assert "Un agente la revisará" in r.response


def test_unrecognized_message_goes_to_n4(student):
    r = ask("hola buenas tardes", student)
    assert (r.level, r.ticket.intent.code) == ("N4", "UNKNOWN_REQUEST")


def test_general_complaint_is_n4_with_intent(student):
    r = ask("Quiero poner una queja", student)
    assert (r.level, r.ticket.intent.code) == ("N4", "GENERAL_COMPLAINT")
    assert "intención GENERAL_COMPLAINT" in r.ticket.alerts.get().message


def test_human_review_alert_resolves_when_triaged(student, make_user):
    agent = make_user("agente", role="Agente")
    Area.objects.get(code="SERVICE").agents.add(agent)
    t = ask("hola", student).ticket
    assignment.assign(t, actor=make_user("sup", role="Supervisor"), area=t.assigned_area,
                      assignee=agent)  # fmt: skip
    assert t.alerts.get().status == Alert.Status.RESOLVED


# --- determine_autonomy ----------------------------------------------------------------------


def test_determine_autonomy_rules():
    grade = Intent.objects.get(code="CHECK_GRADE")
    action = grade.actions.get()
    assert determine_autonomy(None, 1.0) == "N4"
    assert determine_autonomy(grade, 0.69, action) == "N4"
    assert determine_autonomy(grade, 0.70, action) == "N0"
    assert determine_autonomy(grade, 0.9, None) == "N3"
    pwd = Intent.objects.get(code="PASSWORD_PROBLEM")
    assert AutomationService.determine_autonomy(pwd, 0.9) == "N3"


def test_medium_confidence_forces_review_before_ticket(student, monkeypatch):
    """SPEC §46A.4: 0.70–0.849 → revisión humana antes de N2/N3 (lo usará el LLM)."""
    from apps.ai.agent import nodes
    from apps.automation import intents

    real = intents.identify_intent

    def medium(text):
        m = real(text)
        return intents.IntentMatch(m.intent, 0.75, "RULES", m.candidates)

    monkeypatch.setattr(nodes, "identify_intent", medium)
    r = ask("Olvidé mi contraseña", student)
    # El hilo queda pausado en human_review (interrupt) después de responder al usuario.
    assert r.level == "N3" and r.pending_review and r.path[-1] == "request_review"
    assert r.ticket.alerts.get().alert_type == "HUMAN_REVIEW"


def test_empty_message_and_anonymous_user(student):
    from django.contrib.auth.models import AnonymousUser

    with pytest.raises(ValueError):
        ask("   ", student)
    assert ask("mis notas", AnonymousUser()).path[-1] == "respond_link_instructions"


def test_disabled_intent_is_not_used(student, make_user):
    catalogs.set_active(Intent.objects.get(code="CHECK_DEBT"), False,
                        actor=make_user("admin", role="Administrador"))  # fmt: skip
    r = ask("deuda", student)  # las reglas ya no la reconocen: decide el LLM, nunca CHECK_DEBT
    assert r.intent_code != "CHECK_DEBT" and r.ticket is not None
    assert "classify_llm" in r.path


# --- Vista web (CONTRACT-014) -------------------------------------------------------------


def test_assistant_view_prg(client, student):
    client.force_login(student)
    url = reverse("automation:assistant")
    page = client.get(url)
    assert page.status_code == 200 and page.context["exchange"] is None
    assert page.context["examples"]
    r = client.post(url, {"message": "¿Cuánto debo?"})
    assert r.status_code == 302 and r.url == url
    shown = client.get(url)
    assert shown.context["exchange"]["level"] == "N0"
    assert "USD 390.00" in shown.context["exchange"]["response"]
    assert client.get(url).context["exchange"] is None  # se muestra una sola vez


def test_assistant_view_ticket_and_validation(client, student):
    client.force_login(student)
    url = reverse("automation:assistant")
    client.post(url, {"message": "olvidé mi contraseña"})
    exchange = client.get(url).context["exchange"]
    assert exchange["ticket_code"] == Ticket.objects.get().ticket_code
    bad = client.post(url, {"message": ""})
    assert bad.status_code == 200 and bad.context["form"].errors


@pytest.mark.parametrize("role", ["Agente", "Supervisor", "Administrador"])
def test_assistant_view_only_for_users(client, make_user, role):
    client.force_login(make_user("x", role=role))
    assert client.get(reverse("automation:assistant")).status_code == 403


def test_assistant_view_requires_login(client):
    assert client.get(reverse("automation:assistant")).status_code == 302


# --- Comando de demostración ----------------------------------------------------------------


def test_ask_command(student):
    out = StringIO()
    call_command("ask", "ana", "¿Cuánto debo?", stdout=out)
    assert "CHECK_DEBT · nivel N0" in out.getvalue() and "USD 390.00" in out.getvalue()
    out = StringIO()
    call_command("ask", "ana", "olvidé mi contraseña", stdout=out)
    assert "Ticket: HD-" in out.getvalue()
    out = StringIO()
    call_command("ask", "requisitos", anonymous=True, channel="WHATSAPP", stdout=out)
    assert "N1" in out.getvalue()
    with pytest.raises(CommandError):
        call_command("ask", "nadie", "hola")
    with pytest.raises(CommandError):
        call_command("ask", "hola")
