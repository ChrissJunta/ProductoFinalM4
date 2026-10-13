"""Administración propia de catálogos (FE-T09, CONTRACT-016 responde CONTRACT-FRONT-005).

Un registro describe cada entidad administrable: modelo, campos del formulario,
columnas del listado y búsqueda. Toda escritura pasa por `helpdesk.catalogs`
(auditada, sin borrado físico). El código (`code`) no se edita tras crearlo
porque otras configuraciones y la auditoría lo referencian (ADR-058).
"""

from dataclasses import dataclass

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.accounts.roles import Role
from apps.automation.models import Intent, IntentAction, RoutingRule

from .models import Area, Category, SLAPolicy, Subcategory


@dataclass(frozen=True)
class Entity:
    slug: str
    model: type
    label: str  # plural, para títulos
    label_singular: str
    fields: tuple  # campos del formulario (sin is_active: se cambia con su propia acción)
    columns: tuple  # (atributo, encabezado) del listado; admite "a__b" y get_X_display
    search: tuple = ("code", "name")
    select_related: tuple = ()


ENTITIES = {
    e.slug: e
    for e in (
        Entity(
            "areas", Area, "Áreas", "área",
            ("code", "name", "email", "agents"),
            (("code", "Código"), ("name", "Nombre"), ("email", "Correo"),
             ("agent_names", "Agentes")),
        ),
        Entity(
            "categories", Category, "Categorías", "categoría",
            ("code", "name", "default_area"),
            (("code", "Código"), ("name", "Nombre"), ("default_area__name", "Área por defecto")),
            select_related=("default_area",),
        ),
        Entity(
            "subcategories", Subcategory, "Subcategorías", "subcategoría",
            ("category", "code", "name"),
            (("category__name", "Categoría"), ("code", "Código"), ("name", "Nombre")),
            select_related=("category",),
        ),
        Entity(
            "intents", Intent, "Intenciones", "intención",
            ("code", "name", "automation_level", "requires_authentication", "requires_llm",
             "requires_human", "keywords"),
            (("code", "Código"), ("name", "Nombre"),
             ("get_automation_level_display", "Nivel"),
             ("requires_authentication", "Requiere autenticación")),
        ),
        Entity(
            "actions", IntentAction, "Acciones de intención", "acción",
            ("intent", "action_type", "provider_method", "response_template", "fallback_action"),
            (("intent__code", "Intención"), ("get_action_type_display", "Acción"),
             ("provider_method", "Método del proveedor"),
             ("get_fallback_action_display", "Respaldo")),
            search=("intent__code", "intent__name", "response_template"),
            select_related=("intent",),
        ),
        Entity(
            "routing", RoutingRule, "Reglas de routing", "regla de routing",
            ("intent", "category", "subcategory", "area", "priority", "requires_validation",
             "order"),
            (("order", "Orden"), ("intent__code", "Intención"), ("category__name", "Categoría"),
             ("subcategory__name", "Subcategoría"), ("area__name", "Área"),
             ("get_priority_display", "Prioridad"), ("requires_validation", "Requiere validación")),
            search=("intent__code", "category__code", "subcategory__code", "area__code"),
            select_related=("intent", "category", "subcategory", "area"),
        ),
        Entity(
            "sla", SLAPolicy, "Políticas SLA", "política SLA",
            ("category", "priority", "first_response_minutes", "resolution_minutes",
             "business_hours_only"),
            (("category__name", "Categoría"), ("get_priority_display", "Prioridad"),
             ("first_response_minutes", "Primera respuesta (min)"),
             ("resolution_minutes", "Resolución (min)"),
             ("business_hours_only", "Solo horario laboral")),
            search=("category__code", "category__name", "priority"),
            select_related=("category",),
        ),
    )
}  # fmt: skip


def cell(obj, attr):
    """Valor mostrable de una columna (`a__b`, `get_x_display` o `agent_names`)."""
    if attr == "agent_names":
        return ", ".join(sorted(a.username for a in obj.agents.all()))
    if attr.startswith("get_") and attr.endswith("_display"):
        return getattr(obj, attr)()
    value = obj
    for part in attr.split("__"):
        value = getattr(value, part, None)
        if value is None:
            return ""
    return value


def search_filter(entity, q):
    query = Q()
    for field in entity.search:
        query |= Q(**{f"{field}__icontains": q})
    return query


def _active_or_current(queryset, current_pk):
    return (
        queryset.filter(Q(is_active=True) | Q(pk=current_pk))
        if current_pk
        else queryset.filter(is_active=True)
    )


class CatalogForm(forms.ModelForm):
    """Base: código fijo al editar y relaciones limitadas a opciones activas (o la actual)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        editing = self.instance.pk is not None
        if editing and "code" in self.fields:
            self.fields["code"].disabled = True
            self.fields["code"].help_text = "El código no se modifica una vez creado."
        for name, field in self.fields.items():
            if isinstance(field, forms.ModelChoiceField) and name != "agents":
                current = getattr(self.instance, f"{name}_id", None) if editing else None
                field.queryset = _active_or_current(field.queryset, current)


class AreaForm(CatalogForm):
    agents = forms.ModelMultipleChoiceField(
        label="Agentes del área",
        queryset=get_user_model().objects.none(),
        required=False,
        help_text="Solo usuarios activos con rol Agente (CR-003).",
    )

    class Meta:
        model = Area
        fields = ("code", "name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["agents"].queryset = (
            get_user_model()
            .objects.filter(is_active=True, groups__name=Role.AGENTE)
            .order_by("username")
        )
        if self.instance.pk:
            self.initial["agents"] = list(self.instance.agents.values_list("pk", flat=True))


class IntentActionForm(CatalogForm):
    provider_method = forms.ChoiceField(
        label="Método del proveedor",
        required=False,
        choices=[("", "—")] + [(m, m) for m in IntentAction.PROVIDER_METHODS],
    )

    class Meta:
        model = IntentAction
        fields = ENTITIES["actions"].fields


def form_class(entity):
    if entity.slug == "areas":
        return AreaForm
    if entity.slug == "actions":
        return IntentActionForm
    widgets = {"keywords": forms.Textarea(attrs={"rows": 8})} if entity.slug == "intents" else {}
    return forms.modelform_factory(
        entity.model, form=CatalogForm, fields=entity.fields, widgets=widgets
    )
