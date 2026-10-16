from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.permissions import role_required
from apps.accounts.roles import Role, has_role

from . import assignment, conversations, metrics, queries, sla, workflow
from .forms import (
    AssignForm,
    MessageForm,
    MetricsFilterForm,
    TicketCreateForm,
    TransitionForm,
    category_tree,
)
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
            return redirect("helpdesk:ticket_detail", code=ticket.ticket_code)
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
    return redirect(_safe_next(request) or _detail_url(ticket))


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


def _detail_url(ticket):
    return reverse("helpdesk:ticket_detail", args=[ticket.ticket_code])


# Acción de la UI para cada transición permitida (CONTRACT-010).
# (estado origen o None, destino) → (url name, etiqueta)
ACTION_ROUTES = {
    (S.RESOLVED, S.CLOSED): ("helpdesk:ticket_confirm", "Confirmar solución"),
    (S.RESOLVED, S.IN_PROGRESS): ("helpdesk:ticket_reject_resolution", "Rechazar solución"),
    (None, S.RESOLVED): ("helpdesk:ticket_resolve", "Resolver"),
    (None, S.ESCALATED): ("helpdesk:ticket_escalate", "Escalar"),
    (None, S.REOPENED): ("helpdesk:ticket_reopen", "Reabrir"),
    (None, S.CANCELLED): ("helpdesk:ticket_cancel", "Cancelar solicitud"),
    (None, S.IN_PROGRESS): ("helpdesk:ticket_status", "Iniciar / retomar atención"),
    (None, S.WAITING_USER): ("helpdesk:ticket_status", "Esperar respuesta del usuario"),
    (None, S.CLASSIFIED): ("helpdesk:ticket_status", "Marcar como clasificado"),
    (None, S.ASSIGNED): ("helpdesk:ticket_status", "Marcar como asignado"),
}


def ticket_actions(ticket, user):
    """Acciones de estado que `user` puede ejecutar ahora, listas para pintar botones."""
    actions = []
    for target in workflow.allowed_targets(ticket, user):
        route = ACTION_ROUTES.get((ticket.status, target)) or ACTION_ROUTES[(None, target)]
        rule = workflow.TRANSITIONS[(ticket.status, target)]
        actions.append(
            {
                "target": target,
                "label": route[1],
                "url_name": route[0],
                "url": reverse(route[0], args=[ticket.ticket_code]),
                "reason_required": rule.reason_required,
                "generic": route[0] == "helpdesk:ticket_status",
            }
        )
    return actions


@login_required
@require_GET
def ticket_detail(request, code):
    """FE-005 / CONTRACT-010: detalle, conversación omnicanal y acciones autorizadas."""
    ticket = get_object_or_404(
        queries.with_related(queries.visible_tickets(request.user)), ticket_code=code
    )
    user = request.user
    return render(
        request,
        "helpdesk/ticket_detail.html",
        {
            "ticket": ticket,
            "sla": sla.sla_status(ticket),
            "timeline": conversations.timeline(ticket),
            "attachments": ticket.attachments.all(),
            "is_owner": ticket.user_id == user.pk,
            "actions": ticket_actions(ticket, user),
            "can_reply": conversations.can_reply(ticket, user),
            "can_request_info": (
                conversations.sender_type_for(ticket, user) == "AGENT"
                and S.WAITING_USER in workflow.allowed_targets(ticket, user)
            ),
            "message_form": MessageForm(),
            "assign": assignment.assign_options(ticket, user),
            "ai_review": _ai_review(ticket, user),
            "agent_traces": _agent_traces(ticket, user),
        },
    )


def _ai_review(ticket, user):
    """CONTRACT-015: revisión humana pendiente del agente (solo Agente/Supervisor)."""
    from apps.ai.agent.runner import review_options  # import diferido: ai depende de helpdesk

    return review_options(ticket, user)


def _agent_traces(ticket, user):
    """CONTRACT-020: ejecuciones del agente ligadas al ticket (Supervisor/Administrador)."""
    if not has_role(user, Role.SUPERVISOR, Role.ADMINISTRADOR):
        return []
    return list(
        ticket.ai_decisions.filter(operation="AGENT_RUN")
        .order_by("created_at")
        .values("id", "created_at", "autonomy_level", "intent_code")
    )


