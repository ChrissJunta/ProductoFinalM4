# SPEC – MVP Mesa de Ayuda Omnicanal con WhatsApp, IA y futura integración SGA
**Versión:** 3.0  
**Estado:** Propuesta técnica ejecutiva para desarrollo  
**Stack base:** Django + HTML + Bootstrap + MySQL  
**Canales iniciales:** Web + WhatsApp  
**Integración SGA:** desacoplada y no bloqueante para el MVP

---

# 1. Propósito

El presente documento define la especificación funcional y técnica del MVP de una **Mesa de Ayuda Omnicanal** orientada a gestionar solicitudes institucionales mediante una interfaz web y un canal conversacional de WhatsApp.

El sistema deberá ser capaz de responder automáticamente consultas institucionales simples y estructuradas; interpretar lenguaje natural mediante un LLM; clasificar solicitudes; determinar el nivel de autonomía permitido; crear tickets cuando la solicitud requiera seguimiento; enrutar tickets hacia el departamento correspondiente; gestionar estados, responsables, SLA e históricos; conservar trazabilidad completa de las decisiones del sistema; operar inicialmente sin depender de la integración real con el SGA; y permitir incorporar posteriormente el SGA mediante una capa de integración desacoplada.

---

# 2. Objetivos del MVP

1. Disponer de una base propia de usuarios, tickets, mensajes, categorías, estados, reglas y métricas.
2. Implementar atención web y WhatsApp utilizando un mismo modelo de ticket.
3. Automatizar consultas de baja complejidad que no requieran intervención humana.
4. Incorporar un motor de intenciones para determinar qué desea el usuario.
5. Incorporar un motor de autonomía para decidir qué puede responder automáticamente el sistema.
6. Utilizar un LLM como componente de interpretación, clasificación, resumen y generación asistida de respuestas.
7. Mantener las decisiones críticas bajo reglas determinísticas o intervención humana.
8. Incorporar clasificación y enrutamiento automático por departamento.
9. Registrar métricas funcionales, operativas y de IA.
10. Permitir futura conexión con el SGA sin modificar el núcleo funcional.

---

# 3. Alcance

## 3.1 Incluido en el MVP

- autenticación local;
- perfiles básicos de usuario;
- canal web;
- integración con WhatsApp mediante API/Webhook;
- recepción de mensajes;
- identificación de intención;
- clasificación de solicitudes;
- respuestas automáticas;
- creación y gestión de tickets;
- categorías y subcategorías;
- prioridades;
- áreas/departamentos;
- asignación y reasignación;
- estados de ticket;
- histórico completo;
- SLA;
- alertas;
- reglas de negocio;
- motor de enrutamiento;
- motor de autonomía;
- proveedor LLM intercambiable;
- prompt versioning;
- métricas del LLM;
- auditoría;
- datos locales simulados para sustituir temporalmente al SGA;
- adaptador institucional preparado para integración futura.

## 3.2 Fuera del alcance inicial

- modificación directa de datos académicos o financieros;
- modificación de notas;
- eliminación de deuda;
- aprobación automática de trámites;
- matrícula automática;
- cierre autónomo de reclamos administrativos;
- integración definitiva con SGA sin contar con API o especificación técnica;
- entrenamiento propio de un LLM;
- despliegue productivo institucional definitivo.

---

# 4. Principios de diseño

1. **Desacoplamiento:** el MVP no dependerá de la disponibilidad del SGA.
2. **Trazabilidad:** toda acción importante deberá quedar registrada.
3. **Control humano:** las decisiones institucionales sensibles requerirán validación humana.
4. **IA asistiva:** el LLM interpreta y propone; no gobierna el sistema.
5. **Reglas determinísticas:** estados, permisos, SLA, restricciones y enrutamiento deben controlarse mediante reglas.
6. **Omnicanalidad:** web y WhatsApp deben utilizar el mismo modelo de ticket.
7. **Configurabilidad:** categorías, intenciones, respuestas, reglas y destinos deben mantenerse en base de datos cuando sea posible.
8. **Sustituibilidad:** el proveedor LLM y el proveedor de datos institucionales deberán poder cambiarse sin alterar el núcleo de negocio.

---

