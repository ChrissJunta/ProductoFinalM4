"""Palabras clave iniciales del Intent Engine (CR-006, BE-T13).

Son un punto de partida en español: el Administrador las ajusta desde el admin
sin redeploy. Una línea por coincidencia; «a + b» exige todas las partes.
Las intenciones de problema combinan tema + síntoma para ganar a la consulta simple.
"""

from django.db import migrations

SOURCE = {"source": "migration:automation.0004_initial_keywords"}

KEYWORDS = {
    "CHECK_SCHEDULE": ["horario", "horarios", "a que hora", "clases", "aula"],
    "CHECK_GRADE": ["nota", "notas", "calificacion", "calificaciones", "promedio"],
    "CHECK_DEBT": ["deuda", "saldo", "cuanto debo", "que debo", "valor pendiente"],
    "CHECK_ENROLLMENT": ["matricula", "matriculado", "matriculada", "inscripcion", "inscrito"],
    "CHECK_SUBJECTS": ["materias", "asignaturas", "creditos"],
    "CHECK_TICKET": ["ticket", "mi solicitud", "mi caso", "seguimiento"],
    "CHECK_ACADEMIC_DATES": [
        "fechas", "calendario academico", "cuando empiezan", "examenes", "cierre de notas",
    ],
    "CHECK_CONTACT": ["contacto", "telefono", "correo", "oficina", "a quien acudo", "donde queda"],
    "CHECK_REQUIREMENTS": ["requisitos", "que necesito", "que documentos", "documentos necesarios"],
    "GRADE_DISCREPANCY": [
        "nota + incorrecta", "nota + mal", "nota + error", "nota + equivocada",
        "notas + incorrectas", "notas + mal", "notas + error", "nota + no coincide",
        "recalificacion", "revision de nota",
    ],
    "PAYMENT_NOT_REFLECTED": [
        "ya pague", "pague + sigue", "pague + aparece", "pago + no se refleja",
        "pago + no aparece", "pago + no refleja", "pago no reflejado", "comprobante de pago",
    ],
    "DEBT_DISPUTE": [
        "no debo", "no reconozco", "cobro indebido", "cobro incorrecto",
        "deuda + incorrecta", "deuda + error", "deuda + reclamo",
    ],
    "ENROLLMENT_PROBLEM": [
        "matricula + no puedo", "matricula + error", "matricula + problema",
        "matricula + bloqueada", "no puedo matricularme", "no me deja matricular",
    ],
    "SUBJECT_NOT_VISIBLE": [
        "materia + aparece", "materias + aparecen", "materia + veo", "asignatura + aparece",
        "materia + falta",
    ],
    "ACCESS_PROBLEM": [
        "no puedo entrar", "no puedo ingresar", "cuenta bloqueada", "aula virtual",
        "iniciar sesion", "acceso",
    ],
    "PASSWORD_PROBLEM": [
        "contrasena", "clave", "olvide mi contrasena", "restablecer", "cambiar contrasena",
    ],
    "CERTIFICATE_REQUEST": ["certificado", "certificados", "constancia", "record academico"],
    "PROFILE_UPDATE": [
        "actualizar mis datos", "datos personales", "cambiar + telefono", "cambiar + correo",
        "actualizar + direccion", "cambiar + nombre",
    ],
    "GENERAL_COMPLAINT": ["queja", "reclamo", "inconformidad", "mala atencion", "quejarme"],
}  # fmt: skip


def seed(apps, schema_editor):
    Intent = apps.get_model("automation", "Intent")
    AuditLog = apps.get_model("helpdesk", "AuditLog")
    for code, words in KEYWORDS.items():
        intent = Intent.objects.get(code=code)
        intent.keywords = "\n".join(words)
        intent.save(update_fields=["keywords"])
        AuditLog.objects.create(
            actor_type="SYSTEM",
            action="UPDATE",
            entity_type="automation.intent",
            entity_id=str(intent.pk),
            previous_value_json={"keywords": ""},
            new_value_json={"keywords": intent.keywords},
            metadata_json=SOURCE,
        )


def unseed(apps, schema_editor):
    apps.get_model("automation", "Intent").objects.filter(code__in=KEYWORDS).update(keywords="")
    apps.get_model("helpdesk", "AuditLog").objects.filter(metadata_json=SOURCE).delete()


class Migration(migrations.Migration):
    dependencies = [("automation", "0003_intent_keywords")]

    operations = [migrations.RunPython(seed, unseed)]
