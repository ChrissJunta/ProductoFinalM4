# 02 · Tickets, conversación y SLA

[Volver al índice](../README.md) · [Siguiente: agente e integraciones](03-agente-e-integraciones.md)

## 1. Recorrido de una solicitud

```mermaid
sequenceDiagram
    actor U as Usuario
    participant W as Portal Web
    participant B as Backend Django
    participant P as PostgreSQL
    actor A as Agente autorizado
    U->>W: Asunto, descripción y adjunto opcional
    W->>B: POST multipart con CSRF
    B->>B: Validar formulario, catálogo y archivo
    alt Datos inválidos
        B-->>W: Formulario ligado con errores
        W-->>U: Correcciones accesibles
    else Datos válidos
        B->>P: Crear ticket, código único, SLA e historial inicial
        B->>P: Registrar auditoría
        B-->>W: Redirigir al detalle
        A->>B: Consultar bandeja autorizada
        B-->>A: Tickets y acciones permitidas
        A->>B: Asignar y comenzar atención
        B->>P: Validar versión y registrar cambios
        A->>B: Publicar respuesta o solicitar información
        B->>P: Guardar conversación y plazos aplicables
        U->>B: Responder con mensaje/adjunto
        B->>P: Añadir mensaje y reanudar si esperaba al usuario
        A->>B: Resolver con mensaje obligatorio
        B->>P: Guardar resolución, historial y auditoría
        U->>B: Confirmar o rechazar solución
        B->>P: Cerrar o volver a En proceso
    end
```

El código `HD-AAAA-NNNNNN` se genera con una secuencia PostgreSQL para evitar duplicados concurrentes. Estado, prioridad, plazos y área son datos del backend, no campos controlados libremente por el navegador.

## 2. Máquina de estados completa

```mermaid
stateDiagram-v2
    [*] --> Nuevo
    Nuevo --> Clasificado: 1 · clasificación
    Nuevo --> Cancelado: 2 · cancelación con motivo
    Clasificado --> Asignado: 3 · área o responsable
    Clasificado --> Cancelado: 4 · cancelación con motivo
    Asignado --> EnProceso: 5 · iniciar atención
    Asignado --> Escalado: 6 · escalar con motivo
    EnProceso --> EsperandoUsuario: 7 · solicitar información
    EsperandoUsuario --> EnProceso: 8 · respuesta / reanudación
    EsperandoUsuario --> Cancelado: 9 · vencimiento automático
    EnProceso --> Escalado: 10 · escalar con motivo
    EnProceso --> Resuelto: 11 · mensaje de resolución
    Escalado --> Asignado: 12 · decisión del supervisor
    Escalado --> EnProceso: 13 · decisión del supervisor
    Resuelto --> Cerrado: 14 · confirmación o cierre automático
    Resuelto --> EnProceso: 15 · rechazo con motivo
    Cerrado --> Reabierto: 16 · dentro del plazo
    Reabierto --> Asignado: 17 · retomar atención
```

| Transiciones | Actores habilitados, sujetos a visibilidad y condiciones |
|---|---|
| 1 y 3 | Sistema, Agente o Supervisor. |
| 2 y 4 | Dueño del ticket o Supervisor; motivo obligatorio. |
| 5 y 7 | Agente responsable o Supervisor. |
| 6 y 10 | Agente responsable, Supervisor o Sistema; motivo obligatorio. |
| 8 | Dueño, Agente o Supervisor. |
| 9 | Sistema. |
| 11 | Agente responsable o Supervisor; mensaje de resolución obligatorio. |
| 12 y 13 | Supervisor. |
| 14 | Dueño o Sistema. |
| 15 | Dueño; motivo obligatorio. |
| 16 | Dueño o Supervisor; dentro de la ventana configurada. |
| 17 | Sistema o Supervisor. |

Toda transición fuera de esta tabla se rechaza. Cancelado no tiene salida. Asignado exige área o responsable. El backend calcula las acciones visibles para cada usuario.

## 3. Información vinculada al ticket

```mermaid
flowchart LR
    USER["Solicitante"] --> T["Ticket<br/>código · estado · prioridad · versión"]
    CAT["Categoría / subcategoría / intención"] --> T
    AREA["Área y agente responsable"] --> T
    T --> MSG["Mensajes cronológicos<br/>canal Web / WhatsApp"]
    T --> ATT["Adjuntos autorizados"]
    T --> HIST["Historial de estados<br/>actor · motivo · fecha"]
    T --> SLA["Primera respuesta y resolución"]
    T --> ALERT["Alertas"]
    T --> AUDIT["Auditoría de operaciones"]
```

Los mensajes internos se muestran únicamente según el contrato y la autorización del backend. Los adjuntos admitidos son PDF, PNG y JPG/JPEG hasta 5 MB: el servidor verifica extensión, tamaño y firma del contenido. La descarga comprueba visibilidad y pertenencia al ticket.

## 4. Protección frente a ediciones simultáneas

```mermaid
sequenceDiagram
    actor A as Agente A
    actor B as Agente B
    participant S as Servicio de tickets
    A->>S: Leer ticket versión 4
    B->>S: Leer ticket versión 4
    A->>S: Cambiar estado con versión 4
    S->>S: Bloquear fila, validar y guardar versión 5
    S-->>A: Operación confirmada
    B->>S: Cambiar estado con versión 4
    S-->>B: Ticket actualizado por otro usuario
```

## 5. Control de SLA

```mermaid
flowchart TB
    CREATE["Creación del ticket"] --> POLICY["Seleccionar política SLA"]
    POLICY --> CAL{"¿Solo horas laborales?"}
    CAL -->|Sí| WORK["Calendario: horario, fines de semana y feriados"]
    CAL -->|No| CLOCK["Minutos continuos · 24x7"]
    WORK --> DEADLINE["Guardar plazos de primera respuesta y resolución"]
    CLOCK --> DEADLINE
    DEADLINE --> JOB["check_sla · cada 5 minutos"]
    JOB --> STATE{"Estado del plazo"}
    STATE -->|Menos de 80 por ciento| OK["Seguimiento normal"]
    STATE -->|Desde 80 por ciento| WARN["Alerta Por vencer"]
    STATE -->|Vencido| BREACH["Alerta de incumplimiento<br/>y escalamiento cuando aplica"]
    WARN --> SUP["Supervisor revisa alertas y bandeja"]
    BREACH --> SUP
```

| Prioridad | Primera respuesta inicial | Resolución inicial |
|---|---:|---:|
| Baja | 480 minutos | 4320 minutos |
| Media | 240 minutos | 2880 minutos |
| Alta | 60 minutos | 1440 minutos |
| Crítica | 15 minutos | 240 minutos |

Son valores iniciales configurables, no promesas expresadas en días naturales. El FRONT muestra las fechas y el estado SLA calculados por el servidor. La alerta abierta por tipo/ticket se controla para no duplicarse.

| Proceso programado | Frecuencia prevista | Finalidad |
|---|---|---|
| `process_integration_queue` | Cada minuto | Entradas/salidas WhatsApp y reintentos. |
| `check_sla` | Cada cinco minutos | Alertas de plazos y escalamiento aplicable. |
| `close_stale_tickets` | Cada hora | Cierre de resueltos y cancelación por espera vencida según configuración. |

Los comandos existen; para ejecución autónoma es necesario configurarlos en el despliegue.

Fuentes: [workflow](../../apps/helpdesk/workflow.py), [creación](../../apps/helpdesk/tickets.py), [SLA](../../apps/helpdesk/sla.py), [rutas](../../apps/helpdesk/urls.py).