# 5. Arquitectura lógica de referencia

```text
┌──────────────────────────────────────────────────────────────┐
│                    CAPA DE CANALES                           │
│                                                              │
│   Portal Web                         WhatsApp                │
│   HTML + Bootstrap                  API / Webhook            │
└───────────────┬───────────────────────────┬──────────────────┘
                │                           │
                ▼                           ▼
┌──────────────────────────────────────────────────────────────┐
│                 CAPA DE INTERFAZ / API                       │
│                                                              │
│      Django Views / REST / Webhooks / Validaciones           │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                   CAPA DE APLICACIÓN                         │
│                                                              │
│ Ticket Service     Conversation Service     User Service     │
│ SLA Service        Notification Service     Audit Service    │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    CAPA DE DOMINIO                           │
│                                                              │
│ Intent Engine        Autonomy Engine                         │
│ Business Rules       Routing Engine                          │
│ Workflow Engine      SLA Engine                              │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│               CAPA DE INTELIGENCIA ARTIFICIAL               │
│                                                              │
│ AI / LLM Engine                                              │
│                                                              │
│ Classification │ Extraction │ Summary │ Response Generation │
│ Prompt Manager │ Model Selector │ Validator │ Fallback      │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    CAPA DE INTEGRACIÓN                       │
│                                                              │
│ WhatsApp Adapter                                             │
│ InstitutionalDataProvider                                    │
│    ├── LocalProvider (MVP)                                   │
│    └── SGAProvider (futuro)                                  │
│ LLM Provider Adapter                                         │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    CAPA DE PERSISTENCIA                      │
│                           MySQL                              │
│                                                              │
│ Users │ Tickets │ Messages │ Status │ Categories             │
│ Intents │ Rules │ Routing │ SLA │ Models │ Prompts           │
│ AI Decisions │ LLM Usage │ Audit │ Alerts                   │
└──────────────────────────────────────────────────────────────┘
```

---

# 6. Estructura del proyecto Django

```text
project/
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── users/
│   ├── tickets/
│   ├── conversations/
│   ├── catalogs/
│   ├── intents/
│   ├── rules/
│   ├── routing/
│   ├── sla/
│   ├── ai/
│   ├── integrations/
│   ├── notifications/
│   └── audit/
│
├── templates/
├── static/
├── media/
└── manage.py
```

---

# 7. Motor de intenciones

El sistema deberá identificar la intención del usuario antes de determinar cómo responder.

## 7.1 Intenciones automáticas iniciales

| Código | Intención | Descripción | Requiere autenticación | Requiere humano |
|---|---|---|---|---|
| CHECK_SCHEDULE | Consultar horario | Consulta horario del usuario | Sí | No |
| CHECK_GRADE | Consultar notas | Consulta calificaciones registradas | Sí | No |
| CHECK_DEBT | Consultar deuda pendiente | Consulta saldos pendientes | Sí | No |
| CHECK_ENROLLMENT | Consultar estado de matrícula | Consulta estado del período | Sí | No |
| CHECK_SUBJECTS | Consultar materias matriculadas | Lista asignaturas | Sí | No |
| CHECK_TICKET | Consultar estado de ticket | Consulta ticket propio | Sí | No |
| CHECK_ACADEMIC_DATES | Consultar fechas académicas | Consulta calendario parametrizado | No/Parcial | No |
| CHECK_CONTACT | Consultar contacto institucional | Devuelve contacto de área | No | No |
| CHECK_REQUIREMENTS | Consultar requisitos de trámite | Consulta base de conocimiento | No | No |

## 7.2 Intenciones que requieren validación

