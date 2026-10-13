"""BE-T11 / BE-T11A / BE-T12: WhatsApp simulado (ADR-049) con el contrato de Meta."""

import json
from datetime import date, timedelta
from io import StringIO
from unittest import mock

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.ai.agent import runner
from apps.helpdesk import conversations, metrics
from apps.helpdesk.models import AuditLog, Ticket
from apps.helpdesk.tickets import TicketService
from apps.integrations.management.commands.whatsapp_simulate import meta_payload
from apps.integrations.models import IntegrationInbox, IntegrationOutbox, WhatsAppLinkCode
from apps.integrations.whatsapp import client as wa_client
from apps.integrations.whatsapp import linking, processing
from apps.integrations.whatsapp.signature import sign

pytestmark = pytest.mark.django_db
PHONE = "+593991112233"
URL = "/api/webhooks/whatsapp/"


@pytest.fixture(autouse=True)
def fresh_agent():
    runner.reset()
    yield
    runner.reset()


@pytest.fixture
def student(make_user):
    return make_user("ana", role="Usuario", external_id="EST-0001")


def post(client, payload, signature=None):
    body = json.dumps(payload).encode()
    return client.post(
        URL, data=body, content_type="application/json",
        headers={"X-Hub-Signature-256": sign(body) if signature is None else signature},
    )  # fmt: skip


def send(client, text, phone=PHONE, message_id=None):
    """Mensaje entrante + una pasada del worker. Devuelve los textos salientes nuevos."""
    last = IntegrationOutbox.objects.order_by("-id").values_list("id", flat=True).first() or 0
    assert post(client, meta_payload(phone, text, message_id)).status_code == 200
    processing.process_inbox()
    processing.process_outbox()
    return [o.payload_json["text"] for o in IntegrationOutbox.objects.filter(id__gt=last)]


def link(client, user, phone=PHONE):
    code, _ = linking.generate_code(user)
    assert send(client, code, phone) == [linking.LINKED]
    user.refresh_from_db()
    return user


# --- Webhook (BE-T11) -----------------------------------------------------------------------


def test_verification_handshake(client, settings):
    ok = client.get(URL, {"hub.mode": "subscribe", "hub.verify_token": "test-verify-token",
                          "hub.challenge": "1234"})  # fmt: skip
    assert ok.status_code == 200 and ok.content == b"1234"
    bad = client.get(URL, {"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1"})
    assert bad.status_code == 403
    settings.WHATSAPP_APP_SECRET = ""
    assert client.get(URL).status_code == 503


def test_signature_required(client):
    payload = meta_payload(PHONE, "hola")
    assert post(client, payload, signature="sha256=falsa").status_code == 403
    assert post(client, payload, signature="").status_code == 403
    assert IntegrationInbox.objects.count() == 0
    body = b"no-json"
    r = client.post(URL, data=body, content_type="application/json",
                    headers={"X-Hub-Signature-256": sign(body)})  # fmt: skip
    assert r.status_code == 400


def test_idempotency(client):
    payload = meta_payload(PHONE, "hola", "wamid.X1")
    assert post(client, payload).json() == {"received": 1, "duplicated": 0}
    assert post(client, payload).json() == {"received": 0, "duplicated": 1}
    assert IntegrationInbox.objects.count() == 1


def test_non_message_events_are_ignored(client):
    status_event = {"entry": [{"changes": [{"value": {"statuses": [{"id": "s1"}]}}]}]}
    assert post(client, status_event).json() == {"received": 0, "duplicated": 0}
    assert post(client, {"entry": [{"changes": [{"value": {"messages": [{"type": "text"}]}}]}]})
    assert post(client, [1, 2]).json() == {"received": 0, "duplicated": 0}


# --- Número no verificado (SPEC §35.1, criterio BE-T11A) -------------------------------------


@pytest.mark.parametrize("text", ["¿Cuánto debo?", "mis notas", "mi horario de hoy"])
def test_unverified_number_gets_no_sensitive_data(client, student, text):
    student.phone = PHONE  # aunque el número coincida, sin verificar no cuenta
    student.save()
    (reply,) = send(client, text)
    assert "vincula tu WhatsApp" in reply and "390" not in reply and "8.50" not in reply


def test_unverified_number_gets_public_answers(client):
    (reply,) = send(client, "¿Cuáles son los requisitos?")
    assert reply.startswith("Los requisitos dependen del trámite")


def test_unsupported_message_type(client):
    payload = meta_payload(PHONE, "x")
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
    post(client, payload)
    processing.process_inbox()
    assert IntegrationOutbox.objects.get().payload_json["text"] == processing.UNSUPPORTED


# --- Vinculación (BE-T11A) -------------------------------------------------------------------


def test_link_and_minimized_sensitive_answer(client, student):
    link(client, student)
    assert student.phone == PHONE and student.is_phone_verified
    (reply,) = send(client, "¿Cuánto debo?")
    assert reply == "Tu saldo pendiente es USD 390.00. Puedes ver el detalle en el portal."
    assert AuditLog.objects.filter(
        entity_type="accounts.user",
        entity_id=str(student.pk),
        metadata_json__reason="Vinculación por código",
    ).exists()


