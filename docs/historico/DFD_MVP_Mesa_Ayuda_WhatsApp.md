# Diagramas de Flujo de Datos (DFD)
## MVP – Mesa de Ayuda con Canal Web y WhatsApp

### 1. Objetivo de los diagramas

Los siguientes Diagramas de Flujo de Datos (DFD) describen de forma visual el funcionamiento del MVP de Mesa de Ayuda. Su propósito es representar las entidades externas, procesos internos, almacenes de datos y flujos de información que intervienen desde la recepción de una solicitud hasta su clasificación, asignación, seguimiento, resolución y cierre.

El diseño parte del principio de que el MVP debe ser funcional aun cuando la integración con el SGA institucional no se encuentre disponible. Para ello se considera una fuente local de datos de prueba y una capa de abstracción que permitirá incorporar posteriormente un proveedor de datos institucionales sin alterar la lógica principal del sistema.

---

## 2. Convenciones utilizadas

| Elemento | Significado |
|---|---|
| Entidad externa | Actor o sistema que intercambia información con el MVP |
| Proceso | Transformación o procesamiento de información |
| Almacén de datos | Persistencia de información en MySQL |
| Flujo de datos | Información que se mueve entre entidades, procesos y almacenes |
| LLM | Modelo de lenguaje utilizado como componente de apoyo semántico |
| SGA | Sistema de Gestión Académica institucional |

---

# Figura DFD-01. Diagrama de Contexto – Nivel 0

```mermaid
flowchart LR
    U[Usuario]
    A[Agente / Operador]
    W[WhatsApp API]
    S[SGA Futuro / Sistema Institucional]
    L[Proveedor LLM]
    SYS[MVP Mesa de Ayuda]

    U -->|Solicitud / Consulta| SYS
    SYS -->|Respuesta / Estado del ticket| U

    A -->|Gestión / Seguimiento / Resolución| SYS
    SYS -->|Bandeja / Alertas / Historial| A

    W -->|Mensajes entrantes| SYS
    SYS -->|Mensajes salientes| W

    SYS -->|Consulta futura de datos| S
    S -->|Datos institucionales| SYS

    SYS -->|Clasificación / Resumen / Sugerencias| L
    L -->|Resultado IA| SYS
```

**Descripción:**  
El MVP se presenta como un único sistema que interactúa con usuarios, operadores, WhatsApp, un proveedor LLM y, en una fase posterior, con el SGA institucional. El LLM actúa como un componente de apoyo y no como controlador principal del proceso.

---

# Figura DFD-02. Diagrama General del Sistema – Nivel 1

```mermaid
flowchart LR
    U[Usuario]
    A[Agente / Operador]
    W[WhatsApp API]
    L[Proveedor LLM]
    S[SGA Futuro]

    P1[1.0 Gestión de Solicitudes]
    P2[2.0 Clasificación y Enrutamiento]
    P3[3.0 Gestión de Tickets]
    P4[4.0 Gestión Conversacional]
    P5[5.0 Gestión de SLA y Alertas]
    P6[6.0 Integración Institucional]

    D1[(D1 Usuarios)]
    D2[(D2 Tickets)]
    D3[(D3 Mensajes e Históricos)]
    D4[(D4 Reglas de Negocio)]
    D5[(D5 SLA y Configuración)]
    D6[(D6 Auditoría IA)]
    D7[(D7 Catálogos)]

    U -->|Solicitud web| P1
    W -->|Mensaje WhatsApp| P4
    A -->|Acciones de gestión| P3

    P1 --> P2
    P4 --> P2
    P2 --> P3
    P3 --> P5
    P6 --> P1

    P1 <--> D1
    P2 <--> D4
    P2 <--> D7
    P3 <--> D2
    P4 <--> D3
    P5 <--> D5
    P2 <--> D6

    P2 -->|Solicitud de clasificación| L
    L -->|Resultado IA| P2

    P6 -->|Consulta de datos| S
    S -->|Datos institucionales| P6

    P3 -->|Estado / Respuesta| U
    P4 -->|Mensaje de salida| W
    P3 -->|Bandeja / Seguimiento| A
```

**Descripción:**  
El sistema se divide en seis procesos principales: recepción de solicitudes, clasificación y enrutamiento, gestión de tickets, gestión conversacional, control de SLA e integración institucional. La información se almacena en estructuras propias del MVP dentro de MySQL.

---

# Figura DFD-03. Registro y Creación de Ticket – Nivel 2

