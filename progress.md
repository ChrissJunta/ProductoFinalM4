# progress.md — MVP Mesa de Ayuda Omnicanal

## Propósito

Este archivo es la **fuente de coordinación operativa entre agentes de desarrollo**.

Debe evitar:

- repetir tareas ya terminadas;
- sobrescribir trabajo de otro agente;
- crear módulos duplicados;
- volver a tomar decisiones ya cerradas;
- perder contexto entre sesiones;
- romper contratos FRONT/BACK ya acordados.

---

# 1. Regla obligatoria para todos los agentes

Antes de escribir código:

1. Leer `SPEC_MVP_Mesa_Ayuda_v5_2_PostgreSQL_Tareas.md`.
2. Leer este `progress.md`.
3. Verificar el estado de la tarea.
4. Revisar dependencias.
5. Revisar archivos previamente modificados.
6. No repetir tareas marcadas como `DONE`.
7. No tomar tareas `IN_PROGRESS` sin coordinación explícita.
8. No cambiar arquitectura, modelos o contratos sin registrarlo primero aquí.

Después de trabajar:

1. actualizar estado;
2. registrar archivos modificados;
3. registrar migraciones;
4. registrar endpoints;
5. registrar pruebas;
6. registrar decisiones;
7. registrar pendientes o bloqueos.

---

# 2. Estados

```text
TODO        = no iniciada
IN_PROGRESS = en ejecución
BLOCKED     = bloqueada por dependencia o decisión
REVIEW      = implementada, pendiente de revisión/pruebas
DONE        = terminada y validada
CANCELLED   = descartada por cambio aprobado
```

---

# 3. Estado global

```text
SPEC_VERSION: 5.2
DATABASE: PostgreSQL 16
FRAMEWORK: Django 5.2 LTS (Python 3.12+)
ARCHITECTURE: Django monolith modular
FRONT: Django Templates + Bootstrap
BACK_APPS: accounts, helpdesk, automation, integrations, ai
SGA_MODE: LocalProvider para MVP
AI_MODE: asistivo
LLM_PROVIDER: abierto (ADR-010); FakeLLMProvider por defecto
AGENT: LangGraph 1.x embebido en apps/ai/agent/ (ADR-016)
```

## 3.1 Reparto de trabajo entre agentes (ADR-013)

| Ámbito | Agente | Archivos que le pertenecen |
|---|---|---|
| BACKEND | Claude | `config/`, `apps/`, `conftest.py`, `requirements*.txt`, `pyproject.toml`, `.github/`, migraciones, pruebas |
| FRONTEND | ChatGPT | `templates/`, `static/` |

Reglas:

1. El backend **no** diseña plantillas. Solo puede dejar una plantilla mínima marcada `TEMPORAL (backend)` cuando una prueba necesite renderizar la vista; el frontend la reemplaza.
2. Cada vista backend se publica con su **url name**, plantilla esperada y **contrato de contexto** en la sección 12 (`CONTRACT-XXX`). El frontend consume solo lo que figura en el contrato.
3. Si el frontend necesita un dato nuevo en el contexto, lo solicita como CHANGE REQUEST en la sección 12; no lo calcula en la plantilla.
4. Los contextos solo exponen datos ya autorizados por backend: la plantilla nunca decide permisos, estados, SLA ni prioridad.

---

# 4. Tareas FRONT

| ID | Estado | Responsable/Agente | Dependencia | Última actualización |
|---|---|---|---|---|
| FE-T01 | REVIEW (implementada y validada en Cloud; pendiente de revisión) | ChatGPT | BE-T01 | 2026-10-12 |
| FE-T02 | TODO | - | BE-T03, BE-T04 | - |
| FE-T03 | TODO (desbloqueada: CONTRACT-004/005) | ChatGPT | BE-T03, BE-T03A | 2026-10-13 |
| FE-T04 | TODO | - | BE-T04 | - |
| FE-T05 | TODO | - | BE-T05, BE-T07 | - |
| FE-T06 | TODO | - | BE-T04, BE-T06 | - |
| FE-T07 | TODO | - | BE-T07 | - |
| FE-T08 | TODO | - | BE-T08 | - |
| FE-T09 | TODO | - | BE-T03A, BE-T09 | - |
| FE-T10 | TODO | - | BE-T10 | - |
| FE-T11 | TODO | - | BE-T11A | - |

---

# 5. Tareas BACK

| ID | Estado | Responsable/Agente | Dependencia | Última actualización |
|---|---|---|---|---|
| BE-T01 | REVIEW (incluye BE-T02; pendiente de revisión del PR) | Claude | - | 2026-10-12 |
| BE-T02 | CANCELLED (fusionada en BE-T01, v5.2) | - | - | 2026-10-12 |
| BE-T03A | REVIEW (pendiente de revisión del PR) | Claude | BE-T01 | 2026-10-12 |
| BE-T03 | REVIEW (pendiente de revisión del PR) | Claude | BE-T01, BE-T03A | 2026-10-13 |
| BE-T04 | TODO | - | BE-T03 | - |
| BE-T05 | TODO | - | BE-T03 | - |
| BE-T06 | TODO | - | BE-T03 | - |
| BE-T07 | TODO | - | BE-T03 | - |
| BE-T08 | TODO | - | BE-T03, BE-T07 | - |
| BE-T09 | TODO | - | BE-T03 | - |
| BE-T10 | TODO | - | BE-T03, BE-T08 | - |
| BE-T11 | TODO | - | BE-T05 | - |
| BE-T11A | TODO | - | BE-T01, BE-T11 | - |
| BE-T12 | TODO | - | BE-T11 | - |
| BE-T13 | TODO | - | BE-T09 | - |
| BE-T14 | TODO | - | BE-T13, BE-T11A | - |
| BE-T15 | TODO | - | BE-T14 | - |
| BE-T16 | TODO | - | - | - |
| BE-T17 | TODO | - | BE-T16 | - |
| BE-T18 | TODO | - | BE-T16, BE-T17 | - |
| BE-T18A | TODO | - | BE-T13..BE-T18 | 2026-10-12 |
| BE-T19 | TODO | - | BE-T15 | - |
| BE-T20 | TODO | - | BE-T01..BE-T19, BE-T18A | - |

