# SPEC v5.0 — MVP Mesa de Ayuda Omnicanal
## Documento unificado FRONT + BACK

**Estado:** Especificación técnica consolidada para implementación  
**Stack base:** Django + HTML + Bootstrap + PostgreSQL  
**Canales:** Web + WhatsApp  
**SGA:** desacoplado; no requerido para ejecutar el MVP  
**IA:** asistiva; no ejecuta acciones administrativas críticas  
**Objetivo de esta versión:** mantener FRONT y BACK dentro del mismo SPEC, claramente separados, evitando duplicidad, módulos innecesarios y sobrearquitectura.

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
- trazabilidad.

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
- implementar RAG, agentes autónomos o MCP en el MVP.

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
│                         PostgreSQL                                │
└──────────────────────────────────────────────────────────────┘
```

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
- decisiones IA.

---

# 25. Modelo de usuario

```text
User
- id
- username
- first_name
- last_name
- email
- phone
- external_id
- source
- is_active
```

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
created_at
assigned_at
first_response_at
resolved_at
closed_at
sla_due_at
updated_at
```

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

---

# 31. Autonomy Engine

```text
N0 → consulta estructurada
N1 → conocimiento autorizado
N2 → ticket + validación
N3 → ticket + routing
N4 → revisión humana
```

---

# 32. Workflow

Transiciones:

```text
NEW → CLASSIFIED
CLASSIFIED → ASSIGNED
ASSIGNED → IN_PROGRESS
IN_PROGRESS → WAITING_USER
WAITING_USER → IN_PROGRESS
IN_PROGRESS → RESOLVED
RESOLVED → CLOSED
CLOSED → REOPENED
```

No permitido:

```text
NEW → CLOSED
```

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

---

# 35. WhatsApp

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

# 47. API compartida FRONT ↔ BACK

## Tickets

```text
POST   /api/tickets/
GET    /api/tickets/
GET    /api/tickets/{id}/
PATCH  /api/tickets/{id}/
POST   /api/tickets/{id}/assign/
POST   /api/tickets/{id}/status/
POST   /api/tickets/{id}/messages/
```

## WhatsApp

```text
GET  /api/webhooks/whatsapp/
POST /api/webhooks/whatsapp/
```

## Institucional

```text
GET /api/institutional/schedule/
GET /api/institutional/grades/
GET /api/institutional/debt/
GET /api/institutional/enrollment/
GET /api/institutional/subjects/
```

No exponer endpoints IA internos sin necesidad.

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
- PostgreSQL real en CI;
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
IA + proveedor real + fallback.

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
16. sustituye LocalProvider por SGAProvider sin cambiar lógica de negocio.

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
agents
MCP
Kubernetes
```

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
INTENT ENGINE
  ↓
AUTONOMY ENGINE
  ├── N0 → InstitutionalDataProvider → Respuesta
  ├── N1 → AIService / conocimiento → Respuesta
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

**Dependencias:** BE-T03.

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

**Dependencias:** BE-T09.

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

## 60.4 Backlog BACK

### BE-T01 — Autenticación, roles y permisos

**Objetivo:** implementar `accounts`.

**Entregables:**
- `AbstractUser`;
- Groups;
- permisos;
- login/logout;
- control horizontal y vertical.

**Criterio de aceptación:**
- matriz de permisos verificada.

---

### BE-T02 — Modelo base de usuario

**Objetivo:** extender usuario con información mínima.

**Entregables:**
- `phone`;
- `external_id`;
- `source`.

**Criterio de aceptación:**
- migraciones correctas y reversibles.

---

### BE-T03 — Creación de tickets

**Objetivo:** implementar `TicketService.create()`.

**Entregables:**
- modelo Ticket;
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
- reglas de transición;
- historial;
- transacciones atómicas.

**Criterio de aceptación:**
- transiciones inválidas rechazadas.

---

### BE-T08 — SLA y alertas

**Objetivo:** calcular vencimientos.

**Entregables:**
- SLAPolicy;
- cálculo `sla_due_at`;
- Alert.

**Criterio de aceptación:**
- alertas correctas al aproximarse y vencer.

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

**Entregables:**
- GET verificación;
- POST;
- firma;
- idempotencia.

**Criterio de aceptación:**
- duplicados no generan doble procesamiento.

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
- validación de salida.

**Criterio de aceptación:**
- salida ajustada al contrato y catálogos.

---

### BE-T18 — Fallback y auditoría IA

**Objetivo:** garantizar continuidad y trazabilidad.

**Entregables:**
- AIUsage;
- AIDecision;
- retry;
- fallback provider;
- escalamiento humano.

**Criterio de aceptación:**
- ningún fallo IA pierde la solicitud.

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
- benchmark IA;
- dataset;
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
| FE-T03 | BE-T03 |
| FE-T04 | BE-T04 |
| FE-T05 | BE-T05, BE-T07 |
| FE-T06 | BE-T04, BE-T06 |
| FE-T07 | BE-T07 |
| FE-T08 | BE-T08 |
| FE-T09 | BE-T09 |
| FE-T10 | BE-T10 |

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

