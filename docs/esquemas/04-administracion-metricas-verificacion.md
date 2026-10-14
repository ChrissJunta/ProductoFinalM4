# 04 · Administración, métricas y verificación

[Volver al índice](../README.md)

## 1. Configuración de la atención

```mermaid
flowchart TB
    ADMIN["Administrador autenticado"] --> PANEL["Panel de administración propia"]
    PANEL --> AREAS["Áreas y agentes"]
    PANEL --> CAT["Categorías y subcategorías"]
    PANEL --> INTENT["Intenciones y palabras clave"]
    PANEL --> ACTION["Acciones por intención"]
    PANEL --> ROUTE["Reglas de routing"]
    PANEL --> SLA["Políticas SLA"]
    AREAS --> VIS["Visibilidad y asignación por área"]
    CAT --> FORM["Opciones válidas de solicitudes"]
    INTENT --> CLASSIFY["Clasificación de nuevos mensajes"]
    ACTION --> AUTONOMY["Consulta, plantilla, ticket o revisión"]
    ROUTE --> DEST["Destino de nuevos tickets"]
    SLA --> DEADLINE["Plazos de primera respuesta y resolución"]
    AREAS --> AUDIT[("Auditoría")]
    CAT --> AUDIT
    INTENT --> AUDIT
    ACTION --> AUDIT
    ROUTE --> AUDIT
    SLA --> AUDIT
```

La administración propia ofrece siete catálogos: áreas, categorías, subcategorías, intenciones, acciones, reglas de routing y políticas SLA. Las operaciones incluyen crear, editar, filtrar, paginar y activar/desactivar. No se ofrece borrado físico de catálogos; los cambios se validan y auditan en el backend.

La gestión adicional de usuarios, permisos y modelos de IA corresponde a Django admin según sus permisos; no debe confundirse con los siete catálogos del panel propio.

## 2. De un cambio de configuración a una operación

```mermaid
sequenceDiagram
    actor A as Administrador
    participant F as Formulario de catálogo
    participant B as Backend
    participant D as PostgreSQL
    A->>F: Editar una regla o catálogo
    F->>B: POST ligado con CSRF
    B->>B: Validar permisos, campos y relaciones
    alt Error de validación
        B-->>F: Errores ligados al formulario
    else Cambio válido
        B->>D: Guardar cambios en transacción
        B->>D: Registrar campos modificados y actor
        B-->>F: Redirección y mensaje de resultado
        Note over B,D: La siguiente operación consume la configuración activa
    end
```

## 3. Métricas operativas e IA

```mermaid
flowchart LR
    FILTER["Periodo, área, categoría y canal"] --> SCOPE["Backend define universo de tickets"]
    SCOPE --> VOL["Total, abiertos, resueltos,<br/>cerrados y cancelados"]
    SCOPE --> TIMES["Tiempos: media, mediana y P90"]
    SCOPE --> SLA["Primera respuesta y resolución:<br/>cumple, incumple, en curso, sin SLA"]
    SCOPE --> GROUPS["Desgloses por dimensiones contratadas"]
    USAGE["AIUsage / AIDecision"] --> AI["Actividad y resultados de IA"]
    VOL --> UI["Pantalla de métricas"]
    TIMES --> UI
    SLA --> UI
    GROUPS --> UI
    AI --> UI
    UI --> SUP["Supervisor / rol autorizado"]
```

El periodo usa fechas locales y extremos incluidos. Los tiempos de estadísticas se expresan en minutos de reloj; no son la misma medida que los minutos laborales del SLA. El cumplimiento se calcula sobre casos decididos: `cumple / (cumple + incumple)`. Si no existen casos decididos se muestra ausencia de datos, no un cero inventado.

El FRONT no agrega ni calcula métricas. La extensión de métricas WhatsApp solicitada en `CONTRACT-FRONT-007` debe aprobarse/documentarse antes de mostrar variables adicionales; la existencia de cálculos backend no crea un contrato de presentación automáticamente. Consultar su estado vigente en `progress.md`.

## 4. Controles que atraviesan todos los módulos