```mermaid
flowchart TD
    U[Usuario]
    W[WhatsApp API]

    P11[1.1 Recepción de solicitud]
    P12[1.2 Validación / Identificación de usuario]
    P13[1.3 Identificación de canal]
    P14[1.4 Registro inicial]
    P15[1.5 Generación de ticket]

    D1[(D1 Usuarios)]
    D2[(D2 Tickets)]
    D3[(D3 Mensajes)]
    D7[(D7 Catálogos)]

    U -->|Formulario web| P11
    W -->|Mensaje recibido| P11

    P11 --> P12
    P12 <--> D1
    P12 --> P13
    P13 --> P14
    P14 --> D3
    P14 --> P15
    P15 <--> D7
    P15 --> D2
```

**Descripción:**  
Toda solicitud recibida por web o WhatsApp es identificada, asociada a un usuario y registrada. Posteriormente se genera un ticket único. En el MVP, la identificación del usuario podrá realizarse con información local; posteriormente podrá enlazarse con datos institucionales.

---

# Figura DFD-04. Clasificación y Enrutamiento – Nivel 2

```mermaid
flowchart TD
    T[Ticket creado]

    P21[2.1 Preprocesamiento]
    P22[2.2 Evaluación de reglas]
    P23[2.3 Análisis con LLM]
    P24[2.4 Evaluación de confianza]
    P25[2.5 Determinación de categoría y prioridad]
    P26[2.6 Asignación de área]
    P27[2.7 Validación humana cuando aplique]

    D4[(D4 Reglas de Negocio)]
    D7[(D7 Categorías / Prioridades)]
    D8[(D8 Áreas de Servicio)]
    D6[(D6 Auditoría IA)]

    L[Proveedor LLM]

    T --> P21
    P21 --> P22
    P22 <--> D4

    P22 --> P23
    P23 -->|Solicitud estructurada| L
    L -->|Intención / Categoría / Resumen| P23

    P23 --> P24
    P24 --> D6
    P24 --> P25
    P25 <--> D7
    P25 --> P26
    P26 <--> D8
    P26 --> P27
```

**Descripción:**  
La clasificación se realiza mediante una combinación de reglas determinísticas y apoyo del LLM. El resultado del LLM no se aplica directamente; debe pasar por validación estructural, reglas de negocio y umbrales de confianza.

---

# Figura DFD-05. Atención Conversacional por WhatsApp – Nivel 2

```mermaid
flowchart TD
    U[Usuario]
    W[WhatsApp API]

    P41[4.1 Recepción del mensaje]
    P42[4.2 Búsqueda de conversación activa]
    P43[4.3 Asociación a ticket existente]
    P44[4.4 Creación de nuevo ticket]
    P45[4.5 Registro del mensaje]
    P46[4.6 Generación de respuesta]
    P47[4.7 Envío de respuesta]

    D1[(D1 Usuarios)]
    D2[(D2 Tickets)]
    D3[(D3 Mensajes / Históricos)]

    U -->|Mensaje| W
    W --> P41
    P41 --> P42
    P42 <--> D2

    P42 -->|Existe conversación activa| P43
    P42 -->|No existe| P44

    P43 --> P45
    P44 --> P45

    P45 <--> D3
    P45 <--> D1
    P45 --> P46
    P46 --> P47
    P47 --> W
    W -->|Respuesta| U
```

**Descripción:**  
Un mensaje de WhatsApp no debe generar automáticamente un nuevo ticket. Primero se comprueba si existe una conversación activa; si existe, el mensaje se agrega al ticket correspondiente. En caso contrario, se inicia un nuevo caso.

---

# Figura DFD-06. Gestión Operativa del Ticket – Nivel 2

```mermaid
flowchart TD
    A[Agente / Operador]

    P31[3.1 Consulta de bandeja]
    P32[3.2 Revisión del ticket]
    P33[3.3 Cambio de estado]
    P34[3.4 Asignación / Reasignación]
    P35[3.5 Registro de observaciones]
    P36[3.6 Resolución]
    P37[3.7 Cierre]

    D2[(D2 Tickets)]
    D3[(D3 Mensajes)]
    D9[(D9 Historial de Estados)]
    D10[(D10 Usuarios / Responsables)]

    A --> P31
    P31 <--> D2
    P31 --> P32
    P32 <--> D3

    P32 --> P33
    P33 --> D9

    P33 --> P34
    P34 <--> D10
    P34 --> D2

    P32 --> P35
    P35 --> D3

    P35 --> P36
    P36 --> D2
    P36 --> D9
    P36 --> P37
    P37 --> D2
    P37 --> D9
```

