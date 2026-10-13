from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.permissions import check_owner_or_staff

from . import workflow
from .forms import TicketCreateForm, TransitionForm, category_tree
from .models import Attachment, Ticket
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
    """CONTRACT-005: descarga de un adjunto con control de permisos (SPEC §26)."""
    attachment = get_object_or_404(
        Attachment.objects.select_related("ticket"), pk=pk, ticket__ticket_code=code
    )
    check_owner_or_staff(request.user, attachment.ticket.user_id)
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
    ticket = get_object_or_404(Ticket, ticket_code=code)
    check_owner_or_staff(request.user, ticket.user_id)

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
