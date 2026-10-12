# DOCUMENTO DE DISEÑO DE SOFTWARE (SDD)
## MVP – Mesa de Ayuda Omnicanal con WhatsApp, Motor de Reglas e IA

**Versión:** 2.0  
**Estado:** Propuesta técnica para MVP  
**Stack base:** Django + HTML + Bootstrap + MySQL  
**Canales iniciales:** Web + WhatsApp  
**Integración SGA:** Desacoplada y no requerida para la operación del MVP

---

## 1. Resumen ejecutivo

La presente propuesta define el diseño técnico de un **MVP de Mesa de Ayuda omnicanal**, orientado a recibir, clasificar, enrutar, gestionar y mantener trazabilidad sobre solicitudes institucionales realizadas mediante una interfaz web y WhatsApp.

El MVP será construido como una solución **funcionalmente autónoma**, debido a que en esta etapa todavía no se dispone de la especificación técnica ni del modelo de datos del SGA institucional. Por esta razón, la arquitectura no dependerá directamente del SGA para operar. En su lugar, se implementará una **capa de abstracción para datos institucionales**, de manera que durante el MVP pueda trabajar con información local o de prueba y, posteriormente, incorporar un adaptador hacia el SGA sin modificar la lógica de negocio principal.

El sistema utilizará **Django, HTML, Bootstrap y MySQL**, incorporando un motor de flujo de trabajo, un motor de reglas de negocio, una capa de inteligencia artificial basada en LLM y adaptadores de integración. La IA no será responsable de acciones críticas ni de cierre automático de casos; su función será asistir en tareas como clasificación semántica, extracción de información, resumen y generación de respuestas sugeridas. Las decisiones operativas estarán gobernadas por reglas determinísticas, estados controlados y validación humana cuando corresponda.

---

## 2. Objetivo general

Diseñar e implementar un MVP de Mesa de Ayuda capaz de gestionar solicitudes desde canales web y WhatsApp, con trazabilidad completa, reglas de negocio, control de estados, métricas operativas, soporte de clasificación mediante IA y una arquitectura desacoplada que permita integrar posteriormente el SGA institucional.

---

## 3. Objetivos específicos

- Implementar una base de datos propia y estructurada para el MVP.
- Gestionar tickets con identificador único, categorías, prioridades, estados, responsables y SLA.
- Incorporar WhatsApp como canal de entrada y respuesta mediante API/Webhook.
- Mantener histórico de mensajes, estados, asignaciones, decisiones y auditoría.
- Implementar un motor de reglas de negocio en Python/Django.
- Incorporar un motor de IA desacoplado mediante proveedores LLM intercambiables.
- Definir métricas técnicas y funcionales para evaluar el comportamiento del LLM.
- Registrar consumo, latencia, errores y costos asociados al uso de IA.
- Definir mecanismos de fallback ante fallos de proveedor, timeout o baja confianza.
- Preparar la arquitectura para integrar posteriormente el SGA mediante un adaptador.

---

## 4. Alcance del MVP

### 4.1 Incluido

El MVP incluirá:

- Registro e identificación local de usuarios.
- Creación y gestión de tickets.
- Clasificación manual, por reglas y asistida por LLM.
- Enrutamiento hacia áreas responsables.
- Manejo de prioridades.
- Máquina de estados del ticket.
- Registro de SLA configurables.
- Histórico de estados y conversaciones.
- Canal web.
- Integración con WhatsApp mediante Webhook/API.
- Dashboard básico de seguimiento.
- Auditoría de acciones.
- Registro técnico de uso de LLM.
- Capa de abstracción para futura integración institucional.

### 4.2 Fuera del alcance inicial

No se considera obligatorio para el MVP:

- Integración real con el SGA.
- Automatización completa de trámites institucionales.
- Cierre autónomo de tickets por IA.
- Modificación de datos maestros institucionales.
- Procesamiento de pagos.
- Firma electrónica.
- Orquestación compleja con múltiples microservicios.
- Alta disponibilidad multi-región.

---

## 5. Principios de arquitectura

La solución seguirá los siguientes principios:

1. **Desacoplamiento:** el MVP no dependerá directamente del SGA.
2. **Trazabilidad:** toda acción relevante deberá quedar registrada.
3. **Reglas antes que IA:** las decisiones críticas serán determinísticas.
4. **IA asistiva:** el LLM propondrá, clasificará o resumirá; no ejecutará acciones institucionales críticas.
5. **Intercambiabilidad:** el proveedor LLM podrá sustituirse sin modificar la lógica principal.
6. **Configurabilidad:** categorías, prioridades, SLA y reglas deberán ser parametrizables.
7. **Auditabilidad:** las decisiones de IA deberán conservar modelo, versión, prompt, salida y validación.
8. **Evolución progresiva:** el MVP deberá poder crecer hacia integración institucional y automatización avanzada.

