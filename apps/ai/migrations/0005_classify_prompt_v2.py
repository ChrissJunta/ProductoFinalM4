"""Prompt de clasificación v2 (CR-009): desambiguación agéntica.

Distingue consultas informativas (N1) de solicitudes con trámite y recibe los
candidatos cuando las reglas empatan (`{candidates}`). La v1 queda inactiva.
"""

from django.db import migrations

SOURCE = {"source": "migration:ai.0005_classify_prompt_v2"}
TEMPLATE = (
    "Eres el clasificador de la mesa de ayuda universitaria. Devuelve SOLO un objeto JSON con: "
    "intent (uno de los códigos del catálogo), category, subcategory, priority "
    "(LOW|MEDIUM|HIGH|CRITICAL), summary (máx. 500 caracteres, sin datos personales), "
    "requires_human (bool) y confidence (0-1). No inventes códigos.\n"
    "Criterios: una PREGUNTA por requisitos, fechas, contactos o información general es una "
    "consulta informativa (nivel N1), aunque mencione un trámite (certificado, matrícula). "
    "Una PETICIÓN de hacer algo (emitir, corregir, desbloquear, reclamar) es una solicitud "
    "(N2/N3). Si el mensaje contiene varias solicitudes distintas o no estás seguro, usa "
    "confianza menor a 0.7. Si no corresponde a ninguna, usa UNKNOWN_REQUEST con confianza "
    "baja.\n{candidates}\n\nCatálogo: {catalog}\n\nMensaje: {message}"
)


def apply(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AuditLog = apps.get_model("helpdesk", "AuditLog")
    AIPromptVersion.objects.filter(purpose="CLASSIFY", is_active=True).update(is_active=False)
    prompt = AIPromptVersion.objects.create(
        name="classify", version=2, purpose="CLASSIFY", template=TEMPLATE
    )
    AuditLog.objects.create(
        actor_type="SYSTEM", action="CREATE", entity_type="ai.aipromptversion",
        entity_id=str(prompt.pk), new_value_json={"name": "classify", "version": 2},
        metadata_json=SOURCE,
    )  # fmt: skip


def revert(apps, schema_editor):
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    v2 = AIPromptVersion.objects.filter(name="classify", version=2)
    apps.get_model("ai", "AIDecision").objects.filter(prompt_version__in=v2).update(
        prompt_version=None
    )
    v2.delete()
    AIPromptVersion.objects.filter(name="classify", version=1).update(is_active=True)
    apps.get_model("helpdesk", "AuditLog").objects.filter(metadata_json=SOURCE).delete()


class Migration(migrations.Migration):
    dependencies = [("ai", "0004_agent_policies")]

    operations = [migrations.RunPython(apply, revert)]
