from django.db import migrations

# Nombres fijos en la migración: no importar desde roles.py para que la
# migración siga siendo válida aunque el código evolucione.
ROLE_GROUPS = ["Usuario", "Agente", "Supervisor", "Administrador"]


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ROLE_GROUPS:
        Group.objects.get_or_create(name=name)


def delete_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLE_GROUPS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_groups, delete_groups),
    ]