Notas v5.2:

- BE-T03A (catálogos `Area`/`Category`/`Subcategory` + `AuditLog`) es nueva: BE-T03 la necesita para FK y auditoría.
- BE-T08 depende también de BE-T03 porque `sla_due_at` se fija al crear el ticket.
- El dataset etiquetado de IA se adelanta a BE-T17 (antes en BE-T20).
- BE-T18A (grafo agéntico LangGraph) orquesta BE-T13/BE-T14/BE-T15/BE-T17/BE-T18; los motores se implementan como funciones reutilizables que luego son nodos del grafo.
- BE-T11A (vinculación WhatsApp) bloquea a BE-T14: sin ella no se pueden entregar datos sensibles por WhatsApp.

---

# 6. Plantilla de inicio de tarea

Copiar esta sección al iniciar una tarea:

```md
## [ID] — [Nombre]

**Estado:** IN_PROGRESS
**Agente:** 
**Fecha inicio:** 
**Dependencias verificadas:** 
**Archivos previstos:** 

### Objetivo
...

### No tocar
- ...

### Contratos a respetar
- ...

### Notas
...
```

---

# 7. Plantilla de cierre de tarea

```md
## [ID] — Cierre

**Estado:** DONE
**Fecha fin:** 

### Implementado
- ...

### Archivos creados/modificados
- ...

### Migraciones
- ...

### Endpoints afectados
- ...

### Pruebas ejecutadas
- ...

### Resultado
- ...

### Decisiones tomadas
- ...

### Pendientes derivados
- Ninguno / ...
```

---

# 8. Registro de decisiones

Toda decisión técnica relevante debe añadirse aquí.

| ID | Fecha | Decisión | Motivo | Impacto |
|---|---|---|---|---|
| ADR-001 | Inicial | PostgreSQL como BD | Decisión de SPEC v5 | Persistencia |
| ADR-002 | Inicial | 5 apps Django | Evitar sobrearquitectura | Estructura |
| ADR-003 | Inicial | Sin Redis/Celery en MVP | Reducir infraestructura | Integraciones |
| ADR-004 | Inicial | LocalProvider antes de SGA real | Desacoplar MVP | Integración |
| ADR-005 | Inicial | LLM no ejecuta negocio | Seguridad y gobernanza | IA |
| ADR-006 | 2026-10-12 | BE-T02 fusionada en BE-T01 | `AUTH_USER_MODEL` debe existir antes de la primera migración | Backlog |
| ADR-007 | 2026-10-12 | Sin API REST de tickets ni DRF; contrato FRONT/BACK = vistas Django | Front server-rendered; regla 56.6 (sin endpoints sin consumidor) | API |
| ADR-008 | 2026-10-12 | WhatsApp exige teléfono verificado con código desde portal | Proteger notas/deuda | WhatsApp, `User.phone_verified_at` |
| ADR-009 | 2026-10-12 | Meta WhatsApp Cloud API | Proveedor oficial; firma `X-Hub-Signature-256` | Integraciones |
| ADR-010 | 2026-10-12 | Proveedor LLM: **ABIERTO** | Falta comparar costo, latencia, JSON estructurado y privacidad | IA (FakeLLMProvider hasta decidir) |
| ADR-011 | 2026-10-12 | PostgreSQL también en pruebas/CI (sin SQLite) | `SKIP LOCKED`, secuencias, índices parciales; paridad dev/CI/prod | Persistencia, CI |
| ADR-012 | 2026-10-12 | Django 5.2 LTS + psycopg 3 + django-environ | Soporte extendido; configuración por entorno | Stack |
| ADR-013 | 2026-10-12 | Claude = BACKEND, ChatGPT = FRONTEND (`templates/`, `static/`) | Trabajo paralelo sin pisarse | Ver sección 3.1 y contratos de vista |
| ADR-014 | 2026-10-12 | Login con usuario **o** correo; correo ambiguo (compartido) se rechaza | FE-001 “usuario/correo” | `UsernameOrEmailBackend` |
| ADR-016 | 2026-10-12 | Orquestación agéntica con LangGraph (`langgraph` + `langgraph-checkpoint-postgres`) | Sin orquestación el sistema no es agéntico; LangGraph da grafo explícito, memoria, `interrupt` humano y control de herramientas | SPEC §46A; sustituye la prohibición genérica “agents” por reglas de agente controlado; BE-T18A |
| ADR-017 | 2026-10-12 | Catálogos sin borrado físico (`on_delete=PROTECT`, admin sin delete); solo activar/desactivar | Trazabilidad e integridad referencial con tickets | `helpdesk.catalogs` |
| ADR-018 | 2026-10-12 | Toda escritura de catálogo pasa por `helpdesk.catalogs` (`save_catalog_item`, `set_active`) y audita solo los campos cambiados | Un único punto auditado para admin y para FE-T09 | `helpdesk` |
| ADR-019 | 2026-10-12 | `AuditLog` inmutable (sin edición ni borrado desde ORM de instancia ni admin) | Valor probatorio de la auditoría | `helpdesk.AuditLog` |
| ADR-020 | 2026-10-13 | `ticket_code` = `HD-AAAA-NNNNNN` con una secuencia PostgreSQL global (`helpdesk_ticket_code_seq`); el número no se reinicia cada año | `nextval` es atómico: sin duplicados bajo concurrencia y sin tabla de contadores con bloqueo | `helpdesk.tickets.next_ticket_code` |
| ADR-021 | 2026-10-13 | Al crear, `assigned_area` = área por defecto de la categoría; estado `NEW`, prioridad `MEDIUM` | Enrutamiento mínimo hasta BE-T09 (RoutingRule) | `TicketService.create` |
| ADR-022 | 2026-10-13 | Tipo de adjunto por firma del contenido (magic bytes) + extensión; se ignora el tipo MIME declarado por el navegador; nombre en disco aleatorio | Evitar archivos disfrazados y rutas con datos del usuario | `helpdesk.attachments` |
| ADR-015 | 2026-10-12 | Usuario autenticado sin grupo = rol `Usuario`; superusuario = `Administrador` | Mínimo privilegio | `accounts.roles.get_role` |

