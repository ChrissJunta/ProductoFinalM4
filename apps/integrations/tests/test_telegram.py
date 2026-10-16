"""Bot de Telegram (ADR-080): canal separado de WhatsApp, vinculación, agente y colas."""

import json
import urllib.error
from datetime import timedelta
from io import BytesIO, StringIO

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from apps.ai.agent import runner
from apps.helpdesk import conversations, workflow
from apps.helpdesk.models import Area, Ticket
from apps.helpdesk.tickets import TicketService
from apps.integrations.models import (
    IntegrationInbox,
    IntegrationOutbox,
    TelegramLinkAttempt,
    TelegramLinkCode,
)
from apps.integrations.telegram import client as tg_client
from apps.integrations.telegram import linking, processing, resolution
from apps.integrations.telegram.client import (
    BotAPIClient,
    SimulatedTelegramClient,
    TelegramError,
    get_client,
)
from apps.integrations.whatsapp import processing as wa_processing
from conftest import PASSWORD

pytestmark = pytest.mark.django_db
CHAT = "5550001"


@pytest.fixture(autouse=True)
def fresh_graph():
    runner.reset()
    yield
    runner.reset()


@pytest.fixture
def student(make_user):
    return make_user("ana", role="Usuario", external_id="EST-0001")


def say(text, chat=CHAT, chat_type="private", update_id=None):
    """Mensaje entrante → inbox → agente → outbox. Devuelve las respuestas a ese chat."""
    say.counter = getattr(say, "counter", 0) + 1
    last = IntegrationOutbox.objects.order_by("-id").values_list("id", flat=True).first() or 0
    processing.ingest_update(
        {
            "update_id": update_id or say.counter,
            "message": {"chat": {"id": int(chat), "type": chat_type}, "text": text},
        }
    )
    processing.process_inbox()
    processing.process_outbox(client=SimulatedTelegramClient())
    return [
        o.payload_json["text"]
        for o in IntegrationOutbox.objects.filter(id__gt=last, destination=chat)
    ]


def link(user, chat=CHAT):
    code, _ = linking.generate_code(user)
    return say(f"/start {code}", chat=chat)


# --- Vinculación ----------------------------------------------------------------------------


def test_unlinked_chat_gets_general_info_only(student):
    assert "Mesa de Ayuda" in say("/start")[0]
    [reply] = say("¿Cuánto debo?")
    assert "Perfil → Telegram" in reply and "390" not in reply
    [ticket_reply] = say("Olvidé mi contraseña")
    assert "Perfil → Telegram" in ticket_reply and not Ticket.objects.exists()


def test_link_by_deep_link_and_by_code(student, make_user):
    assert link(student) == [linking.LINKED]
    student.refresh_from_db()
    assert student.is_telegram_linked and student.telegram_chat_id == CHAT
    other = make_user("beto", role="Usuario")
    code, _ = linking.generate_code(other)
    assert say(code) == [linking.LINKED]  # el código suelto también vale
    student.refresh_from_db()
    assert not student.is_telegram_linked  # un chat pertenece a una sola cuenta
    assert TelegramLinkCode.objects.filter(used_at__isnull=True).count() == 0


def test_invalid_expired_and_locked_codes(student, settings):
    assert say("/start 000000") == [linking.INVALID]
    code, _ = linking.generate_code(student)
    TelegramLinkCode.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    assert say(code) == [linking.INVALID]
    settings.TELEGRAM_LINK_MAX_FAILURES = 3
    say("111111")
    assert say("222222") == [linking.LOCKED]
    assert TelegramLinkAttempt.objects.filter(chat_id=CHAT).count() == 3
    settings.TELEGRAM_LINK_MAX_FAILURES = 50
    settings.TELEGRAM_LINK_GLOBAL_MAX_FAILURES = 3
    assert say("333333", chat="999") == [linking.LOCKED]


def test_new_code_invalidates_previous_and_unlink(student):
    first, _ = linking.generate_code(student)
    linking.generate_code(student)
    assert say(first) == [linking.INVALID]
    link(student)
    student.refresh_from_db()
    linking.unlink(student, actor=student)
    student.refresh_from_db()
    assert not student.is_telegram_linked
    assert linking.unlink(student, actor=student) == student  # ya desvinculado: sin cambios