---

## 6. Arquitectura lógica propuesta

```text
                              ┌─────────────────────┐
                              │       USUARIO       │
                              └──────────┬──────────┘
                                         │
                          ┌──────────────┴──────────────┐
                          │                             │
                    Portal Web                     WhatsApp
                 HTML + Bootstrap                  API/Webhook
                          │                             │
                          └──────────────┬──────────────┘
                                         │
                               ┌─────────▼─────────┐
                               │      DJANGO       │
                               │ API / Views / Auth│
                               └─────────┬─────────┘
                                         │
         ┌───────────────────────────────┼──────────────────────────────┐
         │                               │                              │
┌────────▼────────┐            ┌─────────▼─────────┐          ┌─────────▼─────────┐
│ Workflow Engine │            │ Business Rules    │          │    AI Engine      │
│ Estados / SLA   │            │ Routing / Policy  │          │ LLM / NLP / JSON  │
└────────┬────────┘            └─────────┬─────────┘          └─────────┬─────────┘
         │                               │                              │
         └───────────────────────────────┼──────────────────────────────┘
                                         │
                               ┌─────────▼─────────┐
                               │      MySQL        │
                               │ Datos + Auditoría │
                               └─────────┬─────────┘
                                         │
                         ┌───────────────▼────────────────┐
                         │ Integration / Adapter Layer    │
                         ├───────────────┬────────────────┤
                         │ WhatsApp      │ SGA futuro     │
                         │ Adapter       │ Adapter        │
                         └───────────────┴────────────────┘
```

---

## 7. Componentes principales

### 7.1 Web Channel

Responsable de la interacción mediante interfaz web.

Tecnologías:

- Django Templates.
- HTML5.
- Bootstrap.
- JavaScript únicamente donde sea necesario.

Funciones:

- Crear tickets.
- Consultar tickets propios.
- Visualizar estado e histórico.
- Gestionar tickets para operadores.
- Mostrar indicadores administrativos.

### 7.2 WhatsApp Adapter

Responsable de:

- Recibir mensajes mediante webhook.
- Validar firma o autenticidad del evento cuando aplique.
- Normalizar el contenido recibido.
- Asociar mensajes con usuarios y tickets.
- Enviar respuestas mediante la API correspondiente.
- Registrar identificadores externos del mensaje.

### 7.3 Workflow Engine

Motor responsable del ciclo de vida del ticket.

Funciones:

- Estados.
- Transiciones válidas.
- Fechas de atención.
- SLA.
- Reaperturas.
- Escalamientos.
- Cierre controlado.

Implementación propuesta para MVP:

- Python nativo.
- Servicios de dominio dentro de Django.
- Validadores de transición.
- Reglas de estado centralizadas.

### 7.4 Business Rules Engine

Responsable de reglas determinísticas.

Funciones:

- Asignación por categoría.
- Selección de área.
- Prioridad.
- Escalamiento.
- Reglas de SLA.
- Restricciones de transición.
- Reglas de validación.

**Motor recomendado para MVP:** implementación propia en Python/Django con reglas configurables desde MySQL.

No se recomienda incorporar inicialmente motores externos como Drools/JBoss u otros motores Java, debido a que aumentarían infraestructura, complejidad operativa y dependencia tecnológica sin una necesidad demostrada en esta fase.

### 7.5 AI Engine

Responsable de capacidades semánticas.

Funciones permitidas:

- Clasificación de intención.
- Clasificación de categoría y subcategoría.
- Extracción de entidades o datos relevantes.
- Resumen de conversación.
- Generación de respuesta sugerida.
- Priorización sugerida.

Funciones no permitidas:

- Cerrar tickets de forma autónoma.
- Modificar datos institucionales maestros.
- Autorizar trámites.
- Ejecutar acciones financieras.
- Eliminar históricos.
- Saltarse reglas de negocio.

### 7.6 Institutional Data Provider

Capa de abstracción para información institucional.

Interfaz conceptual:

```python
class InstitutionalDataProvider:
    def get_user(self, identifier): ...
    def get_user_context(self, user_id): ...
    def validate_user(self, identifier): ...
```

Implementaciones previstas:

