"""AutomationService (SPEC §33). BE-T09 implementa `route_ticket`.

`identify_intent`, `determine_autonomy` y `execute_intent_action` llegan con
BE-T13/BE-T14 (y como nodos del grafo LangGraph en BE-T18A, SPEC §46A).
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
