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

### 3.2 Rama de integración (2026-10-13)

Por pedido del responsable del proyecto, **`main-r0dfx3` es la rama funcional única** que integra backend y frontend y se entregará a `main` vía PR #1.

- Se integraron (merge, sin reescribir historia) las ramas FRONT `feature/fe-t01-login`, `fe-t08-alertas`, `fe-t04-listado-tickets`, `fe-t06-bandeja-agente` y `fe-t03-crear-ticket` (PR #2 a #6).
- Conflicto resuelto entre ramas FRONT: `templates/components/navbar.html` (se conservan «Nueva solicitud» + «Tickets/Bandeja/Alertas») y bitácoras de `progress.md` (se conservan todas, en orden cronológico).
- **Cambios de BACK en archivos FRONT** (mínimos, para que el flujo sea navegable; FRONT puede rehacerlos):
  - `templates/components/ticket_table.html`: el código del ticket enlaza a `helpdesk:ticket_detail`.
  - `templates/helpdesk/ticket_detail.html`: **nueva, TEMPORAL (backend)**, extiende `base.html` y usa `sla_badge`/`ticket_badge`; FRONT la sustituye en FE-T05/FE-T07.
- **A partir de ahora, FRONT trabaja sobre `main-r0dfx3`** (no sobre sus ramas anteriores) y entrega PRs contra `main-r0dfx3`.

---

# 4. Tareas FRONT

| ID | Estado | Responsable/Agente | Dependencia | Última actualización |
|---|---|---|---|---|
| FE-T01 | REVIEW (implementada y validada en Cloud; pendiente de revisión) | ChatGPT | BE-T01 | 2026-10-12 |
| FE-T02 | TODO (desbloqueada: CONTRACT-013) | ChatGPT | BE-T03, BE-T04 | 2026-10-13 |
| FE-T03 | REVIEW (implementada y validada en Cloud; pendiente de revisión) | ChatGPT | BE-T03, BE-T03A | 2026-10-12 |
| FE-T04 | REVIEW (listado validado en Cloud; CONTRACT-008) | ChatGPT | BE-T04 | 2026-10-12 |
| FE-T05 | TODO (desbloqueada: CONTRACT-010/011; hay plantilla TEMPORAL funcional) | ChatGPT | BE-T05, BE-T07 | 2026-10-13 |
| FE-T06 | REVIEW (lectura validada; asignación desbloqueada: CONTRACT-012) | ChatGPT | BE-T04, BE-T06 | 2026-10-13 |
| FE-T07 | TODO (desbloqueada: CONTRACT-006 + `actions` de CONTRACT-010) | ChatGPT | BE-T07 | 2026-10-13 |
| FE-T08 | REVIEW (alertas implementadas y validadas; CONTRACT-007) | ChatGPT | BE-T08 | 2026-10-12 |
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
| BE-T04 | REVIEW (pendiente de revisión del PR) | Claude | BE-T03 | 2026-10-13 |
| BE-T05 | REVIEW (pendiente de revisión del PR; WhatsApp entra con BE-T11) | Claude | BE-T03 | 2026-10-13 |
| BE-T06 | REVIEW (pendiente de revisión del PR) | Claude | BE-T03 | 2026-10-13 |
| BE-T07 | REVIEW (pendiente de revisión del PR) | Claude | BE-T03 | 2026-10-13 |
| BE-T08 | REVIEW (pendiente de revisión del PR) | Claude | BE-T03, BE-T07 | 2026-10-13 |
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
| ADR-023 | 2026-10-13 | El rol Administrador no ejecuta transiciones de tickets (no figura en la tabla §32.1); un superusuario tampoco | Administrador configura (§9.4); operar tickets es de Agente/Supervisor | `helpdesk.workflow` |
| ADR-024 | 2026-10-13 | Hasta BE-T05, el «mensaje de resolución» obligatorio (fila 11) se guarda como motivo del cambio de estado | No hay conversación todavía; no se pierde el dato | `TicketStatusHistory.reason` |
| ADR-025 | 2026-10-13 | Los plazos automáticos (cierre/cancelación) cuentan desde la **última** entrada al estado según `TicketStatusHistory` | Un ticket que vuelve a RESOLVED reinicia su plazo de confirmación | `close_stale_tickets` |
| ADR-026 | 2026-10-13 | Las 4 políticas SLA iniciales (SPEC §34) se crean con `business_hours_only=True` | Una mesa de ayuda institucional no atiende de noche ni en fin de semana; con 24×7, CRITICAL (15 min) vencería de madrugada | Administrable en `/admin/helpdesk/slapolicy/` |
| ADR-027 | 2026-10-13 | Política SLA: primero la de la categoría, si no la general (sin categoría); como máximo una activa por (categoría, prioridad) | Permite excepciones por categoría sin duplicar la general | `sla.policy_for`, restricción única parcial |
| ADR-028 | 2026-10-13 | `SLA_WARNING`/`SLA_BREACHED` se evalúan sobre el plazo de **resolución** (`sla_due_at`); al vencer, `check_sla` escala automáticamente si el ticket está en ASSIGNED o IN_PROGRESS (filas 6 y 10) | SPEC §34.2 y §38.1 | `check_sla` |
| ADR-029 | 2026-10-13 | Los plazos se fijan al crear el ticket y no cambian si luego se edita la política; el % consumido usa la política vigente para decidir si contar horario laboral | SPEC: «el SLA se fija al crear el ticket» | `sla.apply_due_dates`, `sla.sla_status` |
| ADR-030 | 2026-10-13 | Visibilidad: Usuario → sus tickets; Agente → asignados a él + de sus áreas + sin área (triaje) + propios; Supervisor y Administrador → todos | SPEC «tickets autorizados» (§9.2, FE-T06); los tickets sin área deben poder clasificarse (§32.1 fila 1) | `helpdesk.queries.visible_tickets` |
| ADR-031 | 2026-10-13 | Ticket no visible → **404** (no 403) en descarga, acciones y futuras vistas de ticket; 403 solo si el ticket es visible pero el rol no puede ejecutar la acción | No revelar la existencia de tickets ajenos | CR-004 |
| ADR-032 | 2026-10-13 | El tipo de actor «Agente» del workflow exige que el agente pueda ver el ticket | Coherencia entre lo que el agente ve y lo que puede hacer | `workflow.actor_kinds` |
| ADR-033 | 2026-10-13 | Mensajes: escriben el solicitante y el personal con acceso al ticket (Agente de su área/asignado, Supervisor); el Administrador no; no se escribe en CLOSED/CANCELLED | Coherencia con ADR-023/030; un ticket cerrado se reabre para seguir | `conversations.add_message` |
| ADR-034 | 2026-10-13 | Primera respuesta = primer mensaje del personal (o la resolución) → `first_response_at` | Base para el SLA de primera respuesta | `conversations`, `workflow` |
| ADR-035 | 2026-10-13 | La resolución (fila 11) se publica también como mensaje `RESOLUTION` en la conversación | El usuario la lee donde conversa; sustituye a ADR-024 | `workflow.transition` |
| ADR-036 | 2026-10-13 | Asignación: Supervisor a cualquier área/agente; Agente solo dentro de sus áreas (tomar o pasar a un compañero) y nunca un ticket ESCALATED; el responsable debe ser agente activo del área | SPEC §9.2 «reasignar cuando tenga permiso», §9.3, fila 12 | `assignment` |
| ADR-037 | 2026-10-13 | Asignar avanza el estado a ASSIGNED desde NEW (vía CLASSIFIED), CLASSIFIED, REOPENED y ESCALATED, también si área/responsable no cambian; cada paso lo firma el usuario si la tabla §32.1 se lo permite, si no el sistema | Evita tickets asignados que quedan en NEW | `assignment.assign` |
| ADR-038 | 2026-10-13 | `seed_demo`: datos de demostración solo con DEBUG (o `--force`), idempotente, creados con los servicios reales | Verificación manual reproducible | comando `seed_demo` |
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
**Respuestas:** 200 con el archivo (`Content-Disposition: attachment`, nombre original); 404 si el ticket no es visible para el usuario (CR-004), si el adjunto no pertenece a ese ticket o si el archivo no existe.
**Datos del adjunto disponibles** (cuando se publique el contrato de detalle): `original_name`, `content_type`, `size_bytes`, `created_at`.
**Aprobado:** Sí

### CONTRACT-006 — Acciones de estado (FE-005 / FE-T07)
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T07) → consumidor FE-T07
**Métodos:** solo POST (GET → 405), sin plantilla, requieren sesión y `{% csrf_token %}`. Solo sobre tickets visibles para el usuario (CONTRACT-008).

| URL name | Ruta | Destino | Notas |
|---|---|---|---|
| `helpdesk:ticket_status` | `/tickets/<code>/status/` | el indicado en `to_status` | Genérica. `to_status` = código de estado (`WAITING_USER`, `CLASSIFIED`, …). |
| `helpdesk:ticket_resolve` | `/tickets/<code>/resolve/` | `RESOLVED` | `reason` obligatorio (mensaje de resolución). |
| `helpdesk:ticket_escalate` | `/tickets/<code>/escalate/` | `ESCALATED` | `reason` obligatorio. |
| `helpdesk:ticket_confirm` | `/tickets/<code>/confirm/` | `CLOSED` | Solo desde `RESOLVED` (usuario confirma). |
| `helpdesk:ticket_reject_resolution` | `/tickets/<code>/reject-resolution/` | `IN_PROGRESS` | Solo desde `RESOLVED`; `reason` obligatorio. |
| `helpdesk:ticket_reopen` | `/tickets/<code>/reopen/` | `REOPENED` | Dentro de 7 días desde el cierre. |
| `helpdesk:ticket_cancel` | `/tickets/<code>/cancel/` | `CANCELLED` | `reason` obligatorio. |