**Descripción:**  
El operador administra el ciclo de vida del ticket. Todos los cambios de estado, reasignaciones y acciones relevantes deben quedar registrados en un historial auditable.

---

# Figura DFD-07. Gestión de SLA y Alertas – Nivel 2

```mermaid
flowchart TD
    P51[5.1 Monitoreo de tickets]
    P52[5.2 Cálculo de tiempos]
    P53[5.3 Comparación con SLA]
    P54[5.4 Generación de alerta]
    P55[5.5 Escalamiento]
    P56[5.6 Notificación al responsable]

    D2[(D2 Tickets)]
    D5[(D5 Políticas SLA)]
    D11[(D11 Alertas)]
    D10[(D10 Responsables)]

    P51 <--> D2
    P51 --> P52
    P52 --> P53
    P53 <--> D5

    P53 -->|Dentro del SLA| P51
    P53 -->|Próximo a vencer| P54
    P53 -->|Vencido| P55

    P54 --> D11
    P55 --> D11

    P54 --> P56
    P55 --> P56
    P56 <--> D10
```

**Descripción:**  
El sistema debe controlar los tiempos de primera respuesta y resolución. Cuando un ticket se aproxima a su vencimiento o supera el SLA, se generan alertas y, cuando corresponda, procesos de escalamiento.

---

# Figura DFD-08. Integración Futura con el SGA – Nivel 2

```mermaid
flowchart LR
    P61[6.1 Solicitud de datos institucionales]
    P62[6.2 InstitutionalDataProvider]
    P63[6.3 LocalMockProvider]
    P64[6.4 SGAProvider]

    D1[(D1 Usuarios Locales)]
    S[SGA Institucional]

    P61 --> P62

    P62 -->|MVP| P63
    P63 <--> D1

    P62 -->|Fase futura| P64
    P64 -->|API / Servicio institucional| S
    S -->|Datos institucionales| P64
```

**Descripción:**  
Se propone una capa de abstracción denominada `InstitutionalDataProvider`. Durante el MVP se utilizará `LocalMockProvider`. Cuando la especificación del SGA esté disponible, podrá incorporarse `SGAProvider` sin alterar el núcleo de la aplicación.

---

# Figura DFD-09. Procesamiento mediante LLM – Nivel 2

```mermaid
flowchart TD
    M[Mensaje / Descripción del ticket]

    P91[9.1 Preprocesamiento]
    P92[9.2 Selección de modelo y prompt]
    P93[9.3 Invocación al LLM]
    P94[9.4 Parseo de respuesta]
    P95[9.5 Validación estructural]
    P96[9.6 Aplicación de reglas]
    P97[9.7 Resultado operativo]
    P98[9.8 Registro de auditoría]

    L[Proveedor LLM]

    D4[(D4 Reglas de Negocio)]
    D6[(D6 Auditoría IA)]
    D12[(D12 Modelos LLM)]
    D13[(D13 Prompts)]

    M --> P91
    P91 --> P92

    P92 <--> D12
    P92 <--> D13

    P92 --> P93
    P93 --> L
    L --> P94

    P94 --> P95
    P95 --> P96
    P96 <--> D4

    P96 --> P97
    P95 --> P98
    P98 --> D6
```

**Descripción:**  
El LLM funciona como un motor de interpretación semántica. Sus resultados deben transformarse a una salida estructurada y validarse antes de ser utilizados por la lógica de negocio.

Ejemplo esperado de salida:

```json
{
  "intent": "problema_matricula",
  "category": "ACADEMIC",
  "subcategory": "ENROLLMENT",
  "priority": "MEDIUM",
  "summary": "Usuario reporta inconveniente durante el proceso de matrícula",
  "confidence": 0.91
}
```

---

# Figura DFD-10. Fallback y Contingencia del Motor LLM

