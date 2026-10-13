"""Vinculación de WhatsApp (SPEC §35.1, BE-T11A)."""

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

from ..models import WhatsAppLinkAttempt, WhatsAppLinkCode

CODE_DIGITS = 6
LINKED = (
    "Tu WhatsApp quedó vinculado a tu cuenta de la Mesa de Ayuda. Ya puedes consultar tus datos."
)
INVALID = "El código no es válido o ya expiró. Genera uno nuevo en Perfil → WhatsApp."
LOCKED = "Demasiados intentos fallidos. Inténtalo de nuevo en una hora."


def _hash(code):
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


def looks_like_code(text):
    text = (text or "").strip()
    return len(text) == CODE_DIGITS and text.isdigit()


@transaction.atomic
def generate_code(user):
    """Nuevo código de un solo uso; invalida los anteriores pendientes. Devuelve (código, vence)."""
    now = timezone.now()
    WhatsAppLinkCode.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    expires = now + timedelta(minutes=settings.WHATSAPP_LINK_CODE_MINUTES)
    WhatsAppLinkCode.objects.create(user=user, code_hash=_hash(code), expires_at=expires)
    return code, expires


@transaction.atomic
def redeem(code, phone):
    """Valida el código recibido desde `phone`. Devuelve (usuario | None, mensaje de respuesta)."""
    now = timezone.now()
    if _locked(phone, now):
        return None, LOCKED
    link = (
        WhatsAppLinkCode.objects.select_for_update()
        .filter(code_hash=_hash(code.strip()), used_at__isnull=True, expires_at__gt=now)
        .select_related("user")
        .first()
    )
    if link is None or not link.user.is_active:
        WhatsAppLinkAttempt.objects.create(phone=phone)
        return None, INVALID
    link.used_at = now
    link.save(update_fields=["used_at"])
    User = get_user_model()
    # Un número pertenece a una sola cuenta: si otra lo tenía, se le desvincula.
    for other in User.objects.select_for_update().filter(phone=phone).exclude(pk=link.user_id):
        _set_phone(other, "", None, actor=None, reason="Número vinculado por otra cuenta")
    user = User.objects.select_for_update().get(pk=link.user_id)
    _set_phone(user, phone, now, actor=user, reason="Vinculación por código")
    WhatsAppLinkAttempt.objects.filter(phone=phone).delete()
    return user, LINKED


def _locked(phone, now):
    """Máx. 5 fallos por número y hora, y un tope global que frena la rotación de números."""
    recent = WhatsAppLinkAttempt.objects.filter(created_at__gte=now - timedelta(hours=1))
    return (
        recent.filter(phone=phone).count() >= settings.WHATSAPP_LINK_MAX_FAILURES
        or recent.count() >= settings.WHATSAPP_LINK_GLOBAL_MAX_FAILURES
    )


@transaction.atomic
def unlink(user, *, actor):
    if not user.phone and not user.phone_verified_at:
        return user
    return _set_phone(user, "", None, actor=actor, reason="Desvinculación")


def _set_phone(user, phone, verified_at, *, actor, reason):
    previous = {"phone": user.phone, "phone_verified": user.phone_verified_at is not None}
    user.phone, user.phone_verified_at = phone, verified_at
    user.save(update_fields=["phone", "phone_verified_at"])
    audit.record(
        Action.UPDATE,
        user,
        actor=actor,
        previous=previous,
        new={"phone": phone, "phone_verified": verified_at is not None},
        metadata={"reason": reason, "channel": "WHATSAPP"},
    )
    return user


def verified_user(phone):
    return (
        get_user_model()
        .objects.filter(phone=phone, phone_verified_at__isnull=False, is_active=True)
        .first()
    )
