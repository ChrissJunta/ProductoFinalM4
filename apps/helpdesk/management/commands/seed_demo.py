"""Datos de demostración para verificar el MVP a mano (solo desarrollo).

Crea un usuario por rol, asigna agentes a sus áreas y genera tickets en varios
estados usando los mismos servicios que la aplicación (con auditoría e historial).
Es idempotente: si los usuarios demo ya existen, no duplica nada.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.roles import Role
from apps.helpdesk import assignment, conversations, workflow
from apps.helpdesk.models import Area, Category, Subcategory, Ticket
from apps.helpdesk.tickets import TicketService

DEMO_PASSWORD = "Demo-2026!"

USERS = [
    # usuario, nombre, apellido, rol, staff (acceso a /admin)
    ("usuario", "Ana", "Estudiante", Role.USUARIO, False),
    ("agente_ti", "Tomás", "Soporte TI", Role.AGENTE, False),
    ("agente_fin", "Fernanda", "Tesorería", Role.AGENTE, False),
    ("supervisor", "Sofía", "Supervisora", Role.SUPERVISOR, False),
    ("admin", "Andrés", "Administrador", Role.ADMINISTRADOR, True),
]


class Command(BaseCommand):
    help = "Crea usuarios por rol y tickets de ejemplo para probar el MVP (solo desarrollo)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Permite ejecutarlo con DEBUG=False (no en producción).",
        )

    def handle(self, *args, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError(
                "seed_demo solo se ejecuta en desarrollo (DEBUG=True) o con --force."
            )
        User = get_user_model()
        if User.objects.filter(username="usuario").exists():
            self.stdout.write("Los datos demo ya existen; no se crea nada.")
            return
        with transaction.atomic():
            users = self._users(User)
            self._tickets(users)
        self.stdout.write(self.style.SUCCESS("Datos demo creados."))
        self.stdout.write(f"Contraseña de todos los usuarios demo: {DEMO_PASSWORD}")
        for username, *_rest, role, _staff in USERS:
            self.stdout.write(f"  {username:<11} → {role}")

    def _users(self, User):
        users = {}
        for username, first, last, role, staff in USERS:
            user = User.objects.create_user(
                username=username,
                password=DEMO_PASSWORD,
                first_name=first,
                last_name=last,
                email=f"{username}@demo.local",
                is_staff=staff,
            )
            user.groups.add(Group.objects.get(name=role))
            users[username] = user
        Area.objects.get(code="IT").agents.add(users["agente_ti"])
        Area.objects.get(code="FINANCE").agents.add(users["agente_fin"])
        return users

    def _tickets(self, u):
        ana, ti, fin, sup = u["usuario"], u["agente_ti"], u["agente_fin"], u["supervisor"]
        it, finance = Area.objects.get(code="IT"), Area.objects.get(code="FINANCE")
        S = Ticket.Status

        # 1) Nuevo, sin categoría: aparece en «Sin asignar» para triaje.
        TicketService.create(
            user=ana,
            subject="Consulta general sobre trámites",
            description="¿Dónde reviso los requisitos para el certificado de estudios?",
        )

        # 2) Asignado a TI y en proceso, con conversación.
        password = TicketService.create(
            user=ana,
            subject="No puedo ingresar al aula virtual",
            description="Me aparece «usuario bloqueado» desde ayer.",
            subcategory=Subcategory.objects.get(category__code="TECHNICAL", code="PASSWORD"),
        )
        password = assignment.assign(password, actor=ti, area=it, assignee=ti)
        workflow.transition(password, S.IN_PROGRESS, actor=ti)
        conversations.add_message(
            password, ti, "Estamos revisando su cuenta, en breve le escribimos."
        )

        # 3) Pago no reflejado: Finanzas pide información (espera al usuario).
        payment = TicketService.create(
            user=ana,
            subject="Pago no reflejado",
            description="Pagué la matrícula el lunes y sigue apareciendo la deuda.",
            category=Category.objects.get(code="FINANCIAL"),
            subcategory=Subcategory.objects.get(category__code="FINANCIAL", code="PAYMENTS"),
        )
        payment = assignment.assign(payment, actor=sup, area=finance, assignee=fin)
        workflow.transition(payment, S.IN_PROGRESS, actor=fin)
        conversations.add_message(
            payment, fin, "Por favor adjunte el comprobante de pago.", request_info=True
        )

        # 4) Resuelto: Ana debe confirmar o rechazar la solución.
        grade = TicketService.create(
            user=ana,
            subject="Nota incorrecta en Cálculo I",
            description="Mi nota del parcial figura como 0.",
            subcategory=Subcategory.objects.get(category__code="ACADEMIC", code="GRADES"),
        )
        grade = assignment.assign(grade, actor=sup, area=Area.objects.get(code="ACADEMIC"))
        grade = workflow.transition(grade, S.IN_PROGRESS, actor=sup)
        workflow.transition(
            grade, S.RESOLVED, actor=sup, reason="Se corrigió la nota en el sistema académico."
        )