def test_link_codes_are_separate_from_whatsapp(student):
    from apps.integrations.whatsapp import linking as wa_linking

    wa_code, _ = wa_linking.generate_code(student)
    assert say(wa_code) == [linking.INVALID]  # un código de WhatsApp no vincula Telegram
    tg_code, _ = linking.generate_code(student)
    assert wa_linking.redeem(tg_code, "+593991234567")[0] is None


# --- Agente por Telegram --------------------------------------------------------------------


def test_linked_user_talks_to_agent_with_minimized_data(student):
    link(student)
    [debt] = say("¿Cuánto debo?")
    assert debt.startswith("Tu saldo pendiente es USD 390.00") and "Matrícula" not in debt
    [ticket_reply] = say("Olvidé mi contraseña")
    ticket = Ticket.objects.get()
    assert ticket.channel == "TELEGRAM" and ticket.ticket_code in ticket_reply
    decision = ticket.ai_decisions.get()
    assert decision.channel == "TELEGRAM"


def test_reply_to_waiting_ticket_born_in_telegram(student, make_user):
    link(student)
    say("Olvidé mi contraseña")
    ticket = Ticket.objects.get()
    agent = make_user("tomas", role="Agente")
    ticket.assigned_area.agents.add(agent)
    from apps.helpdesk import assignment

    ticket = assignment.assign(ticket, actor=agent, area=ticket.assigned_area, assignee=agent)
    workflow.transition(ticket, Ticket.Status.IN_PROGRESS, actor=agent)
    start = _last_id()
    conversations.add_message(ticket, agent, "¿Desde cuándo?", request_info=True)
    [staff] = _outbox_texts(start)  # ticket nacido en Telegram: se contesta en el chat
    assert staff == f"[{ticket.ticket_code}] ¿Desde cuándo?"
    [reply] = say("Desde ayer")
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.IN_PROGRESS and ticket.ticket_code in reply


def test_web_waiting_ticket_does_not_capture_telegram_messages(student, make_user):
    link(student)
    web = TicketService.create(user=student, subject="Web", description="d")
    Ticket.objects.filter(pk=web.pk).update(status=Ticket.Status.WAITING_USER)
    [reply] = say("¿Cuánto debo?")
    assert reply.startswith("Tu saldo pendiente")  # consulta nueva, no respuesta al ticket web
    assert not web.messages.exists()


def _outbox_texts(after_id):
    """Textos enviados al chat (sin documentos ni respuestas a botones)."""
    return [
        o.payload_json["text"]
        for o in IntegrationOutbox.objects.filter(id__gt=after_id, provider="TELEGRAM")
        if "text" in o.payload_json
    ]


def _last_id():
    return IntegrationOutbox.objects.order_by("-id").values_list("id", flat=True).first() or 0


def test_proactive_status_and_staff_notifications(student, make_user):
    """ADR-081: el chat vinculado recibe los cambios de TODAS las solicitudes del usuario."""
    from apps.helpdesk import assignment

    link(student)
    ticket = TicketService.create(user=student, subject="Certificado", description="d")
    sup = make_user("sup", role="Supervisor")
    area = Area.objects.get(code="ACADEMIC")
    start = _last_id()
    ticket = assignment.assign(ticket, actor=sup, area=area)
    ticket = workflow.transition(ticket, Ticket.Status.IN_PROGRESS, actor=sup)
    conversations.add_message(ticket, sup, "¿Para qué trámite?", request_info=True)
    ticket.refresh_from_db()
    conversations.add_message(ticket, student, "Para una beca")  # el usuario: sin aviso
    ticket.refresh_from_db()
    workflow.transition(ticket, Ticket.Status.RESOLVED, actor=sup, reason="Listo en Secretaría.")
    texts = _outbox_texts(start)
    code = ticket.ticket_code
    assert texts[0] == f"[{code}] «Certificado»: tu solicitud fue asignada al área {area.name}."
    assert texts[1].endswith("estamos atendiendo tu solicitud.")
    assert texts[2] == f"[{code}] ¿Para qué trámite?\nResponde desde el portal (Mis tickets)."
    assert "fue resuelta. Listo en Secretaría." in texts[3] and "botones" in texts[3]
    assert len(texts) == 4  # ni «esperando usuario» ni la vuelta a «en proceso» del usuario
    assert all(o.destination == CHAT for o in IntegrationOutbox.objects.filter(id__gt=start))