```text
InstitutionalDataProvider
    ├── LocalMockProvider       # MVP
    └── SGAProvider             # Fase posterior
```

---

## 8. Modelo de datos

### 8.1 Tabla `users`

```text
id                  BIGINT PK
external_id         VARCHAR(100) NULL
document_number     VARCHAR(30) NULL
first_name          VARCHAR(100)
last_name           VARCHAR(100)
email               VARCHAR(150) NULL
phone               VARCHAR(30) NULL
user_type_id        BIGINT FK
source              VARCHAR(20)     # LOCAL / SGA
is_active           BOOLEAN
created_at          DATETIME
updated_at          DATETIME
```

### 8.2 Tabla `user_types`

```text
id                  BIGINT PK
code                VARCHAR(30) UNIQUE
name                VARCHAR(100)
description         TEXT NULL
```

Valores iniciales sugeridos:

- STUDENT
- TEACHER
- ADMINISTRATIVE
- EXTERNAL

### 8.3 Tabla `channels`

```text
id                  BIGINT PK
code                VARCHAR(30) UNIQUE
name                VARCHAR(100)
is_active           BOOLEAN
```

Valores iniciales:

- WEB
- WHATSAPP

### 8.4 Tabla `ticket_categories`

```text
id                  BIGINT PK
code                VARCHAR(50) UNIQUE
name                VARCHAR(120)
description         TEXT NULL
default_area_id     BIGINT NULL FK
default_priority_id BIGINT NULL FK
is_active           BOOLEAN
```

### 8.5 Tabla `ticket_subcategories`

```text
id                  BIGINT PK
category_id         BIGINT FK
code                VARCHAR(50)
name                VARCHAR(120)
description         TEXT NULL
is_active           BOOLEAN
```

### 8.6 Tabla `service_areas`

```text
id                  BIGINT PK
code                VARCHAR(50) UNIQUE
name                VARCHAR(150)
email               VARCHAR(150) NULL
is_active           BOOLEAN
```

### 8.7 Tabla `priorities`

```text
id                  BIGINT PK
code                VARCHAR(30) UNIQUE
name                VARCHAR(50)
weight              INT
```

Valores sugeridos:

- LOW
- MEDIUM
- HIGH
- CRITICAL

### 8.8 Tabla `ticket_statuses`

```text
id                  BIGINT PK
code                VARCHAR(30) UNIQUE
name                VARCHAR(80)
is_final            BOOLEAN
display_order       INT
```

Estados:

- NEW
- CLASSIFIED
- ASSIGNED
- IN_PROGRESS
- WAITING_USER
- ESCALATED
- RESOLVED
- CLOSED
- REOPENED
- CANCELLED

### 8.9 Tabla `tickets`

```text
id                     BIGINT PK
ticket_code            VARCHAR(30) UNIQUE
user_id                BIGINT FK
channel_id             BIGINT FK
category_id            BIGINT NULL FK
subcategory_id         BIGINT NULL FK
priority_id            BIGINT FK
status_id              BIGINT FK
assigned_area_id       BIGINT NULL FK
assigned_user_id       BIGINT NULL FK
subject                VARCHAR(255)
description            TEXT
classification_source  VARCHAR(20)   # RULE / LLM / MANUAL
classification_score   DECIMAL(5,4) NULL
created_at             DATETIME
assigned_at            DATETIME NULL
first_response_at      DATETIME NULL
resolved_at            DATETIME NULL
closed_at              DATETIME NULL
sla_due_at             DATETIME NULL
created_by             BIGINT NULL
updated_at             DATETIME
```

### 8.10 Tabla `ticket_messages`

```text
id                    BIGINT PK
ticket_id             BIGINT FK
sender_type           VARCHAR(20)   # USER / AGENT / SYSTEM / AI
sender_id             BIGINT NULL
channel_id            BIGINT FK
message_type          VARCHAR(20)   # TEXT / IMAGE / FILE / AUDIO
content               TEXT
external_message_id   VARCHAR(150) NULL
llm_generated         BOOLEAN DEFAULT FALSE
llm_model_id          BIGINT NULL FK
created_at            DATETIME
```

### 8.11 Tabla `ticket_status_history`

```text
id                    BIGINT PK
ticket_id             BIGINT FK
previous_status_id    BIGINT NULL FK
new_status_id         BIGINT FK
changed_by            BIGINT NULL
reason                TEXT NULL
created_at            DATETIME
```

### 8.12 Tabla `ticket_assignments`