| Código | Intención | Acción automática permitida | Destino probable |
|---|---|---|---|
| GRADE_DISCREPANCY | Inconsistencia en nota | Clasificar, resumir, crear ticket | Académico |
| PAYMENT_NOT_REFLECTED | Pago no reflejado | Solicitar comprobante, crear ticket | Financiero |
| DEBT_DISPUTE | Deuda posiblemente incorrecta | Resumir y crear ticket | Financiero |
| ENROLLMENT_PROBLEM | Problema de matrícula | Clasificar y crear ticket | Registro/Académico |
| SUBJECT_NOT_VISIBLE | Materia no visible | Recopilar datos y crear ticket | Académico |
| ACCESS_PROBLEM | Problema de acceso | Diagnóstico inicial | TI |
| PASSWORD_PROBLEM | Problema de contraseña | Orientación o ticket | TI |
| CERTIFICATE_REQUEST | Solicitud de certificado | Identificar tipo | Secretaría |
| PROFILE_UPDATE | Actualización de datos | Recopilar cambio solicitado | Área responsable |
| GENERAL_COMPLAINT | Reclamo general | Clasificar, resumir y enrutar | Según categoría |
| UNKNOWN_REQUEST | Solicitud no identificada | Escalar | Revisión humana |

---

# 8. Motor de autonomía

El sistema deberá determinar qué nivel de autonomía corresponde a cada intención.

| Nivel | Descripción | Respuesta |
|---|---|---|
| N0 | Consulta determinística | Respuesta automática desde fuente estructurada |
| N1 | Consulta basada en conocimiento | Respuesta automática asistida por LLM |
| N2 | Solicitud que requiere validación | IA clasifica y crea ticket |
| N3 | Gestión administrativa | Ticket + enrutamiento + agente humano |
| N4 | Caso ambiguo/no identificado | Revisión manual |

## 8.1 Regla general

```text
INTENT
   ↓
AUTONOMY ENGINE
   ↓
N0 → DataProvider → Respuesta automática
N1 → Knowledge/LLM → Respuesta automática
N2 → Ticket → Validación
N3 → Ticket → Routing → Departamento
N4 → Revisión humana
```

---

# 9. Estrategia de respuestas WhatsApp

## 9.1 Tipos de respuesta

1. Recepción.
2. Identificación.
3. Consulta automática.
4. Orientación basada en conocimiento.
5. Solicitud de información adicional.
6. Confirmación de creación de ticket.
7. Seguimiento.
8. Escalamiento.
9. Resolución.
10. Cierre.
11. Contingencia.

## 9.2 Principios de respuesta

- mensajes breves;
- lenguaje claro;
- no exponer detalles técnicos;
- no inventar datos institucionales;
- distinguir información confirmada de información sugerida;
- solicitar solamente datos necesarios;
- evitar repetir preguntas si la información ya existe en la conversación.

---

# 10. Flujo WhatsApp – Consulta automática

Ejemplo: “¿Qué clases tengo mañana?”

```text
WhatsApp
   ↓
Webhook
   ↓
Conversation Service
   ↓
Intent Engine
   ↓
CHECK_SCHEDULE
   ↓
Autonomy Engine = N0
   ↓
InstitutionalDataProvider
   ↓
LocalProvider (MVP)
   ↓
Respuesta
   ↓
WhatsApp
```

---

# 11. Flujo WhatsApp – Solicitud con validación

Ejemplo: “Mi nota está mal.”

```text
WhatsApp
   ↓
Conversation Service
   ↓
Intent Engine
   ↓
LLM
   ↓
GRADE_DISCREPANCY
   ↓
Autonomy Engine = N2
   ↓
Ticket Service
   ↓
Business Rules
   ↓
Routing Engine
   ↓
Área Académica
   ↓
Agente humano
```

---

# 12. Motor de reglas de negocio

Para el MVP se propone implementar un motor propio en Python/Django, con configuración respaldada en MySQL.

No se considera necesario incorporar inicialmente un motor externo como Drools/JBoss.

## 12.1 Tipos de reglas

- clasificación;
- validación;
- prioridad;
- SLA;
- enrutamiento;
- escalamiento;
- permisos;
- transiciones de estado;
- restricciones de IA.

---

# 13. Reglas de negocio principales

## BR-001 – Identificador único
Todo ticket debe tener un identificador único.

Formato sugerido:

```text
HD-AAAA-NNNNNN
```

## BR-002 – Conversación activa
Un mensaje de WhatsApp no genera automáticamente un nuevo ticket si existe un caso activo compatible.

## BR-003 – Transiciones controladas
No se permitirá pasar de `NEW` a `CLOSED` directamente.

## BR-004 – Restricción LLM
El LLM no podrá modificar notas, eliminar deuda, cambiar matrícula, aprobar trámites, modificar datos maestros ni cerrar casos administrativos por decisión propia.