---

# 9. Contratos congelados actuales

## Apps Django

```text
accounts
helpdesk
automation
integrations
ai
```

No crear otras sin actualización aprobada de SPEC.

## InstitutionalDataProvider

```python
get_schedule(user, date=None)
get_grades(user, period=None)
get_debt(user)
get_enrollment(user, period=None)
get_subjects(user, period=None)
```

## LLMProvider

```python
classify(text, context=None)
extract(text, schema)
summarize(messages)
generate_response(context)
```

## Agente LangGraph (SPEC §46A)

```text
Ubicación: apps/ai/agent/ (state.py, nodes.py, tools.py, graph.py, runner.py)
Entrada:   run_agent(message) / resume_agent(thread_id, decision)
thread_id: Conversation.id
Escritura: create_ticket y route_ticket SOLO desde nodos determinísticos
Cambios:   modificar el grafo exige CHANGE REQUEST + GRAPH_VERSION + pruebas + docs/agent_graph.md
```

## Roles (Groups, creados por migración `accounts/0002`)

```text
Usuario
Agente
Supervisor
Administrador
```

## Estados

```text
NEW
CLASSIFIED
ASSIGNED
IN_PROGRESS
WAITING_USER
RESOLVED
CLOSED
ESCALATED
REOPENED
CANCELLED
```

---

# 10. Archivos o módulos prohibidos salvo cambio de SPEC

```text
apps/catalogs
apps/routing
apps/rules
apps/sla
apps/notifications
apps/audit
apps/conversations
apps/agents            (el agente vive en apps/ai/agent/)

microservices/
kafka/
rabbitmq/
redis/
celery/
graphql/
websockets/
rag/
agents/
mcp/
kubernetes/
```

---

# 11. Bloqueos activos

Actualmente:

```text
NINGUNO
```

Cuando exista uno:

```md
### BLOCK-001
**Tarea:** BE-TXX
**Problema:** ...
**Necesita:** ...
**Impacto:** ...
**Estado:** OPEN
```

---

# 12. Cambios de contrato

Registrar aquí cualquier cambio FRONT/BACK antes de implementarlo.

## 12.1 Contratos de vista publicados por BACKEND

Convenciones para todas las vistas:

- Todos los formularios POST incluyen `{% csrf_token %}`.
- El texto de error se muestra tal como lo entrega el backend o con los mensajes genéricos de SPEC §19; nunca detalles internos.
- Variables globales disponibles en **todas** las plantillas (context processors):
  - `user` — usuario actual (`AnonymousUser` si no hay sesión). Campos utilizables: `username`, `email`, `first_name`, `last_name`, `get_full_name`, `is_authenticated`.
  - `user_role` — `str | None`: `"Usuario"`, `"Agente"`, `"Supervisor"`, `"Administrador"` o `None` si no hay sesión. Usar solo para **mostrar** navegación por rol (SPEC §10); el backend vuelve a validar permisos.
  - `messages` — mensajes flash de Django (`message.tags`: `debug`, `info`, `success`, `warning`, `error`).
  - `request`.

### CONTRACT-001 — Login
**Fecha:** 2026-10-12
**Origen:** BACK (BE-T01) → consumidor FE-T01
**URL name:** `accounts:login` → `/accounts/login/`
**Plantilla:** `auth/login.html` (hoy existe una versión `TEMPORAL (backend)` que FRONT debe reemplazar)
**Métodos:** GET (muestra formulario), POST (autentica)
**Contexto:**

| Variable | Tipo | Descripción |
|---|---|---|
| `form` | `AuthenticationForm` | Campos `form.username` (usuario **o** correo) y `form.password`. Errores en `form.non_field_errors` (un único mensaje genérico; no distingue usuario inexistente, contraseña incorrecta o cuenta inactiva). |
| `next` | `str` | Destino tras login (puede ser vacío). Reenviar como `<input type="hidden" name="next">`. |
| `site`, `site_name` | — | Provistos por Django; no requeridos. |

**POST esperado:** `username`, `password`, `next` (opcional), `csrfmiddlewaretoken`.
**Respuestas:** éxito → 302 a `next` si es del mismo sitio, si no a `accounts:role_redirect`. Error → 200 con `form` con errores. Usuario ya autenticado que hace GET → 302 a `accounts:role_redirect`.
**Aprobado:** Sí

