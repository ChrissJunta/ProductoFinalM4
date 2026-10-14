# 03 · Agente de atención e integraciones

[Volver al índice](../README.md) · [Siguiente: administración y verificación](04-administracion-metricas-verificacion.md)

## 1. Clasificación y autonomía

```mermaid
flowchart TB
    IN["Mensaje Web o WhatsApp"] --> CONTEXT["Cargar contexto y memoria de conversación"]
    CONTEXT --> RULES["Clasificar con reglas configuradas"]
    RULES --> MATCH{"¿Intención o empate de reglas?"}
    MATCH -->|Sí| DECIDE["Determinar nivel por catálogo y confianza"]
    MATCH -->|No| LLM["Consultar LLM configurado"]
    LLM --> VALIDATE["Validar salida estructurada,<br/>intención y confianza"]
    VALIDATE --> DECIDE
    DECIDE --> LEVEL{"Nivel N0–N4"}
    LEVEL -->|N0| AUTH["Comprobar autenticación/verificación"]
    AUTH --> ALLOWED{"¿Consulta autorizada?"}
    ALLOWED -->|No| LINK["Pedir identificación o vinculación"]
    ALLOWED -->|Sí| TOOL["Herramienta de lectura autorizada"]
    TOOL --> RESULT{"¿Hay respuesta válida?"}
    RESULT -->|Sí| ANSWER["Responder al usuario"]
    RESULT -->|No y usuario identificado| TICKET["Crear ticket"]
    RESULT -->|No identificado| LINK
    LEVEL -->|N1| TEMPLATE["Responder con plantilla autorizada"]
    LEVEL -->|N2, N3 o N4 identificado| TICKET
    LEVEL -->|N2, N3 o N4 sin identificar| LINK
    TICKET --> ROUTE["Enrutar con reglas del backend"]
    ROUTE --> ACK["Informar código del ticket"]
    ACK --> REVIEW{"¿Requiere revisión?"}
    REVIEW -->|No| END["Fin de este turno"]
    REVIEW -->|Sí| PAUSE["Alerta y pausa de revisión humana"]
    PAUSE --> HUMAN["Aceptar, corregir o rechazar"]
    HUMAN --> APPLY["Validar y aplicar decisión en backend"]
    APPLY --> END
    ANSWER --> END
    TEMPLATE --> END
    LINK --> END
    classDef brand fill:#3C235F,color:#fff,stroke:#3C235F;
    classDef accent fill:#FFF0E5,color:#3C235F,stroke:#EA600A;
    class CONTEXT,DECIDE,TICKET brand;
    class PAUSE,HUMAN accent;
```

Este mapa agrupa los 16 nodos técnicos. El [grafo generado](../agent_graph.md) mantiene sus nombres y aristas exactas.

| Nivel | Fuente / operación | Resultado funcional |
|---|---|---|
| N0 · Consulta estructurada | Herramientas del proveedor institucional. | Horario, notas, deuda, matrícula, materias o consulta de estado autorizada. |
| N1 · Conocimiento autorizado | Plantilla activa configurada. | Información aprobada; no usa RAG ni inventa hechos. |
| N2 · Ticket + validación | Creación y reglas determinísticas. | Solicitud registrada para el proceso definido. |
| N3 · Ticket + routing | Creación y reglas de enrutamiento. | Solicitud destinada al área configurada. |
| N4 · Revisión humana | Caso ambiguo, desconocido o de baja confianza. | Ticket, alerta y decisión humana. |

La implementación envía a N4 cuando falta intención o la confianza es menor que 0,70. N2/N3 con confianza menor que 0,85 también solicitan revisión. Estos umbrales proceden del backend, no de la plantilla. Un empate de reglas se deriva a decisión humana; no se fuerza una elección por LLM.

## 2. Revisión humana con persistencia

```mermaid
sequenceDiagram
    participant G as Agente LangGraph
    participant P as PostgreSQL / checkpoint
    participant H as Detalle del ticket
    actor R as Revisor autorizado
    participant B as Backend de revisión
    G->>P: Persistir estado y pausar con interrupt
    G->>H: Ticket y alerta de revisión
    R->>H: Abrir ticket visible
    H->>B: Obtener ai_review y acciones autorizadas
    B-->>H: Propuesta, candidatos y catálogo permitido
    R->>B: POST aceptar / corregir / rechazar con CSRF
    B->>B: Validar permiso, decisión y condiciones actuales
    B->>P: Reanudar el hilo con la decisión
    P-->>G: Estado persistido
    G->>B: Aplicar revisión determinísticamente
    B-->>H: Resultado y tarjeta actualizada
```

La corrección se muestra solo cuando BACK entrega `can_correct`. La presencia de la tarjeta depende del contexto aprobado; el FRONT no calcula autonomía ni permite herramientas nuevas. El hilo del agente usa `Conversation.id` y checkpoints PostgreSQL para soportar memoria y reanudación.

