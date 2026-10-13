# SPEC v5.2 — MVP Mesa de Ayuda Omnicanal
## Documento unificado FRONT + BACK

**Versión:** 5.2  
**Fecha:** 2026-10-12  
**Estado:** Especificación técnica consolidada para implementación  
**Stack base:** Django + HTML + Bootstrap + PostgreSQL  
**Canales:** Web + WhatsApp  
**SGA:** desacoplado; no requerido para ejecutar el MVP  
**IA:** agéntica y controlada, orquestada con **LangGraph** (grafo de estados); no ejecuta acciones administrativas críticas  
**Objetivo de esta versión:** mantener FRONT y BACK dentro del mismo SPEC, claramente separados, evitando duplicidad, módulos innecesarios y sobrearquitectura.

---

# 0. Control de versiones

| Versión | Fecha | Cambio principal |
|---|---|---|
| 5.0 | — | Unificación FRONT + BACK en un único documento. |
| 5.1 | — | PostgreSQL como base de datos y backlog de tareas FE/BE. |
| 5.2 | 2026-10-12 | Corrección de inconsistencias detectadas en revisión (ver tabla siguiente). |

## 0.1 Cambios de la v5.2

| # | Problema en v5.1 | Corrección en v5.2 | Sección |
|---|---|---|---|
| 1 | Título interno decía “v5.0” y no había control de versiones. | Título corregido y tabla de versiones. | 0 |
| 2 | Workflow incompleto: `ESCALATED`, `CANCELLED` y `REOPENED` sin transiciones de entrada/salida. | Máquina de estados completa. | 32 |
| 3 | No existía flujo de rechazo de la resolución por parte del usuario. | Transición `RESOLVED → IN_PROGRESS` (rechazo) y cierre automático. | 32 |
| 4 | Las transiciones no indicaban qué rol puede ejecutarlas. | Tabla de transiciones con rol permitido. | 32 |
| 5 | WhatsApp entregaba datos sensibles (notas, deuda) sin autenticación definida. | Teléfono verificado + código de vinculación desde portal. | 35.1 |
| 6 | FE-003 permitía adjuntos pero no existía modelo. | Modelo `Attachment` y restricciones. | 26 |
| 7 | El ticket no guardaba la intención que lo originó. | Campo `Ticket.intent`. | 26 |
| 8 | Mensaje “El ticket fue actualizado por otro usuario” sin mecanismo de control de concurrencia. | Campo `Ticket.version` (bloqueo optimista). | 26 |
| 9 | Fuente de conocimiento N1 indefinida (RAG está prohibido). | N1 usa `IntentAction.response_template` y constantes; sin RAG. | 31.1 |
| 10 | API REST sin consumidor (viola regla 56.6); el front es server-rendered. | Solo webhook WhatsApp como API; el front usa vistas Django. | 47 |
| 11 | Faltaban acciones de resolver, escalar, reabrir y confirmar. | Rutas de acción explícitas. | 47 |
| 12 | Worker y SLA sin mecanismo de ejecución periódica. | Comandos de gestión + cron/systemd timer. | 38 |
| 13 | `business_hours_only` sin calendario definido. | Calendario laboral como constante en settings. | 34 |
| 14 | Proveedor WhatsApp no especificado. | Meta WhatsApp Cloud API. | 35 |
| 15 | Proveedor LLM no definido y presentado como cerrado. | Decisión abierta (ADR pendiente), con `FakeLLMProvider` por defecto. | 42 |
| 16 | Catálogos (`Area`, `Category`, `Subcategory`) y `AuditLog` sin tarea en backlog. | Nueva tarea BE-T03A. | 60.4 |
| 17 | BE-T01/BE-T02 separadas pese a requerir una única migración inicial de usuario; dataset de IA solo en BE-T20. | BE-T01 absorbe BE-T02; dataset etiquetado se adelanta a BE-T17; dependencia SLA explícita. | 60.4 |
| 18 | La IA era un conjunto de llamadas sueltas (clasificar, extraer, resumir) sin orquestación: el sistema no podía considerarse **agéntico**. | Orquestación agéntica con **LangGraph**: Intent Engine, Autonomy Engine, herramientas y revisión humana como nodos y aristas de un grafo de estados versionado. Se levanta la prohibición genérica de “agents” y se sustituye por reglas de agente controlado. | 2, 3.5, 4, 5, 24, 30, 31, 43, 46A, 52, 54, 55, 56, 58, 60.4 |

---

# 1. Propósito

Construir un MVP de Mesa de Ayuda Omnicanal capaz de:

1. recibir solicitudes desde portal web y WhatsApp;
2. responder automáticamente consultas simples y verificables;
3. clasificar solicitudes mediante reglas y, cuando aporte valor, mediante un LLM;
4. crear tickets cuando la solicitud requiera seguimiento;
5. enrutar tickets al área responsable;
6. controlar estados, prioridades, SLA, conversaciones y auditoría;
7. mantener trazabilidad de las decisiones de IA;
8. funcionar sin conexión real al SGA;
9. incorporar posteriormente un proveedor SGA sin modificar la lógica principal;
10. presentar una interfaz web simple, usable y coherente con los roles del sistema.

---

# 2. Principios de simplificación

- Arquitectura monolítica modular con Django.
- No crear una app Django por cada concepto.
- No introducir microservicios.
- No introducir Redis/Celery inicialmente.
- No usar motor externo de reglas.
- No usar motor externo de workflow.
- No crear módulo independiente de notificaciones.
- No crear módulo independiente de catálogos.
- No duplicar usuarios institucionales.
- No permitir que el LLM consulte directamente tablas ni ejecute acciones de negocio.
- Toda orquestación agéntica se modela como **grafo LangGraph** (sección 46A); no se crean bucles de agente ad hoc ni cadenas de prompts fuera del grafo.
- No almacenar como tabla configuraciones que pueden mantenerse como constantes.
- No implementar funciones futuras sin vínculo con un caso de aceptación.
- No incorporar SPA ni frameworks JavaScript adicionales.

---

# 3. Alcance funcional

## 3.1 Atención automática

- Consultar horario.
- Consultar notas.
- Consultar deuda pendiente.
- Consultar estado de matrícula.
- Consultar materias matriculadas.
- Consultar estado de ticket.
- Consultar fechas académicas parametrizadas.
- Consultar contactos institucionales.
- Consultar requisitos parametrizados.

## 3.2 Gestión de tickets

- creación;
- consulta;
- asignación;
- reasignación;
- estados;
- prioridad;
- SLA;
- mensajes;
- historial;
- auditoría;
- alertas;
- resolución;
- cierre;
- reapertura.

## 3.3 WhatsApp

- webhook;
- recepción;
- envío;
- asociación usuario/teléfono;
- conversaciones;
- idempotencia;
- reintentos;
- continuidad con tickets creados desde web.

## 3.4 Automatización

- catálogo de intenciones;
- clasificación determinística inicial;
- nivel de autonomía;
- reglas de enrutamiento;
- respuestas automáticas.

## 3.5 IA / LLM

- clasificación semántica;
- extracción de entidades;
- resumen;
- respuesta asistida sobre contenido autorizado;
- contexto conversacional;
- validación estructural;
- fallback;
- métricas;
- trazabilidad;
- **orquestación agéntica con LangGraph**: grafo de estados que decide, invoca herramientas autorizadas, se autocorrige (reintento/fallback) y pausa para revisión humana (sección 46A).

## 3.6 Integración institucional

- interfaz `InstitutionalDataProvider`;
- `LocalProvider` funcional para el MVP;
- `SGAProvider` como implementación futura.

---

# 4. Fuera de alcance

- modificar notas;
- eliminar deuda;
- modificar matrícula;
- aprobar solicitudes;
- ejecutar transacciones financieras;
- cambiar datos maestros;
- resolver automáticamente reclamos administrativos;
- entrenar un LLM propio;
- usar el LLM como fuente oficial;
- implementar microservicios;
- implementar bus de eventos;
- implementar Kubernetes;
- implementar múltiples bases de datos;
- implementar dashboards BI avanzados;
- implementar app móvil nativa;
- implementar RAG o MCP en el MVP;
- agentes **sin control**: sin grafo definido, con herramientas de escritura libres, multiagente abierto o sin revisión humana (el agente permitido es el de la sección 46A);
- LangGraph Platform/Server, LangGraph Cloud o LangSmith obligatorio (el grafo corre embebido en Django).

---

# 5. Arquitectura general

