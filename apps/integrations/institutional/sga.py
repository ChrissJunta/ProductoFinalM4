"""SGAProvider (SPEC §41, BE-T19): adaptador HTTP al sistema académico.

**No se inventan endpoints reales** (SPEC §41): las rutas y nombres de campo de
`ROUTES`/`map_*` son un contrato *supuesto*, documentado en progress.md
(ADR-060), que se ajusta en un solo lugar cuando el SGA publique el suyo. Hasta
entonces se prueba contra `sga_mock` (servidor HTTP local).

Reglas: timeout por petición, un reintento ante 5xx/timeout, 404 → estudiante
inexistente, otro 4xx → error sin reintento, respuesta inválida → error. Todo
error sale como `ProviderError`: el agente la convierte en ticket (ADR-045).
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date as date_cls
from datetime import time as time_cls
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .base import (
    DebtItem,
    DebtSummary,
    Enrollment,
    Grade,
    InstitutionalDataProvider,
    ProviderError,
    ScheduleEntry,
    StudentNotFound,
    Subject,
)

ROUTES = {
    "schedule": "/estudiantes/{id}/horario",
    "grades": "/estudiantes/{id}/calificaciones",
    "debt": "/estudiantes/{id}/estado-cuenta",
    "enrollment": "/estudiantes/{id}/matricula",
    "subjects": "/estudiantes/{id}/asignaturas",
}
RETRY_STATUSES = range(500, 600)


class SGAProvider(InstitutionalDataProvider):
    def __init__(self, base_url, *, token="", timeout=5.0, retries=1, retry_wait=0.2):
        if not base_url:
            raise ValueError("SGA_BASE_URL vacío.")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.retries = retries
        self.retry_wait = retry_wait

    # --- Transporte ------------------------------------------------------------------------

    def _get(self, user, route, **params):
        external_id = getattr(user, "external_id", "")
        if not external_id:
            raise StudentNotFound(f"{user.username} no tiene código institucional.")
        path = ROUTES[route].format(id=urllib.parse.quote(external_id, safe=""))
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        last_error = None
        for attempt in range(1 + self.retries):
            if attempt:
                time.sleep(self.retry_wait)
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(url, headers=headers), timeout=self.timeout
                ) as response:
                    body = response.read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise StudentNotFound(f"El SGA no conoce a {external_id}.") from exc
                if exc.code in RETRY_STATUSES:
                    last_error = ProviderError(f"SGA respondió {exc.code}.")
                    continue
                raise ProviderError(f"SGA rechazó la consulta ({exc.code}).") from exc
            except (TimeoutError, urllib.error.URLError, OSError) as exc:
                last_error = ProviderError(f"SGA no disponible: {exc}")
                continue
            try:
                return json.loads(body)
            except ValueError as exc:
                raise ProviderError("Respuesta del SGA no es JSON.") from exc
        raise last_error

    # --- Contrato (SPEC §39) ----------------------------------------------------------------

    def get_schedule(self, user, date=None):
        day = date or timezone.localdate()
        data = self._get(user, "schedule", fecha=day.isoformat())
        return _mapped(lambda: [map_schedule(item, day) for item in data["clases"]])

    def get_grades(self, user, period=None):
        data = self._get(user, "grades", periodo=period)
        return _mapped(lambda: [map_grade(item, data["periodo"]) for item in data["notas"]])

    def get_debt(self, user):
        data = self._get(user, "debt")
        return _mapped(lambda: map_debt(data))

    def get_enrollment(self, user, period=None):
        data = self._get(user, "enrollment", periodo=period)
        return _mapped(
            lambda: Enrollment(
                period=data["periodo"], program=data["carrera"], status=data["estado"]
            )
        )

    def get_subjects(self, user, period=None):
        data = self._get(user, "subjects", periodo=period)
        return _mapped(
            lambda: [
                Subject(code=s["codigo"], name=s["nombre"], credits=int(s["creditos"]))
                for s in data["asignaturas"]
            ]
        )


# --- Mapping SGA → contrato (único lugar a ajustar con el contrato real) ----------------------


def _mapped(build):
    try:
        return build()
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise ProviderError(f"Respuesta del SGA con formato inesperado: {exc!r}") from exc


def map_schedule(item, day):
    return ScheduleEntry(
        day=day,
        start=time_cls.fromisoformat(item["inicio"]),
        end=time_cls.fromisoformat(item["fin"]),
        subject=item["asignatura"],
        room=item.get("aula", ""),
    )


def map_grade(item, period):
    return Grade(
        subject=item["asignatura"],
        period=period,
        value=Decimal(str(item["nota"])),
        status=item["estado"],
    )


def map_debt(data):
    items = tuple(
        DebtItem(
            concept=i["concepto"],
            amount=Decimal(str(i["valor"])),
            due_date=date_cls.fromisoformat(i["vence"]),
        )
        for i in data["rubros"]
    )
    return DebtSummary(
        total=sum((i.amount for i in items), Decimal("0")),
        currency=data.get("moneda", "USD"),
        items=items,
    )