@pytest.mark.parametrize(
    ("previous", "target", "reason", "expected"),
    [
        ("RESOLVED", "IN_PROGRESS", "", "retomamos la atención"),
        ("IN_PROGRESS", "ESCALATED", "", "fue escalada"),
        ("RESOLVED", "CLOSED", "Cierre automático.", "quedó cerrada. Cierre automático."),
        ("RESOLVED", "CLOSED", "", "quedó cerrada."),
        ("WAITING_USER", "CANCELLED", "Sin respuesta.", "cancelada. Motivo: Sin respuesta."),
        ("NEW", "CANCELLED", "", "fue cancelada."),
        ("CLOSED", "REOPENED", "", "fue reabierta."),
        ("RESOLVED", "RESOLVED", "", "fue resuelta.\n¿Quedó resuelta?"),
        ("NEW", "CLASSIFIED", "", None),
        ("IN_PROGRESS", "WAITING_USER", "", None),
    ],
)
def test_status_texts(student, previous, target, reason, expected):
    from apps.integrations.telegram.notifications import status_text

    ticket = TicketService.create(user=student, subject="S", description="d")
    text = status_text(ticket, previous, target, reason)
    assert text is None if expected is None else expected in text


def test_no_notifications_without_link_inactive_or_own_action(student, make_user):
    from apps.integrations.telegram.notifications import notify_staff_message, notify_status_change

    ticket = TicketService.create(user=student, subject="S", description="d")
    sup = make_user("sup", role="Supervisor")
    assert notify_status_change(ticket, "NEW", "ASSIGNED", actor=sup) is None  # sin vincular
    link(student)
    student.refresh_from_db()
    ticket.refresh_from_db()
    assert notify_status_change(ticket, "RESOLVED", "CLOSED", actor=student) is None  # propio
    message = conversations.add_message(ticket, student, "hola")
    assert notify_staff_message(message) is None  # mensaje del propio usuario
    student.is_active = False
    student.save()
    ticket.refresh_from_db()
    assert notify_status_change(ticket, "NEW", "ASSIGNED", actor=sup) is None


def test_commands_groups_and_non_text(student):
    assert say("/ayuda") == [processing.HELP]
    assert say("/salir@MesaUtiBot") == [processing.HELP]  # comandos desconocidos: ayuda
    assert say("hola", chat_type="group") == [processing.GROUPS]
    assert say("") == [processing.UNSUPPORTED]
    assert not Ticket.objects.exists()


def test_ingest_is_idempotent_and_ignores_non_messages():
    update = {"update_id": 42, "message": {"chat": {"id": 1, "type": "private"}, "text": "x"}}
    assert processing.ingest_update(update) is True
    assert processing.ingest_update(update) is False
    assert processing.ingest_update({"update_id": 43, "edited_message": {}}) is False
    item = IntegrationInbox.objects.get()
    item.payload_json = {"chat_id": ""}
    assert processing.handle_message(item) is None


# --- Separación de colas y reintentos -------------------------------------------------------


def test_whatsapp_worker_does_not_touch_telegram_queue():
    processing.ingest_update(
        {"update_id": 7, "message": {"chat": {"id": 1, "type": "private"}, "text": "/ayuda"}}
    )
    processing.enqueue_text("1", "hola")
    assert wa_processing.process_inbox() == (0, 0)
    assert wa_processing.process_outbox() == (0, 0)
    assert IntegrationInbox.objects.get().status == "PENDING"


def test_outbox_retries_and_fails(settings):
    settings.INTEGRATION_MAX_ATTEMPTS = 2
    client = SimulatedTelegramClient()
    client.fail_chats = {"9"}
    item = processing.enqueue_text("9", "x")
    assert processing.process_outbox(client=client) == (0, 1)
    item.refresh_from_db()
    assert item.status == "PENDING" and item.next_attempt_at
    processing.process_outbox(now=timezone.now() + timedelta(hours=1), client=client)
    item.refresh_from_db()
    assert item.status == "FAILED"


def test_inbox_error_is_retried(monkeypatch):
    processing.ingest_update(
        {"update_id": 8, "message": {"chat": {"id": 1, "type": "private"}, "text": "hola"}}
    )

    def boom(item):
        raise RuntimeError("x")

    monkeypatch.setattr(processing, "handle_message", boom)
    assert processing.process_inbox() == (0, 1)
    item = IntegrationInbox.objects.get()
    assert item.attempts == 1 and "RuntimeError" in item.last_error


