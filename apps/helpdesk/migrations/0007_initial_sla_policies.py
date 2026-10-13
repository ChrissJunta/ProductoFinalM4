"""Políticas SLA generales (SPEC §34) y permisos por rol para SLA y alertas (BE-T08).

Se crean en horario laboral (ADR-026); el Administrador puede cambiarlas.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

POLICIES = [
    # prioridad, primera respuesta (min), resolución (min)
    ("LOW", 480, 4320),
    ("MEDIUM", 240, 2880),
    ("HIGH", 60, 1440),
    ("CRITICAL", 15, 240),
]

SOURCE = {"source": "migration:helpdesk.0007_initial_sla_policies"}

ROLE_PERMISSIONS = {
    "Administrador": ["add_slapolicy", "change_slapolicy", "view_slapolicy", "view_alert"],
    "Supervisor": ["view_slapolicy", "view_alert"],
    "Agente": ["view_slapolicy"],
}


def seed(apps, schema_editor):
    SLAPolicy = apps.get_model("helpdesk", "SLAPolicy")
    AuditLog = apps.get_model("helpdesk", "AuditLog")
    for priority, first, resolution in POLICIES:
        policy = SLAPolicy.objects.create(
            priority=priority,
            first_response_minutes=first,
            resolution_minutes=resolution,
            business_hours_only=True,
        )
        AuditLog.objects.create(
            actor_type="SYSTEM",
            action="CREATE",
            entity_type="helpdesk.slapolicy",
            entity_id=str(policy.pk),
            new_value_json={
                "category_id": None,
                "priority": priority,
                "first_response_minutes": first,
                "resolution_minutes": resolution,
                "business_hours_only": True,
                "is_active": True,
            },
            metadata_json=SOURCE,
        )

    app_config = apps.get_app_config("helpdesk")
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)
    app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for group_name, codenames in ROLE_PERMISSIONS.items():
        perms = Permission.objects.filter(content_type__app_label="helpdesk", codename__in=codenames)
        Group.objects.get(name=group_name).permissions.add(*perms)


def unseed(apps, schema_editor):
    SLAPolicy = apps.get_model("helpdesk", "SLAPolicy")
    AuditLog = apps.get_model("helpdesk", "AuditLog")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for group_name, codenames in ROLE_PERMISSIONS.items():
        group = Group.objects.filter(name=group_name).first()
        if group:
            group.permissions.remove(
                *Permission.objects.filter(content_type__app_label="helpdesk", codename__in=codenames)
            )
    AuditLog.objects.filter(metadata_json=SOURCE).delete()
    SLAPolicy.objects.filter(category__isnull=True, priority__in=[p for p, _, _ in POLICIES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("helpdesk", "0006_sla_and_alerts"),
        ("accounts", "0002_create_role_groups"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