```text
┌──────────────────────────────────────────────────────────────┐
│                         FRONT                                │
│                                                              │
│   Portal Web - Django Templates + HTML + Bootstrap           │
│                                                              │
│   Login │ Tickets │ Bandejas │ Conversaciones │ Métricas     │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                      BACKEND DJANGO                          │
│                                                              │
│ Views / Forms / API / Webhooks / Auth                        │
│                                                              │
│ Services:                                                    │
│ TicketService                                                │
│ ConversationService                                          │
│ AutomationService                                            │
│ InstitutionalQueryService                                    │
│ AIService                                                    │
│ AgentGraph (LangGraph) ── orquesta Intent/Autonomy/Tools     │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                     DOMINIO                                  │
│                                                              │
│ Workflow │ SLA │ Intents │ Autonomy │ Routing │ Audit        │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    INTEGRACIONES                             │
│                                                              │
│ WhatsAppClient                                               │
│ InstitutionalDataProvider                                    │
│   ├── LocalProvider                                          │
│   └── SGAProvider                                            │
│ LLMProvider                                                  │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                         PostgreSQL                           │
└──────────────────────────────────────────────────────────────┘
```

## 5.1 Justificación de PostgreSQL (v5.2)

- **Concurrencia:** `SELECT ... FOR UPDATE SKIP LOCKED` permite que el worker procese inbox/outbox sin Redis/Celery y sin doble procesamiento.
- **Generación de códigos únicos:** secuencias nativas garantizan `ticket_code` sin duplicados bajo concurrencia (criterio de BE-T03).
- **JSON:** `jsonb` para `payload_json`, `AuditLog` y salidas IA, con validación en aplicación.
- **Integridad:** restricciones únicas parciales (ej. `phone` único solo si no está vacío) y `CHECK` constraints.
- **Paridad dev/CI/prod:** el mismo motor en las tres etapas; SQLite no se usa ni siquiera en pruebas.

---

# 6. Estructura del proyecto

```text
project/
│
├── config/
│   ├── settings/
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── accounts/
│   ├── helpdesk/
│   ├── automation/
│   ├── integrations/
│   └── ai/
│
├── templates/
├── static/
├── media/
└── manage.py
```

Se utilizarán únicamente cinco apps Django funcionales.

---

# PARTE A — FRONTEND

# 7. Objetivo del frontend

El frontend deberá permitir que usuarios, agentes, supervisores y administradores interactúen con el sistema sin exponer complejidad técnica.

Tecnologías:

```text
Django Templates
HTML5
Bootstrap
JavaScript mínimo
```

No se implementará SPA.

---

# 8. Principios del frontend

1. Server-rendered.
2. Bootstrap como framework visual.
3. JavaScript solo donde aporte interacción.
4. No duplicar lógica crítica del backend.
5. Acciones sensibles siempre validadas en servidor.
6. Responsive.
7. Interfaces dependientes del rol.
8. Sin exposición de secretos, prompts o configuraciones internas.
9. No usar React, Vue, Angular o similares.
10. No crear páginas sin caso de uso.

---

# 9. Roles y experiencia

## 9.1 Usuario

Puede:

- iniciar sesión;
- crear solicitud;
- consultar sus tickets;
- visualizar estado;
- leer respuestas;
- responder;
- consultar información autorizada.

## 9.2 Agente

Puede:

- consultar tickets autorizados;
- filtrar;
- responder;
- solicitar información;
- cambiar estados permitidos;
- resolver;
- reasignar cuando tenga permiso.

## 9.3 Supervisor

Puede:

- revisar varias áreas;
- reasignar;
- escalar;
- revisar vencimientos;
- revisar métricas.

## 9.4 Administrador

Puede:

- gestionar áreas;
- categorías;
- subcategorías;
- intenciones;
- routing;
- SLA;
- configuración operativa permitida.

---

# 10. Navegación

## Usuario

```text
Inicio
├── Nueva solicitud
├── Mis tickets
├── Consultar ticket
└── Perfil
    └── Vincular WhatsApp
```

## Agente

```text
Panel
├── Mi bandeja
├── Sin asignar
├── En proceso
├── Pendientes de usuario
├── Por vencer
├── Vencidos
└── Historial
```

## Supervisor

```text
Panel
├── Tickets
├── Áreas
├── Alertas
├── SLA
└── Métricas
```

## Administrador

```text
Administración
├── Categorías
├── Subcategorías
├── Áreas
├── Intenciones
├── Routing
└── SLA
```

---

# 11. Pantallas obligatorias

## FE-001 — Login

Campos:

- usuario/correo;
- contraseña.

Requisitos:

- error genérico;
- CSRF;
- redirección por rol.

## FE-002 — Inicio

Mostrar:

- nueva solicitud;
- últimos tickets;
- estado;
- última actualización.

## FE-003 — Crear ticket

Campos:

- asunto;
- categoría opcional;
- descripción;
- adjunto opcional.

El frontend no calcula:

- código;
- prioridad efectiva;
- SLA;
- área;
- estado final.

## FE-004 — Mis tickets

Columnas:

- código;
- asunto;
- estado;
- categoría;
- fecha;
- última actualización.

Filtros:

- estado;
- fecha.

Paginación obligatoria.

## FE-005 — Detalle de ticket

Cabecera:

- código;
- asunto;
- estado;
- prioridad;
- categoría;
- área;
- responsable;
- fecha;
- SLA.

Conversación:

- orden cronológico;
- remitente;
- canal;
- mensajes del sistema.

Acciones usuario:

- responder;
- adjuntar;
- confirmar resolución cuando aplique.

Acciones agente:

- responder;
- solicitar información;
- asignar;
- reasignar;
- cambiar estado;
- resolver;
- escalar.

## FE-006 — Bandeja del agente

Columnas:

- ticket;
- usuario;
- asunto;
- categoría;
- estado;
- prioridad;
- área;
- responsable;
- tiempo SLA;
- actualización.

Filtros:

- estado;
- prioridad;
- categoría;
- área;
- responsable;
- fecha;
- SLA.

## FE-007 — Alertas

Mostrar:

- próximos a vencer;
- vencidos;
- escalados;
- fallos operativos relevantes.

## FE-008 — Administración

CRUD limitado a:

- áreas;
- categorías;
- subcategorías;
- intenciones;
- routing;
- SLA.

## FE-009 — Métricas

- abiertos;
- cerrados;
- por área;
- por categoría;
- dentro/fuera de SLA;
- primera respuesta;
- resolución;
- tickets por canal.

---

# 12. Estados visuales

```text
NEW → Nuevo
CLASSIFIED → Clasificado
ASSIGNED → Asignado
IN_PROGRESS → En proceso
WAITING_USER → Esperando usuario
RESOLVED → Resuelto
CLOSED → Cerrado
ESCALATED → Escalado
REOPENED → Reabierto
CANCELLED → Cancelado
```

No depender únicamente de color.

---

# 13. Prioridades visuales

```text
LOW → Baja
MEDIUM → Media
HIGH → Alta
CRITICAL → Crítica
```

El backend es la fuente de verdad.

---

# 14. Conversación omnicanal

Web y WhatsApp deberán aparecer dentro del mismo histórico.

Ejemplo:

```text
[WhatsApp] Usuario: Mi nota está incorrecta
[Sistema] Ticket HD-2026-000123 creado
[Web] Agente: Estamos revisando el caso
[WhatsApp] Usuario: Gracias
```

---

# 15. Formularios y validación frontend

Puede validar:

- requerido;
- longitud;
- formato;
- tamaño;
- extensión.

El backend deberá repetir todas las validaciones.

---

# 16. Accesibilidad y responsive

Mínimos:

- labels;
- teclado;
- contraste;
- errores comprensibles;
- tablas responsivas;
- estados con texto.

Prioridad:

```text
Panel agente → Desktop
Portal usuario → Desktop + móvil
Administración → Desktop
```

---

# 17. Plantillas sugeridas

```text
templates/
├── base.html
├── auth/
│   └── login.html
├── helpdesk/
│   ├── dashboard.html
│   ├── ticket_list.html
│   ├── ticket_form.html
│   ├── ticket_detail.html
│   ├── alerts.html
│   └── metrics.html
└── admin_ui/
    ├── categories.html
    ├── areas.html
    ├── intents.html
    ├── routing.html
    └── sla.html
```

---

# 18. Componentes UI reutilizables

```text
components/
├── navbar.html
├── messages.html
├── pagination.html
├── ticket_badge.html
├── sla_badge.html
└── conversation_message.html
```

No crear un design system independiente.

---

# 19. Manejo de errores frontend

Mensajes permitidos:

- “No fue posible guardar la solicitud.”
- “No tiene permisos para realizar esta acción.”
- “El ticket fue actualizado por otro usuario.”
- “El servicio no se encuentra disponible temporalmente.”

No mostrar:

- traceback;
- SQL;
- prompt;
- API keys;
- errores internos del proveedor.

---

# 20. Seguridad frontend

- CSRF;
- autoescape;
- sanitización;
- no usar `|safe` sin justificación;
- no almacenar secretos en JS;
- no exponer IDs de terceros;
- control de adjuntos;
- permisos validados también en backend.

---

# 21. Pruebas frontend