## BR-005 – Validación humana
Toda solicitud administrativa con impacto institucional debe requerir validación humana.

## BR-006 – Datos estructurados
Las consultas de horario, nota, deuda o matrícula deben responderse exclusivamente desde fuentes estructuradas autorizadas.

## BR-007 – Confianza
Las clasificaciones de baja confianza deben escalarse o solicitar información adicional.

## BR-008 – Trazabilidad
Toda clasificación, reasignación, cambio de estado y uso de IA deberá quedar registrado.

## BR-009 – Reasignación
Un agente podrá reasignar un ticket. El cambio deberá generar registro en auditoría.

## BR-010 – Cierre
El cierre deberá producirse únicamente después de resolución o decisión del agente autorizado.

---

# 14. Workflow de tickets

Estados propuestos:

```text
NEW
↓
CLASSIFIED
↓
ASSIGNED
↓
IN_PROGRESS
↓
WAITING_USER
↓
RESOLVED
↓
CLOSED
```

Estados adicionales:

```text
ESCALATED
REOPENED
CANCELLED
```

---

# 15. Motor de enrutamiento

El sistema deberá mapear intención/categoría/subcategoría hacia un departamento.

| Categoría | Subcategoría | Departamento |
|---|---|---|
| Académico | Nota incorrecta | Académico / Coordinación |
| Académico | Matrícula | Registro / Secretaría |
| Financiero | Deuda | Financiero |
| Financiero | Pago no reflejado | Financiero |
| Tecnología | SGA | TI |
| Tecnología | Correo institucional | TI |
| Tecnología | Plataforma virtual | TI |
| Bienestar | Becas | Bienestar Estudiantil |
| Administrativo | Certificados | Secretaría |
| General | No identificado | Revisión inicial |

La asignación final se determinará mediante reglas configurables.

---

# 16. Integración futura con SGA

Se define la interfaz conceptual:

```text
InstitutionalDataProvider
│
├── LocalProvider
└── SGAProvider
```

## 16.1 Operación durante el MVP

`LocalProvider` suministrará datos simulados o parametrizados.

## 16.2 Operación futura

`SGAProvider` implementará autenticación contra servicio; consulta de usuarios; horario; notas; deuda; matrícula; asignaturas; y otros datos autorizados.

El núcleo funcional no deberá conocer qué proveedor se encuentra activo.

---

# 17. Motor IA / LLM

## 17.1 Funciones permitidas

- detectar intención;
- clasificar;
- subclasificar;
- extraer entidades;
- resumir conversación;
- detectar información faltante;
- sugerir prioridad;
- sugerir departamento;
- generar respuesta basada en contexto autorizado;
- identificar solicitudes duplicadas;
- transformar lenguaje natural en salida estructurada.

## 17.2 Funciones no permitidas

- tomar decisiones administrativas finales;
- modificar información académica;
- modificar información financiera;
- aprobar trámites;
- ejecutar acciones irreversibles sin autorización;
- generar información institucional no disponible en fuentes autorizadas.

---

# 18. Abstracción del proveedor LLM

```python
class LLMProvider:
    def classify(self, text, context): ...
    def extract(self, text, schema): ...
    def summarize(self, messages): ...
    def generate_response(self, context): ...
```

El sistema deberá permitir múltiples implementaciones.

---

# 19. Selección y evaluación del LLM

No se fijará un modelo definitivo sin benchmarking.

Candidatos iniciales a evaluar:
- modelos OpenAI;
- Gemini Flash;
- Qwen;
- Llama u otros modelos compatibles.

La selección deberá considerar precisión, Macro F1, latencia, costo, consistencia estructural, facilidad de integración, estabilidad, privacidad y tasa de fallback.

---

# 20. Contrato de salida de clasificación

```json
{
  "intent": "GRADE_DISCREPANCY",
  "category": "ACADEMIC",
  "subcategory": "GRADES",
  "priority": "MEDIUM",
  "summary": "El usuario reporta diferencia entre la nota registrada y la indicada por el docente.",
  "requires_human": true,
  "confidence": 0.91
}
```

