"""Permisos de modelo por rol para catálogos y auditoría (BE-T03A).

Administrador: gestiona catálogos (sin borrado físico) y consulta auditoría.
Supervisor: consulta catálogos y auditoría.
Agente: consulta catálogos.
Usuario: sin permisos de modelo (elige categoría solo mediante vistas).
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

CATALOGS = ["area", "category", "subcategory"]

ROLE_PERMISSIONS = {
    "Administrador": [f"{a}_{m}" for m in CATALOGS for a in ("add", "change", "view")]
    + ["view_auditlog"],
    "Supervisor": [f"view_{m}" for m in CATALOGS] + ["view_auditlog"],
    "Agente": [f"view_{m}" for m in CATALOGS],
}


def _ensure_permissions(apps):
    # Los permisos se crean normalmente en post_migrate; aquí se necesitan antes.
    app_config = apps.get_app_config("helpdesk")
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)
    app_config.models_module = None


def grant(apps, schema_editor):
    _ensure_permissions(apps)
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for group_name, codenames in ROLE_PERMISSIONS.items():
        group = Group.objects.get(name=group_name)
        perms = Permission.objects.filter(content_type__app_label="helpdesk", codename__in=codenames)
        group.permissions.add(*perms)


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for group_name, codenames in ROLE_PERMISSIONS.items():
        group = Group.objects.filter(name=group_name).first()
        if group:
            perms = Permission.objects.filter(
                content_type__app_label="helpdesk", codename__in=codenames
            )
            group.permissions.remove(*perms)


class Migration(migrations.Migration):
    dependencies = [
        ("helpdesk", "0002_initial_catalogs"),
        ("accounts", "0002_create_role_groups"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
