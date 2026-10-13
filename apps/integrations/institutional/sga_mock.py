"""Servidor HTTP simulado del SGA (BE-T19). Solo pruebas y demo; nunca producción.

Sirve los datos de `local_data.json` en el formato *supuesto* del SGA
(`sga.ROUTES`), para comprobar que `SGAProvider` y `LocalProvider` cumplen el
mismo contrato. Códigos especiales para ensayar errores:

- `EST-500`: siempre 500 · `EST-FLAKY`: 503 en la primera petición y luego OK
- `EST-SLOW`: tarda más que el timeout · `EST-BADJSON`: cuerpo no JSON
- `EST-BADFORMAT`: JSON sin los campos esperados · otros códigos desconocidos: 404
"""

import json
import re
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from .base import StudentNotFound
from .local import LocalProvider

ROUTE = re.compile(r"^/estudiantes/(?P<id>[^/]+)/(?P<what>[a-z-]+)$")
SLOW_SECONDS = 2.0


def sga_payload(what, external_id, params):
    """Respuesta en formato SGA construida desde los datos locales."""
    provider = LocalProvider()
    user = SimpleNamespace(external_id=external_id, username=external_id)
    period = params.get("periodo")
    if what == "horario":
        day = date.fromisoformat(params["fecha"]) if params.get("fecha") else None
        entries = provider.get_schedule(user, date=day)
        return {"clases": [
            {"inicio": f"{e.start:%H:%M}", "fin": f"{e.end:%H:%M}", "asignatura": e.subject,
             "aula": e.room} for e in entries
        ]}  # fmt: skip
    if what == "calificaciones":
        grades = provider.get_grades(user, period=period)
        return {
            "periodo": grades[0].period if grades else (period or ""),
            "notas": [
                {"asignatura": g.subject, "nota": str(g.value), "estado": g.status} for g in grades
            ],
        }
    if what == "estado-cuenta":
        debt = provider.get_debt(user)
        return {"moneda": debt.currency, "rubros": [
            {"concepto": i.concept, "valor": str(i.amount), "vence": i.due_date.isoformat()}
            for i in debt.items
        ]}  # fmt: skip
    if what == "matricula":
        e = provider.get_enrollment(user, period=period)
        return {"periodo": e.period, "carrera": e.program, "estado": e.status}
    if what == "asignaturas":
        subjects = provider.get_subjects(user, period=period)
        return {"asignaturas": [
            {"codigo": s.code, "nombre": s.name, "creditos": s.credits} for s in subjects
        ]}  # fmt: skip
    return None


class MockSGAHandler(BaseHTTPRequestHandler):
    server_version = "MockSGA/1.0"

    def log_message(self, *args):  # silencioso en pruebas
        pass

    def _send(self, status, body=b"", content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 (nombre de BaseHTTPRequestHandler)
        self.server.hits += 1
        token = self.server.token
        if token and self.headers.get("Authorization") != f"Bearer {token}":
            return self._send(401, b'{"error": "no autorizado"}')
        url = urlparse(self.path)
        match = ROUTE.match(url.path)
        if not match:
            return self._send(404, b"{}")
        external_id = match["id"]
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        if external_id == "EST-500":
            return self._send(500, b'{"error": "interno"}')
        if external_id == "EST-FLAKY":
            self.server.flaky_calls += 1
            if self.server.flaky_calls == 1:
                return self._send(503, b"{}")
            external_id = "EST-0001"
        if external_id == "EST-SLOW":
            time.sleep(SLOW_SECONDS)
            external_id = "EST-0001"
        if external_id == "EST-BADJSON":
            return self._send(200, b"<html>mantenimiento</html>", "text/html")
        if external_id == "EST-BADFORMAT":
            return self._send(200, b'{"inesperado": true}')
        try:
            payload = sga_payload(match["what"], external_id, params)
        except StudentNotFound:
            return self._send(404, b'{"error": "estudiante no encontrado"}')
        if payload is None:
            return self._send(404, b"{}")
        return self._send(200, json.dumps(payload, ensure_ascii=False).encode())


def start(port=0, token=""):
    """Arranca el servidor en un hilo. Devuelve el servidor (`server.url`, `server.shutdown()`)."""
    server = ThreadingHTTPServer(("127.0.0.1", port), MockSGAHandler)
    server.token, server.hits, server.flaky_calls = token, 0, 0
    server.url = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
