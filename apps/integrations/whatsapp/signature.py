"""Firma de Meta: cabecera `X-Hub-Signature-256: sha256=<HMAC-SHA256(app_secret, cuerpo)>`."""

import hashlib
import hmac

from django.conf import settings


def sign(body, secret=None):
    secret = settings.WHATSAPP_APP_SECRET if secret is None else secret
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def is_valid(body, header):
    if not settings.WHATSAPP_APP_SECRET or not header:
        return False
    return hmac.compare_digest(sign(body), header)
