"""Límite de intentos con la caché de Django (SPEC §48 «rate limiting»).

Ventana fija por clave. En producción con varios procesos se usa una caché
compartida (`CACHE_BACKEND=db`, tabla creada con `createcachetable`): el MVP
no incorpora Redis (ADR-061).
"""

import hashlib

from django.conf import settings
from django.core.cache import cache


def _key(scope, ident):
    digest = hashlib.sha256(str(ident).lower().encode()).hexdigest()[:32]
    return f"rl:{scope}:{digest}"


def _rule(scope):
    return settings.RATE_LIMITS[scope]  # (límite, ventana en segundos)


def is_limited(scope, ident):
    limit, _ = _rule(scope)
    return cache.get(_key(scope, ident), 0) >= limit


def hit(scope, ident):
    """Suma un intento. Devuelve True si con este intento se superó el límite."""
    limit, window = _rule(scope)
    key = _key(scope, ident)
    if cache.add(key, 1, timeout=window):
        count = 1
    else:
        try:
            count = cache.incr(key)
        except ValueError:  # expiró entre add e incr
            cache.add(key, 1, timeout=window)
            count = 1
    return count > limit


def reset(scope, ident):
    cache.delete(_key(scope, ident))


def client_ip(request):
    """IP del cliente; `X-Forwarded-For` solo si se declaró un proxy de confianza."""
    if settings.TRUSTED_PROXY_COUNT:
        forwarded = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")]
        forwarded = [p for p in forwarded if p]
        if len(forwarded) >= settings.TRUSTED_PROXY_COUNT:
            return forwarded[-settings.TRUSTED_PROXY_COUNT]
    return request.META.get("REMOTE_ADDR", "")