- login;
- permisos;
- creación ticket;
- listado;
- filtros;
- paginación;
- detalle;
- respuesta;
- reasignación;
- cambio estado;
- SLA;
- conversación Web/WhatsApp;
- responsive.

---

# 22. Elementos que NO deben generarse en frontend

```text
React
Vue
Angular
Next.js
Nuxt
Redux
SPA
PWA
WebSockets
GraphQL client
mobile app
design system independiente
state manager externo
frontend microservices
```

---

# PARTE B — BACKEND

# 23. Objetivo del backend

El backend es responsable de:

- autenticación;
- autorización;
- persistencia;
- tickets;
- conversaciones;
- workflow;
- SLA;
- auditoría;
- intenciones;
- autonomía;
- routing;
- WhatsApp;
- proveedor institucional;
- IA;
- fallback;
- métricas;
- seguridad;
- API.

---

# 24. Apps Django

## `accounts`

- usuario;
- autenticación;
- roles;
- permisos;
- teléfono;
- identificador institucional.

Usar `AbstractUser`, `Groups`, `Permissions`.

## `helpdesk`

- tickets;
- categorías;
- subcategorías;
- áreas;
- conversaciones;
- mensajes;
- estados;
- SLA;
- alertas;
- auditoría.

## `automation`

- intenciones;
- acciones;
- autonomía;
- routing.

## `integrations`

- WhatsApp;
- inbox/outbox;
- LocalProvider;
- SGAProvider.

## `ai`

- LLMProvider;
- clasificación;
- extracción;
- resumen;
- prompts;
- métricas;
- validación;
- fallback;
- decisiones IA;
- **grafo agéntico LangGraph** (`apps/ai/agent/`: estado, nodos, herramientas, construcción del grafo, checkpointer).

---

# 25. Modelo de usuario

```text
User (AbstractUser)
- id
- username
- first_name
- last_name
- email
- phone              (E.164, único si no está vacío)
- phone_verified_at  (null = teléfono no verificado para WhatsApp)
- external_id        (identificador institucional, único si no está vacío)
- source             (LOCAL | SGA | WHATSAPP)
- is_active
```

`AUTH_USER_MODEL = "accounts.User"` debe definirse antes de la primera migración.

`phone_verified_at` se incorpora en v5.2 para soportar la autenticación por WhatsApp (sección 35.1).

Roles mediante Groups:

```text
Usuario
Agente
Supervisor
Administrador
```

---

# 26. Modelo de datos Helpdesk

## `Area`

```text
id
code
name
email
is_active
```

## `Category`

```text
id
code
name
default_area_id
is_active
```

## `Subcategory`

```text
id
category_id
code
name
is_active
```

## `Ticket`

```text
id
ticket_code
user_id
channel
intent_id              (nullable; intención que originó el ticket — v5.2)
category_id
subcategory_id
priority
status
assigned_area_id
assigned_user_id
subject
description
classification_source
classification_score
version                (entero; bloqueo optimista — v5.2)
created_at
assigned_at
first_response_at
resolved_at
closed_at
first_response_due_at  (v5.2)
sla_due_at
updated_at
```

Reglas:

- `ticket_code` con formato `HD-AAAA-NNNNNN`, generado en backend dentro de transacción (secuencia PostgreSQL), nunca en frontend.
- `version` se incrementa en cada actualización. Toda actualización desde UI envía la versión leída; si no coincide, se rechaza y se muestra “El ticket fue actualizado por otro usuario.”
- `intent_id` permite medir automatización por intención y alimentar métricas IA.

## `Attachment` (v5.2)

```text
id
ticket_id
message_id        (nullable)
uploaded_by_id
file              (FileField en MEDIA_ROOT/attachments/AAAA/MM/)
original_name
content_type
size_bytes
created_at
```

Restricciones:

- extensiones permitidas: `pdf`, `png`, `jpg`, `jpeg`;
- tamaño máximo: 5 MB por archivo;
- se valida extensión, tipo MIME y tamaño en backend;
- se descarga solo mediante vista con control de permisos (no servir `MEDIA_ROOT` público).

## `TicketStatusHistory`

```text
id
ticket_id
previous_status
new_status
actor_id
reason
created_at
```

## `Conversation`

```text
id
user_id
channel
external_conversation_id
active_ticket_id
active_intent
context_summary
last_message_at
is_active
```

## `TicketMessage`

```text
id
ticket_id
conversation_id
sender_type
sender_id
message_type
content
external_message_id
llm_generated
created_at
```

## `SLAPolicy`

```text
id
category_id
priority
first_response_minutes
resolution_minutes
business_hours_only
is_active
```

## `Alert`

```text
id
ticket_id
alert_type
severity
message
status
created_at
resolved_at
```

## `AuditLog`

```text
id
actor_type
actor_id
action
entity_type
entity_id
previous_value_json
new_value_json
metadata_json
created_at
```

---

# 27. Estados y prioridades

Usar `TextChoices`.

## Estado

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

## Prioridad

```text
LOW
MEDIUM
HIGH
CRITICAL
```

---

# 28. Automatización

## `Intent`

```text
id
code
name
automation_level
requires_authentication
requires_llm
requires_human
is_active
```

## `IntentAction`

```text
id
intent_id
action_type
provider_method
response_template
fallback_action
is_active
```

## `RoutingRule`

```text
id
intent_id
category_id
subcategory_id
area_id
priority
requires_validation
order
is_active
```

No crear tabla genérica `business_rules`.

---

# 29. Catálogo inicial de intenciones

## N0 / N1

```text
CHECK_SCHEDULE
CHECK_GRADE
CHECK_DEBT
CHECK_ENROLLMENT
CHECK_SUBJECTS
CHECK_TICKET
CHECK_ACADEMIC_DATES
CHECK_CONTACT
CHECK_REQUIREMENTS
```

## N2 / N3 / N4

```text
GRADE_DISCREPANCY
PAYMENT_NOT_REFLECTED
DEBT_DISPUTE
ENROLLMENT_PROBLEM
SUBJECT_NOT_VISIBLE
ACCESS_PROBLEM
PASSWORD_PROBLEM
CERTIFICATE_REQUEST
PROFILE_UPDATE
GENERAL_COMPLAINT
UNKNOWN_REQUEST
```

---

# 30. Intent Engine

Orden:

```text
Reglas determinísticas
↓
Coincidencias configuradas
↓
LLM si es necesario
↓
Validación / humano
```

No llamar al LLM si una regla simple resuelve la intención.

Desde v5.2 el Intent Engine se implementa como los nodos `classify_rules` → `classify_llm` → `validate_output` del grafo LangGraph (sección 46A). La regla anterior se cumple con una arista condicional: si `classify_rules` resuelve, el grafo no visita `classify_llm`.

---

# 31. Autonomy Engine

```text
N0 → consulta estructurada
N1 → conocimiento autorizado
N2 → ticket + validación
N3 → ticket + routing
N4 → revisión humana
```

Desde v5.2 el Autonomy Engine es el nodo `decide_autonomy` del grafo LangGraph, cuya arista condicional enruta a la rama N0–N4 (sección 46A). La decisión de nivel es **determinística** (catálogo `Intent.automation_level` + confianza), nunca la elige el LLM libremente.

## 31.1 Fuente de conocimiento N1 (v5.2)

N1 **no usa RAG** (prohibido en sección 4). El “conocimiento autorizado” se limita a:

1. `IntentAction.response_template` configurado por el administrador (contactos, requisitos, fechas académicas);
2. constantes versionadas en código para datos que no cambian sin despliegue.

El LLM, si interviene, solo puede reformular el texto de la plantilla sin añadir hechos; la salida se valida contra la plantilla de origen. Si no existe plantilla activa para la intención, la solicitud baja a N3 (ticket).

## 31.2 Autenticación previa

Toda intención con `Intent.requires_authentication = true` (horario, notas, deuda, matrícula, materias, estado de ticket) exige usuario autenticado: sesión web o teléfono verificado en WhatsApp (sección 35.1).

---

# 32. Workflow

## 32.1 Máquina de estados (v5.2)

Toda transición no listada en esta tabla está **prohibida** (por ejemplo `NEW → CLOSED`, `CANCELLED → *`).