**POST esperado:** `version` (entero, obligatorio: la `ticket.version` que se mostró), `reason` (texto, máx. 2000; obligatorio según la acción), `next` (opcional: URL interna a la que volver), `to_status` (solo en la genérica), `csrfmiddlewaretoken`.
**Respuestas:**
- éxito → 302 a `next` (si es interna) o a `accounts:role_redirect`, con mensaje `success`: `"Ticket HD-…: estado cambiado a <Estado>."`;
- transición no válida, motivo faltante o fuera de plazo → 302 igual, con mensaje `error` (textos de SPEC §19, p. ej. `"Debe indicar un motivo para este cambio de estado."`);
- versión desactualizada → 302 con mensaje `error`: `"El ticket fue actualizado por otro usuario."`;
- ticket visible pero rol no permitido → 403; ticket inexistente o no visible para el usuario → 404 (CR-004); falta `version` o `to_status` inválido → 400.

**Qué botones mostrar:** FRONT no decide. Cuando se publique el contrato del detalle (BE-T05), su contexto incluirá `allowed_targets` (lista de estados a los que el usuario actual puede llevar el ticket, calculada con `helpdesk.workflow.allowed_targets`). Solo deben mostrarse esas acciones.
**Aprobado:** Sí

### CONTRACT-FRONT-001 — Contexto de detalle para FE-T07 — Respondida (CONTRACT-010)
**Fecha:** 2026-10-12 — America/Guayaquil
**Origen:** FRONT (coordinación; no implementación FE-T07)
**Estado:** Pendiente de publicación BACK / BE-T05
**Contrato disponible:** CONTRACT-006 publica acciones POST, pero aún no existe contrato GET de detalle con `ticket.version`, `allowed_targets`, historial y acciones autorizadas para ese usuario.
**Solicitud:** BACK debe publicar plantilla, url name y contexto del detalle antes de que FRONT muestre acciones. No inferir transiciones ni permisos desde el rol ni generar botones a partir de SPEC §32.
**Consumidores:** FE-T05/FE-T07. No bloquea FE-T01/FE-T03.
**Aprobado:** Pendiente
### CONTRACT-007 — Alertas (FE-007 / FE-T08)
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T08) → consumidor FE-T08
**URL name:** `helpdesk:alert_list` → `/alerts/`
**Plantilla:** `helpdesk/alerts.html` (hoy existe una versión `TEMPORAL (backend)` que FRONT debe reemplazar)
**Métodos:** GET. Solo rol **Supervisor** (otros roles → 403; sin sesión → 302 a login).
**Parámetros GET:** `status` = `OPEN` (por defecto) | `RESOLVED` | `ALL`; `type` = `SLA_WARNING` | `SLA_BREACHED` | `ESCALATED` | vacío (todos); `page` (25 por página). Valores desconocidos se ignoran.
**Contexto:**

| Variable | Tipo | Descripción |
|---|---|---|
| `alerts` | lista de `Alert` | Alertas de la página. Campos: `alert_type` y `get_alert_type_display` («SLA por vencer», «SLA vencido», «Escalado»), `severity` / `get_severity_display` (`INFO`, `WARNING`, `CRITICAL`), `message`, `status` / `get_status_display`, `created_at`, `resolved_at`, `ticket.ticket_code`, `ticket.subject`, `ticket.get_status_display`, `ticket.get_priority_display`, `ticket.assigned_area.name` (puede ser `None`), `ticket.sla_due_at`. |
| `page_obj` | `Page` | Paginación estándar de Django (`has_next`, `next_page_number`, `paginator.num_pages`…). Conservar `status` y `type` en los enlaces. |
| `filters` | `dict` | `{"status": "OPEN"\|"RESOLVED"\|"ALL", "type": "<tipo>" o ""}` aplicados. |
| `status_choices`, `type_choices` | `list[tuple]` | `(valor, etiqueta)` para construir los filtros. |
| `open_counts` | `dict` | Alertas **abiertas** por tipo: `{"SLA_WARNING": n, "SLA_BREACHED": n, "ESCALATED": n}` (para los indicadores de FE-007). |

**Estados SLA para badges (FE-T08 en bandeja y detalle):** el backend expondrá en los contratos de BE-T04/BE-T05 un objeto `sla` por ticket calculado con `helpdesk.sla.sla_status`: `state` (`NONE`, `OK`, `WARNING`, `BREACHED`, `STOPPED`), `due_at`, `remaining_minutes` (negativo si vencido, en minutos laborables si la política es de horario laboral) y `consumed_ratio`. FRONT no calcula SLA.
**Aprobado:** Sí

### CONTRACT-008 — Listado de tickets (FE-004 / FE-T04)
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T04) → consumidor FE-T04 (y «Tickets» del Supervisor)
**URL name:** `helpdesk:ticket_list` → `/tickets/`
**Plantilla:** `helpdesk/ticket_list.html` (versión `TEMPORAL (backend)` a reemplazar)
**Métodos:** GET. Requiere sesión. Cada rol ve solo sus tickets visibles (ADR-030); para un Usuario es «Mis tickets».
**Parámetros GET (todos opcionales; los inválidos se ignoran):**

| Parámetro | Valores |
|---|---|
| `status` | `OPEN` (no resueltos/cerrados/cancelados), `FINISHED`, o un estado (`NEW`, `IN_PROGRESS`, …) |
| `priority` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `category`, `area` | id |
| `assignee` | `me`, `none` o id de usuario |
| `date_from`, `date_to` | `AAAA-MM-DD` (fecha de creación, inclusiva) |
| `sla` | `WARNING` (por vencer) o `BREACHED` (vencido) |
| `q` | texto en el asunto o código exacto `HD-…` |
| `sort` | `-created_at` (defecto), `created_at`, `-updated_at`, `sla_due_at` |
| `page` | número de página (20 por página) |

FE-004 (Usuario) solo necesita `status`, `date_from`/`date_to` y `page`; el resto sirve a Supervisor/Agente.
**Contexto:**

| Variable | Tipo | Descripción |
|---|---|---|
| `rows` | `list[dict]` | Una por ticket: `{"ticket": Ticket, "sla": SLAStatus}`. Del ticket: `ticket_code`, `subject`, `status`/`get_status_display`, `priority`/`get_priority_display`, `category.name`, `assigned_area.name`, `assigned_user.get_full_name`/`username`, `user` (solicitante), `created_at`, `updated_at`, `version`. Relacionados pueden ser `None`. `sla`: `state` (`NONE`, `OK`, `WARNING`, `BREACHED`, `STOPPED`), `due_at`, `remaining_minutes`, `consumed_ratio` (ver CONTRACT-007). |
| `page_obj` | `Page` | Paginación estándar de Django. Conservar los filtros en los enlaces. |
| `filters` | `dict` | Filtros **aplicados** (ya validados), siempre con `sort`. Usar para repintar el formulario. |
| `status_choices` | `list[tuple]` | `("OPEN", "Abiertos")` + los 10 estados. |
| `priority_choices`, `sort_choices` | `list[tuple]` | `(valor, etiqueta)`. |
| `categories`, `areas` | querysets | Activos, para los selects. |

**Aprobado:** Sí

### CONTRACT-009 — Bandeja del agente (FE-006 / FE-T06)
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T04) → consumidor FE-T06
**URL name:** `helpdesk:agent_inbox` → `/agent/inbox/`
**Plantilla:** `helpdesk/agent_inbox.html` (versión `TEMPORAL (backend)` a reemplazar)
**Métodos:** GET. Roles **Agente** y **Supervisor** (otros → 403).
**Parámetros GET:** `tab` + los mismos filtros de CONTRACT-008 (los filtros explícitos se suman y pueden reemplazar a los de la pestaña). Orden por defecto: `sla_due_at` (lo que vence antes, primero).

| `tab` | Etiqueta (SPEC §10) | Filtro predefinido |
|---|---|---|
| `mine` (defecto) | Mi bandeja | asignados a mí, abiertos |
| `unassigned` | Sin asignar | sin responsable, abiertos |
| `in_progress` | En proceso | `IN_PROGRESS` |
| `waiting_user` | Pendientes de usuario | `WAITING_USER` |
| `due_soon` | Por vencer | SLA `WARNING` |
| `overdue` | Vencidos | SLA `BREACHED` |
| `history` | Historial | resueltos, cerrados y cancelados |

**Contexto:** el mismo de CONTRACT-008 más:

| Variable | Tipo | Descripción |
|---|---|---|
| `tab` | `str` | Pestaña activa. |
| `tabs` | `list[dict]` | `[{"key", "label", "count"}]` en el orden de la tabla; `count` es `None` en `history` (no se cuenta). |
| `assignees` | queryset de usuarios | Agentes activos, para el filtro «responsable» (`assignee=<id>`). |

**Aprobado:** Sí

### CONTRACT-FRONT-002 — Dashboard de usuario FE-T02 — Respondida (CONTRACT-013)
**Fecha:** 2026-10-12 — America/Guayaquil
**Origen:** FRONT
**Estado:** Pendiente de publicación BACK
**Contrato actual:** CONTRACT-002 solo expone variables globales en home.html; CONTRACT-008 aporta listado, no dashboard.
**Solicitud concreta:** publicar url name/plantilla del dashboard y contexto autorizado de tickets recientes (código, asunto, estado, última actualización, enlace publicado si existe) y acceso de creación. BACK decide selección, orden, límite y privacidad; FRONT no consultará ORM desde plantilla ni simulará tickets recientes.
**Precisiones de interfaz pendientes:** método GET, ruta y URL name exactos, nombre/estructura de la variable de tickets recientes, selección/límite/orden ya resueltos por BACK y caso vacío. La creación usa la URL aprobada `helpdesk:ticket_create` (CONTRACT-004); no se requiere inventar un formulario POST dentro del dashboard. Si BACK cambia `accounts:role_redirect`/ROLE_HOME_URLS debe registrarlo como cambio de contrato.
**Consumidor:** FE-T02. No bloquea FE-T04 (listado) ni cambia contratos BACK.
**Aprobado:** Pendiente