### CONTRACT-002 — Inicio (temporal por rol)
**Fecha:** 2026-10-12
**Origen:** BACK (BE-T01) → consumidor FE-T01 / FE-T02
**URL name:** `accounts:home` → `/inicio/`
**Plantilla:** `home.html` (versión `TEMPORAL (backend)`)
**Métodos:** GET. Requiere sesión (sin sesión → 302 a login).
**Contexto:** solo variables globales (`user`, `user_role`, `messages`).
**Nota:** es la pantalla de aterrizaje provisional de todos los roles. Cuando existan FE-T02/FE-T06/FE-T08/FE-T09, backend cambiará `ROLE_HOME_URLS` (CHANGE REQUEST) para apuntar a cada panel.
**Aprobado:** Sí

### CONTRACT-003 — Redirección por rol y logout
**Fecha:** 2026-10-12
**Origen:** BACK (BE-T01) → consumidor FE-T01
**`accounts:role_redirect`** → `/` · GET · sin plantilla. Requiere sesión. Responde 302 a la pantalla de inicio del rol (`apps/accounts/views.py::ROLE_HOME_URLS`). Usar como destino del logo/“Inicio” en la navegación.
**`accounts:logout`** → `/accounts/logout/` · **solo POST** (GET devuelve 405) · sin plantilla. Debe enviarse desde un `<form method="post">` con `{% csrf_token %}`. Responde 302 a `accounts:login`.
**Aprobado:** Sí

### CONTRACT-004 — Crear ticket (FE-003)
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T03) → consumidor FE-T03
**URL name:** `helpdesk:ticket_create` → `/tickets/new/`
**Plantilla:** `helpdesk/ticket_form.html` (hoy existe una versión `TEMPORAL (backend)` que FRONT debe reemplazar)
**Métodos:** GET (formulario vacío), POST (crear). Requiere sesión (sin sesión → 302 a login). Cualquier rol puede crear; el ticket siempre queda a nombre del usuario en sesión.
**Contexto:**

| Variable | Tipo | Descripción |
|---|---|---|
| `form` | `TicketCreateForm` | Campos en este orden: `subject` (texto, máx. 200, obligatorio), `description` (texto largo, máx. 5000, obligatorio), `category` (select, opcional, solo activas), `subcategory` (select, opcional, solo activas), `attachment` (archivo, opcional). Errores por campo en `form.<campo>.errors`; generales en `form.non_field_errors`. |
| `category_tree` | `list[dict]` | `[{"id": int, "name": str, "subcategories": [{"id": int, "name": str}]}]`, solo elementos activos. Para filtrar en el cliente las subcategorías según la categoría elegida (JS mínimo, opcional). |

**POST esperado:** `multipart/form-data` con `subject`, `description`, `category` (id, opcional), `subcategory` (id, opcional), `attachment` (opcional), `csrfmiddlewaretoken`. Cualquier otro campo (estado, prioridad, código, área…) se ignora.
**Adjunto:** PDF, PNG o JPG/JPEG, máximo 5 MB. El backend valida extensión, tamaño y contenido real; la validación del cliente (atributo `accept=".pdf,.png,.jpg,.jpeg"`) es solo de ayuda.
**Respuestas:**
- éxito → 302 a `accounts:role_redirect` con mensaje flash `success`: `"Solicitud HD-AAAA-NNNNNN creada."` (cuando exista el detalle de ticket, BACK cambiará el destino mediante CHANGE REQUEST);
- error de validación → 200 con `form` con errores (no se crea nada).

**Aprobado:** Sí

### CONTRACT-005 — Descargar adjunto
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T03) → consumidor FE-T05 (detalle de ticket)
**URL name:** `helpdesk:attachment_download` → `/tickets/<ticket_code>/attachments/<id>/`
**Uso en plantilla:** `{% url 'helpdesk:attachment_download' ticket.ticket_code attachment.id %}`
**Métodos:** GET · sin plantilla · requiere sesión.
**Respuestas:** 200 con el archivo (`Content-Disposition: attachment`, nombre original); 403 si el usuario no es el dueño del ticket ni un rol de atención; 404 si el adjunto no pertenece a ese ticket o el archivo no existe.
**Datos del adjunto disponibles** (cuando se publique el contrato de detalle): `original_name`, `content_type`, `size_bytes`, `created_at`.
**Aprobado:** Sí

## 12.2 Solicitudes de cambio

### CHANGE REQUEST CR-001 — Agente LangGraph
**Fecha:** 2026-10-12
**Origen:** Solicitud del responsable del proyecto
**Cambio:** la IA pasa de llamadas sueltas a un agente orquestado con LangGraph (SPEC §46A). Se levanta la prohibición genérica de “agents” (SPEC §4, §55) y se reemplaza por reglas de agente controlado.
**Impacto:** nueva tarea BE-T18A; `AIDecision` añade `graph_version`, `node_path`, `thread_id`; nuevas dependencias `langgraph`, `langgraph-checkpoint-postgres` (se añadirán a `requirements.txt` al iniciar BE-T18A, no antes).
**Consumidores afectados:** FRONT sin cambios hasta FE-T06 (la bandeja mostrará los casos pausados en `human_review`; su contrato se publicará con BE-T18A).
**Aprobado:** Sí

### CHANGE REQUEST CR-002 — `Ticket.intent` se añade en BE-T09
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T03)
**Cambio:** BE-T03 debía incluir `Ticket.intent` (FK a `automation.Intent`), pero ese modelo nace en BE-T09. Crear ahora un `Intent` vacío solo para la FK violaría la regla 57 (no adelantar piezas sin requisito). El campo, nullable, se añadirá con su migración en BE-T09.
**Impacto:** ninguno para FRONT (FE-003 no muestra la intención). BE-T09 debe incluir la migración `helpdesk` que añade `Ticket.intent`.
**Aprobado:** Sí (decisión técnica del agente BACKEND; revisable en el PR)

Plantilla:

```md
### CONTRACT-001
**Fecha:** 
**Origen:** FRONT/BACK
**Contrato actual:** 
**Cambio propuesto:** 
**Consumidores afectados:** 
**Aprobado:** Sí/No
```

