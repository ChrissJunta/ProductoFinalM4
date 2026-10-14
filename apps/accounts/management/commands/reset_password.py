"""Restablece la contraseña de un usuario con una temporal aleatoria (ADR-072).

La contraseña se muestra una sola vez y el usuario debe cambiarla al ingresar.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts import passwords
from apps.accounts.signals import Action, record_access


class Command(BaseCommand):
    help = "Asigna una contraseña temporal aleatoria; el usuario deberá cambiarla al ingresar."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"No existe el usuario «{username}».") from exc
        temporary = passwords.generate()
        with transaction.atomic():
            user.set_password(temporary)
            user.must_change_password = True
            user.save(update_fields=["password", "must_change_password"])
            record_access(Action.PASSWORD_RESET, user=user, actor=None, source="reset_password")
        self.stdout.write(f"Contraseña temporal de {username}: {temporary}")
        self.stdout.write(
            "Se pedirá cambiarla en el próximo ingreso. Las sesiones abiertas se cierran."
        )
