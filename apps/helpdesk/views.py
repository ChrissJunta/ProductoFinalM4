from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.permissions import check_owner_or_staff

from .forms import TicketCreateForm, category_tree
from .models import Attachment
from .tickets import TicketService


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