# --- Cliente Bot API --------------------------------------------------------------------------


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_bot_api_client(monkeypatch, settings):
    settings.TELEGRAM_BOT_TOKEN = "123:SECRETO"
    calls = []

    def urlopen(request, timeout):
        calls.append((request.full_url, json.loads(request.data), timeout))
        method = request.full_url.rsplit("/", 1)[1]
        result = {
            "getMe": {"username": "MesaUtiBot"},
            "sendMessage": {"message_id": 77},
            "getUpdates": [{"update_id": 1}],
            "deleteWebhook": True,
            "setMyCommands": True,
        }[method]
        return FakeResponse(json.dumps({"ok": True, "result": result}).encode())

    monkeypatch.setattr(tg_client.urllib.request, "urlopen", urlopen)
    client = BotAPIClient()
    assert client.get_me()["username"] == "MesaUtiBot"
    assert client.send_text("5", "x" * 5000) == "77"
    assert len(calls[-1][1]["text"]) == 4096
    assert client.get_updates(offset=3, timeout=25) == [{"update_id": 1}]
    assert calls[-1][1] == {
        "timeout": 25,
        "allowed_updates": ["message", "callback_query"],
        "offset": 3,
    }
    assert calls[-1][2] == 35
    assert client.delete_webhook() is True
    assert client.set_commands([("menu", "Opciones")]) is True
    assert calls[-1][1] == {"commands": [{"command": "menu", "description": "Opciones"}]}
    client.send_text("5", "hola", reply_markup={"keyboard": []})
    assert calls[-1][1]["reply_markup"] == {"keyboard": []}


def test_bot_api_errors_never_leak_token(monkeypatch, settings):
    settings.TELEGRAM_BOT_TOKEN = "123:SECRETO"

    def http_error(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 401, "x", {}, BytesIO(b'{"description": "Unauthorized"}')
        )

    monkeypatch.setattr(tg_client.urllib.request, "urlopen", http_error)
    with pytest.raises(TelegramError) as exc:
        BotAPIClient().send_text("5", "x")
    assert "SECRETO" not in str(exc.value) and "Unauthorized" in str(exc.value)

    def url_error(request, timeout):
        raise urllib.error.URLError(f"fallo en {request.full_url}")

    monkeypatch.setattr(tg_client.urllib.request, "urlopen", url_error)
    with pytest.raises(TelegramError) as exc:
        BotAPIClient().get_me()
    assert "SECRETO" not in str(exc.value) and "***" in str(exc.value)

    monkeypatch.setattr(
        tg_client.urllib.request,
        "urlopen",
        lambda request, timeout: FakeResponse(b'{"ok": false, "description": "Bad"}'),
    )
    with pytest.raises(TelegramError, match="Bad"):
        BotAPIClient().get_me()

    def http_error_no_body(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 500, "x", {}, BytesIO(b"no json"))

    monkeypatch.setattr(tg_client.urllib.request, "urlopen", http_error_no_body)
    with pytest.raises(TelegramError, match="HTTP 500"):
        BotAPIClient().get_me()


def test_get_client_modes(settings):
    settings.TELEGRAM_MODE = "simulated"
    simulated = get_client()
    assert isinstance(simulated, SimulatedTelegramClient)
    assert simulated.get_updates() == [] and simulated.delete_webhook()
    assert simulated.get_me()["simulated"]
    settings.TELEGRAM_MODE = "bot"
    settings.TELEGRAM_BOT_TOKEN = ""
    with pytest.raises(ImproperlyConfigured):
        get_client()
    settings.TELEGRAM_BOT_TOKEN = "1:x"
    assert isinstance(get_client(), BotAPIClient)
    settings.TELEGRAM_MODE = "otro"
    with pytest.raises(ImproperlyConfigured):
        get_client()


# --- Comandos --------------------------------------------------------------------------------


class ScriptedClient(SimulatedTelegramClient):
    def __init__(self, batches):
        self.batches = list(batches)
        self.sent = []

    def get_updates(self, offset=None, timeout=0):
        batch = self.batches.pop(0)
        if isinstance(batch, Exception):
            raise batch
        return batch

    def send_text(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text))
        return "1"


