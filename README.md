# ProductoFinalM4 — MVP Mesa de Ayuda Omnicanal

Especificación: [`SPEC_MVP_Mesa_Ayuda_v5_2_PostgreSQL_Tareas.md`](SPEC_MVP_Mesa_Ayuda_v5_2_PostgreSQL_Tareas.md)
Coordinación entre agentes, contratos de vista y estado de tareas: [`progress.md`](progress.md)

Backend: Claude · Frontend (`templates/`, `static/`): ChatGPT.

## Requisitos

- Python 3.12+
- PostgreSQL 16

## Puesta en marcha (resumen, Linux/macOS)

```bash
# usuario y base de PostgreSQL (una vez)
sudo -u postgres psql -c "CREATE ROLE helpdesk WITH LOGIN PASSWORD 'helpdesk' CREATEDB;"
sudo -u postgres createdb -O helpdesk helpdesk

python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                 # poner DJANGO_SECRET_KEY; credenciales ya coinciden

python manage.py migrate
python manage.py seed_demo           # usuarios y tickets demo; muestra las contraseñas UNA vez
python manage.py runserver
```

Abrir http://127.0.0.1:8000/ e iniciar sesión. En Windows, ver la sección siguiente.

## Instalación desde cero (Windows + pgAdmin)

Requisitos: PostgreSQL 16 con pgAdmin, Python 3.12+ y Git (`python --version`, `git --version`).

**1. Usuario y base de datos (pgAdmin).** Servers → PostgreSQL → clic derecho en la base
`postgres` → **Query Tool**. Ejecutar **una sentencia a la vez** (F5); juntas fallan con
«CREATE DATABASE no puede ser ejecutado dentro de un bloque de transacción»:

```sql
CREATE ROLE helpdesk WITH LOGIN PASSWORD 'helpdesk' CREATEDB;
```
```sql
CREATE DATABASE helpdesk OWNER helpdesk ENCODING 'UTF8';
```

Si el usuario ya existía con otra clave: `ALTER ROLE helpdesk WITH LOGIN PASSWORD 'helpdesk' CREATEDB;`.
Si la base se creó con otro dueño: `ALTER DATABASE helpdesk OWNER TO helpdesk;`.

**2. Código y dependencias** (cmd):

```bat
cd C:\cursos
git clone https://github.com/ChrissJunta/ProductoFinalM4.git
cd ProductoFinalM4
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
copy .env.example .env
notepad .env
```

**3. `.env`.** Cambiar solo `DJANGO_SECRET_KEY=` por un texto largo cualquiera; las credenciales
`POSTGRES_*` ya coinciden con el paso 1 (ajustar `POSTGRES_PORT` si no es 5432).
Para usar el LLM real (Qwen3-8B, solo en la red de la universidad): `LLM_PROVIDER=openai_compat`
y quitar el `#` de `LLM_BASE_URL` y `LLM_FALLBACK_PROVIDER`. Cada línea debe empezar en la
clave: sin espacios delante ni comentarios al final.

**4. Tablas, datos demo y servidor:**