| # | Desde | Hacia | Rol permitido | Disparador / condición |
|---|---|---|---|---|
| 1 | NEW | CLASSIFIED | Sistema, Agente, Supervisor | Intención/categoría determinada |
| 2 | NEW | CANCELLED | Usuario (propio), Supervisor | Antes de clasificar; motivo obligatorio |
| 3 | CLASSIFIED | ASSIGNED | Sistema (routing), Agente, Supervisor | Área y/o responsable asignados |
| 4 | CLASSIFIED | CANCELLED | Usuario (propio), Supervisor | Motivo obligatorio |
| 5 | ASSIGNED | IN_PROGRESS | Agente asignado, Supervisor | Primera acción del agente |
| 6 | ASSIGNED | ESCALATED | Agente asignado, Supervisor, Sistema (SLA) | Motivo obligatorio |
| 7 | IN_PROGRESS | WAITING_USER | Agente asignado, Supervisor | Solicitud de información |
| 8 | WAITING_USER | IN_PROGRESS | Usuario (propio, al responder), Agente, Supervisor | Nueva respuesta del usuario |
| 9 | WAITING_USER | CANCELLED | Sistema | Sin respuesta en `WAITING_USER_TIMEOUT_DAYS` (7 días) |
| 10 | IN_PROGRESS | ESCALATED | Agente asignado, Supervisor, Sistema (SLA) | Motivo obligatorio |
| 11 | IN_PROGRESS | RESOLVED | Agente asignado, Supervisor | Mensaje de resolución obligatorio |
| 12 | ESCALATED | ASSIGNED | Supervisor | Reasignación a otra área/agente |
| 13 | ESCALATED | IN_PROGRESS | Supervisor | El supervisor atiende directamente |
| 14 | RESOLVED | CLOSED | Usuario (propio, confirma), Sistema | Confirmación o `AUTO_CLOSE_DAYS` (3 días) sin respuesta |
| 15 | RESOLVED | IN_PROGRESS | Usuario (propio, rechaza) | Rechazo de la resolución; motivo obligatorio |
| 16 | CLOSED | REOPENED | Usuario (propio), Supervisor | Dentro de `REOPEN_WINDOW_DAYS` (7 días) desde el cierre |
| 17 | REOPENED | ASSIGNED | Sistema, Supervisor | Vuelve al último responsable si sigue activo; si no, routing |

Notas:

- `CANCELLED` es terminal. `CLOSED` solo admite `REOPENED`.
- El rechazo de la resolución (15) incrementa el contador de reaperturas en métricas y conserva el SLA original.
- La escalada (6, 10) crea un `Alert` de tipo `ESCALATED`.
- “Sistema” significa un proceso backend (routing, comando SLA, cierre automático), nunca el LLM.
- Los plazos (`WAITING_USER_TIMEOUT_DAYS`, `AUTO_CLOSE_DAYS`, `REOPEN_WINDOW_DAYS`) son constantes en settings, no tablas.

## 32.2 Reglas de ejecución

Toda transición:

1. valida;
2. actualiza;
3. registra historial;
4. audita;
5. confirma transacción.

---

# 33. Servicios

## TicketService

- crear;
- generar código;
- asignar;
- reasignar;
- cambiar estado;
- resolver;
- cerrar;
- reabrir.

## ConversationService

- registrar mensaje;
- buscar conversación;
- asociar ticket;
- mantener contexto;
- unificar Web/WhatsApp.

## AutomationService

```text
identify_intent()
determine_autonomy()
route_ticket()
execute_intent_action()
```

## InstitutionalQueryService

Utiliza exclusivamente `InstitutionalDataProvider`.

## AIService

- classify;
- extract;
- summarize;
- generate_response;
- validate_output;
- record_usage;
- fallback.

---

# 34. SLA

Valores iniciales:

| Prioridad | Primera respuesta | Resolución |
|---|---:|---:|
| LOW | 480 min | 4320 min |
| MEDIUM | 240 min | 2880 min |
| HIGH | 60 min | 1440 min |
| CRITICAL | 15 min | 240 min |

## 34.1 Calendario laboral (v5.2)

Cuando `SLAPolicy.business_hours_only = true`, los minutos se cuentan solo dentro del calendario laboral, definido como constante en settings (no tabla):

```python
BUSINESS_HOURS = {
    "timezone": TIME_ZONE,  # zona horaria institucional (variable de entorno)
    "weekdays": [0, 1, 2, 3, 4],  # lunes a viernes
    "start": "08:00",
    "end": "17:00",
}
HOLIDAYS = []  # lista de fechas ISO, mantenida en settings
```

Si `business_hours_only = false`, se usan minutos corridos (24×7).

## 34.2 Evaluación periódica

El SLA se evalúa con el comando `python manage.py check_sla` (ver sección 38), que genera `Alert` de tipo `SLA_WARNING` (≥ 80 % del plazo consumido) y `SLA_BREACHED` (plazo vencido), de forma idempotente (una alerta abierta por tipo y ticket).

---

# 35. WhatsApp

Proveedor: **Meta WhatsApp Cloud API** (v5.2). Verificación del webhook con `hub.verify_token`; validación de firma con cabecera `X-Hub-Signature-256` (HMAC-SHA256 con el App Secret). Credenciales solo por variables de entorno.

> **Decisión del responsable (2026-10-13, ADR-049):** WhatsApp es un **adicional** y se implementa **al final** del MVP y **simulado**, porque no se dispone de acceso a Meta Developer. El webhook, la firma, la idempotencia, la vinculación (35.1) y la bandeja de salida se construyen con el mismo contrato de Meta, pero los eventos los genera un simulador local (comando/pantalla de prueba) y la salida se registra sin enviarse. Pasar a Meta real solo requerirá credenciales y desactivar el simulador.

## 35.1 Autenticación por WhatsApp (v5.2)

Un número de WhatsApp **no** basta por sí mismo para entregar datos sensibles.

Flujo de vinculación:

```text
Usuario inicia sesión en portal web
↓
Perfil → "Vincular WhatsApp" → backend genera código de 6 dígitos
   (un solo uso, válido 10 minutos, almacenado como hash)
↓
Usuario envía el código por WhatsApp desde su número
↓
Backend valida código + número remitente
↓
User.phone = número (E.164), User.phone_verified_at = ahora
```

Reglas:

- Mensajes de un número no verificado: solo intenciones con `requires_authentication = false` (contactos, requisitos, fechas). Para el resto se responde con instrucciones de vinculación.
- Máximo 5 intentos fallidos de código por número y hora (rate limiting).
- Cambiar el teléfono en el perfil anula `phone_verified_at`.
- Toda vinculación y desvinculación se registra en `AuditLog`.
- Los datos sensibles por WhatsApp se minimizan (ej. deuda total, no detalle de pagos).

## Entrada

```text
Webhook
↓
Validación firma
↓
Idempotencia
↓
IntegrationInbox
↓
Worker
↓
ConversationService
```

## Salida

```text
Respuesta
↓
IntegrationOutbox
↓
Worker
↓
WhatsAppClient
↓
API
```

---

# 36. IntegrationInbox

```text
id
provider
external_event_id
payload_json
status
attempts
received_at
processed_at
last_error
```

# 37. IntegrationOutbox

```text
id
provider
destination
payload_json
status
attempts
next_attempt_at
created_at
sent_at
last_error
```

---

# 38. Worker Django

```text
python manage.py process_integration_queue
```

Procesa:

- inbox;
- outbox;
- reintentos;
- backoff;
- errores.

No incorporar Redis/Celery inicialmente.

## 38.1 Ejecución periódica (v5.2)

| Comando | Frecuencia | Función |
|---|---|---|
| `process_integration_queue` | cada 1 min | Inbox/outbox WhatsApp, reintentos con backoff exponencial (máx. 5 intentos) |
| `check_sla` | cada 5 min | Alertas `SLA_WARNING` / `SLA_BREACHED`, escalamiento automático |
| `close_stale_tickets` | cada hora | Cierre automático de `RESOLVED` y cancelación de `WAITING_USER` vencidos |

Se ejecutan mediante **cron** del sistema operativo (o systemd timer) en el servidor; cada comando es idempotente y usa `select_for_update(skip_locked=True)` para evitar doble procesamiento si dos ejecuciones se solapan. En desarrollo pueden lanzarse manualmente. `process_integration_queue` admite `--loop` para ejecución continua en desarrollo.

---

# 39. InstitutionalDataProvider

```python
class InstitutionalDataProvider:
    def get_schedule(self, user, date=None): ...
    def get_grades(self, user, period=None): ...
    def get_debt(self, user): ...
    def get_enrollment(self, user, period=None): ...
    def get_subjects(self, user, period=None): ...
```

---

# 40. LocalProvider

Debe existir desde Fase 4.

Datos simulados para:

- horario;
- notas;
- deuda;
- matrícula;
- asignaturas.

---

# 41. SGAProvider

Durante MVP:

- stub/adapter;
- mock HTTP;
- mapping;
- timeouts;
- errores 4xx/5xx.

No inventar endpoints reales.

---

# 42. LLMProvider

```python
class LLMProvider:
    def classify(self, text, context=None): ...
    def extract(self, text, schema): ...
    def summarize(self, messages): ...
    def generate_response(self, context): ...
```

## 42.1 Selección de proveedor (v5.2)

El proveedor LLM real es una **decisión abierta** (ADR-010 en `progress.md`). Criterios: costo por 1K tokens, latencia P95, soporte de salida JSON estructurada, tratamiento de datos personales y disponibilidad regional.

