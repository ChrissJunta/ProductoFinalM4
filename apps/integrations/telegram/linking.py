"""Vinculación de Telegram (ADR-080), separada de WhatsApp.

El usuario genera un código en Perfil → Telegram y lo envía al bot (o abre el enlace
`t.me/<bot>?start=<código>`). El chat queda ligado a su cuenta; hasta entonces el bot
solo da información general (como un remitente no identificado de WhatsApp, ADR-044).
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.helpdesk import audit
from apps.helpdesk.audit import Action

from ..models import TelegramLinkAttempt, TelegramLinkCode

CODE_DIGITS = 6
LINKED = (
    "Tu Telegram quedó vinculado a tu cuenta de la Mesa de Ayuda. Ya puedes consultar tus datos."
)
INVALID = "El código no es válido o ya expiró. Genera uno nuevo en Perfil → Telegram."
LOCKED = "Demasiados intentos fallidos. Inténtalo de nuevo en una hora."


def _hash(code):
    key = f"telegram:{settings.SECRET_KEY}".encode()
    return hmac.new(key, code.encode(), hashlib.sha256).hexdigest()


def looks_like_code(text):
    text = (text or "").strip()
    return len(text) == CODE_DIGITS and text.isdigit()


@transaction.atomic
def generate_code(user):
    """Código de un solo uso; invalida los anteriores. Devuelve (código, vence)."""
    now = timezone.now()
    TelegramLinkCode.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    expires = now + timedelta(minutes=settings.TELEGRAM_LINK_CODE_MINUTES)
    TelegramLinkCode.objects.create(user=user, code_hash=_hash(code), expires_at=expires)
    return code, expires


@transaction.atomic
def redeem(code, chat_id):
    """Valida el código recibido desde `chat_id`. Devuelve (usuario | None, respuesta)."""
    chat_id = str(chat_id)
    now = timezone.now()
    if _locked(chat_id, now):
        return None, LOCKED
    link = (
        TelegramLinkCode.objects.select_for_update()
        .filter(code_hash=_hash(code.strip()), used_at__isnull=True, expires_at__gt=now)
        .select_related("user")
        .first()
    )
    if link is None or not link.user.is_active:
        TelegramLinkAttempt.objects.create(chat_id=chat_id)
        return None, INVALID
    link.used_at = now
    link.save(update_fields=["used_at"])
    User = get_user_model()
    # Un chat pertenece a una sola cuenta: si otra lo tenía, se le desvincula.
    for other in (
        User.objects.select_for_update().filter(telegram_chat_id=chat_id).exclude(pk=link.user_id)
    ):
        _set_chat(other, "", None, actor=None, reason="Chat vinculado por otra cuenta")
    user = User.objects.select_for_update().get(pk=link.user_id)
    _set_chat(user, chat_id, now, actor=user, reason="Vinculación por código")
    TelegramLinkAttempt.objects.filter(chat_id=chat_id).delete()
    return user, LINKED


def _locked(chat_id, now):
    recent = TelegramLinkAttempt.objects.filter(created_at__gte=now - timedelta(hours=1))
    return (
        recent.filter(chat_id=chat_id).count() >= settings.TELEGRAM_LINK_MAX_FAILURES
        or recent.count() >= settings.TELEGRAM_LINK_GLOBAL_MAX_FAILURES
    )


@transaction.atomic
def unlink(user, *, actor):
    if not user.telegram_chat_id and not user.telegram_verified_at:
        return user
    return _set_chat(user, "", None, actor=actor, reason="Desvinculación")


def _set_chat(user, chat_id, verified_at, *, actor, reason):
    previous = {"telegram_linked": user.telegram_verified_at is not None}
    user.telegram_chat_id, user.telegram_verified_at = chat_id, verified_at
    user.save(update_fields=["telegram_chat_id", "telegram_verified_at"])
    audit.record(
        Action.UPDATE,
        user,
        actor=actor,
        previous=previous,
        new={"telegram_linked": verified_at is not None},
        metadata={"reason": reason, "channel": "TELEGRAM"},
    )
    return user


def linked_user(chat_id):
    return (
        get_user_model()
        .objects.filter(
            telegram_chat_id=str(chat_id), telegram_verified_at__isnull=False, is_active=True
        )
        .first()
    )
