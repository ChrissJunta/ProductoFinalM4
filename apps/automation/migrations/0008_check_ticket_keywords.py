"""«mis solicitudes», «¿qué pasó con mi trámite?»… son consultas de estado (CHECK_TICKET, N0),
no solicitudes nuevas: antes creaban un ticket. Migración auditada y reversible."""

from django.db import migrations

SOURCE = {"source": "migration:automation.0008_check_ticket_keywords"}
WORDS = [
    "mis solicitudes",
    "mis tickets",
    "mis casos",
    "mis tramites",
    "mi tramite",
    "que paso con mi",
    "como va mi",
    "estado de mi",
    "en que va mi",
    "avance de mi",
]


def apply(apps, schema_editor):
    Intent = apps.get_model("automation", "Intent")
    intent = Intent.objects.filter(code="CHECK_TICKET").first()
    if intent is None:
        return
    previous = intent.keywords
    lines = [line for line in previous.split("\n") if line.strip()]
    intent.keywords = "\n".join([*lines, *(w for w in WORDS if w not in lines)])
    intent.save(update_fields=["keywords"])
    apps.get_model("helpdesk", "AuditLog").objects.create(
        actor_type="SYSTEM", action="UPDATE", entity_type="automation.intent",
        entity_id=str(intent.pk), previous_value_json={"keywords": previous},
        new_value_json={"keywords": intent.keywords}, metadata_json=SOURCE,
    )  # fmt: skip


def revert(apps, schema_editor):
    Intent = apps.get_model("automation", "Intent")
    intent = Intent.objects.filter(code="CHECK_TICKET").first()
    if intent is not None:
        intent.keywords = "\n".join(w for w in intent.keywords.split("\n") if w not in WORDS)
        intent.save(update_fields=["keywords"])
    apps.get_model("helpdesk", "AuditLog").objects.filter(metadata_json=SOURCE).delete()


class Migration(migrations.Migration):
    dependencies = [("automation", "0007_requirements_keywords")]

    operations = [migrations.RunPython(apply, revert)]