Hasta cerrar la decisión:

- `LLM_PROVIDER=fake` es el valor por defecto en desarrollo y CI (`FakeLLMProvider` determinístico);
- el proveedor se selecciona por variable de entorno, sin cambiar código de negocio;
- no se envían a un LLM externo datos sensibles (notas, deuda); solo el texto del mensaje del usuario, previamente minimizado.

---

# 43. Configuración IA

## `AIModelConfig`

```text
id
provider
model_name
purpose
is_primary
is_fallback
is_active
created_at
```

## `AIPromptVersion`

```text
id
name
version
purpose
template
is_active
created_at
```

## `AIUsage`

```text
id
ticket_id
message_id
provider
model_name
operation
input_tokens
output_tokens
latency_ms
estimated_cost
success
error_code
created_at
```

## `AIDecision`

```text
id
ticket_id
message_id
prompt_version_id
operation
raw_output
parsed_output
confidence
accepted
corrected
corrected_by
graph_version     (v5.2 — versión del grafo LangGraph)
node_path         (v5.2 — lista JSON de nodos recorridos)
thread_id         (v5.2 — hilo LangGraph = Conversation.id)
created_at
```

---

# 44. Contrato IA

```json
{
  "intent": "GRADE_DISCREPANCY",
  "category": "ACADEMIC",
  "subcategory": "GRADES",
  "priority": "MEDIUM",
  "summary": "El usuario reporta una posible inconsistencia en su calificación.",
  "requires_human": true,
  "confidence": 0.91
}
```

Validar:

- JSON;
- schema;
- intención;
- categoría;
- subcategoría;
- prioridad;
- tipos;
- rangos.

---

# 45. Restricciones IA

El LLM no puede:

- modificar modelos;
- ejecutar ORM;
- cambiar estado;
- asignar;
- modificar nota/deuda;
- cerrar;
- ejecutar SQL;
- aprobar trámites.

---

# 46. Confianza y fallback

```text
>= 0.85 → automática
0.70–0.849 → sugerencia + validación
< 0.70 → humano
```

Fallback:

```text
Regla
↓
LLM primario
↓ fallo
Retry
↓ fallo
LLM fallback
↓ fallo
Humano
```

---

# 46A. Orquestación agéntica con LangGraph (v5.2)

## 46A.1 Decisión

El comportamiento agéntico del MVP se implementa con **LangGraph** (`langgraph` 1.x), embebido en el proceso Django. El agente es un **grafo de estados explícito**: los nodos son pasos (reglas, LLM, herramientas, validación, revisión humana) y las aristas condicionales deciden el siguiente paso según el estado validado.

Esto hace al sistema **agéntico** porque, ante cada mensaje, el agente:

1. **percibe** (mensaje + contexto de conversación + identidad verificada);
2. **razona** (clasifica, extrae entidades, evalúa confianza);
3. **decide** la ruta (N0–N4) mediante aristas condicionales;
4. **actúa** con herramientas autorizadas (consultas institucionales, consulta de ticket, creación de ticket);
5. **observa** el resultado de la herramienta y decide si responde, reintenta, pide aclaración o escala;
6. **mantiene memoria** de la conversación (checkpointer PostgreSQL);
7. **pausa** para revisión humana (`interrupt`) cuando la confianza o el nivel lo exigen.

Modificar el comportamiento del agente = **modificar el grafo** (añadir/quitar nodos, cambiar aristas o condiciones) en `apps/ai/agent/graph.py`, no dispersar lógica en vistas o servicios.

## 46A.2 Ubicación (sin nueva app)

```text
apps/ai/agent/
├── state.py      # AgentState (TypedDict)
├── nodes.py      # funciones de nodo
├── tools.py      # herramientas autorizadas (wrappers de servicios)
├── graph.py      # build_graph(): nodos + aristas; GRAPH_VERSION
└── runner.py     # run_agent(message) / resume_agent(thread_id, decision)
```

## 46A.3 Estado del grafo

```python
class AgentState(TypedDict):
    thread_id: str                 # = conversation_id
    user_id: int | None
    channel: str                   # WEB | WHATSAPP
    is_verified: bool              # sesión web o phone_verified_at (35.1)
    message: str
    intent: str | None
    entities: dict
    confidence: float | None
    classification_source: str     # RULES | LLM | HUMAN
    autonomy_level: str | None     # N0..N4
    tool_calls: list[dict]         # herramientas invocadas y resultado resumido
    ticket_code: str | None
    response: str | None
    attempts: int                  # reintentos LLM consumidos
    errors: list[str]
    requires_human: bool
```

El estado **no** guarda datos sensibles completos (notas, deuda): solo referencias o resúmenes mínimos.

## 46A.4 Grafo

```text
START
  ↓
load_context ──────────────► (usuario, conversación, ticket activo, verificación)
  ↓
classify_rules ──resuelto──────────────────────────────┐
  │ no resuelto                                        │
  ↓                                                    │
classify_llm ──error──► retry_or_fallback ──agotado──► human_review
  ↓                          │ reintento               ▲
validate_output ◄────────────┘                         │
  │ inválido / confianza < 0.70 ───────────────────────┤
  ↓                                                    │
decide_autonomy ◄──────────────────────────────────────┘ (desde classify_rules)
  ├── N0 → check_auth ──no verificado──► respond_link_instructions → END
  │          ↓ verificado
  │        call_tool (InstitutionalQueryService) ──error──► create_ticket
  │          ↓
  │        respond → END
  ├── N1 → respond_template → END
  ├── N2 → create_ticket → human_review (validación) → respond → END
  ├── N3 → create_ticket → route_ticket → respond → END
  └── N4 → create_ticket → human_review → respond → END
```

`human_review` usa `interrupt()` de LangGraph: el hilo queda pausado en el checkpointer hasta que un Agente/Supervisor decide desde la bandeja (acepta, corrige clasificación o rechaza). `resume_agent(thread_id, decision)` reanuda el grafo con `Command(resume=decision)`.

Confianza 0.70–0.849 → `decide_autonomy` fuerza `human_review` antes de ejecutar acciones N2/N3 (§46).

## 46A.5 Herramientas autorizadas

| Herramienta | Tipo | Servicio subyacente | Quién la invoca |
|---|---|---|---|
| `get_schedule`, `get_grades`, `get_debt`, `get_enrollment`, `get_subjects` | Lectura | `InstitutionalQueryService` | Nodo `call_tool` (puede sugerirla el LLM) |
| `get_ticket_status` | Lectura | `TicketService` (solo tickets del usuario) | Nodo `call_tool` |
| `create_ticket` | Escritura | `TicketService.create()` | **Solo nodo determinístico** |
| `route_ticket` | Escritura | `AutomationService.route_ticket()` | **Solo nodo determinístico** |

Reglas:

1. El LLM puede **proponer** una herramienta de lectura de la lista; el nodo valida nombre, argumentos (esquema) y autorización antes de ejecutarla.
2. Las herramientas de escritura nunca se exponen al LLM: las invoca un nodo determinístico tras validar el estado.
3. Las herramientas siempre actúan sobre el **usuario del estado** (`user_id`); el LLM no puede indicar otro usuario.
4. Máximo `AGENT_MAX_STEPS = 12` pasos por ejecución (`recursion_limit`); al superarlo → `human_review`.
5. Cambiar estados, asignar, cerrar, modificar notas/deuda: **no existen como herramientas** (§45 sigue vigente).

## 46A.6 Memoria y persistencia

- Checkpointer: `PostgresSaver` (`langgraph-checkpoint-postgres`) sobre la misma base PostgreSQL, en tablas propias del checkpointer.
- ~~`thread_id` = `Conversation.id`~~ (CR-008): cada mensaje se ejecuta en su propio hilo (`run-…`, guardado en `AIDecision.thread_id`), porque en LangGraph un mensaje nuevo en un hilo pausado descarta la revisión humana pendiente. La memoria entre mensajes vive en `Conversation` (`active_intent`, `last_message_at`), que sí es compartida por canal.
- En pruebas se usa `InMemorySaver`.
- El checkpointer no sustituye a los modelos de negocio: tickets, mensajes y auditoría siguen en sus tablas Django.

## 46A.7 Ejecución

- WhatsApp: el worker `process_integration_queue` invoca `run_agent()` al procesar cada evento de `IntegrationInbox` (sin Redis/Celery).
- Web: la vista de nuevo mensaje/solicitud invoca `run_agent()` de forma síncrona con timeout; si excede el tiempo, el mensaje queda registrado y se procesa como ticket N3.
- Toda ejecución registra `AIDecision` con `graph_version` y el recorrido de nodos (`node_path`), y `AIUsage` por cada llamada LLM.

## 46A.8 Versionado y cambios del grafo