```text
id                    BIGINT PK
ticket_id             BIGINT FK
area_id               BIGINT FK
assigned_user_id      BIGINT NULL
assigned_by            BIGINT NULL
assigned_at           DATETIME
ended_at              DATETIME NULL
reason                TEXT NULL
```

### 8.13 Tabla `sla_policies`

```text
id                       BIGINT PK
category_id              BIGINT NULL FK
priority_id              BIGINT FK
first_response_minutes   INT
resolution_minutes       INT
business_hours_only      BOOLEAN
is_active                BOOLEAN
```

Valores iniciales de prueba para MVP:

| Prioridad | Primera respuesta | Resolución |
|---|---:|---:|
| Baja | 480 min | 4320 min |
| Media | 240 min | 2880 min |
| Alta | 60 min | 1440 min |
| Crítica | 15 min | 240 min |

Estos valores son parámetros técnicos iniciales y deberán validarse antes de convertirse en política institucional.

### 8.14 Tabla `business_rules`

```text
id                    BIGINT PK
code                  VARCHAR(50) UNIQUE
name                  VARCHAR(150)
rule_type             VARCHAR(50)
condition_json        JSON
action_json           JSON
priority_order        INT
is_active             BOOLEAN
version               INT
created_at            DATETIME
updated_at            DATETIME
```

### 8.15 Tabla `llm_models`

```text
id                    BIGINT PK
provider              VARCHAR(50)
model_name            VARCHAR(100)
model_version         VARCHAR(100) NULL
purpose               VARCHAR(100)
temperature           DECIMAL(3,2) NULL
max_tokens            INT NULL
is_active             BOOLEAN
created_at            DATETIME
```

### 8.16 Tabla `llm_prompts`

```text
id                    BIGINT PK
name                  VARCHAR(120)
version               INT
purpose               VARCHAR(100)
prompt_template       LONGTEXT
model_id              BIGINT FK
is_active             BOOLEAN
created_at            DATETIME
```

### 8.17 Tabla `llm_usage`

```text
id                    BIGINT PK
ticket_id             BIGINT NULL FK
message_id            BIGINT NULL FK
provider              VARCHAR(50)
model                  VARCHAR(100)
operation              VARCHAR(50)
input_tokens           INT NULL
output_tokens          INT NULL
total_tokens           INT NULL
latency_ms             INT NULL
estimated_cost         DECIMAL(12,6) NULL
success                BOOLEAN
error_code             VARCHAR(100) NULL
created_at             DATETIME
```

### 8.18 Tabla `ai_decisions`

```text
id                    BIGINT PK
ticket_id             BIGINT NULL FK
message_id            BIGINT NULL FK
model_id              BIGINT FK
prompt_id             BIGINT FK
task_type             VARCHAR(50)
raw_output             LONGTEXT
parsed_output          JSON NULL
confidence             DECIMAL(5,4) NULL
accepted               BOOLEAN NULL
corrected              BOOLEAN DEFAULT FALSE
corrected_by           BIGINT NULL
created_at             DATETIME
```

### 8.19 Tabla `audit_log`

```text
id                    BIGINT PK
actor_type            VARCHAR(30)
actor_id              BIGINT NULL
action                VARCHAR(100)
entity_type           VARCHAR(50)
entity_id             BIGINT NULL
metadata_json         JSON NULL
created_at            DATETIME
```

---

## 9. Relaciones principales

```text
users 1 ───── N tickets
users N ───── 1 user_types
channels 1 ─── N tickets
channels 1 ─── N ticket_messages
ticket_categories 1 ─── N ticket_subcategories
tickets 1 ───── N ticket_messages
tickets 1 ───── N ticket_status_history
tickets 1 ───── N ticket_assignments
tickets 1 ───── N ai_decisions
llm_models 1 ─── N llm_prompts
llm_models 1 ─── N ai_decisions
```

---

## 10. Flujo funcional general

```text
Usuario
  ↓
Web / WhatsApp
  ↓
Normalización de entrada
  ↓
Identificación del usuario
  ↓
¿Existe ticket activo relacionado?
  ├── Sí → Asociar mensaje
  └── No → Crear ticket
             ↓
      Clasificación inicial
             ↓
      Motor de reglas
             ↓
      ¿Se requiere LLM?
        ├── No → Enrutamiento
        └── Sí → AI Engine
                    ↓
             Resultado estructurado
                    ↓
             Validación de reglas
                    ↓
                Enrutamiento
                    ↓
                Asignación
                    ↓
                 Atención
                    ↓
                Resolución
                    ↓
           Validación y cierre
                    ↓
             Histórico + métricas
```

