from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOrEmailBackend(ModelBackend):
    """Permite iniciar sesión con usuario o correo (SPEC FE-001)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        UserModel = get_user_model()
        user = UserModel._default_manager.filter(username=username).first()
        if user is None and "@" in username:
            # Un correo compartido por varias cuentas es ambiguo: no se autentica.
            matches = list(UserModel._default_manager.filter(email__iexact=username)[:2])
            user = matches[0] if len(matches) == 1 else None
        if user is None:
            # Igualar el tiempo de respuesta con el caso de usuario existente.
            UserModel().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