- `GRAPH_VERSION` (constante en `graph.py`) se incrementa en cada cambio de nodos o aristas.
- Todo cambio del grafo requiere: CHANGE REQUEST en `progress.md`, pruebas de las rutas afectadas y diagrama actualizado (`graph.get_graph().draw_mermaid()` guardado en `docs/agent_graph.md`).
- El LLM **no** modifica el grafo en tiempo de ejecución; el grafo solo se cambia en código revisado.

## 46A.9 Pruebas

- Cada ruta N0–N4 tiene una prueba con `FakeLLMProvider` y `InMemorySaver`.
- Pruebas de: regla resuelve sin visitar `classify_llm`; salida LLM inválida → `human_review`; error LLM → retry → fallback → humano; número no verificado no llega a `call_tool`; `interrupt` y reanudación; límite de pasos.

---

# 47. Contrato FRONT ↔ BACK (v5.2)

**Decisión v5.2:** el frontend es server-rendered (Django Templates), por lo que **no** consume una API REST. Una API REST de tickets no tendría consumidor y violaría la regla 56.6. El contrato FRONT ↔ BACK son las **rutas de vistas Django** (formularios con CSRF, POST-redirect-GET). No se incorpora Django REST Framework en el MVP.

Las vistas solo orquestan: validan formulario, llaman al servicio (`TicketService`, etc.) y renderizan. La lógica de negocio vive en los servicios.

## 47.1 Rutas web

```text
GET        /accounts/login/
POST       /accounts/login/
POST       /accounts/logout/
GET        /                                   → redirección por rol

GET        /tickets/                           → listado (filtros + paginación)
GET|POST   /tickets/new/                       → crear
GET        /tickets/{code}/                    → detalle + conversación
POST       /tickets/{code}/messages/           → responder (con adjunto opcional)
POST       /tickets/{code}/assign/             → asignar / reasignar
POST       /tickets/{code}/status/             → transición genérica permitida por rol
POST       /tickets/{code}/resolve/            → IN_PROGRESS → RESOLVED
POST       /tickets/{code}/escalate/           → → ESCALATED
POST       /tickets/{code}/confirm/            → RESOLVED → CLOSED (usuario)
POST       /tickets/{code}/reject-resolution/  → RESOLVED → IN_PROGRESS (usuario)
POST       /tickets/{code}/reopen/             → CLOSED → REOPENED
POST       /tickets/{code}/cancel/             → → CANCELLED
GET        /tickets/{code}/attachments/{id}/   → descarga con control de permisos

GET        /agent/inbox/                       → bandeja del agente
GET        /alerts/                            → alertas (Supervisor)
GET        /metrics/                           → métricas (Supervisor)
GET|POST   /profile/whatsapp/                  → vinculación de WhatsApp (sección 35.1)

/manage/...                                    → CRUD de catálogos (Administrador)
```

Todas las acciones POST envían el campo `version` del ticket (bloqueo optimista).

## 47.2 API (única con consumidor externo)

```text
GET  /api/webhooks/whatsapp/    → verificación Meta (hub.challenge)
POST /api/webhooks/whatsapp/    → recepción de eventos (firma obligatoria)
```

## 47.3 Consultas institucionales

No se exponen endpoints `/api/institutional/*`. Las consultas institucionales se resuelven internamente mediante `InstitutionalQueryService` → `InstitutionalDataProvider`, invocado por el Autonomy Engine (WhatsApp y web). Si en el futuro un consumidor real lo requiere, se añadirá mediante CHANGE REQUEST.

No exponer endpoints IA internos.

---

# 48. Seguridad general

- autenticación;
- autorización horizontal;
- autorización vertical;
- CSRF;
- webhook firmado;
- idempotencia;
- sanitización;
- XSS;
- secretos fuera del repositorio;
- rate limiting;
- timeouts;
- adjuntos restringidos;
- minimización de datos;
- auditoría.

---

# 49. Métricas

## Operativas

- tickets;
- tiempos;
- SLA;
- reasignaciones;
- reaperturas.

## WhatsApp

- mensajes;
- reintentos;
- fallos;
- conversaciones;
- automatización.

## IA

- Accuracy;
- Precision;
- Recall;
- Macro F1;
- P50/P95/P99;
- costo;
- fallback;
- correcciones;
- outputs inválidos.

---

# 50. Objetivos IA

```text
Accuracy >= 85 %
Macro F1 >= 0.80
```

Objetivos experimentales del MVP.

---

# 51. Estrategia de pruebas

- pytest;
- pytest-django;
- PostgreSQL real en CI (GitHub Actions con servicio `postgres:16`);
- FakeLLMProvider;
- mock WhatsApp;
- mock SGA;
- fixtures;
- cobertura >= 80 %;
- integración;
- contratos;
- E2E.

---

# 52. Orden de desarrollo

## Fase 1
Núcleo Web + cuentas + tickets.

## Fase 2
Workflow + SLA + routing + auditoría.

## Fase 3
WhatsApp + inbox/outbox.

## Fase 4
Automatización + LocalProvider.

## Fase 5
IA + proveedor real + fallback + grafo agéntico LangGraph (BE-T18A).

## Fase 6
Contrato SGA + SGAProvider mock.

## Fase 7
Validación + benchmark + carga + seguridad + UAT.

---

# 53. Casos de aceptación

```text
CA-001 Consultar horario
CA-002 Consultar nota
CA-003 Consultar deuda
CA-004 Nota incorrecta
CA-005 Pago no reflejado
CA-006 Solicitud ambigua
CA-007 Error LLM
CA-008 Reasignación
CA-009 Consulta de estado
CA-010 Conversación contextual
```

---

# 54. Criterios de finalización

1. recibe Web y WhatsApp;
2. identifica usuarios;
3. reconoce intenciones;
4. responde horario, nota y deuda;
5. detecta validación;
6. crea tickets;
7. enruta;
8. gestiona estados;
9. conserva conversaciones;
10. calcula SLA;
11. usa proveedor LLM;
12. ejecuta fallback;
13. registra métricas;
14. audita IA;
15. funciona sin SGA;
16. sustituye LocalProvider por SGAProvider sin cambiar lógica de negocio;
17. orquesta todo el flujo con el grafo agéntico LangGraph, con herramientas autorizadas, memoria conversacional y revisión humana (46A).

---

# 55. Componentes que NO deben generarse

## Apps Django separadas

```text
catalogs
routing
rules
sla
notifications
audit
conversations
```

## Infraestructura no autorizada

```text
microservices
CQRS
event sourcing
Kafka
RabbitMQ
Redis
Celery
GraphQL
WebSockets
vector DB
RAG
agentes fuera de LangGraph o sin control (ver 46A)
frameworks multiagente (CrewAI, AutoGen, etc.)
LangGraph Platform / Server / Cloud
MCP
Kubernetes
```

**Autorizado desde v5.2:** `langgraph` y `langgraph-checkpoint-postgres`, únicamente dentro de `apps/ai/agent/`.

## Frontend no autorizado

```text
React
Vue
Angular
Next.js
Nuxt
Redux
SPA
PWA
```

---

# 56. Reglas para generación de código

1. Generar solo las cinco apps definidas.
2. No crear nuevos módulos sin requisito explícito.
3. No crear repositorios genéricos sobre Django ORM.
4. No crear DTOs innecesarios.
5. No crear interfaces salvo sustitución real.
6. No crear endpoints sin consumidor.
7. No inventar endpoints SGA.
8. No permitir persistencia directa desde LLM.
9. No agregar funcionalidades “future-ready” sin CA asociado.
10. No duplicar permisos.
11. Mantener transacciones en operaciones críticas.
12. Toda entidad debe justificar un requisito o prueba.
13. Toda vista frontend debe justificar un flujo funcional.
14. Toda lógica de negocio debe vivir en backend.
15. El frontend nunca debe ser fuente de verdad de estados, SLA o permisos.
16. Toda lógica agéntica vive en el grafo LangGraph de `apps/ai/agent/`; ningún otro módulo llama al LLM para decidir flujo.
17. Las herramientas de escritura del agente solo las invoca un nodo determinístico; el LLM solo propone herramientas de lectura.

---

# 57. Regla de coherencia

Antes de crear cualquier nueva pieza:

```text
¿Está vinculada a un requisito o caso de aceptación?
        │
       No
        ↓
No implementar
```

y:

```text
¿Puede vivir dentro de una app existente sin romper cohesión?
        │
       Sí
        ↓
No crear una nueva app
```

---

# 58. Flujo integral final