def _first_error(form):
    for errors in form.errors.values():
        return errors[0]
    return "Solicitud incompleta."


@login_required
@require_POST
def ticket_message(request, code):
    """CONTRACT-011: responder en la conversación del ticket (con adjunto opcional)."""
    ticket = queries.get_visible_ticket_or_404(request.user, code)
    form = MessageForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, _first_error(form))
        return redirect(_detail_url(ticket))
    data = form.cleaned_data
    try:
        conversations.add_message(
            ticket,
            request.user,
            data["content"],
            attachment=data["attachment"],
            request_info=data["request_info"],
        )
    except workflow.TransitionForbidden:
        raise
    except workflow.TransitionError as exc:
        messages.error(request, exc.message)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, "Mensaje enviado.")
    return redirect(_detail_url(ticket))


@login_required
@require_POST
def ticket_assign(request, code):
    """CONTRACT-012: asignar o reasignar área y responsable."""
    ticket = queries.get_visible_ticket_or_404(request.user, code)
    form = AssignForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Solicitud incompleta.")
    data = form.cleaned_data
    area = Area.objects.filter(pk=data["area"]).first()
    assignee = None
    if data["assignee"]:
        assignee = get_user_model().objects.filter(pk=data["assignee"]).first()
        if assignee is None:
            return HttpResponseBadRequest("Responsable no válido.")
    try:
        ticket = TicketService.assign(
            ticket,
            actor=request.user,
            area=area,
            assignee=assignee,
            expected_version=data["version"],
        )
    except workflow.TransitionForbidden:
        raise
    except workflow.TransitionError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, f"Ticket {ticket.ticket_code} asignado.")
    return redirect(_safe_next(request) or _detail_url(ticket))


@role_required(Role.SUPERVISOR)
@require_GET
def metrics_view(request):
    """FE-009 / CONTRACT-017: métricas operativas (BE-T10). Solo Supervisor."""
    form = MetricsFilterForm(request.GET or None)
    default_from, default_to = metrics.default_period()
    data = form.cleaned_data if form.is_valid() else {}
    date_from = data.get("date_from") or default_from
    date_to = data.get("date_to") or default_to
    if date_from > date_to:  # solo una fecha indicada y fuera del periodo por defecto
        date_from, date_to = min(date_from, date_to), max(date_from, date_to)
    result = (
        metrics.compute(
            date_from,
            date_to,
            area=data.get("area"),
            category=data.get("category"),
            channel=data.get("channel") or None,
        )
        if not form.errors
        else None
    )
    return render(
        request,
        "helpdesk/metrics.html",
        {
            "form": form,
            "metrics": result,
            "period": {"date_from": date_from, "date_to": date_to},
        },
    )


NEW_TICKET_ROLES = (Role.AGENTE, Role.SUPERVISOR, Role.ADMINISTRADOR)
NEW_TICKETS_LIMIT = 5


@role_required(*NEW_TICKET_ROLES)
@require_GET
def new_tickets_feed(request):
    """CONTRACT-023: tickets nuevos de los canales con aviso (Telegram) para el pop-up.

    Sin `after` solo devuelve el último id (punto de partida, sin avisos atrasados). Solo
    tickets visibles para quien consulta y que no creó él mismo.
    """
    qs = queries.visible_tickets(request.user).filter(
        channel__in=settings.NEW_TICKET_ALERT_CHANNELS
    )
    last_id = Ticket.objects.order_by("-id").values_list("id", flat=True).first() or 0
    try:
        after = int(request.GET["after"])
    except (KeyError, ValueError):
        return JsonResponse({"last_id": last_id, "tickets": []})
    rows = (
        qs.filter(id__gt=after, id__lte=last_id)
        .exclude(user=request.user)
        .select_related("user")
        .order_by("-id")[:NEW_TICKETS_LIMIT]
    )
    tickets = [
        {
            "code": t.ticket_code,
            "subject": t.subject,
            "channel": t.get_channel_display(),
            "priority": t.get_priority_display(),
            "user": t.user.get_full_name() or t.user.username,
            "created_at": t.created_at.isoformat(),
            "url": reverse("helpdesk:ticket_detail", args=[t.ticket_code]),
        }
        for t in rows
    ]
    return JsonResponse(
        {"last_id": last_id, "tickets": tickets}, json_dumps_params={"ensure_ascii": False}
    )
