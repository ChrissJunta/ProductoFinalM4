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
from apps.helpdesk.models import Ticket
from apps.helpdesk.tickets import TicketService
from apps.integrations.models import (
    IntegrationInbox,
    IntegrationOutbox,
    TelegramLinkAttempt,
    TelegramLinkCode,
)
from apps.integrations.telegram import client as tg_client
from apps.integrations.telegram import linking, processing
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
    before = IntegrationOutbox.objects.count()
    conversations.add_message(ticket, agent, "¿Desde cuándo?", request_info=True)
    staff = IntegrationOutbox.objects.filter(id__gt=0).order_by("-id").first()
    assert IntegrationOutbox.objects.count() == before + 1  # sale por Telegram al chat
    assert staff.destination == CHAT and staff.payload_json["text"].startswith(
        f"[{ticket.ticket_code}]"
    )
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


def test_staff_reply_on_web_ticket_is_not_sent_to_telegram(student, make_user):
    link(student)
    ticket = TicketService.create(user=student, subject="Web", description="d")
    agent = make_user("tomas", role="Supervisor")
    before = IntegrationOutbox.objects.count()
    conversations.add_message(ticket, agent, "Hola")
    assert IntegrationOutbox.objects.count() == before


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
        }[method]
        return FakeResponse(json.dumps({"ok": True, "result": result}).encode())

    monkeypatch.setattr(tg_client.urllib.request, "urlopen", urlopen)
    client = BotAPIClient()
    assert client.get_me()["username"] == "MesaUtiBot"
    assert client.send_text("5", "x" * 5000) == "77"
    assert len(calls[-1][1]["text"]) == 4096
    assert client.get_updates(offset=3, timeout=25) == [{"update_id": 1}]
    assert calls[-1][1] == {"timeout": 25, "allowed_updates": ["message"], "offset": 3}
    assert calls[-1][2] == 35
    assert client.delete_webhook() is True


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

    def send_text(self, chat_id, text):
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
