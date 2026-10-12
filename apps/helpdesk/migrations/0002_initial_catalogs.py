"""Catálogos iniciales mínimos (BE-T03A).

Los códigos coinciden con el contrato IA (SPEC §44: categoría ACADEMIC,
subcategoría GRADES) y con el catálogo de intenciones (SPEC §29).
Cada alta queda registrada en AuditLog como acción del sistema.
"""

from django.db import migrations

AREAS = [
    ("ACADEMIC", "Secretaría Académica"),
    ("FINANCE", "Tesorería y Finanzas"),
    ("IT", "Soporte Tecnológico"),
    ("SERVICE", "Atención General"),
]

CATEGORIES = {
    # código: (nombre, área por defecto, [(subcódigo, nombre), ...])
    "ACADEMIC": (
        "Académico",
        "ACADEMIC",
        [
            ("GRADES", "Calificaciones"),
            ("ENROLLMENT", "Matrícula"),
            ("SUBJECTS", "Asignaturas"),
            ("SCHEDULE", "Horarios"),
            ("CERTIFICATES", "Certificados"),
        ],
    ),
    "FINANCIAL": (
        "Financiero",
        "FINANCE",
        [("DEBT", "Deuda"), ("PAYMENTS", "Pagos")],
    ),
    "TECHNICAL": (
        "Tecnológico",
        "IT",
        [("ACCESS", "Acceso a plataformas"), ("PASSWORD", "Contraseña")],
    ),
    "GENERAL": (
        "General",
        "SERVICE",
        [("PROFILE", "Actualización de datos"), ("COMPLAINT", "Reclamo"), ("OTHER", "Otro")],
    ),
}

SOURCE = {"source": "migration:helpdesk.0002_initial_catalogs"}


def _audit(AuditLog, entity_type, obj, new):
    AuditLog.objects.create(
        actor_type="SYSTEM",
        action="CREATE",
        entity_type=entity_type,
        entity_id=str(obj.pk),
        new_value_json=new,
        metadata_json=SOURCE,
    )


def seed(apps, schema_editor):
    Area = apps.get_model("helpdesk", "Area")
    Category = apps.get_model("helpdesk", "Category")
    Subcategory = apps.get_model("helpdesk", "Subcategory")
    AuditLog = apps.get_model("helpdesk", "AuditLog")

    areas = {}
    for code, name in AREAS:
        area = Area.objects.create(code=code, name=name)
        areas[code] = area
        _audit(AuditLog, "helpdesk.area", area, {"code": code, "name": name, "email": "", "is_active": True})

    for code, (name, area_code, subs) in CATEGORIES.items():
        category = Category.objects.create(code=code, name=name, default_area=areas[area_code])
        _audit(
            AuditLog,
            "helpdesk.category",
            category,
            {"code": code, "name": name, "default_area_id": areas[area_code].pk, "is_active": True},
        )
        for sub_code, sub_name in subs:
            sub = Subcategory.objects.create(category=category, code=sub_code, name=sub_name)
            _audit(
                AuditLog,
                "helpdesk.subcategory",
                sub,
                {"category_id": category.pk, "code": sub_code, "name": sub_name, "is_active": True},
            )


def unseed(apps, schema_editor):
    Area = apps.get_model("helpdesk", "Area")
    Category = apps.get_model("helpdesk", "Category")
    Subcategory = apps.get_model("helpdesk", "Subcategory")
    AuditLog = apps.get_model("helpdesk", "AuditLog")

    AuditLog.objects.filter(metadata_json=SOURCE).delete()
    Subcategory.objects.filter(category__code__in=CATEGORIES).delete()
    Category.objects.filter(code__in=CATEGORIES).delete()
    Area.objects.filter(code__in=[code for code, _ in AREAS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("helpdesk", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