---

# 13. Migraciones aplicadas

- `accounts/migrations/0001_initial.py` — modelo `User` (AbstractUser + `phone`, `phone_verified_at`, `external_id`, `source`; únicos parciales en `phone` y `external_id`) — aplicada y reversible — BE-T01
- `accounts/migrations/0002_create_role_groups.py` — migración de datos: Groups `Usuario`, `Agente`, `Supervisor`, `Administrador` — aplicada y reversible — BE-T01
- `helpdesk/migrations/0001_initial.py` — `Area`, `Category`, `Subcategory`, `AuditLog` — aplicada y reversible — BE-T03A
- `helpdesk/migrations/0002_initial_catalogs.py` — 4 áreas, 4 categorías, 12 subcategorías (auditadas como SYSTEM) — aplicada y reversible — BE-T03A
- `helpdesk/migrations/0003_role_permissions.py` — permisos de modelo por rol para catálogos y auditoría — aplicada y reversible — BE-T03A
- `helpdesk/migrations/0004_tickets.py` — secuencia `helpdesk_ticket_code_seq`, `Ticket`, `Attachment` e índices — aplicada y reversible — BE-T03

Formato:

```md
- accounts/migrations/0001_initial.py — aplicada
- helpdesk/migrations/0001_initial.py — aplicada
```

---

# 14. Endpoints implementados

Rutas web (vistas Django, ADR-007):

- `GET|POST /accounts/login/` — `accounts:login` — REVIEW — BE-T01 — CONTRACT-001
- `POST /accounts/logout/` — `accounts:logout` — REVIEW — BE-T01 — CONTRACT-003
- `GET /` — `accounts:role_redirect` — REVIEW — BE-T01 — CONTRACT-003
- `GET /inicio/` — `accounts:home` — REVIEW — BE-T01 — CONTRACT-002
- `/admin/` — Django admin (gestión de usuarios y grupos) — REVIEW — BE-T01

- `/admin/helpdesk/{area,category,subcategory}/` — catálogos (alta, edición, activar/desactivar; sin borrado) — REVIEW — BE-T03A
- `/admin/helpdesk/auditlog/` — auditoría, solo lectura — REVIEW — BE-T03A
- `GET|POST /tickets/new/` — `helpdesk:ticket_create` — REVIEW — BE-T03 — CONTRACT-004
- `GET /tickets/<code>/attachments/<id>/` — `helpdesk:attachment_download` — REVIEW — BE-T03 — CONTRACT-005
- `/admin/helpdesk/{ticket,attachment}/` — solo lectura — REVIEW — BE-T03

API: ninguna todavía (el webhook WhatsApp llegará con BE-T11).

Formato:

```md
- POST /api/tickets/ — DONE — BE-T03
- GET /api/tickets/ — DONE — BE-T04
```

---

# 15. Pruebas ejecutadas

### TEST-RUN-001
**Fecha:** 2026-10-12
**Tarea:** BE-T01
**Comando:** `ruff check . && ruff format --check . && python manage.py check && python manage.py makemigrations --check --dry-run && pytest --cov --cov-fail-under=80`
**Entorno:** PostgreSQL 16 local, `config.settings.test`, sin `.env` (igual que CI)
**Resultado:** PASS — 72 pruebas, cobertura 99 %
**Fallos:** ninguno

### TEST-RUN-002
**Fecha:** 2026-10-12
**Tarea:** BE-T03A
**Comando:** mismo que TEST-RUN-001
**Entorno:** PostgreSQL 16 local, `config.settings.test`, sin `.env` (igual que CI)
**Resultado:** PASS — 111 pruebas, cobertura 99 %
**Fallos:** el primer intento falló por orden de pruebas (una prueba transaccional vaciaba los datos sembrados por migraciones); corregido con `serialized_rollback=True` en las pruebas de reversibilidad de migraciones.

### TEST-RUN-003
**Fecha:** 2026-10-13
**Tarea:** BE-T03
**Comando:** mismo que TEST-RUN-001 (ejecutado dos veces, más las pruebas transaccionales en orden inverso)
**Entorno:** PostgreSQL 16 local, `config.settings.test`, sin `.env` (igual que CI)
**Resultado:** PASS — 160 pruebas, cobertura 98,6 %. Incluye 12 hilos creando tickets a la vez sin códigos duplicados.
**Fallos:** ninguno

Formato:

```md
### TEST-RUN-001
**Fecha:** 
**Tarea:** 
**Comando:** 
**Resultado:** PASS/FAIL
**Fallos:** 
```

---

# 16. Historial de trabajo

Añadir siempre al final, sin borrar entradas anteriores.

```md
## YYYY-MM-DD HH:MM — Agente / Tarea

- Estado anterior:
- Estado nuevo:
- Trabajo realizado:
- Archivos:
- Pruebas:
- Observaciones:
```

## 2026-10-12 — Claude (BACKEND) / SPEC v5.2 + BE-T01

- Estado anterior: SPEC 5.1; BE-T01 y BE-T02 en TODO.
- Estado nuevo: SPEC 5.2; BE-T01 en REVIEW; BE-T02 CANCELLED (fusionada).
- Trabajo realizado: corrección de 17 problemas de la SPEC (ver SPEC §0.1); backlog ajustado; esqueleto Django, usuario, roles, login/logout, CI. Reparto FRONT/BACK acordado (ADR-013) y contratos de vista CONTRACT-001..003 publicados.
- Archivos: ver cierre de BE-T01 (sección 20).
- Pruebas: TEST-RUN-001 PASS.
- Observaciones: FE-T01 queda desbloqueada para el agente FRONTEND.
- Actualización: CR-001 / ADR-016 — SPEC §46A incorpora el agente LangGraph; nueva tarea BE-T18A.

