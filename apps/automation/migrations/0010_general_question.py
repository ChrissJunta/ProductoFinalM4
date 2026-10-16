"""GENERAL_QUESTION (ADR-083): saludos y preguntas generales que no son un trámite.

N1 con acción LLM_ANSWER: responde el LLM (sin datos institucionales) y no se crea ticket.
Si el LLM no está disponible se usa la plantilla. Migración auditada y reversible.
"""

from django.db import migrations

SOURCE = {"source": "migration:automation.0010_general_question"}
TEMPLATE = (
    "¡Hola! Soy el asistente de la Mesa de Ayuda. Puedo ayudarte con tu horario, notas, deuda, "
    "el estado de tus solicitudes o registrar un trámite. ¿En qué te ayudo?"
)


def apply(apps, schema_editor):
    Intent = apps.get_model("automation", "Intent")
    IntentAction = apps.get_model("automation", "IntentAction")
    AuditLog = apps.get_model("helpdesk", "AuditLog")
    intent = Intent.objects.create(
        code="GENERAL_QUESTION", name="Saludo o pregunta general", automation_level="N1",
        requires_llm=True,
    )  # fmt: skip
    action = IntentAction.objects.create(
        intent=intent, action_type="LLM_ANSWER", response_template=TEMPLATE,
        fallback_action="TEMPLATE_RESPONSE",
    )  # fmt: skip
    for entity_type, obj, new in (
        ("automation.intent", intent, {"code": intent.code, "automation_level": "N1"}),
        ("automation.intentaction", action, {"intent": intent.code, "action_type": "LLM_ANSWER"}),
    ):
        AuditLog.objects.create(
            actor_type="SYSTEM", action="CREATE", entity_type=entity_type,
            entity_id=str(obj.pk), new_value_json=new, metadata_json=SOURCE,
        )  # fmt: skip


def revert(apps, schema_editor):
    IntentAction = apps.get_model("automation", "IntentAction")
    IntentAction.objects.filter(intent__code="GENERAL_QUESTION").delete()
    Intent = apps.get_model("automation", "Intent")
    Intent.objects.filter(code="GENERAL_QUESTION")._raw_delete(schema_editor.connection.alias)
    apps.get_model("helpdesk", "AuditLog").objects.filter(metadata_json=SOURCE).delete()


class Migration(migrations.Migration):
    dependencies = [("automation", "0009_llm_answer_action")]

    operations = [migrations.RunPython(apply, revert)]
