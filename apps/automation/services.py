"""AutomationService (SPEC §33).

`route_ticket` (BE-T09) vive aquí; `identify_intent` (BE-T13, `intents.py`) y
`determine_autonomy` (BE-T14, `autonomy.py`) se exponen como fachada y son
nodos del grafo LangGraph; `handle_message` ejecuta ese grafo (BE-T18A, §46A).
"""

from django.db.models import Q

from .models import RoutingRule


def _matches(field):
    """Q para «la regla no fija este criterio o coincide con el del ticket»."""

    def build(value_id):
        return Q(**{f"{field}__isnull": True}) | Q(**{f"{field}_id": value_id})

    return build


class AutomationService:
    @staticmethod
    def matching_rule(*, intent_id=None, category_id=None, subcategory_id=None):
        """Regla activa de menor `order` que coincide (vacío en la regla = comodín).

        Se lee de la base en cada llamada: cambiar la configuración afecta al
        siguiente ticket sin redeploy (criterio de BE-T09).
        """
        return (
            RoutingRule.objects.filter(is_active=True, area__is_active=True)
            .filter(_matches("intent")(intent_id))
            .filter(_matches("category")(category_id))
            .filter(_matches("subcategory")(subcategory_id))
            .exclude(intent__isnull=False, intent__is_active=False)
            .select_related("area")
            .order_by("order", "id")
            .first()
        )

    @staticmethod
    def route_ticket(ticket):
        """Aplica la regla que corresponda al ticket (sin guardar). Devuelve la regla o None.

        Fija área y, si la regla lo indica, prioridad. Si no hay regla, el ticket
        conserva el área por defecto de su categoría (ADR-021).
        """
        rule = AutomationService.matching_rule(
            intent_id=ticket.intent_id,
            category_id=ticket.category_id,
            subcategory_id=ticket.subcategory_id,
        )
        if rule is None:
            return None
        ticket.assigned_area = rule.area
        if rule.priority:
            ticket.priority = rule.priority
        return rule

    @staticmethod
    def identify_intent(text):
        from .intents import identify_intent

        return identify_intent(text)

    @staticmethod
    def determine_autonomy(intent, confidence, action=None):
        from .autonomy import determine_autonomy

        return determine_autonomy(intent, confidence, action)

    @staticmethod
    def handle_message(*, text, user=None, channel="WEB", is_verified=True):
        """Punto de entrada Web/WhatsApp: ejecuta el grafo del agente (SPEC §46A.7).

        Devuelve un `AgentResult` (respuesta, nivel, intención, ticket, recorrido).
        """
        # Import diferido: el agente usa TicketService, que a su vez usa este módulo.
        from apps.ai.agent.runner import run_agent

        return run_agent(text=text, user=user, channel=channel, is_verified=is_verified)
