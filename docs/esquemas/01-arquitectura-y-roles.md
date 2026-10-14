# 01 · Arquitectura, roles y pantallas

[Volver al índice](../README.md) · [Siguiente: tickets y SLA](02-tickets-conversacion-sla.md)

## 1. Arquitectura de la aplicación

El MVP es un **monolito modular Django** con cinco apps. El navegador recibe HTML mediante Django Templates, Bootstrap 5 y JavaScript mínimo. Las decisiones de negocio pertenecen al backend.

```mermaid
flowchart TB
    subgraph Channels["Canales de entrada"]
        BROWSER["Navegador · Web responsive"]
        WA["WhatsApp · simulador / Meta configurado"]
    end
    subgraph Django["Aplicación Django"]
        UI["Templates + Bootstrap 5"]
        AUTH["accounts · sesión, roles y vinculación"]
        HD["helpdesk · tickets, conversación, SLA y gestión"]
        AUTO["automation · intenciones y acciones"]
        AI["ai · LangGraph y proveedor LLM"]
        INT["integrations · webhook, colas y proveedores"]
    end
    BROWSER --> UI
    UI --> AUTH
    UI --> HD
    UI --> AUTO
    WA --> INT
    AUTH --> HD
    AUTO --> AI
    AI --> AUTO
    AI --> HD
    AI --> INT
    INT --> AI
    HD --> INT
    subgraph Storage["Persistencia PostgreSQL"]
        DB[("Usuarios, catálogos, tickets,<br/>mensajes, auditoría y colas")]
        CP[("Checkpoints y memoria<br/>de conversaciones del agente")]
    end
    AUTH --> DB
    HD --> DB
    AUTO --> DB
    INT --> DB
    AI --> DB
    AI --> CP
    FILES["Almacenamiento de adjuntos"]
    HD --> FILES
    INT --> SGA["Proveedor institucional<br/>local o SGA HTTP"]
    AI --> LLM["LLM fake o Qwen3/vLLM"]
    classDef brand fill:#3C235F,color:#fff,stroke:#3C235F;
    class UI,HD,AI brand;
```

No hay SPA, WebSockets, GraphQL, Redis ni Celery. Los trabajos periódicos se ejecutan mediante comandos Django programados externamente.

## 2. Acceso y autorización

```mermaid
flowchart LR
    ENTRY["Abrir portal"] --> SESSION{"¿Sesión válida?"}
    SESSION -->|No| LOGIN["Login: usuario o correo"]
    LOGIN --> CHECK{"¿Credenciales válidas?"}
    CHECK -->|No| ERROR["Error genérico<br/>sin revelar si existe la cuenta"]
    ERROR --> LOGIN
    CHECK -->|Sí| ROLE["Backend determina el rol"]
    SESSION -->|Sí| ROLE
    ROLE --> HOME["Inicio y navegación autorizada"]
    HOME --> ACTION["Solicitar una operación"]
    ACTION --> PERM{"Rol, visibilidad,<br/>estado y versión válidos"}
    PERM -->|Sí| EXEC["Ejecutar y auditar"]
    PERM -->|No| DENY["Rechazar con respuesta controlada"]
```

Ocultar un botón es presentación; cada solicitud vuelve a validarse en el servidor. La descarga y las operaciones sobre un ticket no visible devuelven 404 para evitar revelar su existencia. Otros fallos de permisos pueden devolver 403.

## 3. Matriz funcional por rol

| Rol | Universo de tickets visible | Operaciones principales |
|---|---|---|
| Usuario | Sus propios tickets. | Crear, responder, adjuntar, confirmar o rechazar resolución y reabrir dentro del plazo. |
| Agente | Propios, asignados a él, de sus áreas y sin área para triaje compartido. | Atender y ejecutar acciones/asignaciones que el backend autorice. |
| Supervisor | Todos. | Supervisar, asignar/reasignar, escalar, revisar decisiones humanas, alertas y métricas. |
| Administrador | Todos para consulta. | Gestionar catálogos/configuración. No opera transiciones por su rol de administrador. |

Los permisos concretos también dependen del ticket, del responsable y de su estado; esta matriz no reemplaza esas condiciones.

## 4. Mapa de pantallas

```mermaid
flowchart TB
    LOGIN["Login · FE-T01"] --> HOME["Inicio / resumen · FE-T02"]
    HOME --> NEW["Nueva solicitud · FE-T03"]
    HOME --> LIST["Listado y filtros · FE-T04"]
    LIST --> DETAIL["Detalle e historial · FE-T05"]
    NEW --> DETAIL
    DETAIL --> STATES["Acciones de estado · FE-T07"]
    DETAIL --> REVIEW["Revisión humana de IA"]
    HOME --> INBOX["Bandeja y asignación · FE-T06"]
    INBOX --> DETAIL
    HOME --> ALERTS["Alertas y SLA · FE-T08"]
    ALERTS --> DETAIL
    HOME --> MANAGE["Administración · FE-T09"]
    HOME --> METRICS["Métricas · FE-T10"]
    HOME --> PROFILE["Vincular WhatsApp · FE-T11"]
    HOME --> ASSIST["Asistente Web · FE-T12"]
    ASSIST -->|Cuando la respuesta incluye ticket| DETAIL
```

La navegación se muestra según el rol y los contratos aprobados; el mapa reúne todas las pantallas, no significa que un usuario tenga acceso a todas.

## 5. Ubicación de responsabilidades

| Capa | Responsabilidad | Fuente |
|---|---|---|
| FRONT | HTML, formularios ligados, mensajes, etiquetas, accesibilidad y responsive. | `templates/`, `static/` |
| BACK | Sesión, formularios, autorización, estados, SLA, prioridad y acciones disponibles. | `apps/`, `config/` |
| Coordinación | Contratos de URL/contexto/formulario, decisiones y estados de trabajo. | `progress.md` |

Fuentes de código: [rutas principales](../../config/urls.py), [visibilidad de tickets](../../apps/helpdesk/queries.py), [roles](../../apps/accounts/roles.py).