---

## 2026-10-12 21:40 — ChatGPT (FRONTEND) / FE-T01 — America/Guayaquil

- Estado anterior: IN_PROGRESS local, sin código ni commit.
- Estado nuevo: REVIEW.
- Trabajo realizado: login responsive, base común, navegación, mensajes flash y errores accesibles; Bootstrap 5.3.8 local con licencia. Se preservó el inicio local y se actualizó la base a `d91333f` sin editar BACK.
- Archivos: `templates/base.html`, `templates/auth/login.html`, `templates/home.html`, `templates/components/{navbar,messages,field_errors}.html`, `static/css/mesa.css`, `static/vendor/bootstrap/{bootstrap.min.css,LICENSE}` y registros FRONT de `progress.md`.
- Pruebas: suite completa `pytest --cov --cov-report=term-missing --cov-fail-under=80`: 160 PASS, cobertura 98.61 %; ruff check/format PASS. Chromium real: login por correo, error genérico, autoescape, contraseña no repoblada, CSRF, logout POST, teclado y anchos 360/768/1280 PASS. Helpers de validación fuera del checkout.
- Observaciones: la ejecución inicial limitada a accounts pasó 72 pruebas pero no alcanzó el umbral global (77.22 %, helpdesk no ejecutado); suite completa resuelve la selección y supera 80 %. El helper de navegador necesitó cerrar conexiones del servidor antes de eliminar la BD temporal; corregido y revalidado con salida 0. No cambios en pruebas BACK.
- Coordinación: CONTRACT-001/002/003 aprobados habilitan FRONT aunque BE-T01 siga REVIEW. No se cambia estado BACK ni se considera aprobado/merged PR #1. Un PR FE-T01 contra `main-r0dfx3`, sin merge automático. Los componentes de §18 sin consumidor habilitado (paginación, SLA, conversación) se implementarán con sus tareas/contratos.
- Publicación: entorno publicado confirmado por UI del usuario; implementación corre enteramente en Cloud. Git push dry-run autorizado; creación de PR bloqueada por CONNECT 403 a `api.github.com`. Dominio añadido al borrador de red para revisión/aplicación. No hay scheduler Cloud expuesto: seguimiento cada 10 min aún sin configurar.

---

# 17. Regla anti-repetición

Antes de implementar cualquier funcionalidad, buscar en este archivo:

1. ID de tarea;
2. nombre de modelo;
3. endpoint;
4. archivo;
5. decisión ADR;
6. contrato.

Si ya aparece como `DONE`, el agente **NO debe regenerarlo**.

Si necesita modificarlo, debe registrar:

```text
CHANGE REQUEST
```

y explicar qué cambia y por qué.

---

# 18. Regla anti-sobrearquitectura

Si una nueva pieza no está en la SPEC:

```text
NO IMPLEMENTAR
```

hasta que exista una decisión explícita.

Si la funcionalidad puede vivir dentro de una de las cinco apps actuales:

```text
NO CREAR NUEVA APP
```

---

# 19. Estado inicial del proyecto

```text
SPEC aprobada: Sí
SPEC versión: 5.2
Front backlog definido: Sí
Back backlog definido: Sí
Código implementado: BE-T01 (incluye BE-T02), BE-T03A y BE-T03 en REVIEW
Migraciones: accounts 0001, 0002; helpdesk 0001-0004
Endpoints: login, logout, role_redirect, home, ticket_create, attachment_download (vistas web); admin de catálogos, auditoría y tickets
Pruebas: TEST-RUN-001, TEST-RUN-002, TEST-RUN-003 PASS
Bloqueos: Ninguno
```

---

# 20. Registro de tareas

## BE-T01 — Proyecto base, usuario, autenticación y roles (incluye BE-T02) — Cierre

**Estado:** REVIEW (pasa a DONE cuando el PR se apruebe y CI esté en verde)
**Agente:** Claude (BACKEND)
**Fecha:** 2026-10-12

### Implementado
- Proyecto Django 5.2 con `config/settings/{base,dev,test}.py`; secretos y BD por variables de entorno (`.env.example`).
- Cinco apps registradas (`accounts`, `helpdesk`, `automation`, `integrations`, `ai`); solo `accounts` tiene contenido.
- `accounts.User(AbstractUser)` con `phone` (E.164), `phone_verified_at`, `external_id`, `source` (`LOCAL`/`SGA`/`WHATSAPP`); unicidad parcial de `phone` y `external_id`.
- Groups de rol por migración de datos reversible.
- `accounts.roles`: `Role`, `get_role`, `has_role` (prioridad Administrador > Supervisor > Agente > Usuario).
- `accounts.permissions`: control vertical `role_required` / `RoleRequiredMixin`; control horizontal `check_owner_or_staff`.
- `UsernameOrEmailBackend`: login con usuario o correo, error genérico, tiempo de respuesta igualado.
- Vistas `login`, `logout` (solo POST), `role_redirect`, `home`; context processor `user_role`.
- Admin de usuarios con campos institucionales.
- Cookies `HttpOnly`, `Secure` fuera de DEBUG, `X-Frame-Options: DENY`.
- CI GitHub Actions: ruff, `check`, `makemigrations --check`, pytest con PostgreSQL 16 y cobertura ≥ 80 %.