### CONTRACT-FRONT-003 — Asignación FE-T06 — Respondida (CONTRACT-012)
**Fecha:** 2026-10-12 — America/Guayaquil
**Origen:** FRONT
**Estado:** Pendiente de publicación BACK / BE-T06
**Contrato disponible:** CONTRACT-009 permite filtrar/listar bandeja; `assignees` son opciones de filtro, no autorización para asignar un ticket.
**Solicitud concreta:** publicar URL names y POST esperado para asignar/reasignar, manejo de versión/CSRF/errores y contexto por ticket con acciones/destinos autorizados calculados por BACK. Definir quién puede elegir área/responsable y cuándo; FRONT no reutilizará el queryset de filtros como lista de asignación autorizada ni deducirá permisos del rol.
**Precisiones de formulario pendientes:** ruta y URL name de cada POST, variable/instancia del formulario, nombres/tipos/límites/requeridos de sus campos y errores generales/por campo, opciones de área/responsable autorizadas **para el ticket**, campo de versión leída, CSRF, motivo si procede, respuesta/error y destino PRG. BACK publica estos datos; `assignees` del filtro CONTRACT-009 no autoriza una operación de asignación.
**Consumidor:** FE-T06. La lectura/filtros se implementa ahora; acciones bloqueadas hasta el contrato.
**Aprobado:** Pendiente

### CONTRACT-FRONT-004 — Detalle FE-T05 y acciones FE-T07 — Respondida (CONTRACT-010/011)
**Fecha:** 2026-10-12 — America/Guayaquil
**Origen:** FRONT
**Estado:** Pendiente de publicación BACK / BE-T05
**Contrato disponible:** CONTRACT-005 define descargas y CONTRACT-006 POST de estado; ninguno publica vista GET/contexto del detalle.
**Solicitud concreta:** publicar URL name/plantilla del detalle, contexto autorizado del ticket, conversación/histórico ordenados por BACK (remitente/canal/fecha/texto autorizado), adjuntos autorizados, `ticket.version`, `allowed_targets` y datos de acciones permitidas; también URL names/POST de respuesta cuando existan. BACK decide permisos, transiciones y qué contenido puede mostrarse; FRONT no infiere botones, mensajes ni historial desde modelos sin contexto aprobado.
**Precisiones de GET/respuesta pendientes:** ruta y URL name GET del detalle; nombres/estructura exactos de ticket, conversación, historial, adjuntos y `sla`; instancias de formularios publicados (campos, obligatorios/límites, errores y adjunto habilitado), URL name/ruta POST de respuesta, enctype si admite archivo y destino PRG. No se declara existente ninguna vista/contexto aún pendiente.
**Acciones POST ya aprobadas, a consumir solo con contexto de detalle:** CONTRACT-006 publica `helpdesk:ticket_status`, `ticket_resolve`, `ticket_escalate`, `ticket_confirm`, `ticket_reject_resolution`, `ticket_reopen`, `ticket_cancel`; campos `version` leído (entero), `reason` (máx. 2000, requerido según acción), `next` interno opcional, `to_status` solo para genérica, CSRF. Mostrar únicamente `allowed_targets` de BACK; publicación del contexto debe cubrir qué acción/motivo corresponde. Respuestas 400/403/404 y mensajes/PRG se rigen por CONTRACT-006 y CR-004 (no visible → 404), sin lógica de permisos FRONT.
**Consumidores:** FE-T05/FE-T07. La solicitud equivalente de FE-T07 también consta en PR #3 como CONTRACT-FRONT-001; no implica dos implementaciones ni dos bloqueos distintos.
**Aprobado:** Pendiente

### CONTRACT-010 — Detalle de ticket (FE-005 / FE-T05 y FE-T07)
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T05) → consumidores FE-T05, FE-T07 (responde CONTRACT-FRONT-001 y 004)
**URL name:** `helpdesk:ticket_detail` → `/tickets/<code>/`
**Plantilla:** `helpdesk/ticket_detail.html` (hoy **TEMPORAL (backend)** funcional, extiende `base.html`; FRONT la sustituye)
**Métodos:** GET. Requiere sesión; ticket no visible → 404 (CR-004).
**Contexto:**

| Variable | Tipo | Descripción |
|---|---|---|
| `ticket` | `Ticket` | Campos de CONTRACT-008 más `description`, `channel`/`get_channel_display`, `subcategory.name`, `first_response_at`, `first_response_due_at`, `version` (para los formularios POST). |
| `sla` | `SLAStatus` | Estado del SLA de resolución (ver CONTRACT-007). |
| `timeline` | `list[dict]` | Orden cronológico. Mensaje: `{"kind": "message", "created_at", "channel": "WEB"\|"WHATSAPP", "message"}` con `message.content`, `get_sender_type_display` (Usuario/Agente/Sistema/IA), `sender` (puede ser `None`), `message_type` (`TEXT`, `INFO_REQUEST`, `RESOLUTION`) / `get_message_type_display`, `attachments.all` (`id`, `original_name`, `size_bytes`). Cambio de estado: `{"kind": "status", "created_at", "entry"}` con `entry.get_previous_status_display` (vacío en la creación), `get_new_status_display`, `actor` (`None` = sistema), `reason`. |
| `attachments` | queryset | Todos los adjuntos del ticket (descarga con CONTRACT-005). |
| `is_owner` | `bool` | El usuario es el solicitante. |
| `actions` | `list[dict]` | **Botones de estado permitidos ahora** para este usuario (no mostrar otros): `target` (estado destino), `label` (texto sugerido), `url` (POST de CONTRACT-006), `url_name`, `reason_required` (`bool`: pedir `reason` obligatorio), `generic` (`bool`: si es `true`, enviar también `to_status=<target>`). |
| `can_reply` | `bool` | Mostrar el formulario de respuesta (CONTRACT-011). |
| `can_request_info` | `bool` | Mostrar la casilla «Solicitar información» (solo personal). |
| `message_form` | `MessageForm` | Campos `content`, `attachment`, `request_info`. |
| `assign` | `dict` | Para CONTRACT-012: `can_assign` (`bool`), `areas` (`[{"id", "name", "agents": [{"id", "name"}]}]`, solo opciones autorizadas), `current_area_id`, `current_assignee_id`. |

**Aprobado:** Sí

### CONTRACT-011 — Responder en el ticket
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T05) → consumidor FE-T05
**URL name:** `helpdesk:ticket_message` → `/tickets/<code>/messages/`
**Métodos:** solo POST, `multipart/form-data`, `{% csrf_token %}`.
**POST esperado:** `content` (obligatorio, máx. 5000), `attachment` (opcional, mismas reglas que CONTRACT-004), `request_info` (`on`; solo si `can_request_info`).
**Efectos (los decide BACK):** respuesta del solicitante en «Esperando usuario» → vuelve a «En proceso»; primera respuesta del personal fija `first_response_at`; `request_info` pasa el ticket a «Esperando usuario».
**Respuestas:** siempre 302 al detalle, con mensaje `success` («Mensaje enviado.») o `error` (validación, ticket cerrado: «El ticket está cerrado: reábralo para continuar la conversación.»); 403 si el usuario no puede escribir (p. ej. Administrador o `request_info` del solicitante); 404 si no es visible.
**Aprobado:** Sí

### CONTRACT-012 — Asignar / reasignar (FE-T06)
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T06) → consumidor FE-T06 y detalle (responde CONTRACT-FRONT-003)
**URL name:** `helpdesk:ticket_assign` → `/tickets/<code>/assign/`
**Métodos:** solo POST, `{% csrf_token %}`.
**POST esperado:** `version` (obligatorio), `area` (id, obligatorio), `assignee` (id de agente, opcional: vacío = solo área), `next` (opcional, URL interna).
**Opciones autorizadas:** usar **solo** `assign.areas` del contexto del detalle (no el filtro `assignees` de CONTRACT-009). Supervisor: todas las áreas; Agente: sus áreas y sus compañeros; nadie más.
**Respuestas:** 302 a `next` o al detalle con mensaje `success` («Ticket HD-… asignado.») o `error` (versión desactualizada, responsable que no es del área, ticket terminado); 403 sin permiso; 400 si falta `version`/`area` o el responsable no existe; 404 si no es visible.
**Efecto:** si el ticket estaba en Nuevo/Clasificado/Reabierto/Escalado pasa a «Asignado».
**Aprobado:** Sí

### CONTRACT-013 — Inicio con resumen (FE-002 / FE-T02)
**Fecha:** 2026-10-13
**Origen:** BACK → consumidor FE-T02 (responde CONTRACT-FRONT-002)
**URL name:** `accounts:home` → `/inicio/` (amplía CONTRACT-002; plantilla `home.html`)
**Contexto adicional:**

| Variable | Tipo | Descripción |
|---|---|---|
| `recent_rows` | `list[dict]` | Hasta 5 filas `{"ticket", "sla"}` (como CONTRACT-008), por última actualización. Usuario: sus tickets; personal: los que creó o tiene asignados. |
| `summary` | `dict` | `{"open": n, "waiting_user": n, "resolved": n}` sobre los mismos tickets (`resolved` = pendientes de confirmar). |

**Aprobado:** Sí

### CHANGE REQUEST CR-005 — Tras crear o cambiar estado se vuelve al detalle
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T05)
**Contrato actual:** CONTRACT-004 y CONTRACT-006 redirigían a `accounts:role_redirect` porque no existía el detalle.
**Cambio:** crear ticket → 302 a `helpdesk:ticket_detail`; acciones de estado sin `next` → 302 al detalle del ticket.
**Consumidores afectados:** FE-T03, FE-T07 (sin cambios de plantilla).
**Aprobado:** Sí

## 12.2 Solicitudes de cambio

