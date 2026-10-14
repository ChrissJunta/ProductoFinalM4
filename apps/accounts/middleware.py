"""Middleware de acceso (ADR-072).

- `SessionIdleTimeoutMiddleware`: cierra la sesión tras `SESSION_IDLE_TIMEOUT` segundos
  sin actividad (la duración absoluta la limita `SESSION_COOKIE_AGE`).
- `ForcePasswordChangeMiddleware`: quien tiene una contraseña temporal
  (`User.must_change_password`) solo puede cambiarla o cerrar sesión.
"""

import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.urls import reverse

LAST_ACTIVITY_KEY = "_last_activity"
# Se reescribe la marca como mucho una vez por minuto para no guardar la sesión en cada petición.
ACTIVITY_RESOLUTION = 60


class SessionIdleTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        timeout = settings.SESSION_IDLE_TIMEOUT
        if timeout and request.user.is_authenticated:
            now = int(time.time())
            last = request.session.get(LAST_ACTIVITY_KEY)
            if last is not None and now - last > timeout:
                logout(request)
                messages.info(request, "Tu sesión se cerró por inactividad.")
                return redirect_to_login(request.get_full_path())
            if last is None or now - last >= ACTIVITY_RESOLUTION:
                request.session[LAST_ACTIVITY_KEY] = now
        return self.get_response(request)


ALLOWED_URL_NAMES = ("accounts:password_change", "accounts:logout")


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and getattr(user, "must_change_password", False):
            allowed = {reverse(name) for name in ALLOWED_URL_NAMES}
            static = "/" + settings.STATIC_URL.lstrip("/")
            if request.path not in allowed and not request.path.startswith(static):
                return redirect("accounts:password_change")
        return self.get_response(request)
