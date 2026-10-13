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
        "CONN_MAX_AGE": env.int("POSTGRES_CONN_MAX_AGE", default=60),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Autenticación (SPEC §25)
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.UsernameOrEmailBackend"]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:role_redirect"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
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