### CHANGE REQUEST CR-001 — Agente LangGraph
**Fecha:** 2026-10-12
**Origen:** Solicitud del responsable del proyecto
**Cambio:** la IA pasa de llamadas sueltas a un agente orquestado con LangGraph (SPEC §46A). Se levanta la prohibición genérica de “agents” (SPEC §4, §55) y se reemplaza por reglas de agente controlado.
**Impacto:** nueva tarea BE-T18A; `AIDecision` añade `graph_version`, `node_path`, `thread_id`; nuevas dependencias `langgraph`, `langgraph-checkpoint-postgres` (se añadirán a `requirements.txt` al iniciar BE-T18A, no antes).
**Consumidores afectados:** FRONT sin cambios hasta FE-T06 (la bandeja mostrará los casos pausados en `human_review`; su contrato se publicará con BE-T18A).
**Aprobado:** Sí

### CHANGE REQUEST CR-003 — Agentes por área (`Area.agents`)
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T04)
**Cambio:** la SPEC exige que cada agente vea solo «tickets autorizados» (§9.2, FE-T06) pero no define a qué área pertenece cada agente. Se añade `Area.agents` (ManyToMany con usuarios del grupo Agente), gestionado desde el admin de áreas con auditoría (`catalogs.set_area_agents`).
**Impacto:** migración `helpdesk/0008_area_agents`. FE-T09 (administración de áreas) deberá permitir elegir los agentes del área. Sin agentes asignados a un área, sus tickets solo los ven Supervisor, Administrador y el agente responsable.
**Aprobado:** Sí (decisión técnica del agente BACKEND; revisable en el PR)

### CHANGE REQUEST CR-004 — Ticket no visible devuelve 404 (CONTRACT-005 y CONTRACT-006)
**Fecha:** 2026-10-13
**Origen:** BACK (BE-T04)
**Contrato actual:** descarga de adjunto y acciones de estado devolvían **403** a un usuario que no era dueño ni rol de atención.
**Cambio:** ahora devuelven **404** si el ticket no es visible para el usuario (ADR-031). El 403 de CONTRACT-006 queda solo para «ticket visible, pero su rol no puede ejecutar esa transición».
**Consumidores afectados:** FE-T05/FE-T07 (ningún cambio de plantilla: Django muestra la página 404 estándar).
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
- `helpdesk/migrations/0005_ticket_status_history.py` — `TicketStatusHistory` — aplicada y reversible — BE-T07
- `helpdesk/migrations/0006_sla_and_alerts.py` — `SLAPolicy`, `Alert` y restricciones — aplicada y reversible — BE-T08
- `helpdesk/migrations/0007_initial_sla_policies.py` — 4 políticas generales (SPEC §34) auditadas como SYSTEM y permisos por rol — aplicada y reversible — BE-T08
- `helpdesk/migrations/0008_area_agents.py` — `Area.agents` (CR-003) — aplicada y reversible — BE-T04
- `helpdesk/migrations/0009_conversations.py` — `Conversation`, `TicketMessage`, `Attachment.message` — aplicada y reversible — BE-T05

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
- `POST /tickets/<code>/{status,resolve,escalate,confirm,reject-resolution,reopen,cancel}/` — `helpdesk:ticket_*` — REVIEW — BE-T07 — CONTRACT-006
- Comando `python manage.py close_stale_tickets [--dry-run]` — REVIEW — BE-T07 (cron cada hora, SPEC §38.1)
- `GET /alerts/` — `helpdesk:alert_list` — REVIEW — BE-T08 — CONTRACT-007
- `/admin/helpdesk/slapolicy/` (gestión auditada, sin borrado) y `/admin/helpdesk/alert/` (solo lectura) — REVIEW — BE-T08
- Comando `python manage.py check_sla` — REVIEW — BE-T08 (cron cada 5 min, SPEC §38.1)
- `GET /tickets/` — `helpdesk:ticket_list` — REVIEW — BE-T04 — CONTRACT-008
- `GET /agent/inbox/` — `helpdesk:agent_inbox` — REVIEW — BE-T04 — CONTRACT-009
- `GET /tickets/<code>/` — `helpdesk:ticket_detail` — REVIEW — BE-T05 — CONTRACT-010
- `POST /tickets/<code>/messages/` — `helpdesk:ticket_message` — REVIEW — BE-T05 — CONTRACT-011
- `POST /tickets/<code>/assign/` — `helpdesk:ticket_assign` — REVIEW — BE-T06 — CONTRACT-012
- `GET /inicio/` — `accounts:home` con resumen — REVIEW — CONTRACT-013
- Comando `python manage.py seed_demo [--force]` — solo desarrollo (ADR-038)

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

### TEST-RUN-004
**Fecha:** 2026-10-13
**Tarea:** BE-T07
**Comando:** mismo que TEST-RUN-001 (dos ejecuciones completas)
**Entorno:** PostgreSQL 16 local, `config.settings.test`, sin `.env` (igual que CI)
**Resultado:** PASS — 394 pruebas, cobertura 99 % (`workflow.py`, vistas y comando al 100 %). Incluye la matriz 17 transiciones × 7 actores, las 73 transiciones fuera de la tabla y una prueba concurrente de bloqueo optimista.
**Fallos:** el primer intento falló en PostgreSQL (`FOR UPDATE cannot be applied to the nullable side of an outer join`); corregido con `select_for_update(of=("self",))`.

### TEST-RUN-005
**Fecha:** 2026-10-13
**Tarea:** BE-T08
**Comando:** mismo que TEST-RUN-001 (dos ejecuciones completas)
**Entorno:** PostgreSQL 16 local, `config.settings.test`, sin `.env` (igual que CI)
**Resultado:** PASS — 451 pruebas, cobertura 99 % (`sla.py`, `alerts.py`, vistas y workflow al 100 %). Incluye cruces de fin de semana, noches, feriados, inversa suma/diferencia de minutos laborables, umbral del 80 % y escalamiento automático.
**Fallos:** primer intento con 3 expectativas mal calculadas en las propias pruebas (2880 min laborables = 5 días + 180 min → vence el lunes siguiente a las 11:00); el código era correcto y se corrigieron las pruebas. Además se actualizaron 4 pruebas previas cuyo comportamiento cambia a propósito (el ticket ahora tiene SLA al crearse; nuevos permisos por rol).

### TEST-RUN-006
**Fecha:** 2026-10-13
**Tarea:** BE-T04
**Comando:** mismo que TEST-RUN-001 (dos ejecuciones completas)
**Entorno:** PostgreSQL 16 local, `config.settings.test`, sin `.env` (igual que CI)
**Resultado:** PASS — 483 pruebas, cobertura 99 % (`queries.py`, vistas, workflow y catálogos al 100 %). Incluye la matriz de visibilidad de 6 roles, todos los filtros, pestañas, paginación y un límite de 2 consultas para listar (sin N+1).
**Fallos:** 6 pruebas previas cambiaron a propósito (403 → 404 para tickets no visibles; el agente del workflow ahora debe pertenecer al área). Se actualizaron y se añadieron pruebas para el agente de otra área.

### TEST-RUN-007
**Fecha:** 2026-10-13
**Tarea:** integración FRONT + BE-T05 + BE-T06 + CONTRACT-013
**Comando:** mismo que TEST-RUN-001
**Entorno:** PostgreSQL 16 local, `config.settings.test`, sin `.env` (igual que CI), con las plantillas reales del FRONT integradas
**Resultado:** PASS — 535 pruebas, cobertura 99 %.
**Fallos:** 2 pruebas previas cambiaron a propósito (CR-005). Los datos demo destaparon un caso real: asignar un ticket NEW al área que ya tenía por su categoría no avanzaba el estado; corregido (ADR-037) con prueba.

### E2E-RUN-001
**Fecha:** 2026-10-13
**Comando:** `seed_demo` + `runserver` + `python scripts/e2e_demo.py` (Chromium real)
**Resultado:** PASS — 12 pasos con los 5 roles: login; «Mis tickets»; confirmar solución; responder con PDF (vuelve a «En proceso»); crear ticket y llegar al detalle; agente ve «Sin asignar», se asigna, atiende y resuelve; supervisor en alertas/historial; agente de otra área recibe 404; admin entra a `/admin/`; listado a 360 px sin desbordamiento. Sin respuestas 5xx.
**Fallos:** en los primeros intentos fallaron aserciones del propio script (texto del aviso con saltos de línea; botón de cerrar sesión ausente en la página 404 de Django), no la aplicación.

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
- Publicación: entorno publicado confirmado por UI del usuario; implementación corre enteramente en Cloud. Git push dry-run autorizado; creación de PR bloqueada por CONNECT 403 a `api.github.com`. Dominio añadido al borrador de red para revisión/aplicación. Estado en ese momento: sin scheduler configurado. Actualización: UI confirmó seguimiento Cloud ACTIVO cada hora, America/Guayaquil, id `6acd9bd4f1648190a92625ce9eefe1d5`; primera ejecución aún no verificada.

---

## 2026-10-12 21:42 — ChatGPT (FRONTEND) / FE-T03 — Inicio — America/Guayaquil

- Estado anterior: TODO, desbloqueada por CONTRACT-004/005.
- Estado nuevo: IN_PROGRESS.
- Trabajo previsto: `templates/helpdesk/ticket_form.html`, JS vanilla mínimo en `static/`, enlace a la vista aprobada de creación y registros FRONT de este archivo.
- Rama: `feature/fe-t03-crear-ticket`, sobre FE-T01 para reutilizar base/componentes sin merges; backend `d91333f`. El diff de la tarea se revisará separado de FE-T01.
- Contratos: formulario y category_tree de CONTRACT-004; CONTRACT-005 leído, su UI de descarga corresponde a FE-T05 y no se adelanta.
- No tocar: BACK, config, dependencias, CI, pruebas ni estados BACK. Sin datos reales ni secretos de producción.

---

## 2026-10-12 21:49 — ChatGPT (FRONTEND) / FE-T01 — Sincronización — America/Guayaquil