```mermaid
flowchart TD
    U[Solicitud a procesar]

    P101[10.1 Invocar LLM principal]
    G1{¿Respuesta válida?}

    P102[10.2 Reintento controlado]
    P103[10.3 Invocar modelo alternativo]
    G2{¿Respuesta válida?}

    P104[10.4 Aplicar reglas determinísticas]
    P105[10.5 Escalar a revisión humana]
    P106[10.6 Continuar flujo]

    D6[(D6 Auditoría IA)]

    U --> P101
    P101 --> G1

    G1 -->|Sí| P106
    G1 -->|No| P102

    P102 --> P103
    P103 --> G2

    G2 -->|Sí| P106
    G2 -->|No| P104

    P104 --> P105
    P105 --> P106

    P101 --> D6
    P103 --> D6
    P104 --> D6
```

**Descripción:**  
El MVP debe garantizar continuidad incluso si el proveedor LLM falla. La estrategia contempla reintento, modelo alternativo, aplicación de reglas determinísticas y finalmente intervención humana.

---

# Figura DFD-11. Flujo Integral del Ticket

```mermaid
flowchart TD
    U[Usuario]
    C[Canal Web / WhatsApp]

    P1[Recepción]
    P2[Identificación]
    P3[Creación / Asociación de Ticket]
    P4[Clasificación]
    P5[Evaluación de Reglas]
    P6[Asignación]
    P7[Atención]
    P8[Seguimiento SLA]
    P9[Resolución]
    P10[Cierre]
    P11[Histórico / Métricas]

    L[LLM]
    A[Agente Humano]

    DB[(MySQL)]

    U --> C
    C --> P1
    P1 --> P2
    P2 --> P3
    P3 --> P4

    P4 -->|Apoyo semántico| L
    L --> P4

    P4 --> P5
    P5 --> P6
    P6 --> P7

    P7 <--> A
    P7 --> P8

    P8 --> P9
    P9 --> P10
    P10 --> P11

    P3 --> DB
    P4 --> DB
    P6 --> DB
    P7 --> DB
    P8 --> DB
    P9 --> DB
    P10 --> DB
    P11 --> DB
```

**Descripción:**  
Este diagrama sintetiza el ciclo completo del ticket y permite presentar el funcionamiento general del MVP en una sola vista.

---

# 12. Relación entre procesos y tablas principales

| Proceso | Tablas principales |
|---|---|
| Gestión de solicitudes | `users`, `user_types`, `channels` |
| Gestión de tickets | `tickets`, `ticket_statuses`, `ticket_status_history` |
| Clasificación | `ticket_categories`, `ticket_subcategories`, `business_rules` |
| Enrutamiento | `service_areas`, `ticket_assignments` |
| Conversación | `ticket_messages`, `ticket_attachments` |
| SLA | `sla_policies`, `alerts` |
| IA | `llm_models`, `llm_prompts`, `llm_usage`, `ai_decisions` |
| Auditoría | `audit_logs`, `ticket_status_history`, `ai_decisions` |

---

# 13. Consideraciones de diseño

1. El SGA no constituye una dependencia obligatoria para la ejecución del MVP.
2. Los datos institucionales deben consumirse posteriormente mediante una capa de integración desacoplada.
3. El LLM no debe controlar estados críticos ni ejecutar cierres automáticos de tickets.
4. Las decisiones administrativas y transacciones sensibles deben permanecer bajo reglas determinísticas o validación humana.
5. Todo resultado generado por IA debe ser auditable.
6. El sistema debe mantener trazabilidad completa de mensajes, cambios de estado, asignaciones, uso del LLM y tiempos de atención.
7. Las reglas de negocio deben mantenerse desacopladas del canal de entrada.
8. Web y WhatsApp deben converger en el mismo modelo de ticket.
9. El modelo de datos del MVP debe permanecer estable aunque posteriormente se incorpore el SGA.
10. La arquitectura debe permitir sustituir el proveedor LLM sin modificar la lógica principal del sistema.

---

# 14. Uso recomendado en el SDD

Estos diagramas pueden incorporarse dentro de una sección denominada:

**“Arquitectura funcional y Diagramas de Flujo de Datos del MVP”**

Orden recomendado:

1. DFD-01 – Contexto.
2. DFD-02 – Nivel 1.
3. DFD-03 – Registro de solicitudes.
4. DFD-04 – Clasificación y enrutamiento.
5. DFD-05 – WhatsApp.
6. DFD-06 – Gestión operativa.
7. DFD-07 – SLA.
8. DFD-08 – Integración SGA.
9. DFD-09 – Motor LLM.
10. DFD-10 – Fallback.
11. DFD-11 – Flujo integral.

Este conjunto permite explicar tanto la operación funcional como la arquitectura técnica del MVP sin depender todavía de la estructura real del SGA.