La salida debe ser validada antes de utilizarse.

---

# 21. Estrategia de confianza

Parámetros iniciales de prueba:

```text
confidence >= 0.85
→ clasificación automática

0.70 <= confidence < 0.85
→ sugerencia + validación

confidence < 0.70
→ revisión humana
```

Estos valores deberán calibrarse con datos reales del MVP.

---

# 22. Fallback del LLM

```text
Solicitud
   ↓
LLM principal
   ↓
¿Resultado válido?
  Sí → continuar
  No
   ↓
Reintento
   ↓
Modelo alternativo
   ↓
¿Resultado válido?
  Sí → continuar
  No
   ↓
Reglas determinísticas
   ↓
Revisión humana
```

---

# 23. Modelo de datos

## 23.1 users

```text
id
external_id
document_number
first_name
last_name
email
phone
user_type_id
source
is_active
created_at
updated_at
```

## 23.2 user_types

```text
id
code
name
description
```

## 23.3 tickets

```text
id
ticket_code
user_id
channel_id
category_id
subcategory_id
priority_id
status_id
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
created_by
updated_at
```

## 23.4 ticket_messages

```text
id
ticket_id
sender_type
sender_id
channel_id
message_type
content
external_message_id
llm_generated
llm_model_id
created_at
```

## 23.5 ticket_statuses

```text
id
code
name
is_final
display_order
```

## 23.6 ticket_status_history

```text
id
ticket_id
previous_status_id
new_status_id
changed_by
reason
created_at
```

## 23.7 ticket_categories

```text
id
code
name
description
default_area_id
default_priority_id
is_active
```

## 23.8 ticket_subcategories

```text
id
category_id
code
name
description
is_active
```

## 23.9 service_areas

```text
id
code
name
email
active
```

## 23.10 sla_policies

```text
id
category_id
priority_id
first_response_minutes
resolution_minutes
business_hours_only
active
```

## 23.11 intent_catalog

```text
id
code
name
description
automation_level
requires_authentication
requires_llm
requires_human
active
```

## 23.12 intent_actions

```text
id
intent_id
action_type
service
endpoint
response_template
fallback_action
active
```

## 23.13 routing_rules

```text
id
intent_id
category_id
subcategory_id
department_id
priority_id
requires_validation
active
```

## 23.14 business_rules

```text
id
code
name
rule_type
configuration_json
priority
active
created_at
updated_at
```

## 23.15 llm_models

```text
id
provider
model_name
version
purpose
temperature
max_tokens
active
created_at
```

## 23.16 llm_prompts

```text
id
name
version
purpose
prompt_template
model_id
active
created_at
```

## 23.17 llm_usage

```text
id
ticket_id
message_id
provider
model
operation
input_tokens
output_tokens
total_tokens
latency_ms
estimated_cost
success
error_code
created_at
```

## 23.18 ai_decisions

```text
id
ticket_id
message_id
model_id
prompt_id
task_type
raw_output
parsed_output
confidence
accepted
corrected
corrected_by
created_at
```

## 23.19 alerts

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

## 23.20 audit_logs

```text
id
actor_type
actor_id
action
entity_type
entity_id
previous_value
new_value
metadata_json
created_at
```

---

# 24. Conversación y contexto

El sistema deberá conservar contexto conversacional para interpretar mensajes dependientes.

Ejemplo:

```text
Usuario: ¿Cuánto debo?
Sistema: $250.
Usuario: Pero eso ya lo pagué.
```

El segundo mensaje debe interpretarse en el contexto de la deuda consultada previamente.

Campos recomendados:

```text
conversation_id
ticket_id
active_intent
context_summary
last_message_at
```

No deberá enviarse al LLM un histórico ilimitado; se utilizará una ventana controlada o resumen de contexto.

---