- Estado: REVIEW, sin cambios BACK.
- Actualización: `main-r0dfx3` avanzó a `9bd4b58` (BE-T07, CONTRACT-006). Se incorporó a la rama FRONT propia y se resolvió el conflicto de progress.md conservando íntegramente registros BACK y FRONT; sin force push ni merge a main.
- Publicación: PR #2 abierto en https://github.com/ChrissJunta/ProductoFinalM4/pull/2; rama FE-T01 `7532bd5`. GitHub confirma MERGEABLE y CI backend PASS tras sincronizar.
- Pruebas sobre nueva base: 394 PASS, cobertura 98.83 %, Django check y migraciones sin cambios; login y sesión en Chromium real revalidados.
- Acceso: API GitHub ya permite crear/consultar PR. Actualización UI: seguimiento Cloud ACTIVO cada hora, America/Guayaquil, id `6acd9bd4f1648190a92625ce9eefe1d5`; primera ejecución/acceso GitHub/continuación del chat pendientes de validar. No duplicar ni depender de heartbeat local.

## 2026-10-12 21:49 — ChatGPT (FRONTEND) / FE-T03 — Cierre — America/Guayaquil

- Estado anterior: IN_PROGRESS.
- Estado nuevo: REVIEW.
- Base backend: `9bd4b58`, con todos los registros recientes de Claude preservados. Rama `feature/fe-t03-crear-ticket` reutiliza FE-T01; PR #3 separado, base actual `feature/fe-t01-login`, dependiente de PR #2; originalmente se abrió contra `main-r0dfx3` y se ajustó para dejar el diff exclusivamente FE-T03. El commit FE-T03 contiene solo su formulario, JS, enlaces y registros FRONT; el diff actual excluye la base FRONT compartida gracias a la base FE-T01; retarget solo tras revisión humana de PR #2.
- Archivos: `templates/helpdesk/ticket_form.html`, `templates/components/navbar.html`, `templates/home.html`, `static/js/ticket-form.js`, registros FRONT de `progress.md`.
- Implementado: multipart y CSRF, campos/longitudes según CONTRACT-004, errores de backend accesibles, preservación de valores no sensibles, adjunto opcional, ayuda de formatos/tamaño y filtrado opcional de subcategorías con `json_script` y JS vanilla. Formulario usable sin JS; backend conserva autenticación, permisos, categoría efectiva, código, estado y prioridad.
- Pruebas: 394 PASS, cobertura 98.83 %, ruff check/format, Django check, makemigrations --check --dry-run, node --check PASS. Chromium 360/768/1280: creación real con PDF, rechazo de EXE, validación servidor con noValidate, autoescape, errores de campo, filtros dependientes, cambio de categoría, flash success y descarga real CONTRACT-005; creación sin JS con inferencia de categoría BACK PASS.
- Validación usa BD temporal y archivos sintéticos, eliminados al terminar. El helper necesitó aislar consultas ORM del event loop del navegador; corregido fuera del repo, sin tocar pruebas BACK.
- Migraciones/endpoints nuevos: ninguno. CONTRACT-005 se verifica pero la UI de descarga se reserva a FE-T05. No se implementan acciones FE-T07: contexto pendiente CONTRACT-FRONT-001 en sección 12.
- Pendiente: revisión humana de FRONT y base backend; no DONE ni merge automático. Ninguna nueva tarea se toma sin contrato vigente y registro FRONT.

---

## 2026-10-12 21:54 — ChatGPT (FRONTEND) / FE-T08 — Inicio — America/Guayaquil

- Estado anterior: TODO, CONTRACT-007 recién publicado y aprobado en backend `5ea6941`.
- Estado nuevo: IN_PROGRESS; rama `feature/fe-t08-alertas` sobre FE-T01, sin duplicar FE-T03.
- Trabajo previsto: `templates/helpdesk/alerts.html`, componentes de paginación y badges de presentación con consumidor real, navegación Supervisor y registros FRONT.
- Alcance: indicadores `open_counts`, filtros y 25 filas por página, fechas/estados/severidades recibidos del backend. No calcular SLA, plazos, permisos ni acciones. El tiempo restante por ticket se reservará al objeto `sla` de futuros contratos BE-T04/BE-T05.
- No tocar: BACK/config/dependencias/CI/pruebas ni filas BACK. Seguimiento Cloud ya ACTIVO cada hora según UI; primera ejecución aún no validada. No crear monitor duplicado.

---

## 2026-10-12 21:59 — ChatGPT (FRONTEND) / FE-T08 — Cierre — America/Guayaquil

- Estado anterior: IN_PROGRESS.
- Estado nuevo: REVIEW; rama `feature/fe-t08-alertas`, base FRONT FE-T01. Contrato aprobado habilita la UI aunque BACK siga REVIEW.
- Implementado: pantalla de alertas Supervisor, indicadores de alertas abiertas obtenidos de BACK, filtros GET por estado/tipo, 25 filas por página, paginación con filtros preservados, estados/severidades con texto, fechas y vencimiento recibido, estado vacío y tabla móvil desplazable por teclado. Componentes reutilizables `pagination.html` y `ticket_badge.html` con consumidor real; no se calculan SLA ni permisos en FRONT.
- Archivos: `templates/helpdesk/alerts.html`, `templates/components/{pagination,ticket_badge,navbar}.html` y registros FRONT de `progress.md`.
- Pruebas sobre backend `5ea6941`: 451 PASS, cobertura 98.62 %; ruff check/format, Django check y makemigrations --check --dry-run PASS. Chromium 360/768/1280: Supervisor autorizado, Usuario 403, anónimo 302, contadores, filtros/limpiar/estado vacío, 25 filas y página 2 conservando filtros, escape de mensaje script, fechas iguales a BACK y ausencia de overflow del documento PASS. BD y archivos de prueba sintéticos y temporales, eliminados al terminar.
- Migraciones/endpoints nuevos: ninguno. Valores SLA de bandeja/detalle requieren el objeto `sla` de los contratos BE-T04/BE-T05; no se infiere tiempo restante en esta pantalla de alertas.
- Coordinación: FE-T03 PR #3 ya usa base `feature/fe-t01-login`; diff limitado al formulario/JS/enlaces/registros FRONT de esa tarea. PR #2 y #3 MERGEABLE y CI PASS. Seguimiento Cloud confirmado por UI ACTIVO cada hora en America/Guayaquil (id `6acd9bd4f1648190a92625ce9eefe1d5`); primera ejecución/GitHub/continuación pendientes de verificar, sin monitor duplicado.
- Nueva base detectada al cerrar: `b421f24` publica CONTRACT-008/009. Se sincronizará antes de publicar; FE-T04 queda habilitada por CONTRACT-008. FE-T02 aún no tiene contexto de dashboard: `home.html` solo recibe variables globales según CONTRACT-002. FE-T06 tiene contrato de listado, asignación todavía pendiente. No inferir endpoints ni acciones.

---

## 2026-10-12 22:02 — ChatGPT (FRONTEND) / FE-T08 — Sincronización de entrega — America/Guayaquil

- Base backend actualizada a `b421f24`, CONTRACT-008/009 y todos los registros BACK preservados.
- Validación sobre esa base: 483 pruebas PASS, cobertura 98.78 %, navegador FE-T01/FE-T08 PASS; archivos BACK sin diferencias respecto a la base.
- PR FE-T08 separado contra `feature/fe-t01-login`; alertas/filtros/paginación/badges y registros FRONT únicamente. Estado REVIEW, sin merge automático.
- Seguimiento Cloud ACTIVO cada hora según UI (id `6acd9bd4f1648190a92625ce9eefe1d5`); primera ejecución remota pendiente de verificar. FE-T04 será la siguiente tarea habilitada. FE-T02 requiere contrato de dashboard (CONTRACT-002 sigue sin tickets recientes).

---

## 2026-10-12 22:04 — ChatGPT (FRONTEND) / FE-T04 — Inicio — America/Guayaquil

- Estado anterior: TODO, desbloqueada por CONTRACT-008 en `b421f24`.
- Estado nuevo: IN_PROGRESS; rama `feature/fe-t04-listado-tickets`, base FE-T08 para reutilizar paginación/badges sin duplicarlos. Un PR separado.
- Alcance: listado de tickets autorizado por backend, filtros GET por estado/fechas (más campos ya publicados para roles de atención), paginación de 20 filas, valores SLA del objeto recibido. No enlaces de detalle ni transiciones sin contrato GET de detalle.
- Archivos previstos: `templates/helpdesk/ticket_list.html`, componentes de tabla/SLA/paginación, navegación y registros FRONT.
- Coordinación: FE-T08 entregada PR #4; FE-T02 espera CONTRACT-FRONT-002 para dashboard. FE-T06 dispone de CONTRACT-009 de lectura, asignación pendiente; se puede preparar listado sin acciones tras FE-T04. No cambios BACK ni monitor duplicado.

---

## 2026-10-12 22:09 — ChatGPT (FRONTEND) / FE-T04 — Cierre — America/Guayaquil