---

## 11. Reglas de negocio iniciales

### BR-001 – Identificador único

Todo ticket debe poseer un código único.

Formato sugerido:

```text
HD-AAAA-NNNNNN
```

Ejemplo:

```text
HD-2026-000001
```

### BR-002 – Conversación activa

Un mensaje nuevo de WhatsApp no debe crear automáticamente un nuevo ticket si existe una conversación/ticket activo compatible dentro de la ventana definida por configuración.

### BR-003 – Transiciones controladas

No se permite pasar directamente de `NEW` a `CLOSED`.

Ruta normal:

```text
NEW → CLASSIFIED → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
```

### BR-004 – Cierre humano

El LLM no puede ejecutar la transición hacia `CLOSED`.

### BR-005 – Clasificación de baja confianza

Si la clasificación automática no supera el umbral establecido, el ticket debe requerir revisión humana.

### BR-006 – Priorización

La prioridad puede ser propuesta por IA, pero su resultado debe ser validado por reglas determinísticas antes de aplicarse.

### BR-007 – SLA

Todo ticket debe asociarse a una política SLA válida según su prioridad y/o categoría.

### BR-008 – Escalamiento

Si un ticket alcanza un porcentaje configurable del tiempo de SLA sin atención, debe generar alerta y, si corresponde, escalamiento.

### BR-009 – Reapertura

Un ticket `RESOLVED` o `CLOSED` solo puede reabrirse bajo reglas definidas y debe registrar motivo.

### BR-010 – Auditoría

Toda modificación sensible de estado, responsable, prioridad, categoría o SLA debe registrarse en auditoría.

### BR-011 – Fallo del LLM

Un fallo, timeout o indisponibilidad del LLM no debe bloquear la creación ni el procesamiento básico del ticket.

### BR-012 – Integridad del histórico

Los mensajes y cambios de estado no deben eliminarse físicamente desde la operación normal del sistema.

---

## 12. Estrategia del motor de reglas

### 12.1 Motor recomendado para MVP

Se recomienda utilizar un **motor propio basado en Python/Django**, organizado en servicios de dominio y reglas configurables persistidas en MySQL.

Estructura conceptual:

```text
RuleEngine
 ├── ClassificationRules
 ├── RoutingRules
 ├── PriorityRules
 ├── SLARules
 ├── EscalationRules
 └── TransitionRules
```

Ventajas para el MVP:

- Consistencia con el stack actual.
- Menor complejidad de despliegue.
- Pruebas unitarias directas.
- Menor curva de aprendizaje.
- Ausencia de dependencia adicional de Java.
- Facilidad de evolución hacia un motor especializado si el volumen o la complejidad lo requieren.

### 12.2 Criterio para migrar a un motor externo

La adopción futura de Drools, Camunda DMN u otro motor especializado podrá evaluarse si se presentan condiciones como:

- cientos de reglas activas;
- reglas modificadas frecuentemente por usuarios no técnicos;
- necesidad de DMN/BPMN formal;
- múltiples sistemas consumidores;
- versionado de reglas independiente del ciclo de despliegue de Django.

---

## 13. Diseño del AI Engine

### 13.1 Patrón de proveedor

La aplicación no debe depender directamente de un proveedor específico.

```python
class LLMProvider:
    def classify(self, text, context=None): ...
    def extract(self, text, schema): ...
    def summarize(self, messages): ...
    def generate_response(self, context): ...
```

Implementaciones posibles:

- OpenAIProvider
- GeminiProvider
- ClaudeProvider
- QwenProvider
- LlamaProvider

### 13.2 Salida estructurada

Para clasificación, el LLM deberá responder mediante estructura JSON validable.

Ejemplo:

```json
{
  "intent": "problema_matricula",
  "category": "ACADEMIC",
  "subcategory": "ENROLLMENT",
  "priority": "MEDIUM",
  "summary": "Usuario reporta imposibilidad de realizar matrícula",
  "confidence": 0.91
}
```

El resultado debe pasar por:

```text
LLM → Schema Validation → Business Rules → Acción
```

Nunca:

```text
LLM → Acción crítica directa
```

---

## 14. Selección del LLM

El proveedor y modelo definitivo no debe definirse únicamente por preferencia tecnológica. Debe seleccionarse mediante benchmarking.

### 14.1 Modelos candidatos

Para el MVP se propone evaluar al menos tres alternativas dentro de las opciones disponibles para el proyecto, por ejemplo:

- una variante de OpenAI orientada a costo/latencia;
- Gemini Flash o equivalente;
- Qwen o Llama desplegado mediante proveedor o infraestructura propia.

La selección final deberá considerar:

- calidad de clasificación;
- cumplimiento de JSON estructurado;
- latencia;
- costo;
- estabilidad;
- disponibilidad;
- privacidad y condiciones de tratamiento de datos;
- facilidad de integración;
- capacidad de fallback.

---

## 15. Métricas para evaluar el LLM

### 15.1 Métricas de clasificación

Sobre un conjunto de tickets previamente etiquetados:

- Accuracy.
- Precision.
- Recall.
- F1-score.
- Macro F1.
- Matriz de confusión.

Criterios experimentales iniciales del MVP:

```text
Accuracy ≥ 85 %
Macro F1 ≥ 0.80
```

Estos valores constituyen metas de prueba y deberán ajustarse después de obtener datos reales.

### 15.2 Métricas de confianza

Propuesta inicial:

```text
confidence >= 0.85
    clasificación automática

0.70 <= confidence < 0.85
    clasificación sugerida + revisión

confidence < 0.70
    clasificación manual
```

La confianza reportada por el modelo deberá posteriormente contrastarse con el porcentaje real de aciertos para verificar calibración.

### 15.3 Métricas de latencia

Registrar:

- P50.
- P95.
- P99.

Metas preliminares:

```text
Clasificación LLM: P95 < 3 s
Respuesta sugerida: P95 < 5 s
```

### 15.4 Métricas de costo

Registrar por operación:

- tokens de entrada;
- tokens de salida;
- tokens totales;
- costo estimado;
- costo promedio por ticket.

### 15.5 Métricas de calidad operativa

- Porcentaje de clasificaciones aceptadas por el operador.
- Porcentaje de clasificaciones corregidas.
- Tasa de fallback.
- Tasa de error de parsing.
- Tasa de timeout.
- Porcentaje de respuestas IA modificadas antes de envío.

---

## 16. Estrategia de fallback

```text
Solicitud
   ↓
LLM principal
   │
   ├── OK → Validación → Continuar
   │
   └── Error / Timeout
            ↓
      Reintento controlado
            ↓
      ¿Disponible fallback?
        ├── Sí → Segundo proveedor/modelo
        └── No
             ↓
      Motor de reglas determinístico
             ↓
      Revisión humana
```

Reglas:

- El fallback no debe generar loops indefinidos.
- Los reintentos deben tener límite configurable.
- Todo fallo debe registrarse en `llm_usage`.
- La indisponibilidad de IA no debe impedir crear tickets.

---

## 17. Gestión de SLA

El sistema debe controlar al menos:

- tiempo hasta primera respuesta;
- tiempo total de resolución;
- tiempo en espera del usuario;
- tickets próximos a vencer;
- tickets vencidos.

Eventos mínimos:

```text
Ticket creado
   ↓
SLA calculado
   ↓
50 % del tiempo consumido → seguimiento
   ↓
80 % consumido → alerta
   ↓
100 % consumido → vencimiento / escalamiento
```

Los porcentajes deben quedar configurables.

---

## 18. Estados y transiciones

### Flujo principal

```text
NEW
 ↓
CLASSIFIED
 ↓
ASSIGNED
 ↓
IN_PROGRESS
 ├──→ WAITING_USER
 │        ↓
 │   IN_PROGRESS
 ↓
RESOLVED
 ↓
CLOSED
```

### Excepciones

```text
IN_PROGRESS → ESCALATED
RESOLVED → REOPENED
CLOSED → REOPENED   # solo bajo regla autorizada
ANY_VALID_STATE → CANCELLED  # según permisos
```

Las transiciones deberán implementarse mediante una matriz validada por el Workflow Engine.

---

## 19. Integración con WhatsApp

### 19.1 Flujo de entrada

```text
WhatsApp
  ↓
Webhook
  ↓
Validación evento
  ↓
Normalización
  ↓
Identificación usuario
  ↓
Ticket activo / nuevo ticket
  ↓
Registro mensaje
  ↓
Clasificación / reglas
  ↓
Respuesta o asignación
```

### 19.2 Histórico

Todos los mensajes deben conservar:

- dirección del mensaje;
- fecha y hora;
- canal;
- identificador externo;
- usuario remitente;
- ticket asociado;
- indicador de generación por IA;
- modelo utilizado cuando aplique.

---

## 20. API interna sugerida

Endpoints orientativos:

```text
POST   /api/tickets/
GET    /api/tickets/{id}/
PATCH  /api/tickets/{id}/
POST   /api/tickets/{id}/messages/
POST   /api/tickets/{id}/assign/
POST   /api/tickets/{id}/transition/
GET    /api/tickets/{id}/history/
POST   /api/webhooks/whatsapp/
GET    /api/catalog/categories/
GET    /api/catalog/statuses/
GET    /api/catalog/priorities/
```

Para el MVP puede utilizarse Django REST Framework si el equipo requiere una API formal. Si no existe dicha necesidad inicial, puede mantenerse la lógica en vistas Django y encapsular servicios de dominio para facilitar una futura exposición REST.

---

## 21. Seguridad y control de acceso

El MVP deberá contemplar:

- autenticación de usuarios web;
- control por roles;
- separación entre usuario final, operador, supervisor y administrador;
- protección CSRF;
- validación estricta de entrada;
- protección de webhooks;
- almacenamiento seguro de secretos;
- no registrar credenciales en logs;
- principio de mínimo privilegio;
- auditoría de acciones sensibles.

Roles iniciales sugeridos:

```text
END_USER
AGENT
SUPERVISOR
ADMIN
```

---

## 22. Observabilidad

El MVP debe registrar:

- errores de aplicación;
- errores de integración;
- errores del LLM;
- tiempos de respuesta;
- volumen de tickets;
- volumen de mensajes;
- eventos de SLA;
- cambios de estado;
- uso del modelo.

Logs recomendados:

```text
application.log
integration.log
ai.log
audit.log
```

---

## 23. Indicadores del MVP

### 23.1 Operativos

- Tickets creados por periodo.
- Tickets por categoría.
- Tickets por canal.
- Tickets por área.
- Tiempo medio de primera respuesta.
- Tiempo medio de resolución.
- Porcentaje dentro de SLA.
- Porcentaje vencido.
- Porcentaje escalado.
- Tasa de reapertura.

### 23.2 IA

- Accuracy.
- Macro F1.
- Precision.
- Recall.
- Porcentaje de clasificación aceptada.
- Porcentaje de corrección humana.
- P50/P95/P99 de latencia.
- Costo medio por operación.
- Costo medio por ticket.
- Tasa de timeout.
- Tasa de fallback.
- Tasa de errores de salida estructurada.

### 23.3 WhatsApp

- Mensajes recibidos.
- Mensajes enviados.
- Tickets originados desde WhatsApp.
- Conversaciones activas.
- Errores de webhook.
- Tiempo medio de respuesta.

---

## 24. Benchmark para selección del LLM

Se recomienda construir un dataset de prueba con tickets anonimizados o sintéticos y comparar cada modelo bajo las mismas condiciones.

| Métrica | Modelo A | Modelo B | Modelo C |
|---|---:|---:|---:|
| Accuracy | Pendiente | Pendiente | Pendiente |
| Macro F1 | Pendiente | Pendiente | Pendiente |
| JSON válido | Pendiente | Pendiente | Pendiente |
| P95 latencia | Pendiente | Pendiente | Pendiente |
| Costo/1000 casos | Pendiente | Pendiente | Pendiente |
| Tasa de timeout | Pendiente | Pendiente | Pendiente |
| Corrección humana | Pendiente | Pendiente | Pendiente |

La selección del modelo se realizará con base en evidencia experimental y no únicamente por capacidad general del proveedor.

---

## 25. Estrategia de pruebas

### 25.1 Pruebas unitarias

- reglas de transición;
- reglas de SLA;
- reglas de enrutamiento;
- normalización de mensajes;
- validación de schemas de IA.

### 25.2 Pruebas de integración

- Web → Django → MySQL.
- WhatsApp → Webhook → Ticket.
- Django → LLM Provider.
- Fallback de LLM.
- MockProvider institucional.

### 25.3 Pruebas funcionales

- creación de ticket;
- asignación;
- cambio de estado;
- reapertura;
- vencimiento SLA;
- conversación multicanal;
- revisión humana de clasificación IA.

### 25.4 Pruebas de IA

- clasificación por categoría;
- extracción estructurada;
- robustez ante mensajes incompletos;
- mensajes ambiguos;
- mensajes fuera de dominio;
- consistencia JSON;
- evaluación de costo y latencia.

---

## 26. Criterios de aceptación del MVP

El MVP se considerará funcional cuando:

