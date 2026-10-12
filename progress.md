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

1. Leer `SPEC_MVP_Mesa_Ayuda_v5_1_PostgreSQL_Tareas.md`.
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
SPEC_VERSION: 5.1
DATABASE: PostgreSQL
ARCHITECTURE: Django monolith modular
FRONT: Django Templates + Bootstrap
BACK_APPS: accounts, helpdesk, automation, integrations, ai
SGA_MODE: LocalProvider para MVP
AI_MODE: asistivo
```

---

# 4. Tareas FRONT

| ID | Estado | Responsable/Agente | Dependencia | Última actualización |
|---|---|---|---|---|
| FE-T01 | TODO | - | BE-T01 | - |
| FE-T02 | TODO | - | BE-T03, BE-T04 | - |
| FE-T03 | TODO | - | BE-T03 | - |
| FE-T04 | TODO | - | BE-T04 | - |
| FE-T05 | TODO | - | BE-T05, BE-T07 | - |
| FE-T06 | TODO | - | BE-T04, BE-T06 | - |
| FE-T07 | TODO | - | BE-T07 | - |
| FE-T08 | TODO | - | BE-T08 | - |
| FE-T09 | TODO | - | BE-T09 | - |
| FE-T10 | TODO | - | BE-T10 | - |

---

# 5. Tareas BACK

| ID | Estado | Responsable/Agente | Dependencia | Última actualización |
|---|---|---|---|---|
| BE-T01 | TODO | - | - | - |
| BE-T02 | TODO | - | BE-T01 | - |
| BE-T03 | TODO | - | BE-T01, BE-T02 | - |
| BE-T04 | TODO | - | BE-T03 | - |
| BE-T05 | TODO | - | BE-T03 | - |
| BE-T06 | TODO | - | BE-T03 | - |
| BE-T07 | TODO | - | BE-T03 | - |
| BE-T08 | TODO | - | BE-T07 | - |
| BE-T09 | TODO | - | BE-T03 | - |
| BE-T10 | TODO | - | BE-T03, BE-T08 | - |
| BE-T11 | TODO | - | BE-T05 | - |
| BE-T12 | TODO | - | BE-T11 | - |
| BE-T13 | TODO | - | BE-T09 | - |
| BE-T14 | TODO | - | BE-T13 | - |
| BE-T15 | TODO | - | BE-T14 | - |
| BE-T16 | TODO | - | - | - |
| BE-T17 | TODO | - | BE-T16 | - |
| BE-T18 | TODO | - | BE-T16, BE-T17 | - |
| BE-T19 | TODO | - | BE-T15 | - |
| BE-T20 | TODO | - | BE-T01..BE-T19 | - |

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

Actualmente:

```text
NINGUNO
```

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

Actualmente:

```text
NINGUNA
```

Formato:

```md
- accounts/migrations/0001_initial.py — aplicada
- helpdesk/migrations/0001_initial.py — aplicada
```

---

# 14. Endpoints implementados

Actualmente:

```text
NINGUNO
```

Formato:

```md
- POST /api/tickets/ — DONE — BE-T03
- GET /api/tickets/ — DONE — BE-T04
```

---

# 15. Pruebas ejecutadas

Actualmente:

```text
NINGUNA
```

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
SPEC versión: 5.1
Front backlog definido: Sí
Back backlog definido: Sí
Código implementado: No registrado
Migraciones: No registradas
Endpoints: No registrados
Pruebas: No registradas
Bloqueos: Ninguno
```
