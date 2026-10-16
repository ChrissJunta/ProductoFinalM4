"""Relación intención → categoría/subcategoría del catálogo (SPEC §29 y §44).

Permite que los tickets creados por automatización o IA lleguen categorizados
(SLA por categoría, filtros) y es la referencia para validar la salida del LLM.
"""

INTENT_CATEGORY = {
    "CHECK_SCHEDULE": ("ACADEMIC", "SCHEDULE"),
    "CHECK_GRADE": ("ACADEMIC", "GRADES"),
    "CHECK_DEBT": ("FINANCIAL", "DEBT"),
    "CHECK_ENROLLMENT": ("ACADEMIC", "ENROLLMENT"),
    "CHECK_SUBJECTS": ("ACADEMIC", "SUBJECTS"),
    "CHECK_TICKET": ("GENERAL", "OTHER"),
    "CHECK_ACADEMIC_DATES": ("ACADEMIC", None),
    "CHECK_CONTACT": ("GENERAL", "OTHER"),
    "CHECK_REQUIREMENTS": ("GENERAL", "OTHER"),
    "GRADE_DISCREPANCY": ("ACADEMIC", "GRADES"),
    "PAYMENT_NOT_REFLECTED": ("FINANCIAL", "PAYMENTS"),
    "DEBT_DISPUTE": ("FINANCIAL", "DEBT"),
    "ENROLLMENT_PROBLEM": ("ACADEMIC", "ENROLLMENT"),
    "SUBJECT_NOT_VISIBLE": ("ACADEMIC", "SUBJECTS"),
    "ACCESS_PROBLEM": ("TECHNICAL", "ACCESS"),
    "PASSWORD_PROBLEM": ("TECHNICAL", "PASSWORD"),
    "CERTIFICATE_REQUEST": ("ACADEMIC", "CERTIFICATES"),
    "PROFILE_UPDATE": ("GENERAL", "PROFILE"),
    "GENERAL_COMPLAINT": ("GENERAL", "COMPLAINT"),
    "UNKNOWN_REQUEST": ("GENERAL", "OTHER"),
    "GENERAL_QUESTION": ("GENERAL", "OTHER"),  # N1 sin ticket (ADR-083)
}


def category_for(intent_code):
    """(Category, Subcategory) activas para la intención, o (None, None)."""
    from apps.helpdesk.models import Category, Subcategory

    cat_code, sub_code = INTENT_CATEGORY.get(intent_code, (None, None))
    category = Category.objects.filter(code=cat_code, is_active=True).first() if cat_code else None
    subcategory = None
    if category and sub_code:
        subcategory = Subcategory.objects.filter(
            category=category, code=sub_code, is_active=True
        ).first()
    return category, subcategory