def test_run_telegram_bot_once(monkeypatch):
    client = ScriptedClient(
        [[{"update_id": 10, "message": {"chat": {"id": 3, "type": "private"}, "text": "/ayuda"}}]]
    )
    monkeypatch.setattr(
        "apps.integrations.management.commands.run_telegram_bot.get_client", lambda: client
    )
    out = StringIO()
    call_command("run_telegram_bot", "--once", stdout=out)
    assert "escuchando" in out.getvalue() and "Recibidos 1" in out.getvalue()
    assert client.sent == [("3", processing.HELP)]


def test_run_telegram_bot_loop_recovers_and_stops(monkeypatch):
    client = ScriptedClient([TelegramError("caído"), [], KeyboardInterrupt()])
    sleeps = []
    module = "apps.integrations.management.commands.run_telegram_bot"
    monkeypatch.setattr(f"{module}.get_client", lambda: client)
    monkeypatch.setattr(f"{module}.time.sleep", sleeps.append)

    def raise_interrupt(*args, **kwargs):
        batch = client.batches.pop(0)
        if isinstance(batch, BaseException):
            raise batch
        return batch

    monkeypatch.setattr(client, "get_updates", raise_interrupt)
    out, err = StringIO(), StringIO()
    call_command("run_telegram_bot", stdout=out, stderr=err)
    assert "caído" in err.getvalue() and sleeps == [5] and "Bot detenido" in out.getvalue()


def test_run_telegram_bot_errors(monkeypatch):
    module = "apps.integrations.management.commands.run_telegram_bot"

    class Down(SimulatedTelegramClient):
        def get_me(self):
            raise TelegramError("sin red")

    monkeypatch.setattr(f"{module}.get_client", Down)
    with pytest.raises(CommandError, match="No se pudo conectar"):
        call_command("run_telegram_bot", "--once", stdout=StringIO())
    monkeypatch.setattr(f"{module}.get_client", lambda: ScriptedClient([TelegramError("x")]))
    with pytest.raises(CommandError):
        call_command("run_telegram_bot", "--once", stdout=StringIO(), stderr=StringIO())


def test_telegram_simulate_command(student):
    out = StringIO()
    call_command("telegram_simulate", "12", "/start", stdout=out)
    assert "Mesa de Ayuda" in out.getvalue()


# --- Portal ----------------------------------------------------------------------------------


def test_telegram_link_page(client, student):
    url = reverse("accounts:telegram")
    assert client.get(url).status_code == 302
    client.login(username="ana", password=PASSWORD)
    page = client.get(url)
    assert (
        page.status_code == 200 and not page.context["is_linked"] and page.context["code"] is None
    )
    assert page.context["bot_url"] == "https://t.me/MesaUtiBot"
    client.post(url, {"action": "generate"})
    page = client.get(url)
    code = page.context["code"]
    assert code and page.context["code_url"] == f"https://t.me/MesaUtiBot?start={code}"
    assert client.get(url).context["code"] is None  # se muestra una sola vez
    say(f"/start {code}")
    assert client.get(url).context["is_linked"]
    r = client.post(url, {"action": "unlink"}, follow=True)
    assert "Telegram desvinculado" in r.content.decode()
    assert "Acción inválida" in client.post(url, {"action": "x"}, follow=True).content.decode()


# --- Menú de opciones -------------------------------------------------------------------------


def _last_payload(chat=CHAT):
    return IntegrationOutbox.objects.filter(destination=chat).order_by("-id").first().payload_json


def test_menu_keyboard_on_start_menu_and_help(student):
    [welcome] = say("/start")
    assert welcome.startswith("¡Hola!") and processing.HELP in welcome
    keyboard = _last_payload()["reply_markup"]["keyboard"]
    assert [b["text"] for row in keyboard for b in row] == [
        label for row in processing.MENU for label in row
    ]
    for text in ("/menu", "Menú", "opciones", "Ayuda", "¿Qué puedes hacer?"):
        assert say(text) == [processing.HELP]
        assert "reply_markup" in _last_payload()
    say("¿Cuánto debo?")
    assert "reply_markup" not in _last_payload()  # las respuestas del agente no repiten el menú