1. Permita crear tickets desde web.
2. Permita crear o actualizar tickets desde WhatsApp.
3. Mantenga histórico completo de mensajes y estados.
4. Aplique transiciones de estado válidas.
5. Permita asignar tickets por reglas.
6. Calcule y registre SLA.
7. Ejecute clasificación asistida por LLM.
8. Registre modelo, prompt, latencia y consumo.
9. Active revisión humana cuando la confianza sea insuficiente.
10. Permita continuar la operación aunque el LLM falle.
11. Disponga de métricas básicas en dashboard.
12. Permita reemplazar el proveedor LLM mediante configuración/adaptador.
13. Permita conectar posteriormente un `SGAProvider` sin modificar el núcleo del dominio.

---

## 27. Fases de implementación

### Fase 1 – Núcleo funcional

- Modelo de datos.
- Usuarios locales.
- Tickets.
- Estados.
- Categorías.
- Áreas.
- Prioridades.
- Histórico.

### Fase 2 – Workflow y reglas

- Motor de transiciones.
- SLA.
- Enrutamiento.
- Alertas.
- Auditoría.

### Fase 3 – WhatsApp

- Webhook.
- Normalización.
- Asociación de conversación.
- Creación y actualización de tickets.
- Respuesta básica.

### Fase 4 – IA

- LLMProvider.
- Clasificación.
- JSON estructurado.
- Prompt versioning.
- Métricas.
- Fallback.

### Fase 5 – Benchmark y optimización

- Dataset de prueba.
- Comparación de modelos.
- Ajuste de umbrales.
- Ajuste de prompts.
- Selección del modelo de producción.

### Fase 6 – Integración institucional

- Levantamiento del SGA.
- Diseño de contrato de integración.
- Implementación de `SGAProvider`.
- Sincronización o consumo de datos autorizados.

---

## 28. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| No disponer aún del SGA | Medio | Uso de `LocalMockProvider` y arquitectura desacoplada |
| Respuestas incorrectas del LLM | Alto | Reglas determinísticas + umbral + validación humana |
| Indisponibilidad del LLM | Medio | Fallback + operación sin IA |
| Crecimiento del costo IA | Medio | Registro de tokens, benchmarking y límites |
| Duplicación de tickets por WhatsApp | Medio | Regla de conversación activa |
| Reglas difíciles de mantener | Medio | Configuración en BD y servicios centralizados |
| Datos sensibles en prompts | Alto | Minimización, filtrado y política de envío |
| Errores de webhook | Medio | Reintentos controlados e idempotencia |

---

## 29. Decisiones técnicas del MVP

### DT-001 – Django como núcleo

Se mantiene Django por alineación con el stack existente, velocidad de desarrollo y facilidad de integración con MySQL.

### DT-002 – MySQL como persistencia principal

MySQL almacenará la información operacional, histórica, de auditoría y configuración del MVP.

### DT-003 – Motor de reglas propio

El MVP utilizará Python/Django en lugar de un motor externo de reglas para reducir complejidad y mantener coherencia tecnológica.

### DT-004 – LLM desacoplado

Se implementará un patrón `LLMProvider` para evitar dependencia rígida de un proveedor.

### DT-005 – SGA desacoplado

La integración futura se realizará mediante `InstitutionalDataProvider` y `SGAProvider`.

### DT-006 – IA sin control de acciones críticas

Toda decisión crítica permanecerá bajo reglas y permisos explícitos.

---

## 30. Resultado esperado

El MVP resultante deberá demostrar que es técnicamente viable administrar una Mesa de Ayuda institucional mediante una arquitectura modular, capaz de integrar canales web y WhatsApp, mantener trazabilidad completa, aplicar reglas de negocio, medir niveles de servicio e incorporar IA de manera controlada y evaluable.

La principal característica del diseño será que **la solución puede funcionar antes de disponer de la integración real con el SGA**, sin generar deuda arquitectónica significativa. Cuando el SGA pueda ser consumido, la integración deberá incorporarse como un adaptador adicional, conservando intactos el Workflow Engine, el Business Rules Engine, la persistencia y la lógica de atención.

---

## 31. Próximos entregables técnicos recomendados

Para pasar de este SDD a construcción, se recomienda producir como siguiente conjunto de artefactos:

1. Diagrama entidad-relación definitivo.
2. Diccionario de datos por tabla.
3. Matriz completa de reglas BR-001…BR-0XX.
4. Matriz de estados y transiciones.
5. Contrato JSON del LLM.
6. Dataset inicial para benchmarking.
7. Matriz comparativa de modelos LLM.
8. Especificación de endpoints.
9. Modelo de permisos y roles.
10. Plan de pruebas del MVP.
11. Backlog técnico priorizado por sprint.

