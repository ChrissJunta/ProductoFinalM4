"""Prompt de clasificación v3 (ADR-083): saludos y preguntas generales → GENERAL_QUESTION.

UNKNOWN_REQUEST queda para peticiones no identificadas que necesitan a una persona. La v2
queda inactiva.
"""

from django.db import migrations

SOURCE = {"source": "migration:ai.0006_classify_prompt_v3"}
TEMPLATE = (
    "Eres el clasificador de la mesa de ayuda universitaria. Devuelve SOLO un objeto JSON con: "
    "intent (uno de los códigos del catálogo), category, subcategory, priority "
    "(LOW|MEDIUM|HIGH|CRITICAL), summary (máx. 500 caracteres, sin datos personales), "
    "requires_human (bool) y confidence (0-1). No inventes códigos.\n"
    "Criterios: una PREGUNTA por requisitos, fechas, contactos o información general es una "
    "consulta informativa (nivel N1), aunque mencione un trámite (certificado, matrícula). "
    "Una PETICIÓN de hacer algo (emitir, corregir, desbloquear, reclamar) es una solicitud "
    "(N2/N3). Un saludo, un agradecimiento o una pregunta de cultura general que no es un "
    "trámite de la universidad ni pide datos personales es GENERAL_QUESTION. Si el mensaje "
    "contiene varias solicitudes distintas o no estás seguro, usa confianza menor a 0.7. "
    "Usa UNKNOWN_REQUEST solo para una petición que no reconoces y necesita a una persona, "
    "con confianza baja.\n{candidates}\n\nCatálogo: {catalog}\n\nMensaje: {message}"
)


def apply(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AuditLog = apps.get_model("helpdesk", "AuditLog")
    AIPromptVersion.objects.filter(purpose="CLASSIFY", is_active=True).update(is_active=False)
    prompt = AIPromptVersion.objects.create(
        name="classify", version=3, purpose="CLASSIFY", template=TEMPLATE
    )
    AuditLog.objects.create(
        actor_type="SYSTEM", action="CREATE", entity_type="ai.aipromptversion",
        entity_id=str(prompt.pk), new_value_json={"name": "classify", "version": 3},
        metadata_json=SOURCE,
    )  # fmt: skip


def revert(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    v3 = AIPromptVersion.objects.filter(name="classify", version=3)
    apps.get_model("ai", "AIDecision").objects.filter(prompt_version__in=v3).update(
        prompt_version=None
    )
    v3.delete()
    AIPromptVersion.objects.filter(name="classify", version=2).update(is_active=True)
    apps.get_model("helpdesk", "AuditLog").objects.filter(metadata_json=SOURCE).delete()


class Migration(migrations.Migration):
    dependencies = [("ai", "0005_classify_prompt_v2"), ("automation", "0010_general_question")]

    operations = [migrations.RunPython(apply, revert)]