def test_menu_buttons_reach_the_right_answers(student):
    link(student)
    assert "reply_markup" in _last_payload()  # tras vincular, el menú queda a mano
    answers = {label: say(label)[0] for row in processing.MENU for label in row}
    assert answers["¿Cuánto debo?"].startswith("Tu saldo pendiente")
    assert answers["¿Cuáles son mis notas?"].startswith("Tus notas")
    assert answers["Mis asignaturas"].startswith("Tus asignaturas")
    assert "solicitudes" in answers["Mis solicitudes"].lower()
    assert answers["Ayuda"] == processing.HELP
    assert not Ticket.objects.exists()  # ningún botón crea tickets


def test_status_query_phrases_do_not_create_tickets(student):
    link(student)
    TicketService.create(user=student, subject="Certificado", description="d")
    for text in ("mis solicitudes", "¿Qué pasó con mi trámite?", "¿Cómo va mi ticket?"):
        [reply] = say(text)
        assert "Certificado" in reply
    assert Ticket.objects.count() == 1


def test_run_telegram_bot_registers_commands(monkeypatch):
    client = ScriptedClient([[]])
    registered = []
    client.set_commands = registered.append
    monkeypatch.setattr(
        "apps.integrations.management.commands.run_telegram_bot.get_client", lambda: client
    )
    call_command("run_telegram_bot", "--once", stdout=StringIO())
    assert [c for c, _ in registered[0]] == ["start", "menu", "ayuda"]
    assert SimulatedTelegramClient().set_commands([]) is True


# --- Resolución por botones y documentos (ADR-082) -----------------------------------------


def press(data, chat=CHAT):
    """Pulsa un botón de un mensaje del bot. Devuelve las respuestas de texto al chat."""
    say.counter = getattr(say, "counter", 0) + 1
    last = _last_id()
    processing.ingest_update(
        {
            "update_id": 100000 + say.counter,
            "callback_query": {
                "id": f"cb{say.counter}",
                "data": data,
                "message": {"chat": {"id": int(chat), "type": "private"}},
            },
        }
    )
    processing.process_inbox()
    processing.process_outbox(client=SimulatedTelegramClient())
    return [t for t in _outbox_texts(last) if t]


def _resolved_ticket(student, make_user, attachment=None):
    from apps.helpdesk import assignment

    ticket = TicketService.create(user=student, subject="Certificado", description="d")
    sup = make_user("sup", role="Supervisor")
    ticket = assignment.assign(ticket, actor=sup, area=Area.objects.get(code="ACADEMIC"))
    ticket = workflow.transition(ticket, Ticket.Status.IN_PROGRESS, actor=sup)
    if attachment is not None:
        conversations.add_message(ticket, sup, "Adjuntamos tu certificado.", attachment=attachment)
        ticket.refresh_from_db()
    return workflow.transition(ticket, Ticket.Status.RESOLVED, actor=sup, reason="Listo.")


def test_resolved_notice_has_buttons_and_confirm_closes(student, make_user):
    link(student)
    ticket = _resolved_ticket(student, make_user)
    notice = IntegrationOutbox.objects.filter(provider="TELEGRAM").latest("id").payload_json
    [[yes, no]] = notice["reply_markup"]["inline_keyboard"]
    assert yes["callback_data"] == f"close:{ticket.ticket_code}"
    assert no["callback_data"] == f"reject:{ticket.ticket_code}"
    assert press(yes["callback_data"]) == [f"¡Gracias! Cerramos tu solicitud {ticket.ticket_code}."]
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.CLOSED
    history = ticket.status_history.order_by("-id").first()
    assert history.actor == student and "Telegram" in history.reason
    answers = IntegrationOutbox.objects.filter(payload_json__type="callback_answer")
    assert answers.filter(status="SENT").exists()  # se quita el «cargando» del botón
    assert press(yes["callback_data"]) == [resolution.NOT_YOURS]  # ya no está resuelta


def test_reject_asks_reason_and_reopens_attention(student, make_user):
    link(student)
    ticket = _resolved_ticket(student, make_user)
    [ask] = press(f"reject:{ticket.ticket_code}")
    assert "qué sigue fallando" in ask
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.RESOLVED  # todavía falta el motivo
    [ok] = say("El certificado tiene mal mi apellido")
    assert ticket.ticket_code in ok
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.IN_PROGRESS
    assert ticket.status_history.order_by("-id").first().reason.startswith("El certificado")
    [debt] = say("¿Cuánto debo?")  # el siguiente mensaje ya sigue el curso normal
    assert debt.startswith("Tu saldo pendiente")