def test_code_single_use_and_expiry(client, student):
    code, _ = linking.generate_code(student)
    assert send(client, code) == [linking.LINKED]
    assert send(client, code, phone="+593990000001") == [linking.INVALID]  # reutilizado
    code2, _ = linking.generate_code(student)
    WhatsAppLinkCode.objects.filter(used_at__isnull=True).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert send(client, code2, phone="+593990000002") == [linking.INVALID]  # expirado


def test_new_code_invalidates_previous(client, student):
    old, _ = linking.generate_code(student)
    new, _ = linking.generate_code(student)
    assert send(client, old) == [linking.INVALID]
    assert send(client, new) == [linking.LINKED]


def test_code_attempts_rate_limited(client, student):
    for i in range(5):
        assert send(client, f"00000{i}") == [linking.INVALID]
    code, _ = linking.generate_code(student)
    assert send(client, code) == [linking.LOCKED]  # incluso con código válido
    assert WhatsAppLinkCode.objects.get(used_at__isnull=True) is not None


def test_phone_moves_to_new_account(client, student, make_user):
    link(client, student)
    other = make_user("otro", role="Usuario")
    link(client, other)
    student.refresh_from_db()
    assert (student.phone, student.phone_verified_at) == ("", None)
    assert other.phone == PHONE


def test_changing_phone_resets_verification(client, student):
    link(client, student)
    student.phone = "+593990009999"
    student.save(update_fields=["phone"])
    student.refresh_from_db()
    assert student.phone_verified_at is None
    student.first_name = "Ana"
    student.save()  # otros cambios no tocan la verificación
    assert student.phone == "+593990009999"


def test_unlink(client, student):
    link(client, student)
    linking.unlink(student, actor=student)
    assert linking.unlink(student, actor=student).phone == ""  # idempotente
    (reply,) = send(client, "¿Cuánto debo?")
    assert "vincula tu WhatsApp" in reply


# --- Conversación con tickets (Web y WhatsApp comparten ticket) -------------------------------


def test_user_reply_resumes_waiting_ticket(client, student, make_user):
    link(client, student)
    ticket = TicketService.create(user=student, subject="s", description="d",
                                  channel="WHATSAPP")  # fmt: skip
    sup = make_user("sup", role="Supervisor")
    Ticket.objects.filter(pk=ticket.pk).update(status="IN_PROGRESS")
    conversations.add_message(ticket, sup, "¿Nos envías tu cédula?", request_info=True)
    out = IntegrationOutbox.objects.get(destination=PHONE, payload_json__text__icontains="cédula")
    assert out.payload_json["text"].startswith(f"[{ticket.ticket_code}]")
    (reply,) = send(client, "Mi cédula es 1234567890")
    ticket.refresh_from_db()
    assert ticket.status == "IN_PROGRESS" and ticket.ticket_code in reply
    msg = ticket.messages.order_by("-id").first()
    assert (msg.content, msg.external_message_id[:5]) == ("Mi cédula es 1234567890", "wamid")


def test_staff_reply_on_web_ticket_does_not_use_whatsapp(client, student, make_user):
    link(client, student)
    ticket = TicketService.create(user=student, subject="s", description="d")
    conversations.add_message(ticket, make_user("sup", role="Supervisor"), "hola")
    assert not IntegrationOutbox.objects.filter(payload_json__text__icontains="hola").exists()


def test_whatsapp_ticket_created_by_agent(client, student):
    link(client, student)
    (reply,) = send(client, "Olvidé mi contraseña")
    ticket = Ticket.objects.get(user=student)
    assert ticket.channel == "WHATSAPP" and ticket.ticket_code in reply


# --- Worker: reintentos y backoff (BE-T12) ----------------------------------------------------


def test_outbox_retries_with_backoff_then_fails(client, monkeypatch):
    monkeypatch.setattr(wa_client.SimulatedClient, "fail_destinations", {PHONE})
    send(client, "¿Cuáles son los requisitos?")
    out = IntegrationOutbox.objects.get()
    assert (out.status, out.attempts) == ("PENDING", 1) and out.next_attempt_at
    now = timezone.now()
    for _ in range(4):
        now += timedelta(hours=1)
        processing.process_outbox(now=now)
    out.refresh_from_db()
    assert (out.status, out.attempts) == ("FAILED", 5) and "simulado" in out.last_error
    monkeypatch.setattr(wa_client.SimulatedClient, "fail_destinations", set())
    assert processing.process_outbox(now=now + timedelta(hours=1)) == (0, 0)


def test_backoff_waits_before_retry(client, monkeypatch):
    monkeypatch.setattr(wa_client.SimulatedClient, "fail_destinations", {PHONE})
    send(client, "¿Cuáles son los requisitos?")
    monkeypatch.setattr(wa_client.SimulatedClient, "fail_destinations", set())
    assert processing.process_outbox() == (0, 0)  # aún no toca
    assert processing.process_outbox(now=timezone.now() + timedelta(minutes=2)) == (1, 0)
    assert processing.backoff(1) == timedelta(minutes=1)
    assert processing.backoff(4) == timedelta(minutes=8)


