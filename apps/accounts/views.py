from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .roles import Role, get_role

# Pantalla de inicio de cada rol (SPEC §10). Cada tarea FRONT que implemente la
# pantalla correspondiente actualiza su entrada:
#   Usuario → FE-T02, Agente → FE-T06, Supervisor → FE-T08, Administrador → FE-T09.
ROLE_HOME_URLS = {
    Role.USUARIO: "accounts:home",
    Role.AGENTE: "accounts:home",
    Role.SUPERVISOR: "accounts:home",
    Role.ADMINISTRADOR: "accounts:home",
}


class LoginView(auth_views.LoginView):
    template_name = "auth/login.html"
    redirect_authenticated_user = True


@login_required
def role_redirect(request):
    return redirect(ROLE_HOME_URLS[get_role(request.user)])


@login_required
def home(request):
    return render(request, "home.html")