- Estado anterior: IN_PROGRESS.
- Estado nuevo: REVIEW; rama `feature/fe-t04-listado-tickets`, PR separado sobre FE-T08 para reutilizar componentes sin duplicación.
- Implementado: listado «Mis tickets» para Usuario / «Tickets» para otros roles, datos visibles provistos por BACK, filtros GET de estado/fechas/búsqueda/orden y filtros publicados de atención, 20 filas por página, fechas/SLA backend y estados vacíos. Componente `sla_badge.html` muestra state/due_at/remaining_minutes sin calcularlos; la paginación común usa querystring de Django para preservar todos los filtros.
- Archivos: `templates/helpdesk/ticket_list.html`, `templates/components/{ticket_table,sla_badge,pagination,navbar}.html`, registros FRONT de `progress.md`.
- Pruebas: suite vigente 483 PASS, cobertura 98.78 %, ruff check/format y diff check PASS. Chromium 360/768/1280: Usuario no ve ticket ajeno ni por código exacto; Supervisor sí, 20 filas/página y filtros estado/fechas preservados, búsqueda/limpiar/estado vacío, autoescape, tiempo restante idéntico a BACK y ausencia de enlaces de detalle no publicados PASS. La paginación FE-T08 se revalidó en navegador para evitar regresión.
- Incidencias corregidas: caso de responsable nulo detectado en navegador requería condicional de presentación para evitar resolver un atributo inexistente en un argumento default; corregido solo en plantilla. El helper necesitó buscar el ticket ajeno por código al probar Supervisor (el ticket era antiguo y no salía en la primera página); datos y expectativas corregidos fuera del checkout.
- Migraciones/endpoints/archivos BACK nuevos: ninguno. Datos sintéticos temporales eliminados al concluir. Se respeta CR-004 (tickets no visibles → 404 en descargas/acciones), sin inferir permisos FRONT.
- Pendientes: revisión humana; FE-T02 necesita contexto específico de dashboard (CONTRACT-FRONT-002). Próxima tarea con lectura habilitada: FE-T06, CONTRACT-009; sin inventar acciones de asignación pendientes BE-T06 ni acciones FE-T07 pendientes contexto BE-T05.
- Seguimiento Cloud: ACTIVO cada hora según UI, id `6acd9bd4f1648190a92625ce9eefe1d5`, primera ejecución aún no validada. No duplicados, no heartbeat local.

---

## 2026-10-12 22:12 — ChatGPT (FRONTEND) / FE-T06 — Inicio — America/Guayaquil

- Estado anterior: TODO (listado listo por CONTRACT-009; asignación pendiente).
- Estado nuevo: IN_PROGRESS, solo lectura habilitada; rama `feature/fe-t06-bandeja-agente`, base FE-T04 para reutilizar tabla/filtros/SLA.
- Alcance: vistas por pestaña y conteos provistos por BACK, filtros incluyendo responsable, prioridad/área/SLA y paginación. Navegación Agente/Supervisor solo de presentación; BACK valida acceso y visibilidad. No botones de asignación ni cambios de estado sin contrato/contexto autorizado.
- Archivos previstos: `templates/helpdesk/agent_inbox.html`, filtros comunes de presentación, navegación y registros FRONT. Contexto de asignación solicitado como CONTRACT-FRONT-003 en sección 12.
- FE-T04 entregada en PR #5; seguimiento Cloud ACTIVO cada hora según UI, primera ejecución pendiente. No monitor duplicado, datos reales ni cambios BACK.

---

## 2026-10-12 22:15 — ChatGPT (FRONTEND) / FE-T06 — Entrega de lectura — America/Guayaquil

- Estado anterior: IN_PROGRESS, lectura habilitada por CONTRACT-009.
- Estado nuevo: REVIEW **de lectura**; asignación/reasignación sigue pendiente BE-T06 y CONTRACT-FRONT-003. No se declara completada esa parte.
- Implementado: bandeja Agente/Supervisor, pestañas y conteos BACK, filtros compartidos con listado incluyendo responsable, orden/SLA/prioridad/área, 20 filas/página y querystring preservando tab/filtros, limpiar conservando pestaña, estado vacío y tabla responsive. Solo acciones GET de consulta; no se deducen permisos ni estados.
- Archivos: `templates/helpdesk/agent_inbox.html`, `templates/components/ticket_filters.html`, integración de filtros en `templates/helpdesk/ticket_list.html`, `templates/components/navbar.html`, registros FRONT.
- Pruebas: 483 PASS, cobertura 98.78 %; ruff check/format/diff check PASS. Chromium 360/768/1280: Usuario 403; Agente ve solo área/asignación/propios/triaje autorizados por BACK; pestañas y conteos, responsable, 20 filas y segunda página conservando tab/assignee, espera de usuario, vencidos, historial, limpiar/vacío y ausencia de formularios POST de acciones no contratadas PASS. Listado FE-T04 revalidado para la extracción de filtros. BD sintética temporal eliminada.
- Base vigente revisada: `b421f24`. No se han publicado dashboard FE-T02, detalle FE-T05/contexto allowed_targets FE-T07, asignación FE-T06 ni catálogos/métricas FE-T09/10. Sus acciones/vistas no se inventan; solicitudes FRONT concretas en sección 12 y PR #3/#5/este PR.
- Entregas previas: PR #2 FE-T01, #3 FE-T03, #4 FE-T08, #5 FE-T04; todos sin merge automático y con registros BACK preservados. Este PR queda sobre FE-T04 para diff exclusivo de lectura FE-T06.
- Seguimiento Cloud ACTIVO cada hora confirmado por UI, id `6acd9bd4f1648190a92625ce9eefe1d5`, America/Guayaquil. Primera ejecución/acceso GitHub/continuación automática aún no verificados; no se crea otro monitor.

---

## 2026-10-12 22:17 — ChatGPT (FRONTEND) / Entregas y reanudación Cloud — America/Guayaquil

