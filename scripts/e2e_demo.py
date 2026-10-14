"""Recorrido E2E del MVP en un navegador real (Chromium) — verificación manual asistida.

Requisitos (fuera de requirements, solo para esta verificación):
    pip install playwright && playwright install chromium

Uso, con la base recién preparada con una contraseña común para los usuarios demo
(python manage.py seed_demo --password <clave>) y el servidor corriendo:
    E2E_PASSWORD=<clave> python scripts/e2e_demo.py salida_e2e/

Variables opcionales: E2E_BASE_URL (por defecto http://127.0.0.1:8000) y
E2E_CHROMIUM (ruta a un Chromium ya instalado).
"""

import os
import re
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000")
PWD = os.environ["E2E_PASSWORD"]  # la de `seed_demo --password` (ADR-072)
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "salida_e2e")
OUT.mkdir(exist_ok=True)
CHROME = os.environ.get("E2E_CHROMIUM")  # None = el Chromium de Playwright
results = []


def step(name):
    results.append(name)
    print("OK ·", name, flush=True)


def login(page, username):
    page.goto(f"{BASE}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", PWD)
    page.click("button[type=submit]")
    expect(page.get_by_role("heading", level=1)).to_contain_text("Hola")


def logout(page):
    page.get_by_role("button", name="Cerrar sesión").click()
    expect(page).to_have_url(re.compile(r"/accounts/login/"))


def open_ticket(page, subject):
    page.goto(f"{BASE}/tickets/")
    row = page.locator("tr", has_text=subject)
    row.get_by_role("link").first.click()
    expect(page.get_by_role("heading", level=1)).to_have_text(subject)


def status_is(page, label):
    expect(page.locator("section").first).to_contain_text(label)


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME) if CHROME else pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("response", lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 500 else None)

    # --- Usuario -----------------------------------------------------------------------
    login(page, "usuario")
    step("Usuario inicia sesión")
    page.goto(f"{BASE}/tickets/")
    expect(page.locator("tbody tr")).to_have_count(4)
    step("Usuario ve sus 4 tickets en «Mis tickets»")

    open_ticket(page, "Nota incorrecta en Cálculo I")
    expect(page.get_by_text("Se corrigió la nota en el sistema académico.").first).to_be_visible()
    page.screenshot(path=OUT / "1_usuario_detalle_resuelto.png", full_page=True)
    page.get_by_role("button", name="Confirmar solución").click()
    expect(page.get_by_text("estado cambiado a Cerrado")).to_be_visible()
    step("Usuario ve la resolución en la conversación y confirma → Cerrado")

    open_ticket(page, "Pago no reflejado")
    status_is(page, "Esperando usuario")
    page.fill("#id_content", "Adjunto el comprobante de pago.")
    pdf = OUT / "comprobante.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% demo\n")
    page.set_input_files("#id_attachment", str(pdf))
    page.get_by_role("button", name="Enviar").click()
    expect(page.get_by_text("Mensaje enviado.")).to_be_visible()
    status_is(page, "En proceso")
    expect(page.get_by_role("link", name=re.compile("comprobante.pdf")).first).to_be_visible()
    step("Usuario responde con adjunto → el ticket vuelve a «En proceso»")

    page.goto(f"{BASE}/tickets/new/")
    page.fill("#id_subject", "Certificado de matrícula")
    page.fill("#id_description", "Necesito el certificado para una beca.")
    page.get_by_role("button", name=re.compile("Enviar|Crear")).click()
    expect(page.get_by_role("heading", level=1)).to_have_text("Certificado de matrícula")
    status_is(page, "Nuevo")
    step("Usuario crea un ticket y llega a su detalle")
    logout(page)

    # --- Agente TI ---------------------------------------------------------------------
    login(page, "agente_ti")
    page.goto(f"{BASE}/agent/inbox/?tab=unassigned")
    expect(page.locator("tbody tr", has_text="Certificado de matrícula")).to_have_count(1)
    page.screenshot(path=OUT / "2_agente_bandeja.png", full_page=True)
    step("Agente ve el ticket nuevo en «Sin asignar» (triaje)")

    open_ticket(page, "Certificado de matrícula")
    page.select_option("#assign-area", label="Soporte Tecnológico")
    page.select_option("#assign-user", label="Tomás Soporte TI")
    page.get_by_role("button", name="Asignar").click()
    expect(page.get_by_role("status")).to_contain_text("asignado.")
    status_is(page, "Asignado")
    step("Agente se asigna el ticket → Asignado")

    page.get_by_role("button", name="Iniciar / retomar atención").click()
    status_is(page, "En proceso")
    form = page.locator("form", has=page.get_by_role("button", name="Resolver"))
    form.locator("textarea").fill("Certificado emitido y enviado a su correo.")
    form.get_by_role("button", name="Resolver").click()
    status_is(page, "Resuelto")
    page.screenshot(path=OUT / "3_agente_resuelto.png", full_page=True)
    step("Agente atiende y resuelve con mensaje → Resuelto")
    logout(page)

    # --- Supervisor --------------------------------------------------------------------
    login(page, "supervisor")
    page.goto(f"{BASE}/alerts/")
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    page.goto(f"{BASE}/agent/inbox/?tab=history")
    expect(page.locator("tbody tr").first).to_be_visible()
    step("Supervisor accede a alertas y al historial de la bandeja")
    logout(page)

    # --- Usuario: aislamiento ----------------------------------------------------------
    login(page, "agente_fin")
    response = page.goto(f"{BASE}/tickets/HD-2026-000002/")
    assert response.status == 404, response.status
    step("Agente de Finanzas no puede ver un ticket de TI (404)")
    page.goto(f"{BASE}/")
    logout(page)

    # --- Administrador -----------------------------------------------------------------
    login(page, "admin")
    page.goto(f"{BASE}/admin/")
    expect(page.get_by_text("Helpdesk")).to_be_visible()
    step("Administrador entra al admin de Django")

    # --- Móvil -------------------------------------------------------------------------
    mobile = browser.new_page(viewport={"width": 360, "height": 800})
    mobile.goto(f"{BASE}/accounts/login/")
    mobile.fill("#id_username", "usuario")
    mobile.fill("#id_password", PWD)
    mobile.click("button[type=submit]")
    mobile.goto(f"{BASE}/tickets/")
    overflow = mobile.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    assert not overflow, "desbordamiento horizontal en móvil"
    mobile.screenshot(path=OUT / "4_usuario_movil.png", full_page=True)
    step("Listado usable a 360 px sin desbordamiento horizontal")

    assert not errors, errors
    browser.close()

print(f"\nE2E PASS: {len(results)} pasos, sin errores 5xx")
