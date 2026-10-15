from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import role_required
from apps.accounts.roles import Role
from apps.helpdesk import queries

from . import traces
from .agent.runner import REVIEW_ACTIONS, can_review, resume_agent

TRACE_ROLES = (Role.SUPERVISOR, Role.ADMINISTRADOR)
TRACES_PER_PAGE = 25

LABELS = {"accept": "aceptada", "correct": "corregida", "reject": "rechazada"}


@login_required
@require_POST
def ticket_review(request, code):
    """CONTRACT-015: decisión humana sobre la clasificación del agente (reanuda el grafo)."""
    ticket = queries.get_visible_ticket_or_404(request.user, code)
    if not can_review(request.user, ticket):
        raise PermissionDenied
    action = request.POST.get("action", "")
    if action not in REVIEW_ACTIONS:
        messages.error(request, "Acción de revisión inválida.")
        return redirect("helpdesk:ticket_detail", code=code)
    try:
        resume_agent(
            ticket, actor=request.user, action=action, intent_code=request.POST.get("intent")
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, f"Clasificación {LABELS[action]}.")
    return redirect("helpdesk:ticket_detail", code=code)


@role_required(*TRACE_ROLES)
@require_GET
def trace_list(request):
    """CONTRACT-020: ejecuciones del agente con filtros (Supervisor y Administrador)."""
    form = traces.TraceFilterForm(request.GET or None)
    data = form.cleaned_data if form.is_valid() else {}
    page = Paginator(traces.filter_runs(data), TRACES_PER_PAGE).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "ai/trace_list.html",
        {
            "form": form,
            "page_obj": page,
            "runs": [traces.row(d) for d in page.object_list],
            "querystring": query.urlencode(),
        },
    )


@role_required(*TRACE_ROLES)
@require_GET
def trace_detail(request, pk):
    """CONTRACT-020: línea de tiempo de una ejecución, nodo por nodo."""
    decision = get_object_or_404(traces.runs(), pk=pk)
    return render(request, "ai/trace_detail.html", traces.detail(decision))


@role_required(*TRACE_ROLES)
@require_GET
def trace_json(request, pk):
    """CONTRACT-020: la misma traza en JSON (descarga)."""
    decision = get_object_or_404(traces.runs(), pk=pk)
    response = JsonResponse(traces.export(decision), json_dumps_params={"ensure_ascii": False})
    response["Content-Disposition"] = f'attachment; filename="traza-{decision.pk}.json"'
    return response


POLICY_ACTIONS = {"approve": "aprobada", "reject": "rechazada", "revert": "revertida"}


@role_required(*TRACE_ROLES)
@require_GET
def policy_list(request):
    """CONTRACT-021: métricas por intención y decisiones propias del agente (ADR-077)."""
    from . import circuit, policies
    from .models import AgentPolicyDecision

    decisions = AgentPolicyDecision.objects.select_related("intent", "decided_by")
    status = request.GET.get("status", "")
    if status in AgentPolicyDecision.Status.values:
        decisions = decisions.filter(status=status)
    page = Paginator(decisions, TRACES_PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "ai/policy_list.html",
        {
            "summary": policies.summary(),
            "circuit": circuit.state(),
            "llm_stats": circuit.failure_stats(),
            "metrics": policies.intent_metrics(),
            "page_obj": page,
            "decisions": page.object_list,
            "status": status,
            "status_choices": AgentPolicyDecision.Status.choices,
            "thresholds": settings.AGENT_POLICY,
        },
    )


@role_required(*TRACE_ROLES)
@require_POST
def policy_evaluate(request):
    """CONTRACT-021: el agente revisa sus métricas ahora (lo mismo que el comando diario)."""
    from . import policies

    created = policies.evaluate()
    if created:
        messages.success(request, f"El agente tomó {len(created)} decisiones nuevas.")
    else:
        messages.info(request, "Sin decisiones nuevas: las métricas no superan los umbrales.")
    return redirect("ai:policy_list")


@role_required(*TRACE_ROLES)
@require_POST
def policy_decide(request, pk):
    """CONTRACT-021: aprobar o rechazar una propuesta, o revertir una decisión aplicada."""
    from . import policies
    from .models import AgentPolicyDecision

    decision = get_object_or_404(AgentPolicyDecision, pk=pk)
    action = request.POST.get("action", "")
    if action not in POLICY_ACTIONS:
        messages.error(request, "Acción inválida.")
        return redirect("ai:policy_list")
    try:
        getattr(policies, action)(decision, request.user, request.POST.get("note", ""))
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, f"Decisión #{decision.pk} {POLICY_ACTIONS[action]}.")
    return redirect("ai:policy_list")
