"""BE-T13: Intent Engine por reglas (SPEC §30) con palabras clave configurables (CR-006)."""

import pytest

from apps.automation.intents import identify_intent, normalize, parse_keywords, score
from apps.automation.models import Intent
from apps.helpdesk import catalogs

pytestmark = pytest.mark.django_db


def test_normalize():
    assert normalize("¿Cuánto DEBO? Contraseña, matrícula…") == "cuanto debo contrasena matricula"


def test_parse_and_score():
    rules = parse_keywords("nota + incorrecta\n\n  promedio  \n+")
    assert rules == [("nota", "incorrecta"), ("promedio",)]
    assert score("mi nota esta incorrecta", rules) == 2
    assert score("notas incorrectas", rules) == 0  # palabras completas, no subcadenas
    assert score("a que hora", parse_keywords("a que hora")) == 3


@pytest.mark.parametrize(
    "text,expected",
    [
        # CA-001 a CA-003: consultas N0
        ("¿Cuál es mi horario de hoy?", "CHECK_SCHEDULE"),
        ("A qué hora tengo clases", "CHECK_SCHEDULE"),
        ("Quiero ver mis notas", "CHECK_GRADE"),
        ("¿Cuál es mi promedio?", "CHECK_GRADE"),
        ("¿Cuánto debo?", "CHECK_DEBT"),
        ("Tengo deuda pendiente?", "CHECK_DEBT"),
        ("¿Estoy matriculado?", "CHECK_ENROLLMENT"),
        ("Qué materias tengo este periodo", "CHECK_SUBJECTS"),
        # N1
        ("¿Cuáles son los requisitos para graduarme?", "CHECK_REQUIREMENTS"),
        ("¿Cuándo son los exámenes?", "CHECK_ACADEMIC_DATES"),
        # Problemas: el tema + síntoma gana a la consulta simple
        ("Mi nota de Cálculo está incorrecta", "GRADE_DISCREPANCY"),  # CA-004
        ("Ya pagué y sigue apareciendo la deuda", "PAYMENT_NOT_REFLECTED"),  # CA-005
        ("Mi pago no se refleja", "PAYMENT_NOT_REFLECTED"),
        ("No debo esa deuda, es un cobro indebido", "DEBT_DISPUTE"),
        ("No puedo matricularme", "ENROLLMENT_PROBLEM"),
        ("No me aparece una materia", "SUBJECT_NOT_VISIBLE"),
        ("No puedo entrar al aula virtual", "ACCESS_PROBLEM"),
        ("Olvidé mi contraseña", "PASSWORD_PROBLEM"),
        ("Necesito un certificado de estudios", "CERTIFICATE_REQUEST"),
        ("Quiero cambiar mi teléfono", "PROFILE_UPDATE"),
        ("Quiero poner una queja por mala atención", "GENERAL_COMPLAINT"),
    ],
)
def test_rules_resolve_simple_intents(text, expected):
    match = identify_intent(text)
    assert match.intent is not None and match.intent.code == expected
    assert (match.source, match.confidence) == ("RULES", 0.90)


def test_ticket_code_is_a_deterministic_rule():
    match = identify_intent("¿cómo va el hd-2026-000042? también mi nota")
    assert (match.intent.code, match.confidence) == ("CHECK_TICKET", 1.0)
    assert match.entities == {"ticket_code": "HD-2026-000042"}


def test_no_match_is_left_for_llm():
    match = identify_intent("Necesito ayuda con algo")
    assert (match.intent, match.confidence, match.ambiguous) == (None, 0.0, False)


@pytest.mark.parametrize(
    "text", ["Hola, buenas tardes", "¡Muchas gracias!", "buenos días, ¿qué tal?"]
)
def test_greeting_alone_is_general_question(text):
    """ADR-083: un saludo solo se responde sin ticket."""
    match = identify_intent(text)
    assert (match.intent.code, match.confidence) == ("GENERAL_QUESTION", 0.90)


def test_greeting_with_a_request_is_still_the_request():
    match = identify_intent("Hola, necesito un certificado de matrícula")
    assert match.intent.code == "CERTIFICATE_REQUEST"


def test_tie_is_ambiguous():
    """CA-006: dos intenciones con el mismo puntaje → no se adivina."""
    match = identify_intent("certificado y contraseña")
    assert match.intent is None and match.ambiguous
    assert match.candidates == ("CERTIFICATE_REQUEST", "PASSWORD_PROBLEM")
    assert match.confidence < 0.70


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("¿Cuáles son los requisitos para un certificado?", "CHECK_REQUIREMENTS"),
        ("¿Qué requisitos necesito para matricularme?", "CHECK_REQUIREMENTS"),
        ("requisitos para el certificado de estudios", "CHECK_REQUIREMENTS"),
        ("¿Qué necesito para sacar un certificado?", "CHECK_REQUIREMENTS"),
        ("Necesito un certificado de matrícula", "CERTIFICATE_REQUEST"),
        ("No puedo matricularme", "ENROLLMENT_PROBLEM"),
    ],
)
def test_requirements_question_is_informative_not_a_request(text, expected):
    """Preguntar por requisitos es N1 (respuesta automática), no un trámite con ticket."""
    assert identify_intent(text).intent.code == expected


def test_requirements_question_answered_without_ticket(make_user):
    from apps.ai.agent import runner

    runner.reset()
    user = make_user("ana", role="Usuario")
    r = runner.run_agent(text="¿Cuáles son los requisitos para un certificado?", user=user)
    assert (r.level, r.ticket, r.path[-1]) == ("N1", None, "respond_template")
    runner.reset()


def test_keywords_are_configuration(make_user):
    """Cambiar palabras clave desde el admin cambia la clasificación sin redeploy."""
    admin = make_user("admin", role="Administrador")
    assert identify_intent("necesito el sílabo").intent is None
    req = Intent.objects.get(code="CHECK_REQUIREMENTS")
    req.keywords += "\nsilabo"
    catalogs.save_catalog_item(req, actor=admin)
    assert identify_intent("necesito el sílabo").intent == req

    catalogs.set_active(req, False, actor=admin)
    assert identify_intent("necesito el sílabo").intent is None


def test_inactive_check_ticket_falls_back_to_keywords(make_user):
    catalogs.set_active(Intent.objects.get(code="CHECK_TICKET"), False,
                        actor=make_user("admin", role="Administrador"))  # fmt: skip
    assert identify_intent("HD-2026-000001 mi nota").intent.code == "CHECK_GRADE"
