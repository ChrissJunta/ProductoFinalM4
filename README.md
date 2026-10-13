# ProductoFinalM4 — MVP Mesa de Ayuda Omnicanal

Especificación: [`SPEC_MVP_Mesa_Ayuda_v5_2_PostgreSQL_Tareas.md`](SPEC_MVP_Mesa_Ayuda_v5_2_PostgreSQL_Tareas.md)
Coordinación entre agentes, contratos de vista y estado de tareas: [`progress.md`](progress.md)

Backend: Claude · Frontend (`templates/`, `static/`): ChatGPT.

## Requisitos

- Python 3.12+
- PostgreSQL 16

## Puesta en marcha

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # ajustar credenciales de PostgreSQL y TIME_ZONE

# crear la base de datos (una vez)
createdb -U postgres -O helpdesk helpdesk

python manage.py migrate
python manage.py seed_demo           # usuarios y tickets de ejemplo (solo desarrollo)
python manage.py runserver
```

Abrir http://127.0.0.1:8000/ e iniciar sesión.

## Cómo verificar el MVP

`seed_demo` crea un usuario por rol, todos con contraseña **`Demo-2026!`**:

| Usuario | Rol | Qué probar |
|---|---|---|
| `usuario` | Usuario | «Mis tickets» (4 tickets en distintos estados), crear solicitud con adjunto, responder, confirmar o rechazar una solución, reabrir. |
| `agente_ti` | Agente (área TI) | «Bandeja» → «Sin asignar», abrir un ticket, asignárselo, iniciar atención, pedir información, resolver con mensaje. |
| `agente_fin` | Agente (área Finanzas) | Solo ve tickets de Finanzas, los asignados a él y los sin área; un ticket de TI le da 404. |
| `supervisor` | Supervisor | Ve todos los tickets, reasigna entre áreas, «Alertas» de SLA, escalados. |
| `admin` | Administrador | `/admin/`: áreas (y sus agentes), categorías, políticas SLA, auditoría. |

Recorrido sugerido:
1. `usuario` → «Mis tickets» → «Nota incorrecta en Cálculo I» → **Confirmar solución** (queda Cerrado).
2. `usuario` → «Pago no reflejado» (esperando al usuario) → responder con un PDF → vuelve a «En proceso».
3. `usuario` → «Nueva solicitud» → crear → se abre el detalle del ticket nuevo.
4. `agente_ti` → «Bandeja» → «Sin asignar» → abrir el ticket nuevo → asignarse → «Iniciar atención» → «Resolver» con un mensaje.
5. `usuario` → abrir ese ticket → ver la resolución en la conversación → confirmar o rechazar.
6. `supervisor` → «Alertas» y «Bandeja» → «Historial».
7. `usuario` → abrir **`/assistant/`** (pantalla provisional hasta que FRONT la diseñe) y preguntar:
   «¿Cuál es mi horario de hoy?», «¿Cuáles son mis notas?», «¿Cuánto debo?» (respuesta automática con datos simulados),
   «Mi nota de Cálculo I está incorrecta» (crea ticket para Secretaría Académica) o «certificado y contraseña»
   (ambigua: ticket + alerta de revisión humana, visible para `supervisor` en «Alertas»).

El mismo agente se puede probar desde consola (muestra intención, nivel N0–N4 y recorrido):

```bash
python manage.py ask usuario "¿Cuánto debo?"
python manage.py ask usuario "¿Cuánto debo?" --channel WHATSAPP    # solo el total (minimización)
python manage.py ask --anonymous "¿Cuáles son los requisitos?"      # sin identificar: solo respuestas N1
```

Tareas periódicas (en producción, con cron; en desarrollo se pueden lanzar a mano):

```bash
python manage.py check_sla              # cada 5 min: alertas de SLA y escalamiento automático
python manage.py close_stale_tickets    # cada hora: cierre/cancelación automáticos
```

### Verificación automática en navegador (opcional)

```bash
pip install playwright && playwright install chromium   # solo para esta verificación
python manage.py seed_demo                                # sobre una base recién migrada
python manage.py runserver &
python scripts/e2e_demo.py salida_e2e/                    # 12 pasos con los 5 roles + capturas
```

## Pruebas

```bash
pytest --cov
ruff check . && ruff format --check .
```

Las pruebas usan PostgreSQL real (`config.settings.test`); CI ejecuta lo mismo en GitHub Actions.