```mermaid
flowchart TB
    REQ["Petición"] --> AUTH["Identidad y rol"]
    AUTH --> SCOPE["Visibilidad de datos"]
    SCOPE --> VALID["Formulario, acción y condiciones"]
    VALID --> WRITE{"¿Operación de escritura?"}
    WRITE -->|Sí| CSRF["POST + CSRF en Web<br/>firma en webhook"]
    CSRF --> TX["Transacción y versión cuando aplica"]
    TX --> AUDIT["Auditoría / historial"]
    AUDIT --> RESP["Respuesta controlada"]
    WRITE -->|No| RESP
    RESP --> ESCAPE["Autoescape y mensajes aptos para usuario"]
    ESCAPE --> ACCESS["Labels, teclado, texto y responsive"]
```

También se aplican límites de intentos de login, validación de archivos, secretos por entorno y configuración de producción. El dibujo es una lista lógica de controles, no el orden exacto de cada middleware. Ningún control debe inferirse únicamente por el color o por ocultar un elemento visual.

## 5. Recorrido funcional para revisar el MVP

Usar una base de desarrollo aislada con `seed_demo`, según el [README del proyecto](../../README.md). El siguiente recorrido conecta los módulos sin utilizar datos reales.

```mermaid
flowchart TB
    START["Preparar entorno y datos demo"] --> USER["Usuario: login e inicio"]
    USER --> CREATE["Crear ticket con adjunto"]
    CREATE --> AGENT["Agente: triaje, asignar e iniciar atención"]
    AGENT --> ASK["Solicitar información"]
    ASK --> REPLY["Usuario: responder y adjuntar"]
    REPLY --> RESOLVE["Agente: resolver con mensaje"]
    RESOLVE --> CONFIRM["Usuario: confirmar o rechazar"]
    CONFIRM --> SUP["Supervisor: alertas, revisión humana y métricas"]
    SUP --> ADMIN["Administrador: catálogos y auditoría"]
    ADMIN --> ASSIST["Usuario: consultas al asistente"]
    ASSIST --> WA["Vincular, consultar y desvincular WhatsApp simulado"]
    WA --> END["Registrar resultado y observaciones de UAT"]
```

| Verificación | Resultado esperado |
|---|---|
| Privacidad Usuario | No puede consultar ni descargar datos de tickets ajenos. |
| Áreas Agente | Solo ve su universo autorizado, incluida la cola compartida sin área. |
| Estados | No se ejecutan transiciones no permitidas; motivos y versión se validan. |
| Conversación | Mensajes ordenados con etiqueta de canal y adjuntos autorizados. |
| Revisión IA | Solo el revisor habilitado acepta/corrige/rechaza; el grafo se reanuda. |
| Asistente | Respuesta escapada, ejemplos y formulario operativos sin JavaScript. |
| WhatsApp | Código vigente, identificación correcta y modo simulado explícito. |
| Métricas | Filtros y errores ligados, cero distinguido de ausencia de datos. |
| Accesibilidad | Teclado, labels, errores, contraste y tablas utilizables en móvil. |
| Recuperación | Fallos de proveedor, duplicados y versiones antiguas se manejan sin repetir efectos. |

## 6. Condiciones de aceptación y despliegue

```mermaid
flowchart LR
    CODE["Código integrado"] --> AUTO["Pruebas automatizadas y CI"]
    AUTO --> E2E["Recorridos de navegador y permisos"]
    E2E --> UAT["Validación del usuario"]
    UAT --> CONFIG["Configuración del despliegue"]
    CONFIG --> REAL["Verificación de servicios externos reales"]
    REAL --> OPERATE["Operación y seguimiento"]
```

Las pruebas automatizadas no sustituyen UAT. Publicar un entorno Cloud no instala por sí mismo los comandos periódicos de la aplicación ni demuestra la primera ejecución de una automatización de seguimiento. La elección de tipografía oficial y las conexiones reales se validan aparte.

Fuentes: [administración](../../apps/helpdesk/manage_views.py), [métricas](../../apps/helpdesk/metrics.py), [seguridad y configuración](../../config/settings/), [registro de coordinación](../../progress.md).
