"""Ajuste de palabras clave con el conjunto de DESARROLLO del dataset (BE-T17).

Solo se miraron errores de desarrollo; el conjunto de prueba se usa para medir.
"""

from django.db import migrations

SOURCE = {"source": "migration:automation.0005_tune_keywords"}

EXTRA = {
    "ACCESS_PROBLEM": ["no logro ingresar", "no tengo acceso", "usuario + no funciona", "no carga"],
    "CERTIFICATE_REQUEST": ["constancia de", "certificado de"],
    "CHECK_ACADEMIC_DATES": ["hasta cuando", "vacaciones", "inicio del periodo"],
    "CHECK_CONTACT": ["extension", "atienden", "a donde llamo", "con quien hablo"],
    "CHECK_DEBT": ["cuota", "adeudo", "al dia + pagos", "estado de cuenta", "pagos pendientes"],
    "CHECK_ENROLLMENT": ["me matricularon", "estoy inscrito"],
    "CHECK_REQUIREMENTS": ["papeles", "que tengo que presentar"],
    "DEBT_DISPUTE": ["dos veces", "mal cargados", "cobran + no tome", "cobraron + no"],
    "ENROLLMENT_PROBLEM": [
        "matricularme", "inscribirme", "no puedo terminar", "intento matricularme",
    ],
    "GENERAL_COMPLAINT": ["trataron mal", "atencion + lenta", "molesto", "me atendieron"],
    "GRADE_DISCREPANCY": [
        "pusieron mal", "calificacion + mal", "calificacion + no coincide", "bajaron la nota",
        "nota + reclamar",
    ],
    "PASSWORD_PROBLEM": ["se me olvido", "contrasena + expiro", "recupero mi clave"],
    "PAYMENT_NOT_REFLECTED": [
        "transferencia", "figura pendiente", "cancele la cuota", "impaga", "deposite",
    ],
    "PROFILE_UPDATE": [
        "direccion + actualizo", "numero de celular", "modificar + correo", "apellido",
        "mal escrito",
    ],
    "SUBJECT_NOT_VISIBLE": [
        "asignatura + no aparece", "no veo + materias", "matricule + no aparece",
        "desaparecio", "no aparece + materias",
    ],
}  # fmt: skip


def apply(apps, schema_editor):
    Intent = apps.get_model("automation", "Intent")
    AuditLog = apps.get_model("helpdesk", "AuditLog")
    for code, words in EXTRA.items():
        intent = Intent.objects.get(code=code)
        previous = intent.keywords
        intent.keywords = "\n".join([previous, *words]) if previous else "\n".join(words)
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
    for code, words in EXTRA.items():
        intent = Intent.objects.get(code=code)
        lines = intent.keywords.split("\n")
        intent.keywords = "\n".join(lines[: len(lines) - len(words)])
        intent.save(update_fields=["keywords"])
    apps.get_model("helpdesk", "AuditLog").objects.filter(metadata_json=SOURCE).delete()


class Migration(migrations.Migration):
    dependencies = [("automation", "0004_initial_keywords")]

    operations = [migrations.RunPython(apply, revert)]