```text
USUARIO
  ↓
FRONT WEB / WHATSAPP
  ↓
DJANGO
  ↓
IDENTIFICACIÓN
  ↓
CONVERSATION SERVICE
  ↓
AGENTE LANGGRAPH (46A)
  │  INTENT ENGINE  (nodos classify_rules / classify_llm / validate_output)
  ↓
  │  AUTONOMY ENGINE (nodo decide_autonomy + aristas condicionales)
  ├── N0 → InstitutionalDataProvider → Respuesta
  ├── N1 → IntentAction.response_template (+ AIService opcional) → Respuesta
  ├── N2 → TicketService → Validación
  ├── N3 → TicketService → Routing → Agente
  └── N4 → Revisión humana
  ↓
WORKFLOW / SLA / AUDIT
  ↓
PostgreSQL
  ↓
RESPUESTA WEB / WHATSAPP
```

---

# 59. Resultado esperado

La solución final debe permanecer simple:

```text
FRONT
Django Templates + Bootstrap

BACK
accounts
helpdesk
automation
integrations
ai

PERSISTENCIA
PostgreSQL
```

El MVP debe demostrar de extremo a extremo:

**entrada → comprensión → autonomía → consulta o ticket → enrutamiento → atención → trazabilidad → respuesta**

sin añadir módulos que no aporten directamente a este flujo.

---

# 60. Matriz de tareas independientes FRONT / BACK

Esta sección convierte la SPEC en un backlog ejecutable para trabajo paralelo entre agentes o equipos de frontend y backend, sin modificar la arquitectura definida en las secciones anteriores.

## 60.1 Reglas de ejecución

1. FRONT y BACK pueden trabajar en paralelo cuando la dependencia esté cubierta por contrato, mock o endpoint definido.
2. Ningún agente debe modificar la arquitectura base sin actualizar primero esta SPEC.
3. Antes de iniciar una tarea, el agente debe revisar `progress.md`.
4. Una tarea marcada como `DONE` no debe volver a implementarse.
5. Una tarea marcada como `IN_PROGRESS` no debe ser tomada por otro agente salvo coordinación explícita.
6. Si una tarea requiere modificar un contrato existente, debe registrar el cambio en `progress.md`.
7. Todo cambio que afecte FRONT y BACK debe actualizar su dependencia cruzada.
8. Las tareas deben cerrarse únicamente cuando cumplan su criterio de aceptación.
9. FRONT es dueño exclusivo de `templates/` y `static/`; BACK publica cada vista con su url name, plantilla esperada y contrato de contexto (`CONTRACT-XXX` en `progress.md`). BACK solo crea plantillas mínimas marcadas `TEMPORAL (backend)` cuando una prueba lo requiera.

---

## 60.2 Estados de tarea

```text
TODO
IN_PROGRESS
BLOCKED
REVIEW
DONE
CANCELLED
```

---

## 60.3 Backlog FRONT

### FE-T01 — Login y sesión

**Objetivo:** implementar pantalla de autenticación.

**Dependencias:** BE-T01.

**Entregables:**
- `login.html`;
- mensajes de error;
- redirección por rol;
- CSRF.

**Criterio de aceptación:**
- usuario válido ingresa;
- usuario inválido recibe mensaje genérico;
- sesión y permisos respetados.

---

### FE-T02 — Dashboard de usuario

**Objetivo:** mostrar acceso a nueva solicitud y tickets recientes.

**Dependencias:** BE-T03, BE-T04.

**Entregables:**
- `dashboard.html`;
- listado resumido;
- acceso a creación y consulta.

**Criterio de aceptación:**
- el usuario solo visualiza información propia.

---

### FE-T03 — Crear ticket

**Objetivo:** permitir crear una solicitud desde web.

**Dependencias:** BE-T03, BE-T03A.

**Entregables:**
- `ticket_form.html`;
- validaciones visuales;
- adjunto opcional si está habilitado.

**Criterio de aceptación:**
- ticket creado correctamente;
- errores de backend mostrados de forma controlada.

---

### FE-T04 — Listado y filtros

**Objetivo:** mostrar tickets con filtros y paginación.

**Dependencias:** BE-T04.

**Entregables:**
- `ticket_list.html`;
- filtros por estado y fecha;
- paginación.

**Criterio de aceptación:**
- resultados correctos y sin acceso a tickets ajenos.

---

### FE-T05 — Detalle e histórico

**Objetivo:** mostrar ticket, mensajes y cambios relevantes.

**Dependencias:** BE-T05, BE-T07.

**Entregables:**
- `ticket_detail.html`;
- histórico;
- conversación omnicanal.

**Criterio de aceptación:**
- orden cronológico correcto;
- web y WhatsApp aparecen en el mismo historial.

---

### FE-T06 — Bandeja del agente

**Objetivo:** permitir operación de tickets asignados o disponibles.

**Dependencias:** BE-T04, BE-T06.

**Entregables:**
- bandeja;
- filtros;
- prioridad;
- área;
- responsable;
- SLA.

**Criterio de aceptación:**
- cada agente ve solo tickets autorizados.

---

### FE-T07 — Gestión visual de estados

**Objetivo:** permitir ejecutar transiciones válidas.

**Dependencias:** BE-T07.

**Entregables:**
- acciones de cambio de estado;
- confirmaciones;
- mensajes de error.

**Criterio de aceptación:**
- no se muestran ni ejecutan transiciones inválidas.

---

### FE-T08 — Alertas y SLA

**Objetivo:** visualizar vencimientos y alertas.

**Dependencias:** BE-T08.

**Entregables:**
- alertas;
- tiempo restante;
- estados vencido / por vencer.

**Criterio de aceptación:**
- valores coinciden con backend.

---

### FE-T09 — Administración de catálogos

**Objetivo:** administrar áreas, categorías, subcategorías, intenciones, routing y SLA.

**Dependencias:** BE-T03A, BE-T09.

**Entregables:**
- vistas CRUD;
- desactivación lógica;
- permisos administrativos.

**Criterio de aceptación:**
- solo administrador puede modificar configuración.

---

### FE-T10 — Métricas operativas

**Objetivo:** visualizar métricas básicas del MVP.

**Dependencias:** BE-T10.

**Entregables:**
- abiertos/cerrados;
- SLA;
- tiempos;
- tickets por área, categoría y canal.

**Criterio de aceptación:**
- valores coinciden con backend y pruebas conocidas.

---

### FE-T11 — Vinculación de WhatsApp (v5.2)

**Objetivo:** permitir al usuario vincular su número de WhatsApp desde el perfil.

**Dependencias:** BE-T11A.

**Entregables:**
- vista de perfil con estado de vinculación;
- botón “Vincular WhatsApp” que muestra el código temporal;
- opción de desvincular.

**Criterio de aceptación:**
- el código solo se muestra al usuario autenticado propietario;
- el estado refleja `phone_verified_at`.

---

## 60.4 Backlog BACK

### BE-T01 — Proyecto base, usuario, autenticación y roles (incluye BE-T02)

**Objetivo:** crear el esqueleto del proyecto e implementar `accounts`.

> v5.2: BE-T02 se fusiona en BE-T01 porque el usuario personalizado (`AUTH_USER_MODEL`) debe existir **antes** de la primera migración del proyecto; separarlos obligaría a rehacer migraciones.

**Entregables:**
- proyecto Django (`config/settings/{base,dev,test}.py`) y las cinco apps vacías;
- PostgreSQL por variables de entorno (`.env.example`);
- `User(AbstractUser)` con `phone`, `phone_verified_at`, `external_id`, `source`;
- Groups `Usuario`, `Agente`, `Supervisor`, `Administrador` mediante migración de datos;
- login/logout con redirección por rol;
- utilidades de control vertical (rol) y horizontal (propietario);
- pytest + pytest-django + CI con PostgreSQL.

**Criterio de aceptación:**
- migraciones correctas y reversibles;
- matriz de permisos verificada por pruebas;
- CI en verde contra PostgreSQL.

---

### BE-T02 — Modelo base de usuario

**Estado:** CANCELLED — fusionada en BE-T01 (v5.2).

---

### BE-T03A — Catálogos y auditoría (v5.2)

**Objetivo:** crear las entidades de las que dependen tickets, routing y SLA.

**Dependencias:** BE-T01.

**Entregables:**
- `Area`, `Category`, `Subcategory` con desactivación lógica;
- `AuditLog` y función de servicio `audit.record(...)` en `helpdesk`;
- datos iniciales mínimos (migración de datos o fixture).

**Criterio de aceptación:**
- catálogos administrables desde Django admin;
- toda escritura de catálogo genera `AuditLog`.

---

### BE-T03 — Creación de tickets

**Objetivo:** implementar `TicketService.create()`.

**Dependencias:** BE-T01, BE-T03A.

**Entregables:**
- modelo Ticket (incluye `intent`, `version`);
- modelo `Attachment` con validaciones;
- código único;
- creación web;
- auditoría inicial.

**Criterio de aceptación:**
- sin códigos duplicados bajo concurrencia.

---

### BE-T04 — Consulta, filtros y paginación

**Objetivo:** implementar lectura eficiente de tickets.

