import logging

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.helpdesk.queries import dashboard

from . import ratelimit
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


LOCKED_MESSAGE = "Demasiados intentos fallidos. Espere unos minutos e inténtelo de nuevo."


class LoginView(auth_views.LoginView):
    """Login con límite de intentos fallidos por IP y por usuario (SPEC §48)."""

    template_name = "auth/login.html"
    redirect_authenticated_user = True

    def _keys(self):
        username = self.request.POST.get("username", "")
        return (("login_ip", ratelimit.client_ip(self.request)), ("login_user", username))

    def post(self, request, *args, **kwargs):
        if any(ratelimit.is_limited(scope, ident) for scope, ident in self._keys()):
            form = self.get_form()
            form.errors.clear()
            form.add_error(None, LOCKED_MESSAGE)
            logger.warning("Login bloqueado por límite de intentos (%s)", self._keys()[0][1])
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        for scope, ident in self._keys():
            ratelimit.hit(scope, ident)
        return super().form_invalid(form)

    def form_valid(self, form):
        ratelimit.reset("login_user", form.get_user().get_username())
        return super().form_valid(form)


@login_required
def role_redirect(request):
    return redirect(ROLE_HOME_URLS[get_role(request.user)])


@login_required
def home(request):
    """FE-002 / CONTRACT-013: inicio con tickets recientes y resumen."""
    return render(request, "home.html", dashboard(request.user))