### Archivos creados/modificados
- `manage.py`, `config/**`, `apps/**`, `conftest.py`
- `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `.env.example`, `.gitignore`
- `.github/workflows/ci.yml`
- `templates/auth/login.html`, `templates/home.html` — **TEMPORAL (backend)**, para que FRONT los reemplace.

### Migraciones
- `accounts/0001_initial`, `accounts/0002_create_role_groups`

### Pruebas ejecutadas
- TEST-RUN-001 (modelo, roles, matriz de permisos, login/logout/CSRF/redirects, reversibilidad de migraciones).

### Decisiones tomadas
- ADR-006, ADR-011, ADR-012, ADR-013, ADR-014, ADR-015.

### Pendientes derivados
- Los Groups no tienen permisos de modelo asignados todavía: se asignarán en la migración de cada tarea que cree modelos (BE-T03A, BE-T03…).
- Anular `phone_verified_at` al cambiar el teléfono → BE-T11A.
- Rate limiting de login (SPEC §48) → BE-T20 (seguridad), salvo que se adelante.
- Settings de producción (`config/settings/prod.py`, HSTS, logging) → antes del despliegue.

## BE-T03A — Catálogos y auditoría — Cierre

**Estado:** REVIEW (pasa a DONE cuando el PR se apruebe y CI esté en verde)
**Agente:** Claude (BACKEND)
**Fecha:** 2026-10-12

### Implementado
- `helpdesk.Area`, `Category`, `Subcategory`: código en mayúsculas (`^[A-Z][A-Z0-9_]*$`), único (subcategoría: único por categoría), `is_active`, `created_at`/`updated_at`, `on_delete=PROTECT`.
- Una categoría activa no puede tener un área por defecto inactiva (`Category.clean`).
- `helpdesk.AuditLog` según SPEC §26 (`actor_type` USER/SYSTEM/AI, `actor`, `action`, `entity_type` = `app.modelo`, `entity_id`, JSON anterior/nuevo/metadatos), inmutable.
- `helpdesk.audit.record(action, instance, *, actor, actor_type, previous, new, metadata)` y constantes `audit.Action`.
- `helpdesk.catalogs.save_catalog_item(instance, *, actor)` y `set_active(instance, active, *, actor)`: transaccionales, auditan solo los campos cambiados, no auditan si no hubo cambios.
- Django admin: catálogos con acciones activar/desactivar y sin borrado; auditoría solo lectura.
- Datos iniciales: áreas ACADEMIC, FINANCE, IT, SERVICE; categorías ACADEMIC, FINANCIAL, TECHNICAL, GENERAL con 12 subcategorías (códigos alineados con SPEC §29 y §44).
- Permisos por rol: Administrador gestiona catálogos y ve auditoría; Supervisor ve catálogos y auditoría; Agente ve catálogos; Usuario ninguno. Nadie tiene permiso de borrado de catálogos ni de edición de auditoría.

### Archivos creados/modificados
- `apps/helpdesk/{models,audit,catalogs,admin}.py`
- `apps/helpdesk/migrations/0001_initial.py`, `0002_initial_catalogs.py`, `0003_role_permissions.py`
- `apps/helpdesk/tests/{test_catalogs,test_audit,test_admin,test_permissions}.py`
- `apps/accounts/tests/test_migrations.py` (`serialized_rollback`)

### Contratos para FRONT
- Sin vistas web nuevas: la administración usa Django admin hasta FE-T09. Cuando se implemente FE-T09, backend publicará sus vistas (`CONTRACT-XXX`) y estas llamarán a `helpdesk.catalogs`.

### Decisiones tomadas
- ADR-017, ADR-018, ADR-019.

### Pendientes derivados
- Para entrar a Django admin, un usuario del grupo Administrador también necesita `is_staff=True` (lo marca un superusuario). FE-T09 eliminará esa dependencia con vistas propias.
- El historial de `AuditLog` desde la UI (filtros por entidad/actor) se definirá con FE-T08/FE-T09.

## 2026-10-12 — Claude (BACKEND) / BE-T03A

- Estado anterior: TODO.
- Estado nuevo: REVIEW.
- Trabajo realizado: catálogos, auditoría, datos iniciales, permisos por rol, admin.
- Archivos: ver cierre de BE-T03A.
- Pruebas: TEST-RUN-002 PASS.
- Observaciones: desbloquea BE-T03 (tickets) en cuanto se apruebe.

## BE-T03 — Creación de tickets — Cierre

**Estado:** REVIEW (pasa a DONE cuando el PR se apruebe y CI esté en verde)
**Agente:** Claude (BACKEND)
**Fecha:** 2026-10-13

### Implementado
- `helpdesk.Ticket` con todos los campos de SPEC §26 salvo `intent` (CR-002): estados y prioridades como `TextChoices` (§27), `version` para bloqueo optimista, plazos SLA vacíos hasta BE-T08, índices por usuario y por cola (estado + área).
- `helpdesk.Attachment` (SPEC §26): archivo con nombre aleatorio en `attachments/AAAA/MM/`, nombre original, tipo MIME real, tamaño.
- `TicketService.create(...)`: transaccional; código desde secuencia PostgreSQL; estado `NEW`, prioridad `MEDIUM`; área inicial de la categoría; infiere la categoría si solo llega la subcategoría; rechaza categoría/subcategoría inactivas o incoherentes; valida el adjunto antes de consumir número; auditoría `CREATE` del ticket y del adjunto.
- `TicketService.add_attachment(...)`: valida y guarda un adjunto auditado.
- `helpdesk.attachments.validate_upload`: PDF/PNG/JPG, máx. 5 MB, firma del contenido coherente con la extensión.
- Vistas: `helpdesk:ticket_create` (CONTRACT-004) y `helpdesk:attachment_download` (CONTRACT-005).
- Admin de tickets y adjuntos en solo lectura (`ReadOnlyAdmin`, compartido con auditoría).

### Archivos creados/modificados
- `apps/helpdesk/{models,tickets,attachments,forms,views,urls,admin}.py`
- `apps/helpdesk/migrations/0004_tickets.py`
- `apps/helpdesk/tests/{factories,test_tickets,test_attachments,test_ticket_views}.py`
- `config/urls.py`, `conftest.py` (adjuntos de prueba en directorio temporal)
- `templates/helpdesk/ticket_form.html` — **TEMPORAL (backend)**, para que FRONT la reemplace.

### Criterio de aceptación
- Sin códigos duplicados bajo concurrencia: verificado con 12 hilos simultáneos contra PostgreSQL.

### Decisiones tomadas
- ADR-020, ADR-021, ADR-022; CR-002.

### Pendientes derivados
- `Ticket.intent` → BE-T09 (CR-002).
- `first_response_due_at` / `sla_due_at` → BE-T08.
- Registro inicial en `TicketStatusHistory` (None → NEW) → BE-T07, cuando exista el modelo.
- Restringir la descarga de adjuntos de Agentes a tickets de su área/asignación → BE-T04 (hoy cualquier rol de atención puede).
- Redirigir tras crear al detalle del ticket → cuando existan BE-T05/FE-T05 (CHANGE REQUEST de CONTRACT-004).
- Limpieza periódica de archivos huérfanos si una transacción externa revierte tras guardar el archivo → junto a los comandos periódicos (BE-T12).

## 2026-10-13 — Claude (BACKEND) / BE-T03

- Estado anterior: TODO.
- Estado nuevo: REVIEW.
- Trabajo realizado: modelos Ticket y Attachment, TicketService, validación de adjuntos, vistas de creación y descarga, contratos CONTRACT-004/005.
- Archivos: ver cierre de BE-T03.
- Pruebas: TEST-RUN-003 PASS.
- Observaciones: FE-T03 queda desbloqueada para el agente FRONTEND; desbloquea BE-T04, BE-T05, BE-T06, BE-T07 y BE-T09.

## FE-T01 — Inicio FRONT en Cloud

**Estado:** IN_PROGRESS (entorno verificado; implementación pendiente)
**Agente:** ChatGPT (FRONTEND)
**Fecha inicio:** 2026-10-12
**Rama local:** `feature/fe-t01-login`
**Base inspeccionada:** `main-r0dfx3` / PR #1, commit `29d83934de0dd8f594a23b9fa021d009cebd8078`; no integrada en `main`.
**Dependencias verificadas:** SPEC v5.2, CONTRACT-001/002/003 aprobados; BE-T01 sigue REVIEW, aprobación del PR backend no verificada.
**Archivos previstos:** `templates/`, `static/` y registros FRONT de `progress.md` exclusivamente.

### Objetivo
- Implementar login y sesión con Django Templates, Bootstrap 5 y JavaScript vanilla mínimo, consumiendo exclusivamente los contratos publicados.
- Mantener REVIEW para la implementación hasta validar contra backend real y completar revisión; un PR por tarea, sin merge automático.

### Preparación y pruebas FRONT / Cloud
- Python 3.12.14, Django 5.2.18, PostgreSQL 16.15 local aislado.
- Dependencias instaladas sin modificar requirements, pyproject ni archivos BACK; helpers de entorno fuera del checkout.
- Ruff check y format PASS; Django check PASS; migraciones aplicadas y makemigrations --check --dry-run sin cambios.
- Suite existente: 72 PASS, cobertura 99.48 % sobre PostgreSQL real; valida autenticación, roles, permisos, CSRF y reversibilidad.
- Smoke HTTP: login 200, credenciales inválidas con error genérico, POST sin CSRF 403, logout GET 405, inicio sin sesión redirige al login.
- BD de desarrollo con cero usuarios; fixtures sintéticas confinadas a la BD de pruebas eliminada por pytest. Sin datos reales ni secretos de producción.

### No tocar
- `config/`, `apps/`, migraciones, pruebas, `conftest.py`, dependencias, CI ni rama `main`.
- No cambiar estados BACK, contratos ni arquitectura; solicitar datos faltantes como CHANGE REQUEST FRONT.

### Pendientes
- Reemplazar las plantillas temporales backend y realizar validación visual/responsive al implementar FE-T01.
- Registro de inicio solo local y sin commit: no constituye implementación ni publicación en GitHub, ni reproduce la entrada de la computadora del usuario.
- Confirmar aprobación de PR #1 antes de considerar la base backend aprobada; pruebas locales verdes no equivalen a aprobación/merge ni a CI de GitHub.
- Publicar el entorno desde la UI y configurar por separado una automatización si se desea seguimiento periódico; esta preparación no programa ejecuciones futuras.

## FE-T01 — Login y sesión — Cierre FRONT

**Estado:** REVIEW
**Agente:** ChatGPT (FRONTEND)
**Fecha:** 2026-10-12 21:40 — America/Guayaquil
**Base:** `main-r0dfx3`, `d91333f`; rama `feature/fe-t01-login`.
**Contratos:** CONTRACT-001/002/003, aprobados.

- Implementado: base, navegación y mensajes reutilizables de SPEC §18, campos login con labels/autocomplete, error genérico y CSRF, logout POST e inicio provisional por rol. Sin JavaScript adicional ni lógica de permisos FRONT.
- Migraciones/endpoints nuevos: ninguno. Solo consume vistas publicadas por BACK.
- Pruebas efectivas y archivos: ver historial FRONT en sección 16. Datos sintéticos exclusivamente en BD temporal, eliminada al cerrar validación; sin usuarios reales ni secretos de producción.
- Pendientes: revisión humana del FRONT/backend y creación del PR cuando la API GitHub sea accesible. Nunca merge automático ni push a main.