# 25. API interna propuesta

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
GET    /api/webhooks/whatsapp/
POST   /api/webhooks/whatsapp/
```

## Intenciones

```text
POST   /api/intents/classify/
GET    /api/intents/
```

## IA

```text
POST   /api/ai/classify/
POST   /api/ai/summarize/
POST   /api/ai/extract/
```

## Datos institucionales

```text
GET /api/institutional/schedule/
GET /api/institutional/grades/
GET /api/institutional/debt/
GET /api/institutional/enrollment/
```

---

# 26. SLA inicial parametrizable

| Prioridad | Primera respuesta | Resolución |
|---|---:|---:|
| Baja | 480 min | 4320 min |
| Media | 240 min | 2880 min |
| Alta | 60 min | 1440 min |
| Crítica | 15 min | 240 min |

Estos tiempos son parámetros iniciales del MVP y deberán validarse institucionalmente.

---

# 27. Métricas funcionales

- tickets creados;
- tickets resueltos;
- tickets abiertos;
- tickets por departamento;
- tickets por categoría;
- tickets por canal;
- tiempo promedio de primera respuesta;
- tiempo promedio de resolución;
- porcentaje de cumplimiento SLA;
- porcentaje de reapertura;
- porcentaje de reasignación.

---

# 28. Métricas IA

- Accuracy;
- Precision;
- Recall;
- Macro F1;
- clasificación automática correcta;
- porcentaje de correcciones humanas;
- tasa de aceptación;
- tasa de fallback;
- latencia P50;
- latencia P95;
- latencia P99;
- tokens por operación;
- costo por operación;
- costo promedio por ticket;
- errores por proveedor;
- salidas inválidas.

Objetivos experimentales iniciales:

```text
Accuracy >= 85 %
Macro F1 >= 0.80
```

No deberán interpretarse como valores institucionales definitivos hasta disponer de dataset real.

---

# 29. Métricas WhatsApp

- mensajes recibidos;
- mensajes respondidos;
- conversaciones iniciadas;
- tickets creados desde WhatsApp;
- conversaciones resueltas sin humano;
- mensajes fallidos;
- errores webhook;
- tiempo medio de respuesta;
- porcentaje de automatización.

---

# 30. Seguridad

El MVP deberá contemplar autenticación, autorización por roles, mínimo privilegio, validación de payloads, protección CSRF en interfaces web, protección de endpoints, gestión segura de secretos, cifrado en tránsito, auditoría, sanitización de entradas, restricción de datos enviados a LLM, control de adjuntos, límites de tamaño y rate limiting cuando corresponda.

---

# 31. Roles iniciales

## Usuario
- crear solicitudes;
- consultar estado;
- responder mensajes;
- consultar datos autorizados.

## Agente
- revisar tickets;
- responder;
- cambiar estados;
- solicitar información;
- resolver casos.

## Supervisor
- reasignar;
- escalar;
- monitorear SLA;
- revisar métricas.

## Administrador
- gestionar catálogos;
- reglas;
- departamentos;
- prompts;
- modelos;
- permisos;
- configuraciones.

---

# 32. Auditoría

Se deberán registrar al menos inicio/cierre de ticket, cambios de estado, asignaciones, reasignaciones, cambios de prioridad, respuestas del agente, clasificación IA, modelo utilizado, prompt utilizado, confianza, correcciones humanas, errores y acciones administrativas.

---

# 33. Casos de aceptación prioritarios

## CA-001 – Consultar horario
El usuario solicita su horario y obtiene respuesta sin intervención humana.

## CA-002 – Consultar nota
El usuario consulta una nota registrada y recibe el dato desde la fuente estructurada.

## CA-003 – Consultar deuda
El usuario consulta saldo pendiente y recibe respuesta automática.

## CA-004 – Nota incorrecta
El usuario reporta inconsistencia; el sistema genera ticket y lo dirige al área correspondiente.

## CA-005 – Pago no reflejado
El sistema solicita información adicional, genera ticket y lo enruta a financiero.

## CA-006 – Solicitud ambigua
El sistema intenta clasificar; si la confianza es insuficiente, escala a humano.

## CA-007 – Error LLM
El sistema ejecuta fallback y no pierde la solicitud.

## CA-008 – Reasignación
Un agente reasigna el ticket y queda registro de auditoría.

## CA-009 – Consulta de estado
El usuario consulta un ticket y recibe el estado actual.

## CA-010 – Conversación contextual
El sistema interpreta correctamente un mensaje dependiente del contexto previo.

---

# 34. Fases de implementación

## Fase 1 – Núcleo
- proyecto Django;
- usuarios;
- tickets;
- estados;
- categorías;
- áreas;
- MySQL;
- panel web.

## Fase 2 – Workflow y reglas
- motor de estados;
- reglas;
- routing;
- SLA;
- auditoría.

## Fase 3 – WhatsApp
- webhook;
- recepción;
- envío;
- conversaciones;
- históricos.

## Fase 4 – Intenciones y autonomía
- intent catalog;
- autonomy engine;
- respuestas automáticas.

## Fase 5 – IA
- LLMProvider;
- clasificación;
- resumen;
- extracción;
- prompts;
- métricas;
- fallback.

## Fase 6 – Integración institucional
- LocalProvider;
- contrato InstitutionalDataProvider;
- preparación SGAProvider.

## Fase 7 – Validación del MVP
- dataset;
- pruebas;
- benchmarking;
- métricas;
- evaluación de costos;
- ajustes de reglas.

---

# 35. Decisiones técnicas consolidadas

## DT-001
Django será el framework central del MVP.

## DT-002
MySQL será la base de datos principal.

## DT-003
HTML + Bootstrap se utilizarán para la interfaz web inicial.

## DT-004
WhatsApp será un canal adicional, no una base independiente de tickets.

## DT-005
El SGA se integrará mediante un adapter/provider desacoplado.

## DT-006
El MVP podrá operar mediante LocalProvider mientras no exista integración con el SGA.

## DT-007
Las reglas críticas se implementarán en Python/Django y datos configurables en MySQL.

## DT-008
El LLM no será responsable del workflow ni de decisiones administrativas críticas.

## DT-009
El proveedor LLM deberá ser intercambiable.

## DT-010
Todo uso de IA deberá registrar modelo, prompt, latencia, confianza y resultado.

## DT-011
Se incorporará un Autonomy Engine para decidir cuándo responder, cuándo validar y cuándo escalar.

## DT-012
Se incorporará un Routing Engine para dirigir los tickets al departamento adecuado.

---

# 36. Criterio de finalización del MVP

El MVP podrá considerarse funcional cuando:

1. pueda recibir solicitudes desde web y WhatsApp;
2. pueda identificar al usuario localmente;
3. pueda reconocer las intenciones automáticas principales;
4. pueda responder horario, nota y deuda desde una fuente estructurada simulada;
5. pueda detectar solicitudes que requieren validación;
6. pueda crear tickets automáticamente;
7. pueda enrutar tickets por departamento;
8. pueda gestionar estados;
9. pueda registrar conversaciones;
10. pueda calcular SLA;
11. pueda utilizar al menos un proveedor LLM;
12. pueda ejecutar fallback;
13. pueda registrar métricas;
14. pueda auditar decisiones IA;
15. pueda operar sin conexión real al SGA;
16. pueda incorporar posteriormente un SGAProvider sin reestructurar el núcleo.

---

# 37. Resumen arquitectónico

```text
CANAL
↓
INTERFAZ
↓
SERVICIOS DE APLICACIÓN
↓
INTENCIONES / AUTONOMÍA / REGLAS / WORKFLOW / ROUTING
↓
IA / LLM
↓
INTEGRACIONES
↓
PERSISTENCIA
```

La responsabilidad del LLM será **comprender, clasificar, extraer, resumir y asistir**.

La responsabilidad del sistema será **validar, decidir el nivel de autonomía, aplicar reglas, mantener el workflow, enrutar, auditar y controlar la operación**.

La responsabilidad humana será **resolver, validar o decidir aquellos casos que impliquen gestión institucional, excepción, incertidumbre o modificación de información oficial**.

---

# 38. Próximos artefactos recomendados

1. Diagrama de arquitectura de componentes.
2. Diagrama de despliegue.
3. Diagrama entidad-relación.
4. Diagrama de secuencia WhatsApp – consulta automática.
5. Diagrama de secuencia WhatsApp – ticket con intervención humana.
6. Matriz completa de intenciones.
7. Matriz de reglas de negocio.
8. Matriz de permisos por rol.
9. Catálogo de endpoints.
10. Casos de prueba del MVP.
11. Dataset inicial para evaluación de clasificación.
12. Benchmark de proveedores LLM.