def test_inbox_failure_is_not_lost(client, monkeypatch):
    post(client, meta_payload(PHONE, "¿Cuáles son los requisitos?"))
    with mock.patch.object(processing, "handle_message", side_effect=RuntimeError("caído")):
        assert processing.process_inbox() == (0, 1)
    item = IntegrationInbox.objects.get()
    assert (item.status, item.attempts) == ("PENDING", 1) and "caído" in item.last_error
    assert processing.process_inbox(now=timezone.now() + timedelta(minutes=2)) == (1, 0)
    item.refresh_from_db()
    assert item.status == "DONE"


def test_ignored_message_without_sender(client):
    payload = meta_payload("", "hola")
    post(client, payload)
    processing.process_inbox()
    assert IntegrationInbox.objects.get().status == "IGNORED"
    assert processing.normalize_phone("593 99-111") == "+59399111"


# --- Clientes de salida -----------------------------------------------------------------------


def test_get_client_modes(settings):
    assert isinstance(wa_client.get_client(), wa_client.SimulatedClient)
    settings.WHATSAPP_MODE = "cloud"
    with pytest.raises(ImproperlyConfigured):
        wa_client.get_client()
    settings.WHATSAPP_ACCESS_TOKEN, settings.WHATSAPP_PHONE_NUMBER_ID = "tok", "123"
    assert isinstance(wa_client.get_client(), wa_client.CloudAPIClient)
    settings.WHATSAPP_MODE = "otro"
    with pytest.raises(ImproperlyConfigured):
        wa_client.get_client()


def test_cloud_client_request_and_errors(settings):
    settings.WHATSAPP_ACCESS_TOKEN, settings.WHATSAPP_PHONE_NUMBER_ID = "tok", "123"
    cloud = wa_client.CloudAPIClient()
    response = mock.MagicMock()
    response.__enter__.return_value.read.return_value = b'{"messages": [{"id": "wamid.OK"}]}'
    with mock.patch("urllib.request.urlopen", return_value=response) as urlopen:
        assert cloud.send_text(PHONE, "hola") == "wamid.OK"
    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("/123/messages")
    assert request.headers["Authorization"] == "Bearer tok"
    assert json.loads(request.data)["to"] == PHONE.lstrip("+")
    response.__enter__.return_value.read.return_value = b"{}"
    with mock.patch("urllib.request.urlopen", return_value=response):
        with pytest.raises(wa_client.SendError):
            cloud.send_text(PHONE, "hola")
    with mock.patch("urllib.request.urlopen", side_effect=OSError("red")):
        with pytest.raises(wa_client.SendError):
            cloud.send_text(PHONE, "hola")


# --- Comandos ---------------------------------------------------------------------------------


def test_simulator_and_worker_commands(student):
    out = StringIO()
    call_command("whatsapp_simulate", PHONE, "¿Cuáles son los requisitos?", stdout=out)
    assert "received': 1" in out.getvalue() and "[SENT]" in out.getvalue()
    out = StringIO()
    call_command("process_integration_queue", stdout=out)
    assert "Entrada: 0 procesados" in out.getvalue()
    call_command("process_integration_queue", "--loop", "--max-loops", "1", stdout=StringIO())


def test_simulator_reports_webhook_error(settings):
    from django.core.management import CommandError

    settings.WHATSAPP_APP_SECRET = ""
    with pytest.raises(CommandError):
        call_command("whatsapp_simulate", PHONE, "hola", stdout=StringIO())


# --- Perfil web (CONTRACT-018) y métricas ------------------------------------------------------


def test_profile_view(client, student):
    url = reverse("accounts:whatsapp")
    assert client.get(url).status_code == 302  # requiere sesión
    client.force_login(student)
    ctx = client.get(url).context
    assert (ctx["is_verified"], ctx["code"]) == (False, None)
    assert client.post(url, {"action": "generate"}).status_code == 302
    ctx = client.get(url).context
    assert len(ctx["code"]) == 6 and ctx["code_expires_at"] > timezone.now()
    assert client.get(url).context["code"] is None  # se muestra una sola vez
    client.post(url, {"action": "x"})
    student.phone, student.phone_verified_at = PHONE, timezone.now()
    student.save()
    assert client.get(url).context["is_verified"]
    client.post(url, {"action": "unlink"})
    student.refresh_from_db()
    assert not student.is_phone_verified


def test_whatsapp_metrics(client, student, monkeypatch):
    send(client, "¿Cuáles son los requisitos?")
    monkeypatch.setattr(wa_client.SimulatedClient, "fail_destinations", {"+593990000077"})
    send(client, "hola", phone="+593990000077")
    today = timezone.localdate()
    wa = metrics.compute(today, today)["whatsapp"]
    assert (wa["inbound"], wa["outbound_sent"], wa["outbound_pending"]) == (2, 1, 1)
    assert (wa["conversations"], wa["retries"]) == (2, 0)
    assert metrics.whatsapp_metrics(date(2020, 1, 1), date(2020, 1, 2))["inbound"] == 0