```bat
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Abrir http://127.0.0.1:8000/ con los usuarios y contraseñas que imprimió `seed_demo` (ver
«Seguridad de accesos»). Las siguientes veces basta:
`cd C:\cursos\ProductoFinalM4`, `.venv\Scripts\activate`, `python manage.py runserver`.

**Errores frecuentes**

| Mensaje | Causa y solución |
|---|---|
| `la autentificación password falló para el usuario «helpdesk»` | El usuario no existe o tiene otra clave: paso 1 (`CREATE ROLE` / `ALTER ROLE`). |
| `CREATE DATABASE no puede ser ejecutado dentro de un bloque de transacción` | Se ejecutaron varias sentencias juntas: una por vez. |
| `Invalid line: LLM_...` | Línea del `.env` con espacio inicial o comentario al final. |
| `connection refused` | El servicio de PostgreSQL no está iniciado o el puerto no es 5432. |
| `permission denied for schema public` | La base no es del usuario `helpdesk`: `ALTER DATABASE helpdesk OWNER TO helpdesk;`. |
| `'python' no se reconoce…` | Python no está en el PATH (reinstalar marcando «Add python.exe to PATH»). |

## Cómo verificar el MVP

`seed_demo` crea un usuario por rol, cada uno con una **contraseña aleatoria distinta** que
se imprime una sola vez (si se pierde: `python manage.py seed_demo --rotate`):

| Usuario | Rol | Qué probar |
|---|---|---|
| `usuario` | Usuario | «Mis tickets» (4 tickets en distintos estados), crear solicitud con adjunto, responder, confirmar o rechazar una solución, reabrir. |
| `agente_ti` | Agente (área TI) | «Bandeja» → «Sin asignar», abrir un ticket, asignárselo, iniciar atención, pedir información, resolver con mensaje. |
| `agente_fin` | Agente (área Finanzas) | Solo ve tickets de Finanzas, los asignados a él y los sin área; un ticket de TI le da 404. |
| `supervisor` | Supervisor | Ve todos los tickets, reasigna entre áreas, «Alertas» de SLA, escalados y `/metrics/` (métricas operativas e IA). |
| `admin` | Administrador | `/manage/` (administración propia: áreas y agentes, categorías, intenciones, routing, SLA) y `/admin/` (auditoría). |

Recorrido sugerido:
1. `usuario` → «Mis tickets» → «Nota incorrecta en Cálculo I» → **Confirmar solución** (queda Cerrado).
2. `usuario` → «Pago no reflejado» (esperando al usuario) → responder con un PDF → vuelve a «En proceso».
3. `usuario` → «Nueva solicitud» → crear → se abre el detalle del ticket nuevo.
4. `agente_ti` → «Bandeja» → «Sin asignar» → abrir el ticket nuevo → asignarse → «Iniciar atención» → «Resolver» con un mensaje.
5. `usuario` → abrir ese ticket → ver la resolución en la conversación → confirmar o rechazar.
6. `supervisor` → «Alertas» y «Bandeja» → «Historial».
7. `usuario` → abrir **`/assistant/`** (pantalla provisional hasta que FRONT la diseñe) y preguntar:
   «¿Cuál es mi horario de hoy?», «¿Cuáles son mis notas?», «¿Cuánto debo?» (respuesta automática con datos simulados),
   «Mi nota de Cálculo I está incorrecta» (crea ticket para Secretaría Académica) o «certificado y contraseña»
   (ambigua: ticket + alerta de revisión humana, visible para `supervisor` en «Alertas»).

El mismo agente se puede probar desde consola (muestra intención, nivel N0–N4 y recorrido):

```bash
python manage.py ask usuario "¿Cuánto debo?"
python manage.py ask usuario "¿Cuánto debo?" --channel WHATSAPP    # solo el total (minimización)
python manage.py ask --anonymous "¿Cuáles son los requisitos?"      # sin identificar: solo respuestas N1
```

**Agente LangGraph (IA).** Cada mensaje recorre el grafo de `docs/agent_graph.md`: reglas → LLM (solo si
las reglas no resuelven) → decisión N0–N4 → herramienta/ticket → revisión humana si hace falta. En
desarrollo el LLM es simulado (`LLM_PROVIDER=fake`). Para verlo:

```bash
python manage.py ask usuario "¿Cuál es mi horario de hoy?"
python manage.py ask usuario "¿Y mañana?"                            # memoria de conversación (CA-010)
python manage.py ask usuario "no logro acceder a la biblioteca digital"   # lo clasifica el LLM
python manage.py ask usuario "algo raro #fallo-llm"                  # LLM caído → ticket + revisión (CA-007)
python manage.py evaluate_intents                                    # accuracy y macro F1 del clasificador
```

Los casos que quedan en revisión aparecen como alerta «Revisión humana»; un `agente_ti` o el
`supervisor` decide (aceptar/corregir/rechazar) con `POST /tickets/<código>/review/` (la tarjeta
visual del detalle la hará FRONT; mientras tanto, también desde `python manage.py shell`).

Tareas periódicas (en producción, con cron; en desarrollo se pueden lanzar a mano):

```bash
python manage.py process_integration_queue  # cada minuto: WhatsApp (entrada, salida, reintentos)
python manage.py check_sla              # cada 5 min: alertas de SLA y escalamiento automático
python manage.py close_stale_tickets    # cada hora: cierre/cancelación automáticos
```

### LLM real: Qwen3-8B (vLLM) en la red de la universidad

En `.env`: `LLM_PROVIDER=openai_compat`, `LLM_BASE_URL=http://172.16.8.69:8000/v1` (opcional
`LLM_FALLBACK_PROVIDER=fake`). Luego:

