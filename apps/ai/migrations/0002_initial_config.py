"""Configuración IA inicial (BE-T16/BE-T18): modelos fake, prompts v1 y permisos.

Mientras ADR-010 siga abierto solo existe el proveedor «fake». Al decidir el
proveedor real se añaden sus filas desde el admin (sin redeploy del negocio).
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

SOURCE = {"source": "migration:ai.0002_initial_config"}
PURPOSES = ["CLASSIFY", "EXTRACT", "SUMMARIZE", "GENERATE_RESPONSE"]

PROMPTS = {
    "CLASSIFY": (
        "classify",
        "Eres el clasificador de la mesa de ayuda universitaria. Devuelve SOLO un objeto JSON "
        "con: intent (uno de los códigos del catálogo), category, subcategory, priority "
        "(LOW|MEDIUM|HIGH|CRITICAL), summary (máx. 500 caracteres, sin datos personales), "
        "requires_human (bool) y confidence (0-1). Si dudas, usa UNKNOWN_REQUEST con "
        "confianza baja. No inventes códigos.\n\nCatálogo: {catalog}\n\nMensaje: {message}"
    ),
    "EXTRACT": (
        "extract",
        "Extrae del mensaje SOLO los campos {schema} y devuelve un objeto JSON. Usa null si "
        "el dato no aparece; no lo deduzcas.\n\nMensaje: {message}",
    ),
    "SUMMARIZE": (
        "summarize",
        "Resume la conversación para el agente en máximo 500 caracteres, en español, sin "
        "datos sensibles (notas, montos).\n\n{messages}",
    ),
    "GENERATE_RESPONSE": (
        "generate_response",
        "Reformula el texto oficial en tono cordial y breve. No añadas hechos, cifras ni "
        "fechas que no estén en el texto.\n\nTexto oficial: {template}",
    ),
}
ROLE_PERMISSIONS = {
    "Administrador": [
        f"{a}_{m}" for m in ("aimodelconfig", "aipromptversion") for a in ("add", "change", "view")
    ] + ["view_aiusage", "view_aidecision"],
    "Supervisor": ["view_aiusage", "view_aidecision"],
    "Agente": ["view_aidecision"],
}


def seed(apps, schema_editor):
    AIModelConfig = apps.get_model("ai", "AIModelConfig")
    AIPromptVersion = apps.get_model("ai", "AIPromptVersion")
    AuditLog = apps.get_model("helpdesk", "AuditLog")
    for purpose in PURPOSES:
        for model_name, primary in (("fake-1", True), ("fake-1-respaldo", False)):
            cfg = AIModelConfig.objects.create(
                provider="fake",
                model_name=model_name,
                purpose=purpose,
                is_primary=primary,
                is_fallback=not primary,
            )
            AuditLog.objects.create(
                actor_type="SYSTEM", action="CREATE", entity_type="ai.aimodelconfig",
                entity_id=str(cfg.pk), new_value_json={"model_name": model_name, "purpose": purpose},
                metadata_json=SOURCE,
            )  # fmt: skip
        name, template = PROMPTS[purpose]
        prompt = AIPromptVersion.objects.create(
            name=name, version=1, purpose=purpose, template=template
        )
        AuditLog.objects.create(
            actor_type="SYSTEM", action="CREATE", entity_type="ai.aipromptversion",
            entity_id=str(prompt.pk), new_value_json={"name": name, "version": 1},
            metadata_json=SOURCE,
        )  # fmt: skip

    app_config = apps.get_app_config("ai")
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)
    app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for group_name, codenames in ROLE_PERMISSIONS.items():
        perms = Permission.objects.filter(content_type__app_label="ai", codename__in=codenames)
        Group.objects.get(name=group_name).permissions.add(*perms)


def unseed(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for group_name, codenames in ROLE_PERMISSIONS.items():
        group = Group.objects.filter(name=group_name).first()
        if group:
            group.permissions.remove(
                *Permission.objects.filter(content_type__app_label="ai", codename__in=codenames)
            )
    apps.get_model("ai", "AIModelConfig").objects.all().delete()
    apps.get_model("ai", "AIPromptVersion").objects.all().delete()
    apps.get_model("helpdesk", "AuditLog").objects.filter(metadata_json=SOURCE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0001_initial"),
        ("accounts", "0002_create_role_groups"),
    ]

    operations = [migrations.RunPython(seed, unseed)]