def test_resolution_buttons_only_for_owner_and_resolved(student, make_user):
    ticket = _resolved_ticket(student, make_user)
    assert press(f"close:{ticket.ticket_code}") == [resolution.NOT_YOURS]  # chat sin vincular
    other = make_user("beto", role="Usuario")
    link(other)
    assert press(f"close:{ticket.ticket_code}") == [resolution.NOT_YOURS]  # no es suyo
    link(student)
    assert press(f"borrar:{ticket.ticket_code}") == [resolution.NOT_YOURS]  # acción inválida
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.RESOLVED


def test_pending_reject_ignored_if_ticket_no_longer_resolved(student, make_user):
    from django.core.cache import cache

    link(student)
    ticket = _resolved_ticket(student, make_user)
    press(f"reject:{ticket.ticket_code}")
    Ticket.objects.filter(pk=ticket.pk).update(status=Ticket.Status.CLOSED)
    [reply] = say("¿Cuánto debo?")
    assert reply.startswith("Tu saldo pendiente")
    assert cache.get(f"telegram:reject:{CHAT}") is None


def test_staff_attachment_is_sent_as_document(student, make_user, settings, tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile

    settings.MEDIA_ROOT = tmp_path
    link(student)
    pdf = SimpleUploadedFile("certificado.pdf", b"%PDF-1.4 demo", content_type="application/pdf")
    start = _last_id()
    ticket = _resolved_ticket(student, make_user, attachment=pdf)
    doc = IntegrationOutbox.objects.get(id__gt=start, payload_json__type="document")
    assert doc.destination == CHAT
    assert doc.payload_json["caption"] == f"[{ticket.ticket_code}] certificado.pdf"

    sent = []

    class Recorder(SimulatedTelegramClient):
        def send_document(self, chat_id, filename, content, content_type, caption=""):
            sent.append((chat_id, filename, content, content_type, caption))
            return "9"

    processing.process_outbox(client=Recorder())
    caption = doc.payload_json["caption"]
    assert sent == [(CHAT, "certificado.pdf", b"%PDF-1.4 demo", "application/pdf", caption)]
    doc.refresh_from_db()
    assert doc.status == "SENT"
    missing = processing.enqueue(CHAT, {"type": "document", "attachment_id": 999999})
    processing.process_outbox(client=Recorder())
    missing.refresh_from_db()
    assert missing.status == "PENDING" and "ya no existe" in missing.last_error


def test_bot_api_send_document_and_answer_callback(monkeypatch, settings):
    settings.TELEGRAM_BOT_TOKEN = "123:SECRETO"
    calls = []

    def urlopen(request, timeout):
        calls.append((request.full_url, request.headers, request.data))
        method = request.full_url.rsplit("/", 1)[1]
        result = {"sendDocument": {"message_id": 5}, "answerCallbackQuery": True}[method]
        return FakeResponse(json.dumps({"ok": True, "result": result}).encode())

    monkeypatch.setattr(tg_client.urllib.request, "urlopen", urlopen)
    client = BotAPIClient()
    assert client.send_document(7, 'cer"t.pdf', b"PDFDATA", "application/pdf", "cap") == "5"
    url, headers, body = calls[-1]
    assert url.endswith("/sendDocument")
    assert headers["Content-type"].startswith("multipart/form-data; boundary=")
    assert b'filename="cert.pdf"' in body and b"PDFDATA" in body and b"cap" in body
    assert client.answer_callback("cb1", "ok") is True
    assert json.loads(calls[-1][2]) == {"callback_query_id": "cb1", "text": "ok"}
    simulated = SimulatedTelegramClient()
    assert simulated.answer_callback("x") is True
    assert simulated.send_document("1", "a", b"", "x").startswith("tg.SIM.doc")
    simulated.fail_chats = {"1"}
    with pytest.raises(TelegramError):
        simulated.send_document("1", "a", b"", "x")


def test_ingest_callback_and_simulate_button_command(student, make_user):
    link(student)
    ticket = _resolved_ticket(student, make_user)
    out = StringIO()
    call_command("telegram_simulate", CHAT, "--boton", f"close:{ticket.ticket_code}", stdout=out)
    assert "Cerramos tu solicitud" in out.getvalue()
    item = IntegrationInbox.objects.filter(payload_json__kind="callback").latest("id")
    assert item.payload_json["data"] == f"close:{ticket.ticket_code}"
