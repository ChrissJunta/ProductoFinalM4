from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.permissions import role_required
from apps.accounts.roles import Role

from . import queries, workflow
from .forms import TicketCreateForm, TransitionForm, category_tree
from .models import Alert, Area, Attachment, Category, Ticket
from .tickets import TicketService

S = Ticket.Status

# Acciones con nombre de SPEC §47.1 → (estado destino, estado origen exigido o None).
NAMED_ACTIONS = {
    "resolve": (S.RESOLVED, None),
    "escalate": (S.ESCALATED, None),
    "confirm": (S.CLOSED, S.RESOLVED),
    "reject_resolution": (S.IN_PROGRESS, S.RESOLVED),
    "reopen": (S.REOPENED, None),
    "cancel": (S.CANCELLED, None),
}


@login_required
@require_http_methods(["GET", "POST"])
def ticket_create(request):
    """FE-003 / CONTRACT-004: crear una solicitud desde web."""
    form = TicketCreateForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            ticket = TicketService.create(
                user=request.user,
                subject=data["subject"],
                description=data["description"],
                category=data["category"],
                subcategory=data["subcategory"],
                attachment=data["attachment"],
            )
        except ValidationError as exc:
            for field, errors in exc.message_dict.items():
                form.add_error(field if field in form.fields else None, errors)
        else:
            messages.success(request, f"Solicitud {ticket.ticket_code} creada.")
            # Cuando exista el detalle (BE-T05/FE-T05) se redirigirá allí (CHANGE REQUEST).
            return redirect("accounts:role_redirect")
    return render(
        request,
        "helpdesk/ticket_form.html",
        {"form": form, "category_tree": category_tree()},
    )


@login_required
@require_GET
def attachment_download(request, code, pk):
    """CONTRACT-005: descarga de un adjunto; 404 si el ticket no es visible (SPEC §26)."""
    ticket = queries.get_visible_ticket_or_404(request.user, code)
    attachment = get_object_or_404(Attachment, pk=pk, ticket=ticket)
    try:
        handle = attachment.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc
    return FileResponse(
        handle,
        as_attachment=True,
        filename=attachment.original_name,
        content_type=attachment.content_type,
    )


def _safe_next(request):
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    # Cuando exista el detalle (BE-T05/FE-T05) será el destino por defecto (CHANGE REQUEST).
    return None


@login_required
@require_POST
def ticket_transition(request, code, action=None):
    """CONTRACT-006: ejecutar una transición de estado (SPEC §32.1, §47.1)."""
    ticket = queries.get_visible_ticket_or_404(request.user, code)

    if action is None:
        try:
            target, required_source = S(request.POST.get("to_status", "")), None
        except ValueError:
            return HttpResponseBadRequest("Estado destino no válido.")
    else:
        target, required_source = NAMED_ACTIONS[action]

    form = TransitionForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Solicitud incompleta.")

    try:
        if required_source is not None and ticket.status != required_source:
            raise workflow.InvalidTransition()
        ticket = TicketService.change_status(
            ticket,
            target,
            actor=request.user,
            reason=form.cleaned_data["reason"],
            expected_version=form.cleaned_data["version"],
        )
    except workflow.TransitionForbidden:
        raise
    except workflow.TransitionError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(
            request,
            f"Ticket {ticket.ticket_code}: estado cambiado a {ticket.get_status_display()}.",
        )
    return redirect(_safe_next(request) or "accounts:role_redirect")


ALERTS_PER_PAGE = 25


@role_required(Role.SUPERVISOR)
@require_GET
def alert_list(request):
    """FE-007 / CONTRACT-007: alertas de SLA y escalados (Supervisor)."""
    status = request.GET.get("status", Alert.Status.OPEN)
    alert_type = request.GET.get("type", "")
    alerts = Alert.objects.select_related("ticket", "ticket__assigned_area")
    if status in Alert.Status.values:
        alerts = alerts.filter(status=status)
    else:
        status = "ALL"
    if alert_type in Alert.Type.values:
        alerts = alerts.filter(alert_type=alert_type)
    else:
        alert_type = ""

    open_counts = dict(
        Alert.objects.filter(status=Alert.Status.OPEN)
        .values_list("alert_type")
        .annotate(n=Count("id"))
    )
    page = Paginator(alerts, ALERTS_PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "helpdesk/alerts.html",
        {
            "page_obj": page,
            "alerts": page.object_list,
            "filters": {"status": status, "type": alert_type},
            "status_choices": Alert.Status.choices,
            "type_choices": Alert.Type.choices,
            "open_counts": {value: open_counts.get(value, 0) for value in Alert.Type.values},
        },
    )


def _list_context(request, qs, applied, extra=None):
    page = Paginator(queries.with_related(qs), queries.PAGE_SIZE).get_page(request.GET.get("page"))
    context = {
        "page_obj": page,
        "rows": queries.ticket_rows(page.object_list),
        "filters": applied,
        "status_choices": [("OPEN", "Abiertos"), *Ticket.Status.choices],
        "priority_choices": Ticket.Priority.choices,
        "categories": Category.objects.filter(is_active=True),
        "areas": Area.objects.filter(is_active=True),
        "sort_choices": [
            ("-created_at", "Más recientes"),
            ("created_at", "Más antiguos"),
            ("-updated_at", "Última actualización"),
            ("sla_due_at", "Vencimiento SLA"),
        ],
    }
    context.update(extra or {})
    return context


@login_required
@require_GET
def ticket_list(request):
    """FE-004 / CONTRACT-008: tickets visibles para el usuario, con filtros y paginación."""
    qs, applied = queries.apply_filters(
        queries.visible_tickets(request.user), request.GET, request.user
    )
    return render(request, "helpdesk/ticket_list.html", _list_context(request, qs, applied))


# Pestañas de la bandeja (SPEC §10, navegación del Agente): filtros predefinidos.
INBOX_TABS = {
    "mine": ("Mi bandeja", {"assignee": "me", "status": "OPEN"}),
    "unassigned": ("Sin asignar", {"assignee": "none", "status": "OPEN"}),
    "in_progress": ("En proceso", {"status": S.IN_PROGRESS}),
    "waiting_user": ("Pendientes de usuario", {"status": S.WAITING_USER}),
    "due_soon": ("Por vencer", {"sla": "WARNING"}),
    "overdue": ("Vencidos", {"sla": "BREACHED"}),
    "history": ("Historial", {"status": "FINISHED"}),
}


@role_required(Role.AGENTE, Role.SUPERVISOR)
@require_GET
def agent_inbox(request):
    """FE-006 / CONTRACT-009: bandeja del agente con pestañas y filtros."""
    tab = request.GET.get("tab", "mine")
    if tab not in INBOX_TABS:
        tab = "mine"
    params = {"sort": "sla_due_at", **INBOX_TABS[tab][1]}
    params.update({k: v for k, v in request.GET.items() if k not in ("tab", "page")})

    visible = queries.visible_tickets(request.user)
    qs, applied = queries.apply_filters(visible, params, request.user)
    tabs = [
        {
            "key": key,
            "label": label,
            "count": queries.apply_filters(visible, preset, request.user)[0].count(),
        }
        for key, (label, preset) in INBOX_TABS.items()
        if key != "history"
    ]
    tabs.append({"key": "history", "label": INBOX_TABS["history"][0], "count": None})
    agents = (
        get_user_model()
        .objects.filter(groups__name=Role.AGENTE, is_active=True)
        .order_by("first_name", "username")
    )
    return render(
        request,
        "helpdesk/agent_inbox.html",
        _list_context(request, qs, applied, {"tab": tab, "tabs": tabs, "assignees": agents}),
    )
