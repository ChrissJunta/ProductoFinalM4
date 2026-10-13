import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_custom_user_model_is_configured():
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_defaults(make_user):
    user = make_user()
    assert user.phone == ""
    assert user.external_id == ""
    assert user.source == User.Source.LOCAL
    assert user.phone_verified_at is None
    assert user.is_phone_verified is False


@pytest.mark.parametrize("phone", ["+593991234567", "+14155552671"])
def test_valid_phone(make_user, phone):
    user = make_user(phone=phone)
    user.full_clean()


@pytest.mark.parametrize(
    "phone", ["0991234567", "+0991234567", "+59399 123", "593991234567", "+12"]
)
def test_invalid_phone(make_user, phone):
    user = make_user(phone=phone)
    with pytest.raises(ValidationError) as exc:
        user.full_clean()
    assert "phone" in exc.value.message_dict


def test_is_phone_verified_requires_phone_and_timestamp(make_user):
    user = make_user(phone="+593991234567")
    assert user.is_phone_verified is False
    user.phone_verified_at = timezone.now()
    assert user.is_phone_verified is True


def test_empty_phone_and_external_id_can_repeat(make_user):
    make_user("a")
    make_user("b")
    assert User.objects.filter(phone="", external_id="").count() == 2


def test_phone_must_be_unique(make_user):
    make_user("a", phone="+593991234567")
    with pytest.raises(IntegrityError):
        make_user("b", phone="+593991234567")


def test_external_id_must_be_unique(make_user):
    make_user("a", external_id="EST-001")
    with pytest.raises(IntegrityError):
        make_user("b", external_id="EST-001")


def test_invalid_source_rejected(make_user):
    user = make_user(source="OTRO")
    with pytest.raises(ValidationError):
        user.full_clean()