- Entregas abiertas en REVIEW: FE-T01 PR #2 (`feature/fe-t01-login` → `main-r0dfx3`); FE-T03 PR #3 y FE-T08 PR #4 → FE-T01; FE-T04 PR #5 → FE-T08; FE-T06 lectura PR #6 → FE-T04. Cada diff contiene su tarea, sin merges a main ni force push.
- No retomar FE-T03 como TODO: su fila se actualiza para reflejar PR #3 ya publicado. Los registros FRONT de ramas separadas se sincronizan al revisar, conservando BACK íntegro.
- Continuación segura: fetch backend y PR propios, leer contratos/progress y preservar cambios locales. Solo iniciar tareas TODO con dependencia verificada o contrato aprobado; no duplicar trabajo IN_PROGRESS/REVIEW ni abrir segundo PR para la misma tarea. Completar asignación FE-T06 en su PR cuando BE-T06 publique contrato; detalle/acciones requieren BE-T05 y CONTRACT-FRONT-004.
- Solicitudes concretas pendientes: dashboard FE-T02 (CONTRACT-FRONT-002); asignación FE-T06 (003); detalle/conversación/allowed_targets FE-T05/07 (004; petición previa 001 en PR #3). FE-T09/10 esperan BE-T09/10 y sus contratos. No faltan credenciales de producción porque no se usan.
- Seguimiento único Cloud ACTIVO cada hora, America/Guayaquil, confirmado por UI: `6acd9bd4f1648190a92625ce9eefe1d5`; monitor local pausado según supervisor. No configurado cada 10 min; no se ha validado aún primera ejecución remota, acceso GitHub desde esa ejecución ni continuación automática de chat.

---

## 2026-10-13 01:27 — ChatGPT (FRONTEND) / FE-T01 — Branding y contraste — America/Guayaquil

- Estado: REVIEW; corrección FRONT autorizada por usuario. No se crea otro PR FE-T01.
- Logo: cherry-pick únicamente del commit de asset `c51bbd0`, rama institucional proporcionada por usuario. PNG original sin edición, 3000×3000, 105687 bytes, SHA256 `a47e0d829d9305a77183f1a2a95cb4a55776118161520737ed4b57ef8ef41fa4`; `object-fit: contain`, dimensiones cuadradas y alt «Universidad Indoamérica».
- Branding: morado principal `#3C235F`, naranja acento `#EA600A`, fondos blancos/neutros. Botones/enlaces/foco/paginación en morado; naranja reservado a logo/bordes decorativos porque naranja/blanco = 3.40:1. Tipografía de sistema provisional: el usuario no proporcionó fuente oficial; no se deduce del logo.
- Defectos corregidos: axe-core detectó texto secundario 4.44:1 y pestañas 4.26:1 sobre `#F8F9FA`; se ajustan colores compartidos. Morado/blanco = 13.14:1 y texto secundario/neutro = 5.81:1.
- Archivos: `static/img/LOGO-UTI-2.png`, `static/css/mesa.css`, `templates/auth/login.html`, `templates/components/navbar.html`, registros FRONT.
- Validación efectiva: Chromium 360/768/1280, logo no deformado y fondo real de botón morado, login/correo/error genérico/CSRF/logout/teclado PASS; axe-core 4.11.0 (integridad SHA512 verificada) WCAG2A/AA/2.1AA/2.2AA sin violaciones en login/error/inicio. Auditoría automatizada no sustituye revisión humana completa.
- Observaciones de Claude recibidas a través del usuario/repositorio, no comunicación directa: mergeability de ramas hermanas no demuestra integración. Se preparará rama conjunta `feature/integracion-mvp` autorizada explícitamente, validando navbar/progress y conservando registros BACK/FRONT; prohibido merge/push main hasta validación del usuario.
- Cambio remoto detectado: `main-r0dfx3` avanzó a `5ac611b` al integrar ramas FRONT por Claude. PR #1 sigue OPEN; PR #2 consta MERGED hacia esa rama, no hacia main. Esta corrección de FE-T01 se revisará en la rama/PR draft conjunto, preservando los PR por tarea existentes.

---

## 2026-10-13 01:35 — ChatGPT (FRONTEND) / Integración funcional para revisión — America/Guayaquil

- Autorización explícita del usuario: entregar una rama conjunta verificable de Claude + ChatGPT **antes** de pasar a main. Rama `feature/integracion-mvp`, base remota `main-r0dfx3` / `5ac611b`; main permanece `48e04a5`.
- Autoría: Claude = BACK; ChatGPT = FRONT. Coordinación mediante repositorio/progress y observaciones de Claude transmitidas por el usuario; no comunicación directa ni cambios manuales a BACK.
- Se integra FE-T01 actual (logo/branding), FE-T03 y la punta FE-T06 que contiene FE-T08/04. Todas las ramas/commits de tarea son ancestros de esta rama. Claude ya había integrado sus versiones previas en main-r0dfx3; no se duplican implementaciones.
- Conflictos de progress.md resueltos conservando las entradas de ambas ramas; navegación combinada mantiene Inicio, Nueva solicitud, Mis tickets/Tickets, Bandeja (Agente/Supervisor), Alertas (Supervisor) y logout POST/CSRF. La combinación se valida realmente, no solo mergeability individual. No se mezcló la rama antigua de identidad: se copió exclusivamente el commit PNG original.
- Capacidad operativa actual: login usuario/correo y sesión; creación con categoría/subcategoría/adjunto; listado y filtros de tickets autorizados; bandeja de lectura; alertas Supervisor. Django Templates + Bootstrap5 local + JS mínimo, branding morado/naranja accesible y tipografía de sistema provisional.
- Validación sobre la rama conjunta: **483 pruebas PASS, cobertura 98.78 %** contra PostgreSQL 16.15; Django check, migraciones sin cambios, ruff check/format, node --check y diff check PASS. Chromium real 360/768/1280: navegación de los cuatro roles y respuestas 200/403/302, login/correo/errores/CSRF/logout, crear/adjunto válido-inválido/descarga/uso sin JS, privacidad de listado, filtros/paginación y bandeja por área/asignación/triaje/alertas PASS. Datos y archivos sintéticos solo en BD temporal eliminada.
- axe-core 4.11.0 verificado SHA512: cero violaciones detectadas en login, error, inicio de los cuatro roles, creación, listado, alertas y bandeja para reglas WCAG2A/AA/2.1AA/2.2AA; no equivale a certificación completa. Logo original no deformado; botones/foco/enlaces morados y acento naranja decorativo, sin fuente oficial inventada.
- Verificación de conservación: archivos fuente BACK sin diferencias respecto a `5ac611b`; filas/historias/contratos BACK íntegros; IDs de contratos sin colisiones, solicitudes FRONT en espacio `CONTRACT-FRONT-*`; PNG idéntico al asset de usuario.
- Esta entrega **no es el MVP completo**: dashboard FE-T02, detalle/conversación FE-T05, acciones FE-T07 y asignación FE-T06 requieren contratos BACK pendientes; FE-T06 continúa REVIEW de lectura, sin operaciones de asignación. FE-T09/10 esperan BACK/contratos. No se inventan datos, vistas, formularios ni allowed_targets.
- Publicación prevista: rama conjunta + PR **DRAFT contra main** para validación del usuario, sin merge automático ni push main. PR #2 figura MERGED solo hacia main-r0dfx3 por la integración de Claude; PR #1 sigue OPEN. PR #3–#6 y ramas por tarea se conservan; no se anticipan retargets de main.
- Reproducción en este Cloud (helpers fuera del checkout): `source /workspace/.mesa-cloud/env.sh`; `bash /workspace/.mesa-cloud/start-db.sh`; `cd /workspace/ProductoFinalM4`; `source .venv/bin/activate`; `python manage.py migrate --noinput`; `python manage.py check`; `python manage.py runserver 127.0.0.1:8000 --noreload` en sesión persistente. Pruebas: `DJANGO_SETTINGS_MODULE=config.settings.test pytest --cov --cov-fail-under=80`; revisión funcional con `python /workspace/.mesa-cloud/validate_front.py --ticket --nav --audit --audit-strict --branding` y modos independientes `--list`, `--alerts`, `--inbox`. No crear usuarios reales ni usar secretos de producción.
- Seguimiento Cloud único ACTIVO cada hora según UI, America/Guayaquil, id `6acd9bd4f1648190a92625ce9eefe1d5`; primera ejecución/GitHub/continuación automática aún no verificados. No monitores duplicados ni dependencia de PC local.

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
Código implementado: BE-T01 (incluye BE-T02), BE-T03A, BE-T03, BE-T04, BE-T05, BE-T06, BE-T07 y BE-T08 en REVIEW; FRONT FE-T01, FE-T03, FE-T04, FE-T06 (lectura) y FE-T08 integrados
Migraciones: accounts 0001, 0002; helpdesk 0001-0009
Endpoints: login, logout, role_redirect, home, ticket_create, attachment_download (vistas web); admin de catálogos, auditoría y tickets
Pruebas: TEST-RUN-001 a TEST-RUN-007 PASS; E2E-RUN-001 PASS
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
- ~~Registro inicial en `TicketStatusHistory` (None → NEW) → BE-T07~~ — resuelto en BE-T07.
- ~~Restringir la descarga de adjuntos de Agentes a tickets de su área/asignación → BE-T04~~ — resuelto en BE-T04.
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
- Registro histórico de preparación: publicación y programación pendientes en ese momento. Resuelto posteriormente según UI: entorno publicado y seguimiento Cloud ACTIVO cada hora (id `6acd9bd4f1648190a92625ce9eefe1d5`); primera ejecución remota pendiente de validación.

## FE-T01 — Login y sesión — Cierre FRONT

**Estado:** REVIEW
**Agente:** ChatGPT (FRONTEND)
**Fecha:** 2026-10-12 21:40 — America/Guayaquil
**Base:** `main-r0dfx3`, `d91333f`; rama `feature/fe-t01-login`.
**Contratos:** CONTRACT-001/002/003, aprobados.

- Implementado: base, navegación y mensajes reutilizables de SPEC §18, campos login con labels/autocomplete, error genérico y CSRF, logout POST e inicio provisional por rol. Sin JavaScript adicional ni lógica de permisos FRONT.
- Migraciones/endpoints nuevos: ninguno. Solo consume vistas publicadas por BACK.
- Pruebas efectivas y archivos: ver historial FRONT en sección 16. Datos sintéticos exclusivamente en BD temporal, eliminada al cerrar validación; sin usuarios reales ni secretos de producción.
- Pendientes: revisión humana del FRONT/backend. PR #2 ya creado y conflicto resuelto; nunca merge automático ni push a main.
## BE-T07 — Workflow y estados — Cierre

**Estado:** REVIEW (pasa a DONE cuando el PR se apruebe y CI esté en verde)
**Agente:** Claude (BACKEND)
**Fecha:** 2026-10-13

### Implementado
- `helpdesk.workflow.TRANSITIONS`: las 17 transiciones de SPEC §32.1 como datos (origen, destino, actores permitidos, motivo obligatorio). Toda otra transición está prohibida.
- Actores: `SYSTEM` (proceso backend, `actor=None`), `OWNER` (solicitante), `AGENT`, `ASSIGNED_AGENT`, `SUPERVISOR`. Administrador no opera tickets (ADR-023).
- `workflow.transition(ticket, target, *, actor, reason, expected_version)` (= `TicketService.change_status`): bloquea la fila, comprueba versión (bloqueo optimista), regla, actor, motivo y condiciones; aplica efectos; incrementa `version`; escribe `TicketStatusHistory` y `AuditLog` (`STATUS_CHANGE`); todo en una transacción.
- Condiciones: `ASSIGNED` exige área o responsable; reapertura solo dentro de `REOPEN_WINDOW_DAYS`.
- Efectos: `assigned_at`, `resolved_at`, `closed_at`; reabrir limpia resolución/cierre; rechazo de resolución limpia `resolved_at` y conserva el SLA; `REOPENED → ASSIGNED` vuelve al último responsable solo si sigue activo.
- `workflow.allowed_targets(ticket, user)`: estados alcanzables por el usuario (para que FRONT muestre solo acciones válidas).
- Errores con mensajes de SPEC §19: `InvalidTransition`, `TransitionForbidden` (403), `ReasonRequired`, `StaleTicket`.
- `TicketService.create` ahora registra la entrada inicial `— → NEW` al crearse.
- Vistas POST de SPEC §47.1 (CONTRACT-006) y comando `close_stale_tickets` (filas 9 y 14).
- Constantes en settings: `WAITING_USER_TIMEOUT_DAYS=7`, `AUTO_CLOSE_DAYS=3`, `REOPEN_WINDOW_DAYS=7`.

### Archivos creados/modificados
- `apps/helpdesk/{workflow,models,tickets,audit,forms,views,urls}.py`
- `apps/helpdesk/management/commands/close_stale_tickets.py`
- `apps/helpdesk/migrations/0005_ticket_status_history.py`
- `apps/helpdesk/tests/{test_workflow,test_workflow_views,test_close_stale_tickets}.py`
- `config/settings/base.py`

### Criterio de aceptación
- Transiciones inválidas o no permitidas al rol rechazadas: matriz completa probada (17 × 7 actores + 73 transiciones fuera de tabla).
- Actualización concurrente detectada: dos hilos con la misma versión → uno gana, el otro recibe `StaleTicket`.

### Operación (cron, SPEC §38.1)
```cron
0 * * * *  cd /ruta/proyecto && .venv/bin/python manage.py close_stale_tickets
```

### Decisiones tomadas
- ADR-023, ADR-024, ADR-025.

### Pendientes derivados
- ~~Crear `Alert` de tipo `ESCALATED` al escalar (filas 6 y 10) → BE-T08~~ — resuelto en BE-T08.
- ~~Exponer `allowed_targets` y el historial en el contexto del detalle → BE-T05~~ — resuelto (CONTRACT-010).
- ~~Restringir `AGENT` (filas 1, 3 y 8) a tickets de su área → BE-T04~~ — resuelto en BE-T04.
- ~~`WAITING_USER → IN_PROGRESS` automático cuando el usuario responda → BE-T05~~ — resuelto.

## 2026-10-13 — Claude (BACKEND) / BE-T07

- Estado anterior: TODO.
- Estado nuevo: REVIEW.
- Trabajo realizado: máquina de estados, historial, bloqueo optimista, acciones POST, comando de cierre automático, CONTRACT-006.
- Archivos: ver cierre de BE-T07.
- Pruebas: TEST-RUN-004 PASS.
- Observaciones: desbloquea BE-T08 (SLA y alertas) y las acciones de FE-T07.

## BE-T08 — SLA y alertas — Cierre

**Estado:** REVIEW (pasa a DONE cuando el PR se apruebe y CI esté en verde)
**Agente:** Claude (BACKEND)
**Fecha:** 2026-10-13

### Implementado
- `helpdesk.SLAPolicy` (SPEC §26): por prioridad y opcionalmente por categoría; una activa por (categoría, prioridad); resolución ≥ primera respuesta; administrable como catálogo (auditado, sin borrado).
- `helpdesk.Alert` (SPEC §26): tipos `SLA_WARNING`, `SLA_BREACHED`, `ESCALATED`; una abierta por tipo y ticket (restricción en BD).
- `helpdesk.sla`: calendario laboral (`BUSINESS_HOURS`, `HOLIDAYS`, `TIME_ZONE`): `add_business_minutes`, `business_minutes_between`; modo 24×7; `policy_for`; `apply_due_dates`; `sla_status` (estado, vencimiento, minutos restantes, % consumido).
- `TicketService.create` fija `first_response_due_at` y `sla_due_at` desde `created_at`.
- `helpdesk.alerts`: `open_alert` (idempotente, tolera carreras) y `resolve_alerts`.
- Workflow: al escalar abre alerta `ESCALATED`; al salir de `ESCALATED` la resuelve; al resolver/cerrar/cancelar resuelve todas las alertas del ticket.
- Comando `check_sla`: alerta al 80 % (`SLA_WARNING_RATIO`), alerta de vencimiento y escalamiento automático; idempotente.
- Vista `helpdesk:alert_list` (CONTRACT-007) y admin de políticas y alertas.

### Archivos creados/modificados
- `apps/helpdesk/{sla,alerts,models,tickets,workflow,views,urls,admin}.py`
- `apps/helpdesk/management/commands/check_sla.py`
- `apps/helpdesk/migrations/0006_sla_and_alerts.py`, `0007_initial_sla_policies.py`
- `apps/helpdesk/tests/{test_sla,test_check_sla}.py` (+ ajustes en `test_permissions`, `test_tickets`)
- `config/settings/base.py` (`BUSINESS_HOURS`, `HOLIDAYS` por variable de entorno, `SLA_WARNING_RATIO`)
- `templates/helpdesk/alerts.html` — **TEMPORAL (backend)**.

### Criterio de aceptación
- Alertas correctas al aproximarse (≥ 80 %) y al vencer: probado con reloj controlado.
- Cálculo correcto cruzando fines de semana y fuera de horario: probado (viernes → lunes, noche, sábado, feriados, inversa).

### Operación (cron, SPEC §38.1)
```cron
*/5 * * * *  cd /ruta/proyecto && .venv/bin/python manage.py check_sla
```

### Decisiones tomadas
- ADR-026, ADR-027, ADR-028, ADR-029.

### Pendientes derivados
- Alertas de **primera respuesta** (`first_response_due_at`): el plazo ya se calcula, pero `first_response_at` lo fija la primera respuesta del agente → BE-T05.
- Exponer `sla_status` en bandeja y detalle → contratos de BE-T04 / BE-T05.
- Recalcular plazos si cambia la prioridad → cuando exista el cambio de prioridad (BE-T06/BE-T09).
- Pausar el SLA en `WAITING_USER`: la SPEC no lo pide; el reloj sigue corriendo. Decidir si se quiere (CHANGE REQUEST).
- Alertas de «fallos operativos» (FE-007) → BE-T12 (worker WhatsApp).

## 2026-10-13 — Claude (BACKEND) / BE-T08

- Estado anterior: TODO.
- Estado nuevo: REVIEW.
- Trabajo realizado: políticas SLA, calendario laboral, plazos al crear, alertas, `check_sla` con escalamiento automático, vista de alertas, CONTRACT-007.
- Archivos: ver cierre de BE-T08.
- Pruebas: TEST-RUN-005 PASS.
- Observaciones: FE-T08 queda desbloqueada; desbloquea BE-T10 (métricas).

## BE-T04 — Consulta, filtros y paginación — Cierre

**Estado:** REVIEW (pasa a DONE cuando el PR se apruebe y CI esté en verde)
**Agente:** Claude (BACKEND)
**Fecha:** 2026-10-13

### Implementado
- `helpdesk.queries.visible_tickets(user)`: control horizontal por rol (ADR-030), sin duplicados; `can_view_ticket` y `get_visible_ticket_or_404`.
- `Area.agents` (CR-003) con servicio auditado `catalogs.set_area_agents` (solo agentes activos) y selector en el admin de áreas.
- `queries.apply_filters`: estado (incl. `OPEN`/`FINISHED`), prioridad, categoría, área, responsable (`me`/`none`/id), fechas, SLA (`WARNING`/`BREACHED`), texto y orden; valores inválidos ignorados; devuelve los filtros aplicados.
- `queries.ticket_rows`: ticket + estado SLA sin consultas por fila (`sla.policy_index`).
- Vistas `helpdesk:ticket_list` (CONTRACT-008) y `helpdesk:agent_inbox` con las 7 pestañas de SPEC §10 (CONTRACT-009), 20 por página.
- La descarga de adjuntos y las acciones de estado usan la misma visibilidad (404 si no es visible, CR-004); el actor «Agente» del workflow exige visibilidad (ADR-032).
- Eliminado `accounts.permissions.check_owner_or_staff` (y `STAFF_ROLES`): quedó sin uso y era más laxo que la nueva regla; el control horizontal vive solo en `helpdesk.queries`.

### Archivos creados/modificados
- `apps/helpdesk/{queries,models,catalogs,sla,views,urls,workflow,admin}.py`
- `apps/helpdesk/migrations/0008_area_agents.py`
- `apps/helpdesk/tests/test_queries.py` (+ ajustes en `test_workflow`, `test_workflow_views`, `test_ticket_views`, `test_admin`, `test_catalogs`)
- `apps/accounts/{permissions,roles}.py`, `apps/accounts/tests/test_permissions.py`
- `templates/helpdesk/{ticket_list,agent_inbox}.html` — **TEMPORAL (backend)**.

### Criterio de aceptación
- Resultados correctos por rol: matriz de visibilidad para Usuario, Agente (con y sin áreas, asignado fuera de su área, triaje), Supervisor y Administrador.

### Decisiones tomadas
- ADR-030, ADR-031, ADR-032; CR-003, CR-004.

### Pendientes derivados
- Pantalla de administración de áreas con selección de agentes → FE-T09 (hoy en Django admin).
- ~~Mostrar en la bandeja acciones de asignación → BE-T06~~ — resuelto (CONTRACT-012).

## 2026-10-13 — Claude (BACKEND) / BE-T04

- Estado anterior: TODO.
- Estado nuevo: REVIEW.
- Trabajo realizado: visibilidad por rol, agentes por área, filtros, pestañas de bandeja, paginación, CONTRACT-008/009, CR-003/004.
- Archivos: ver cierre de BE-T04.
- Pruebas: TEST-RUN-006 PASS.
- Observaciones: FE-T04 desbloqueada; FE-T06 puede maquetar el listado (la asignación llega con BE-T06).

## BE-T05 — Mensajes y conversaciones — Cierre

**Estado:** REVIEW (pasa a DONE cuando el PR se apruebe y CI esté en verde)
**Agente:** Claude (BACKEND)
**Fecha:** 2026-10-13

### Implementado
- `Conversation` (una activa por usuario y canal) y `TicketMessage` (SPEC §26) con tipos `TEXT`, `INFO_REQUEST`, `RESOLUTION`; `external_message_id` único para la idempotencia de WhatsApp (BE-T11); `Attachment.message`.
- `helpdesk.conversations` (ConversationService): `add_message` (reglas ADR-033, primera respuesta ADR-034, fila 8 automática, solicitud de información), `timeline` (mensajes + cambios de estado en orden), `can_reply`.
- La resolución se publica como mensaje (ADR-035).
- Vistas `ticket_detail` (CONTRACT-010) y `ticket_message` (CONTRACT-011); creación y acciones vuelven al detalle (CR-005).

### Criterio de aceptación
- «Web y WhatsApp comparten ticket e histórico»: probado con mensajes de ambos canales en el mismo ticket y conversación por canal. La **entrada real** por WhatsApp llega con BE-T11 (webhook), que usará `add_message(channel="WHATSAPP", external_message_id=…)`.

### Pendientes derivados
- Alertas de SLA de **primera respuesta** (ya existe `first_response_at`) → ampliar `check_sla`.
- Página 404 propia con la navegación → FRONT (`templates/404.html`).

## BE-T06 — Asignación y reasignación — Cierre

**Estado:** REVIEW (pasa a DONE cuando el PR se apruebe y CI esté en verde)
**Agente:** Claude (BACKEND)
**Fecha:** 2026-10-13

### Implementado
- `helpdesk.assignment`: `assign` (= `TicketService.assign`) con bloqueo optimista, reglas ADR-036, avance de estado ADR-037 y auditoría `ASSIGN`/`REASSIGN` con valores anteriores y nuevos; `assign_options` (opciones autorizadas para la UI).
- Vista `ticket_assign` (CONTRACT-012).

### Criterio de aceptación
- «Cambios trazables y autorizados»: auditoría probada; matriz de permisos (Supervisor, Agente dentro/fuera de su área, Usuario, Administrador, ticket escalado, ticket terminado).

## Entrega integrada BACK + FRONT — 2026-10-13

- Pedido del responsable: una rama funcional única, verificable, para pasar a `main`.
- `main-r0dfx3` integra FE-T01/03/04/06/08 (ChatGPT) con BE-T01..T08 (Claude) y BE-T05/T06 nuevos.
- Verificación: TEST-RUN-007 (535 pruebas) y E2E-RUN-001 (navegador real, 5 roles). Guía paso a paso en `README.md` («Cómo verificar el MVP»), usuarios demo con `seed_demo`.
- Para FRONT: contratos 010-013 publicados; ver sección 3.2 sobre los dos archivos FRONT tocados por BACK y la plantilla temporal del detalle.