**Entregables:**
- listado;
- filtros;
- paginación;
- permisos.

**Criterio de aceptación:**
- resultados correctos por rol.

---

### BE-T05 — Mensajes y conversaciones

**Objetivo:** implementar conversación omnicanal.

**Entregables:**
- Conversation;
- TicketMessage;
- ConversationService.

**Criterio de aceptación:**
- web y WhatsApp comparten ticket e histórico.

---

### BE-T06 — Asignación y reasignación

**Objetivo:** permitir gestionar responsable y área.

**Entregables:**
- assign;
- reassign;
- auditoría.

**Criterio de aceptación:**
- cambios trazables y autorizados.

---

### BE-T07 — Workflow y estados

**Objetivo:** implementar transiciones controladas.

**Entregables:**
- máquina de estados de la sección 32.1 (17 transiciones con rol);
- historial;
- transacciones atómicas;
- bloqueo optimista con `Ticket.version`;
- comando `close_stale_tickets`.

**Criterio de aceptación:**
- transiciones inválidas o no permitidas al rol rechazadas;
- actualización concurrente detectada.

---

### BE-T08 — SLA y alertas

**Objetivo:** calcular vencimientos.

**Dependencias:** BE-T03 (el SLA se fija al crear el ticket), BE-T07.

**Entregables:**
- SLAPolicy;
- cálculo `first_response_due_at` y `sla_due_at` con calendario laboral (34.1);
- Alert;
- comando `check_sla`.

**Criterio de aceptación:**
- alertas correctas al aproximarse y vencer;
- cálculo correcto cruzando fines de semana y fuera de horario.

---

### BE-T09 — Routing y configuración

**Objetivo:** implementar automatización configurable.

**Entregables:**
- Intent;
- IntentAction;
- RoutingRule.

**Criterio de aceptación:**
- routing correcto sin redeploy cuando cambia configuración.

---

### BE-T10 — Métricas operativas

**Objetivo:** exponer cálculos requeridos por frontend.

**Entregables:**
- métricas de tickets;
- SLA;
- tiempos;
- canal;
- área.

**Criterio de aceptación:**
- coinciden con cálculos manuales de referencia.

---

### BE-T11 — Webhook WhatsApp

**Objetivo:** recibir y validar eventos.

**Nota (ADR-049):** se ejecuta al final del MVP, con eventos simulados (sin acceso a Meta Developer).

**Entregables:**
- GET verificación;
- POST;
- firma;
- idempotencia.

**Criterio de aceptación:**
- duplicados no generan doble procesamiento.

---

### BE-T11A — Vinculación y autenticación WhatsApp (v5.2)

**Objetivo:** impedir la entrega de datos sensibles a números no verificados.

**Dependencias:** BE-T01, BE-T11.

**Entregables:**
- generación de código de vinculación (hash, un solo uso, 10 min);
- validación del código recibido por WhatsApp;
- `phone_verified_at`;
- rate limiting de intentos;
- auditoría de vinculación.

**Criterio de aceptación:**
- número no verificado no recibe notas/deuda/horario;
- código expirado o reutilizado rechazado.

---

### BE-T12 — Inbox / Outbox

**Objetivo:** soportar procesamiento asíncrono básico sin Redis/Celery.

**Entregables:**
- IntegrationInbox;
- IntegrationOutbox;
- worker;
- retries/backoff.

**Criterio de aceptación:**
- no se pierden mensajes ante fallos controlados.

---

### BE-T13 — Intent Engine

**Objetivo:** reconocer intención por reglas antes de LLM.

**Entregables:**
- reglas determinísticas;
- coincidencias parametrizadas.

**Criterio de aceptación:**
- intenciones simples se resuelven sin LLM.

---

### BE-T14 — Autonomy Engine

**Objetivo:** decidir N0–N4.

**Entregables:**
- determinación de nivel;
- ejecución de acción;
- escalamiento.

**Criterio de aceptación:**
- N0/N1 automáticos;
- N2/N3 generan ticket;
- N4 escala.

---

### BE-T15 — InstitutionalDataProvider + LocalProvider

**Objetivo:** permitir consultas institucionales sin SGA real.

**Entregables:**
- contrato;
- horario;
- notas;
- deuda;
- matrícula;
- asignaturas.

**Criterio de aceptación:**
- CA-001, CA-002 y CA-003 funcionan con datos simulados.

---

### BE-T16 — LLMProvider

**Objetivo:** abstraer proveedor IA.

**Entregables:**
- interfaz;
- FakeLLMProvider;
- proveedor real.

**Criterio de aceptación:**
- cambio de proveedor por configuración.

---

### BE-T17 — IA: clasificación, resumen y extracción

**Objetivo:** implementar AIService.

**Entregables:**
- classify;
- extract;
- summarize;
- generate_response;
- validación de salida;
- dataset etiquetado de evaluación (mínimo 20 ejemplos por intención, separado en desarrollo/prueba) — adelantado desde BE-T20 en v5.2.

**Criterio de aceptación:**
- salida ajustada al contrato y catálogos;
- métricas base (Accuracy, Macro F1) calculadas sobre el dataset con `FakeLLMProvider` y reglas.

---

### BE-T18 — Fallback y auditoría IA

**Objetivo:** garantizar continuidad y trazabilidad.

**Entregables:**
- AIUsage;
- AIDecision (incluye `graph_version` y `node_path` — v5.2);
- retry;
- fallback provider;
- escalamiento humano.

**Criterio de aceptación:**
- ningún fallo IA pierde la solicitud.

---

### BE-T18A — Grafo agéntico LangGraph (v5.2)

**Objetivo:** orquestar Intent Engine, Autonomy Engine, herramientas y revisión humana como un grafo LangGraph (sección 46A).

**Dependencias:** BE-T13, BE-T14, BE-T15, BE-T16, BE-T17, BE-T18.

**Entregables:**
- `apps/ai/agent/` (`state.py`, `nodes.py`, `tools.py`, `graph.py`, `runner.py`);
- herramientas autorizadas con validación de esquema y autorización;
- `human_review` con `interrupt` y reanudación desde la bandeja;
- checkpointer PostgreSQL (`PostgresSaver`) e `InMemorySaver` en pruebas;
- integración con `process_integration_queue` y la vista web de mensajes;
- `GRAPH_VERSION`, `node_path` en `AIDecision` y diagrama `docs/agent_graph.md`.

**Criterio de aceptación:**
- CA-001 a CA-010 recorren el grafo con `FakeLLMProvider`;
- ninguna herramienta de escritura es invocable por el LLM;
- número no verificado no obtiene datos sensibles;
- error del LLM nunca pierde la solicitud (termina en ticket o revisión humana).

---

### BE-T19 — SGAProvider mock/contrato

**Objetivo:** dejar lista la integración futura.

**Entregables:**
- mock HTTP;
- adapter;
- mapping;
- timeouts;
- manejo 4xx/5xx.

**Criterio de aceptación:**
- LocalProvider y SGAProvider mock cumplen el mismo contrato.

---

### BE-T20 — Pruebas, seguridad y benchmark

**Objetivo:** validar MVP.

**Entregables:**
- integración;
- E2E;
- seguridad;
- carga;
- benchmark IA (sobre el dataset de BE-T17);
- UAT.

**Criterio de aceptación:**
- CA-001 a CA-010 aprobados;
- sin defectos críticos/altos;
- métricas documentadas.

---

## 60.5 Dependencias cruzadas principales

| FRONT | BACK requerido |
|---|---|
| FE-T01 | BE-T01 |
| FE-T02 | BE-T03, BE-T04 |
| FE-T03 | BE-T03, BE-T03A |
| FE-T04 | BE-T04 |
| FE-T05 | BE-T05, BE-T07 |
| FE-T06 | BE-T04, BE-T06 |
| FE-T07 | BE-T07 |
| FE-T08 | BE-T08 |
| FE-T09 | BE-T03A, BE-T09 |
| FE-T10 | BE-T10 |
| FE-T11 | BE-T11A |

FRONT puede trabajar antes de completar BACK utilizando datos mock, siempre que respete el contrato definido en esta SPEC.

---

# 61. Uso obligatorio de `progress.md`

El archivo `progress.md` es el registro operativo compartido entre agentes.

Todo agente deberá:

1. leerlo antes de iniciar trabajo;
2. localizar la tarea que pretende ejecutar;
3. comprobar su estado;
4. registrar que comienza;
5. registrar archivos modificados;
6. registrar decisiones relevantes;
7. registrar bloqueos;
8. registrar pruebas ejecutadas;
9. marcar la tarea como `DONE` únicamente tras cumplir el criterio de aceptación.

Una tarea `DONE` no deberá repetirse.

Si un agente detecta que una tarea ya implementada necesita corrección, deberá crear una entrada de corrección en `progress.md` y no rehacer silenciosamente la implementación.

