"""Webhook de WhatsApp (SPEC §47.2, BE-T11): verificación GET y eventos POST firmados."""

import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import processing, signature

logger = logging.getLogger(__name__)


@csrf_exempt  # Meta no envía token CSRF: la autenticidad la da la firma HMAC.
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    if not (settings.WHATSAPP_VERIFY_TOKEN and settings.WHATSAPP_APP_SECRET):
        return HttpResponse("WhatsApp no configurado.", status=503)
    if request.method == "GET":
        params = request.GET
        if params.get("hub.mode") == "subscribe" and hmac.compare_digest(
            params.get("hub.verify_token", ""), settings.WHATSAPP_VERIFY_TOKEN
        ):
            return HttpResponse(params.get("hub.challenge", ""), content_type="text/plain")
        return HttpResponseForbidden("Token de verificación inválido.")

    if not signature.is_valid(request.body, request.headers.get("X-Hub-Signature-256", "")):
        logger.warning("Webhook WhatsApp con firma inválida")
        return HttpResponseForbidden("Firma inválida.")
    try:
        payload = json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "JSON inválido"}, status=400)
    new, duplicated = processing.ingest(payload if isinstance(payload, dict) else {})
    # 200 rápido: el procesamiento lo hace el worker (SPEC §35 «Entrada»).
    return JsonResponse({"received": new, "duplicated": duplicated})
