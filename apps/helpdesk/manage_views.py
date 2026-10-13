"""Vistas de administración de catálogos (CONTRACT-016). Solo rol Administrador."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.permissions import role_required
from apps.accounts.roles import Role

from . import catalogs
from .catalog_admin import ENTITIES, cell, form_class, search_filter

PAGE_SIZE = 20


def _entity(slug):
    try:
        return ENTITIES[slug]
    except KeyError:
        raise Http404 from None


def _nav():
    return [{"slug": e.slug, "label": e.label} for e in ENTITIES.values()]


@role_required(Role.ADMINISTRADOR)
@require_GET
def manage_index(request):
    entities = [
        {
            "slug": e.slug,
            "label": e.label,
            "active": e.model.objects.filter(is_active=True).count(),
            "total": e.model.objects.count(),
            "url": reverse("manage:list", args=[e.slug]),
        }
        for e in ENTITIES.values()
    ]
    return render(request, "manage/index.html", {"entities": entities})


@role_required(Role.ADMINISTRADOR)
@require_GET
def manage_list(request, entity):
    e = _entity(entity)
    qs = e.model.objects.select_related(*e.select_related)
    if e.slug == "areas":
        qs = qs.prefetch_related("agents")
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    if q:
        qs = qs.filter(search_filter(e, q))
    if status in ("active", "inactive"):
        qs = qs.filter(is_active=status == "active")
    else:
        status = "all"
    page_obj = Paginator(qs.order_by(*e.model._meta.ordering, "pk"), PAGE_SIZE).get_page(
        request.GET.get("page")
    )
    rows = [
        {
            "pk": obj.pk,
            "object": obj,
            "is_active": obj.is_active,
            "values": [cell(obj, attr) for attr, _ in e.columns],
            "edit_url": reverse("manage:edit", args=[e.slug, obj.pk]),
            "toggle_url": reverse("manage:toggle", args=[e.slug, obj.pk]),
        }
        for obj in page_obj.object_list
    ]
    return render(
        request,
        "manage/list.html",
        {
            "entity": e.slug,
            "entity_label": e.label,
            "entity_label_singular": e.label_singular,
            "entities": _nav(),
            "columns": [label for _, label in e.columns],
            "rows": rows,
            "page_obj": page_obj,
            "filters": {"q": q, "status": status},
            "status_choices": [("all", "Todos"), ("active", "Activos"), ("inactive", "Inactivos")],
            "create_url": reverse("manage:create", args=[e.slug]),
        },
    )


def _save(e, form, actor):
    """Guarda vía el servicio auditado; los errores de modelo vuelven al formulario."""
    obj = form.save(commit=False)
    try:
        with transaction.atomic():
            catalogs.save_catalog_item(obj, actor=actor)
            if e.slug == "areas":
                catalogs.set_area_agents(obj, form.cleaned_data["agents"], actor=actor)
    except ValidationError as exc:
        errors = exc.message_dict if hasattr(exc, "error_dict") else {None: exc.messages}
        for field, msgs in errors.items():
            form.add_error(field if field in form.fields else None, msgs)
        return None
    except IntegrityError:
        form.add_error(None, "Ya existe un elemento activo equivalente (restricción de unicidad).")
        return None
    return obj


def _form_view(request, e, instance=None):
    form = form_class(e)(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = _save(e, form, request.user)
        if obj is not None:
            verb = "actualizado" if instance else "creado"
            messages.success(request, f"{e.label_singular.capitalize()} «{obj}» {verb}.")
            return redirect("manage:list", entity=e.slug)
    return render(
        request,
        "manage/form.html",
        {
            "entity": e.slug,
            "entity_label": e.label,
            "entity_label_singular": e.label_singular,
            "entities": _nav(),
            "form": form,
            "object": instance,
            "is_create": instance is None,
            "cancel_url": reverse("manage:list", args=[e.slug]),
        },
    )


@role_required(Role.ADMINISTRADOR)
@require_http_methods(["GET", "POST"])
def manage_create(request, entity):
    return _form_view(request, _entity(entity))


@role_required(Role.ADMINISTRADOR)
@require_http_methods(["GET", "POST"])
def manage_edit(request, entity, pk):
    e = _entity(entity)
    return _form_view(request, e, get_object_or_404(e.model, pk=pk))


@role_required(Role.ADMINISTRADOR)
@require_POST
def manage_toggle(request, entity, pk):
    """Activa/desactiva lógicamente. Campo POST `active` = "1" | "0"."""
    e = _entity(entity)
    obj = get_object_or_404(e.model, pk=pk)
    active = request.POST.get("active")
    if active not in ("0", "1"):
        messages.error(request, "Indique si se activa o desactiva.")
        return redirect("manage:list", entity=e.slug)
    try:
        with transaction.atomic():
            obj = catalogs.set_active(obj, active == "1", actor=request.user)
    except IntegrityError:
        messages.error(request, "No se puede activar: ya existe un elemento activo equivalente.")
    else:
        estado = "activado" if obj.is_active else "desactivado"
        messages.success(request, f"«{obj}» {estado}.")
    return redirect("manage:list", entity=e.slug)
