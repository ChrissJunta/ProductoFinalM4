import pytest
from django.contrib.auth.models import Group

PASSWORD = "Clave-Segura-2026"


@pytest.fixture
def make_user(django_user_model):
    """Crea un usuario con el rol (Group) indicado."""

    def _make_user(username="usuario", role=None, password=PASSWORD, **extra):
        user = django_user_model.objects.create_user(username=username, password=password, **extra)
        if role:
            user.groups.add(Group.objects.get(name=role))
        return user

    return _make_user


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    """Los adjuntos de las pruebas se escriben en un directorio temporal."""
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(autouse=True)
def _clear_cache():
    """Los contadores de límite de intentos (caché) no se arrastran entre pruebas."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
