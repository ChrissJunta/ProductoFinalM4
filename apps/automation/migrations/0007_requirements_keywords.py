"""«¿Requisitos para un certificado?» es una consulta informativa (N1), no una solicitud.

Antes «requisitos» (CHECK_REQUIREMENTS) empataba con el trámite mencionado
(«certificado», «matricularme»…) y el mensaje terminaba en revisión humana con ticket.
Las combinaciones «requisitos + trámite» suman más que el trámite solo.
"""

from django.db import migrations

SOURCE = {"source": "migration:automation.0007_requirements_keywords"}
WORDS = [
    "requisitos para",
    "requisitos + certificado",
    "requisitos + certificados",
    "requisitos + constancia",
    "requisitos + matricula",
    "requisitos + matricularme",
    "requisitos + inscribirme",
    "requisitos + titulo",
    "que necesito + certificado",
    "que necesito + matricularme",
    "que documentos + certificado",
]


def apply(apps, schema_editor):
    Intent = apps.get_model("automation", "Intent")
    AuditLog = apps.get_model("helpdesk", "AuditLog")
    intent = Intent.objects.filter(code="CHECK_REQUIREMENTS").first()
    if intent is None:
        return
    previous = intent.keywords
    lines = [line for line in previous.split("\n") if line.strip()]
    intent.keywords = "\n".join([*lines, *(w for w in WORDS if w not in lines)])
    intent.save(update_fields=["keywords"])
    AuditLog.objects.create(
        actor_type="SYSTEM",
        action="UPDATE",
        entity_type="automation.intent",
        entity_id=str(intent.pk),
        previous_value_json={"keywords": previous},
        new_value_json={"keywords": intent.keywords},
        metadata_json=SOURCE,
    )


def revert(apps, schema_editor):
    Intent = apps.get_model("automation", "Intent")
    intent = Intent.objects.filter(code="CHECK_REQUIREMENTS").first()
    if intent is not None:
        intent.keywords = "\n".join(w for w in intent.keywords.split("\n") if w not in WORDS)
        intent.save(update_fields=["keywords"])
    apps.get_model("helpdesk", "AuditLog").objects.filter(metadata_json=SOURCE).delete()


class Migration(migrations.Migration):
    dependencies = [("automation", "0006_agent_policies"), ("helpdesk", "0011_alert_human_review")]

    operations = [migrations.RunPython(apply, revert)]
