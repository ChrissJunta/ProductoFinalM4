import logging
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods

from apps.helpdesk.queries import dashboard

from . import ratelimit, signals
from .roles import Role, get_role

logger = logging.getLogger(__name__)

# Pantalla de inicio de cada rol (SPEC §10). Cada tarea FRONT que implemente la
# pantalla correspondiente actualiza su entrada:
#   Usuario → FE-T02, Agente → FE-T06, Supervisor → FE-T08, Administrador → FE-T09.
ROLE_HOME_URLS = {
    Role.USUARIO: "accounts:home",
    Role.AGENTE: "accounts:home",
    Role.SUPERVISOR: "accounts:home",
    Role.ADMINISTRADOR: "accounts:home",
}


def _account_key(identifier):
    """Clave del contador por cuenta: el usuario real si existe (usuario o correo
    comparten contador), si no el texto enviado."""
    User = get_user_model()
    user = User.objects.filter(username=identifier).first()
    if user is None and "@" in identifier:
        matches = list(User.objects.filter(email__iexact=identifier)[:2])
        user = matches[0] if len(matches) == 1 else None
    return f"pk:{user.pk}" if user else identifier.strip().lower()


LOCKED_MESSAGE = "Demasiados intentos fallidos. Espere unos minutos e inténtelo de nuevo."


class LoginView(auth_views.LoginView):
    """Login con límite de intentos fallidos por IP y por usuario (SPEC §48)."""

    template_name = "auth/login.html"
    redirect_authenticated_user = True

    def _keys(self):
        return (
            ("login_ip", ratelimit.client_ip(self.request)),
            ("login_user", _account_key(self.request.POST.get("username", ""))),
        )

    def post(self, request, *args, **kwargs):
        if any(ratelimit.is_limited(scope, ident) for scope, ident in self._keys()):
            form = self.get_form()
            form.errors.clear()
            form.add_error(None, LOCKED_MESSAGE)
            logger.warning("Login bloqueado por límite de intentos (%s)", self._keys()[0][1])
            signals.record_access(
                signals.Action.LOGIN_LOCKED,
                request=request,
                username=request.POST.get("username", ""),
            )
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        for scope, ident in self._keys():
            ratelimit.hit(scope, ident)
        return super().form_invalid(form)

    def form_valid(self, form):
        ratelimit.reset("login_user", f"pk:{form.get_user().pk}")
        return super().form_valid(form)


class PasswordChangeView(auth_views.PasswordChangeView):
    """CONTRACT-019: cambio de contraseña propio; obligatorio si la contraseña es temporal.

    Django mantiene la sesión actual y cierra las demás sesiones del usuario (el hash de
    sesión cambia con la contraseña).
    """

    template_name = "auth/password_change.html"
    success_url = reverse_lazy("accounts:role_redirect")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["forced"] = self.request.user.must_change_password
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        signals.record_access(signals.Action.PASSWORD_CHANGE, user=user, request=self.request)
        if user.must_change_password:
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
        messages.success(self.request, "Contraseña actualizada.")
        return response


def admin_login(request):
    """El admin de Django usa el mismo login (con límite de intentos y auditoría) que el
    portal, en lugar de su formulario propio sin protección (ADR-073)."""
    if request.user.is_authenticated:  # sin is_staff: evita el bucle admin ↔ login
        raise PermissionDenied
    return redirect_to_login(request.GET.get("next") or reverse("admin:index"))


@login_required
def role_redirect(request):
    return redirect(ROLE_HOME_URLS[get_role(request.user)])


@login_required
def home(request):
    """FE-002 / CONTRACT-013: inicio con tickets recientes y resumen."""
    return render(request, "home.html", dashboard(request.user))


WA_SESSION_KEY = "whatsapp_link_code"


@login_required
@require_http_methods(["GET", "POST"])
def whatsapp_link(request):
    """FE-T11 / CONTRACT-018: estado, código de vinculación y desvinculación (SPEC §35.1)."""
    from apps.integrations.whatsapp import linking

    user = request.user
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "generate":
            code, expires = linking.generate_code(user)
            request.session[WA_SESSION_KEY] = {"code": code, "expires_at": expires.isoformat()}
        elif action == "unlink":
            linking.unlink(user, actor=user)
            messages.success(request, "WhatsApp desvinculado.")
        else:
            messages.error(request, "Acción inválida.")
        return redirect("accounts:whatsapp")
    pending = request.session.pop(WA_SESSION_KEY, None)  # el código se muestra una sola vez
    return render(
        request,
        "accounts/whatsapp.html",
        {
            "phone": user.phone,
            "is_verified": user.is_phone_verified,
            "verified_at": user.phone_verified_at,
            "code": pending["code"] if pending else None,
            "code_expires_at": (datetime.fromisoformat(pending["expires_at"]) if pending else None),
            "code_minutes": settings.WHATSAPP_LINK_CODE_MINUTES,
        },
    )


TG_SESSION_KEY = "telegram_link_code"


@login_required
@require_http_methods(["GET", "POST"])
def telegram_link(request):
    """CONTRACT-022: vinculación del chat de Telegram por código (ADR-080)."""
    from apps.integrations.telegram import linking

    user = request.user
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "generate":
            code, expires = linking.generate_code(user)
            request.session[TG_SESSION_KEY] = {"code": code, "expires_at": expires.isoformat()}
        elif action == "unlink":
            linking.unlink(user, actor=user)
            messages.success(request, "Telegram desvinculado.")
        else:
            messages.error(request, "Acción inválida.")
        return redirect("accounts:telegram")
    pending = request.session.pop(TG_SESSION_KEY, None)  # el código se muestra una sola vez
    bot = settings.TELEGRAM_BOT_USERNAME
    return render(
        request,
        "accounts/telegram.html",
        {
            "is_linked": user.is_telegram_linked,
            "linked_at": user.telegram_verified_at,
            "bot_username": bot,
            "bot_url": f"https://t.me/{bot}",
            "code": pending["code"] if pending else None,
            "code_url": f"https://t.me/{bot}?start={pending['code']}" if pending else None,
            "code_expires_at": (datetime.fromisoformat(pending["expires_at"]) if pending else None),
            "code_minutes": settings.TELEGRAM_LINK_CODE_MINUTES,
        },
    )
