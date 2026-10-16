"""Configuración común a todos los entornos.

Los valores sensibles se leen de variables de entorno (o de un archivo `.env`
en la raíz del proyecto). Ver `.env.example`.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps del proyecto (SPEC §24: solo estas cinco)
    "apps.accounts",
    "apps.helpdesk",
    "apps.automation",
    "apps.integrations",
    "apps.ai",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.accounts.middleware.SessionIdleTimeoutMiddleware",
    "apps.accounts.middleware.ForcePasswordChangeMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.accounts.context_processors.role",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# PostgreSQL es el único motor soportado (SPEC §5.1).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="helpdesk"),
        "USER": env("POSTGRES_USER", default="helpdesk"),
        "PASSWORD": env("POSTGRES_PASSWORD", default=""),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        # 0 = una conexión por petición. Con un servidor de hilos efímeros (runserver)
        # las conexiones persistentes se acumulan hasta agotar PostgreSQL (TEST-RUN-013).
        # En producción con workers fijos (gunicorn) puede subirse si
        # workers × hilos < max_connections (ADR-062).
        "CONN_MAX_AGE": env.int("POSTGRES_CONN_MAX_AGE", default=0),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Autenticación (SPEC §25)
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.UsernameOrEmailBackend"]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:role_redirect"
LOGOUT_REDIRECT_URL = "accounts:login"

# Política de contraseñas (ADR-071): 10+ caracteres, con letras y números, no común,
# no parecida a los datos del usuario y no solo numérica.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "apps.accounts.validators.LettersAndDigitsValidator"},
]

# Argon2id como algoritmo principal (ADR-071). Los hashes PBKDF2 existentes siguen siendo
# válidos y se migran a Argon2 de forma transparente en el siguiente login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# Internacionalización
LANGUAGE_CODE = "es"
TIME_ZONE = env("TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True

# Archivos estáticos y adjuntos
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# `static/` pertenece al frontend; se incluye solo si existe.
STATICFILES_DIRS = [p for p in [BASE_DIR / "static"] if p.exists()]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Seguridad (SPEC §20, §48)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = env.bool("DJANGO_SECURE_COOKIES", default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool("DJANGO_SECURE_COOKIES", default=not DEBUG)
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

# Workflow de tickets (SPEC §32.1). Constantes, no tablas.
WAITING_USER_TIMEOUT_DAYS = 7  # WAITING_USER → CANCELLED sin respuesta del usuario
AUTO_CLOSE_DAYS = 3  # RESOLVED → CLOSED sin confirmación del usuario
REOPEN_WINDOW_DAYS = 7  # CLOSED → REOPENED solo dentro de este plazo desde el cierre

# SLA (SPEC §34.1). Calendario laboral como constante, no tabla.
BUSINESS_HOURS = {
    "weekdays": [0, 1, 2, 3, 4],  # lunes a viernes (0 = lunes)
    "start": "08:00",
    "end": "17:00",
}
HOLIDAYS = env.list("HOLIDAYS", default=[])  # fechas ISO, p. ej. 2026-12-25
SLA_WARNING_RATIO = 0.8  # SLA_WARNING al consumir el 80 % del plazo (§34.2)

# Integración institucional (SPEC §39-§41). «local» = datos simulados; «sga» llega con BE-T19.
INSTITUTIONAL_PROVIDER = env("INSTITUTIONAL_PROVIDER", default="local")
SGA_BASE_URL = env("SGA_BASE_URL", default="")  # solo con INSTITUTIONAL_PROVIDER=sga (BE-T19)
SGA_TOKEN = env("SGA_TOKEN", default="")
SGA_TIMEOUT = env.float("SGA_TIMEOUT", default=5.0)  # segundos por petición

# IA (SPEC §42-§46). LLM_PROVIDER elige la familia de proveedor (ADR-010 abierto: «fake»
# en desarrollo y CI); los modelos primario/respaldo se configuran en AIModelConfig.
LLM_PROVIDER = env("LLM_PROVIDER", default="fake")
# Servidor compatible con OpenAI (ADR-069): vLLM con Qwen3-8B en la red de la universidad.
LLM_BASE_URL = env("LLM_BASE_URL", default="")  # p. ej. http://172.16.8.69:8000/v1
LLM_MODEL = env("LLM_MODEL", default="Qwen/Qwen3-8B-AWQ")
LLM_API_KEY = env("LLM_API_KEY", default="")  # vLLM no la exige por defecto
LLM_TIMEOUT = env.float("LLM_TIMEOUT", default=20.0)  # segundos por llamada
LLM_ENABLE_THINKING = env.bool("LLM_ENABLE_THINKING", default=False)
# Respaldo si el proveedor principal no responde (SPEC §46), p. ej. «fake». Vacío = ninguno.
LLM_FALLBACK_PROVIDER = env("LLM_FALLBACK_PROVIDER", default="")
AI_MAX_RETRIES = 1  # reintentos del primario antes de pasar al respaldo (SPEC §46)
AI_SUMMARY_MAX_CHARS = 500
AI_ANSWER_MAX_CHARS = 1000  # respuesta libre a saludos y preguntas generales (ADR-083)
# Pop-up en el portal cuando llega un ticket por estos canales (CONTRACT-023).
NEW_TICKET_ALERT_CHANNELS = env.list("NEW_TICKET_ALERT_CHANNELS", default=["TELEGRAM"])
NEW_TICKET_POLL_SECONDS = env.int("NEW_TICKET_POLL_SECONDS", default=15)

# Agente LangGraph (SPEC §46A). «postgres» persiste los hilos pausados en revisión humana;
# «memory» solo para pruebas (se pierde al reiniciar).
AGENT_CHECKPOINTER = env("AGENT_CHECKPOINTER", default="postgres")
AGENT_MAX_STEPS = 12  # recursion_limit (SPEC §46A.5, regla 4)

# Límite de intentos (SPEC §48, ADR-061): (intentos, ventana en segundos).
RATE_LIMITS = {
    "login_ip": (20, 15 * 60),  # fallos de login por IP
    "login_user": (5, 15 * 60),  # fallos de login por nombre de usuario
    "assistant": (30, 5 * 60),  # mensajes al asistente por usuario
}
TRUSTED_PROXY_COUNT = env.int("TRUSTED_PROXY_COUNT", default=0)  # proxies delante de Django
CACHE_BACKEND = env("CACHE_BACKEND", default="locmem")  # locmem | db (varios procesos)
CACHES = {
    "default": (
        {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}
        if CACHE_BACKEND == "db"
        else {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    )
}

# Producción detrás de HTTPS (SPEC §48). Desactivados por defecto para desarrollo local.
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = env.int("DJANGO_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = False
# Entrar en la lista de precarga HSTS de los navegadores es una decisión institucional
# irreversible a corto plazo; no la toma el MVP.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
if TRUSTED_PROXY_COUNT:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_AGE = 8 * 60 * 60  # duración máxima absoluta: jornada laboral
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # no deja sesiones abiertas en equipos compartidos
SESSION_IDLE_TIMEOUT = env.int("SESSION_IDLE_TIMEOUT_MINUTES", default=30) * 60  # 0 = sin límite
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
# Ruta del admin de Django configurable (ADR-073): reduce el escaneo automático de /admin/.
ADMIN_URL = env("DJANGO_ADMIN_URL", default="admin/").strip("/") + "/"

# WhatsApp (SPEC §35, ADR-049): «simulated» registra la salida sin enviarla (sin acceso a
# Meta Developer); «cloud» usa Meta WhatsApp Cloud API con las credenciales de abajo.
WHATSAPP_MODE = env("WHATSAPP_MODE", default="simulated")
WHATSAPP_VERIFY_TOKEN = env("WHATSAPP_VERIFY_TOKEN", default="")
WHATSAPP_APP_SECRET = env("WHATSAPP_APP_SECRET", default="")
WHATSAPP_ACCESS_TOKEN = env("WHATSAPP_ACCESS_TOKEN", default="")
WHATSAPP_PHONE_NUMBER_ID = env("WHATSAPP_PHONE_NUMBER_ID", default="")
WHATSAPP_API_VERSION = env("WHATSAPP_API_VERSION", default="v21.0")
WHATSAPP_LINK_CODE_MINUTES = 10
# Telegram (ADR-080): «simulated» registra la salida sin enviarla; «bot» usa la Bot API con
# long polling (`python manage.py run_telegram_bot`), sin URL pública. El token va solo en .env.
TELEGRAM_MODE = env("TELEGRAM_MODE", default="simulated")
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", default="MesaUtiBot")
TELEGRAM_POLL_TIMEOUT = env.int("TELEGRAM_POLL_TIMEOUT", default=10)  # segundos; también
# es la demora máxima de los avisos proactivos, que salen en cada vuelta del bot
TELEGRAM_LINK_CODE_MINUTES = 10
TELEGRAM_LINK_MAX_FAILURES = 5  # códigos fallidos por chat y hora
TELEGRAM_LINK_GLOBAL_MAX_FAILURES = 100  # por hora, sumando todos los chats
INTEGRATION_MAX_ATTEMPTS = 5  # reintentos con backoff exponencial (SPEC §38.1)
WHATSAPP_LINK_MAX_FAILURES = 5  # códigos fallidos por número y hora (§35.1)
WHATSAPP_LINK_GLOBAL_MAX_FAILURES = 100  # por hora, sumando todos los números

# Logs (ADR-076). La traza del agente sale por `apps.ai.agent.trace`: una línea por nodo y
# un resumen por ejecución. `LOG_FILE` añade un archivo rotativo (p. ej. logs/agent.log).
AGENT_LOG_LEVEL = env("AGENT_LOG_LEVEL", default="INFO")
LOG_FILE = env("LOG_FILE", default="")
if LOG_FILE:
    LOG_FILE = Path(LOG_FILE) if Path(LOG_FILE).is_absolute() else BASE_DIR / LOG_FILE
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
        **(
            {
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": LOG_FILE,
                    "maxBytes": 5 * 1024 * 1024,
                    "backupCount": 3,
                    "encoding": "utf-8",
                    "formatter": "simple",
                }
            }
            if LOG_FILE
            else {}
        ),
    },
    "loggers": {
        "apps": {
            "handlers": ["console", *(["file"] if LOG_FILE else [])],
            "level": AGENT_LOG_LEVEL,
            "propagate": False,
        },
    },
}

# Decisiones propias del agente (ADR-077). Umbrales sobre la ventana de métricas.
AGENT_POLICY = {
    "window_days": 30,
    "trust_up_min_reviews": 10,  # D1: revisiones mínimas para dejar de pedir revisión
    "trust_up_rate": 0.90,  # D1: % aceptadas sin corregir
    "trust_down_min_reviews": 5,  # D2
    "trust_down_rate": 0.30,  # D2: % corregidas o rechazadas
    "review_sample_rate": 0.10,  # con D1 aplicada, 1 de cada 10 sigue yendo a revisión
    "keyword_min_messages": 3,  # D3: mensajes corregidos distintos con la palabra
    "keyword_max": 5,
    "sla_min_tickets": 5,  # D5: tickets con SLA decidido
    "sla_breach_rate": 0.30,
    "llm_window_minutes": 60,  # D4
    "llm_min_calls": 6,
    "llm_failure_rate": 0.50,
    "llm_pause_minutes": 15,
}