```bash
python manage.py llm_ping                     # conectividad, modelo y una clasificación de prueba
python manage.py evaluate_intents --agent     # accuracy / macro F1 / latencia con el LLM real
```

### WhatsApp simulado (sin acceso a Meta)

```bash
# 1) usuario → /profile/whatsapp/ → «Generar código» (6 dígitos)
python manage.py whatsapp_simulate +593991112233 "¿Cuánto debo?"   # sin vincular: pide vincular
python manage.py whatsapp_simulate +593991112233 "<código>"         # vincula el número
python manage.py whatsapp_simulate +593991112233 "¿Cuánto debo?"   # responde solo el total
```

En producción el worker corre por cron: `* * * * * python manage.py process_integration_queue`.

### Carga y benchmark (opcional)

```bash
LOAD_PASSWORD=<clave de seed_demo --password> python scripts/load_test.py --threads 10 --requests 50
python manage.py evaluate_intents --agent     # accuracy y latencia P50/P95/P99 del agente
python manage.py run_sga_mock --port 8099     # SGA simulado (INSTITUTIONAL_PROVIDER=sga, SGA_BASE_URL=…)
```

Para producción: `DJANGO_SETTINGS_MODULE=config.settings.prod` (exige clave secreta y hosts reales; DEBUG siempre apagado) y el bloque «Producción» de `.env.example` (HTTPS, cookies seguras, proxy, caché compartida).

### Verificación automática en navegador (opcional)

```bash
pip install playwright && playwright install chromium   # solo para esta verificación
python manage.py seed_demo --password Prueba-E2E-2026     # sobre una base recién migrada
python manage.py runserver &
E2E_PASSWORD=Prueba-E2E-2026 python scripts/e2e_demo.py salida_e2e/   # 12 pasos, 5 roles
```

## Seguridad de accesos

| Protección | Detalle |
|---|---|
| Contraseñas | Mínimo 10 caracteres, con letras y números, no comunes ni parecidas al usuario. Hash **Argon2id** (las PBKDF2 antiguas se migran solas al ingresar). |
| Usuarios demo | Sin contraseña publicada: `seed_demo` genera una aleatoria por usuario. `seed_demo --rotate` las regenera. |
| Contraseña temporal | `python manage.py reset_password <usuario>` (o crear/cambiar la clave de otro desde el admin) obliga a cambiarla en el siguiente ingreso. Cada usuario la cambia en `/accounts/password/`. |
| Fuerza bruta | 5 fallos por cuenta y 20 por IP cada 15 min → bloqueo temporal (HTTP 429). El login de `/admin/` usa el mismo formulario protegido. |
| Sesión | Se cierra tras `SESSION_IDLE_TIMEOUT_MINUTES` (30) de inactividad, al cerrar el navegador y como máximo a las 8 h. Cambiar la contraseña cierra las demás sesiones. |
| Auditoría | Ingresos, fallos, bloqueos, salidas y cambios de contraseña quedan en el registro de auditoría con IP (nunca la contraseña). |
| Admin | Ruta configurable con `DJANGO_ADMIN_URL` (p. ej. `gestion-7k2/`). |
| Revisión | `python manage.py check --deploy` avisa si queda un usuario demo con la contraseña antigua `Demo-2026!` o el admin en `/admin/`. |

**Antes de compartir el sistema con otras personas** (red local o túnel):

```bash
pip install -r requirements.txt        # incluye argon2-cffi
python manage.py migrate
python manage.py seed_demo --rotate    # contraseñas nuevas; entregar a cada quien solo la suya
python manage.py check --deploy        # sin avisos accounts.W001/W002
```

y en `.env`: una `DJANGO_SECRET_KEY` propia (comando en `.env.example`), `DJANGO_DEBUG=False`
y `DJANGO_ADMIN_URL` distinta de `admin/`.

## Pruebas

```bash
pytest --cov
ruff check . && ruff format --check .
```

Las pruebas usan PostgreSQL real (`config.settings.test`); CI ejecuta lo mismo en GitHub Actions.
