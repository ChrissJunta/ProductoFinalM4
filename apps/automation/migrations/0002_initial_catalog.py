"""Catálogo inicial de intenciones (SPEC §29), acciones, routing y permisos (BE-T09).

Las plantillas N1 son textos de ejemplo: el Administrador debe reemplazarlas con
la información oficial desde el admin (no requiere redeploy).
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

SOURCE = {"source": "migration:automation.0002_initial_catalog"}

# código, nombre, nivel, requiere autenticación
INTENTS = [
    ("CHECK_SCHEDULE", "Consultar horario", "N0", True),
    ("CHECK_GRADE", "Consultar notas", "N0", True),
    ("CHECK_DEBT", "Consultar deuda", "N0", True),
    ("CHECK_ENROLLMENT", "Consultar matrícula", "N0", True),
    ("CHECK_SUBJECTS", "Consultar materias", "N0", True),
    ("CHECK_TICKET", "Consultar estado de ticket", "N0", True),
    ("CHECK_ACADEMIC_DATES", "Consultar fechas académicas", "N1", False),
    ("CHECK_CONTACT", "Consultar contactos", "N1", False),
    ("CHECK_REQUIREMENTS", "Consultar requisitos", "N1", False),
    ("GRADE_DISCREPANCY", "Nota incorrecta", "N2", True),
    ("PAYMENT_NOT_REFLECTED", "Pago no reflejado", "N2", True),
    ("PROFILE_UPDATE", "Actualizar datos personales", "N2", True),
    ("DEBT_DISPUTE", "Reclamo de deuda", "N3", True),
    ("ENROLLMENT_PROBLEM", "Problema de matrícula", "N3", True),
    ("SUBJECT_NOT_VISIBLE", "Materia no visible", "N3", True),
    ("ACCESS_PROBLEM", "Problema de acceso", "N3", False),
    ("PASSWORD_PROBLEM", "Problema de contraseña", "N3", False),
    ("CERTIFICATE_REQUEST", "Solicitud de certificado", "N3", True),
    ("GENERAL_COMPLAINT", "Reclamo general", "N4", False),
    ("UNKNOWN_REQUEST", "Solicitud no identificada", "N4", False),
]

PROVIDER = {
    "CHECK_SCHEDULE": "get_schedule",
    "CHECK_GRADE": "get_grades",
    "CHECK_DEBT": "get_debt",
    "CHECK_ENROLLMENT": "get_enrollment",
    "CHECK_SUBJECTS": "get_subjects",
    "CHECK_TICKET": "get_ticket_status",
}

TEMPLATES = {
    "CHECK_ACADEMIC_DATES": (
        "Las fechas del calendario académico vigente (matrículas, exámenes y cierre de notas) "
        "están publicadas por Secretaría Académica. Si necesita una fecha específica, indíquenos "
        "el trámite y le orientamos."
    ),
    "CHECK_CONTACT": (
        "Áreas de atención: Secretaría Académica (notas, matrícula, certificados), Tesorería y "
        "Finanzas (pagos y deuda), Soporte Tecnológico (accesos y contraseñas) y Atención General. "
        "Puede abrir una solicitud desde este portal y la derivamos al área correcta."
    ),
    "CHECK_REQUIREMENTS": (
        "Los requisitos dependen del trámite. Indíquenos cuál necesita (certificado, matrícula, "
        "cambio de datos u otro) y le enviamos la lista oficial."
    ),
}

# intención → (área, prioridad, requiere validación)
ROUTING = {
    "GRADE_DISCREPANCY": ("ACADEMIC", "MEDIUM", True),
    "PAYMENT_NOT_REFLECTED": ("FINANCE", "HIGH", True),
    "PROFILE_UPDATE": ("SERVICE", "LOW", True),
    "DEBT_DISPUTE": ("FINANCE", "MEDIUM", False),
    "ENROLLMENT_PROBLEM": ("ACADEMIC", "HIGH", False),
    "SUBJECT_NOT_VISIBLE": ("ACADEMIC", "MEDIUM", False),
    "ACCESS_PROBLEM": ("IT", "HIGH", False),
    "PASSWORD_PROBLEM": ("IT", "MEDIUM", False),
    "CERTIFICATE_REQUEST": ("ACADEMIC", "LOW", False),
    "GENERAL_COMPLAINT": ("SERVICE", "MEDIUM", False),
    "UNKNOWN_REQUEST": ("SERVICE", "MEDIUM", False),
}

ROLE_PERMISSIONS = {
    "Administrador": [
        f"{a}_{m}" for m in ("intent", "intentaction", "routingrule") for a in ("add", "change", "view")
    ],
    "Supervisor": ["view_intent", "view_intentaction", "view_routingrule"],
    "Agente": ["view_intent"],
}


def _audit(AuditLog, entity_type, obj, new):
    AuditLog.objects.create(
        actor_type="SYSTEM",
        action="CREATE",
        entity_type=entity_type,
        entity_id=str(obj.pk),
        new_value_json=new,
        metadata_json=SOURCE,
    )


def seed(apps, schema_editor):
    Intent = apps.get_model("automation", "Intent")
    IntentAction = apps.get_model("automation", "IntentAction")
    RoutingRule = apps.get_model("automation", "RoutingRule")
    Area = apps.get_model("helpdesk", "Area")
    AuditLog = apps.get_model("helpdesk", "AuditLog")

    for order, (code, name, level, auth) in enumerate(INTENTS, start=1):
        human = level in ("N2", "N3", "N4")
        intent = Intent.objects.create(
            code=code,
            name=name,
            automation_level=level,
            requires_authentication=auth,
            requires_human=human,
        )
        _audit(
            AuditLog,
            "automation.intent",
            intent,
            {"code": code, "automation_level": level, "requires_authentication": auth},
        )
        if level == "N0":
            action_type, extra = "PROVIDER_QUERY", {"provider_method": PROVIDER[code]}
        elif level == "N1":
            action_type, extra = "TEMPLATE_RESPONSE", {"response_template": TEMPLATES[code]}
        elif level == "N4":
            action_type, extra = "HUMAN_REVIEW", {}
        else:
            action_type, extra = "CREATE_TICKET", {}
        action = IntentAction.objects.create(intent=intent, action_type=action_type, **extra)
        _audit(AuditLog, "automation.intentaction", action, {"intent": code, "action_type": action_type})

        if code in ROUTING:
            area_code, priority, validation = ROUTING[code]
            rule = RoutingRule.objects.create(
                intent=intent,
                area=Area.objects.get(code=area_code),
                priority=priority,
                requires_validation=validation,
                order=order * 10,
            )
            _audit(
                AuditLog,
                "automation.routingrule",
                rule,
                {"intent": code, "area": area_code, "priority": priority},
            )

    app_config = apps.get_app_config("automation")
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)
    app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for group_name, codenames in ROLE_PERMISSIONS.items():
        perms = Permission.objects.filter(content_type__app_label="automation", codename__in=codenames)
        Group.objects.get(name=group_name).permissions.add(*perms)


def unseed(apps, schema_editor):
    Intent = apps.get_model("automation", "Intent")
    IntentAction = apps.get_model("automation", "IntentAction")
    RoutingRule = apps.get_model("automation", "RoutingRule")
    AuditLog = apps.get_model("helpdesk", "AuditLog")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for group_name, codenames in ROLE_PERMISSIONS.items():
        group = Group.objects.filter(name=group_name).first()
        if group:
            group.permissions.remove(
                *Permission.objects.filter(content_type__app_label="automation", codename__in=codenames)
            )
    codes = [c for c, *_ in INTENTS]
    RoutingRule.objects.filter(intent__code__in=codes).delete()
    IntentAction.objects.filter(intent__code__in=codes).delete()
    # Borrado directo: según el orden del plan inverso, el estado histórico puede incluir
    # Ticket.intent aunque su columna ya no exista, y el colector la consultaría.
    Intent.objects.filter(code__in=codes)._raw_delete(schema_editor.connection.alias)
    AuditLog.objects.filter(metadata_json=SOURCE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0001_initial"),
        ("helpdesk", "0008_area_agents"),
        ("accounts", "0002_create_role_groups"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