## 3. LLM y protección de datos

```mermaid
flowchart LR
    ASK["Clasificación solicitada"] --> SERVICE["AIService"]
    SERVICE --> CONFIG["Modelo, prompt y proveedor configurados"]
    CONFIG --> PROVIDER{"Proveedor"}
    PROVIDER -->|fake| FAKE["Respuesta determinística local"]
    PROVIDER -->|openai_compat| QWEN["Qwen3-8B / vLLM"]
    FAKE --> VALID["Validación estricta de la salida"]
    QWEN --> VALID
    QWEN -->|Error / timeout| RETRY["Reintento y respaldo configurado"]
    RETRY --> VALID
    VALID --> AUDIT["AIUsage y AIDecision"]
    VALID --> DECISION["Propuesta para decisión backend"]
```

Al clasificador se envían el mensaje, el catálogo y el prompt correspondiente; no se envían notas, deuda ni registros institucionales del usuario. El backend valida la respuesta antes de usarla. El LLM no ejecuta cambios de estado, asignaciones ni escrituras de negocio libremente.

El adaptador real existe, pero su conectividad y calidad deben medirse desde la red universitaria. Las pruebas con `fake` o un servidor HTTP simulado no equivalen a probar Qwen3 real. Los reintentos, el respaldo configurado y la derivación a ticket protegen la continuidad de la solicitud.

## 4. Datos institucionales

```mermaid
flowchart TB
    QUERY["Consulta N0"] --> AUTH["Sesión Web o teléfono verificado"]
    AUTH --> TOOL["Herramienta de lectura permitida"]
    TOOL --> CONTRACT["InstitutionalDataProvider"]
    CONTRACT --> LOCAL["LocalProvider · datos ficticios"]
    CONTRACT --> SGA["SGAProvider · adaptador HTTP"]
    SGA --> SERVER["SGA simulado / servicio real configurado"]
    LOCAL --> RESP["Respuesta autorizada por canal"]
    SERVER --> RESP
    SERVER -->|Fallo| FALLBACK["Ticket para atención humana"]
```

Métodos institucionales: `get_schedule`, `get_grades`, `get_debt`, `get_enrollment` y `get_subjects`. La consulta de estado de ticket también se ofrece como herramienta autorizada del sistema. No hay escritura de notas ni pagos mediante el agente.

## 5. Vinculación de WhatsApp

```mermaid
sequenceDiagram
    actor U as Usuario autenticado
    participant W as Perfil Web
    participant B as Backend
    participant C as WhatsApp simulado / Meta
    U->>W: Generar código
    W->>B: POST con CSRF
    B-->>W: Código y vencimiento para su usuario
    U->>C: Enviar el código desde su teléfono
    C->>B: Webhook firmado
    B->>B: Validar mensaje, código y vinculación
    B-->>C: Confirmar número verificado
    U->>C: Consultar información
    C->>B: Mensaje asociado al número
    B->>B: Validar identidad y permisos
    B-->>C: Respuesta autorizada
    U->>W: Desvincular
    W->>B: POST con CSRF
    B->>B: Retirar la vinculación
```

La pantalla muestra el código según el contrato de una sola vista, su vigencia y el estado de vinculación. Los datos personales requieren número verificado; la deuda por WhatsApp se minimiza al total. El modo simulado se señala explícitamente en la interfaz.

## 6. Canal WhatsApp y colas

```mermaid
flowchart LR
    IN["Mensaje entrante"] --> SIGN["Verificar firma del webhook"]
    SIGN --> DEDUP["Identificador externo<br/>control de duplicados"]
    DEDUP --> INBOX[("IntegrationInbox")]
    INBOX --> WORKER["process_integration_queue"]
    WORKER --> LINK["Vinculación / identificar remitente"]
    LINK --> DISPATCH["Consulta al agente o respuesta al ticket"]
    DISPATCH --> HISTORY["Historial omnicanal"]
    DISPATCH --> OUTBOX[("IntegrationOutbox")]
    OUTBOX --> SEND["Envío por proveedor"]
    SEND -->|Fallo| RETRY["Reintento controlado"]
    RETRY --> OUTBOX
    SEND -->|Éxito| SENT["Registrar entrega del envío"]
```

El procesamiento evita repetir efectos de un mismo mensaje y separa recepción de envío. No usa WebSockets ni colas Redis/Celery. Para Meta real se necesitan configuración, credenciales, conectividad y pruebas; el MVP puede recorrerse con `whatsapp_simulate`.

Fuentes: [grafo](../../apps/ai/agent/graph.py), [autonomía](../../apps/automation/autonomy.py), [proveedor LLM](../../apps/ai/providers/openai_compat.py), [integraciones](../../apps/integrations/), [contratos](../../progress.md).
