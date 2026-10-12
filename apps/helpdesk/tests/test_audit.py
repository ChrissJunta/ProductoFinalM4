import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from apps.helpdesk import audit
from apps.helpdesk.models import Area, AuditLog

pytestmark = pytest.mark.django_db


def test_record_with_user(make_user):
    user = make_user()
    area = Area.objects.get(code="IT")
    log = audit.record("CUSTOM", area, actor=user, metadata={"ip": "127.0.0.1"})
    assert log.entity_type == "helpdesk.area"
    assert log.entity_id == str(area.pk)
    assert log.actor_type == AuditLog.ActorType.USER
    assert log.metadata_json == {"ip": "127.0.0.1"}


def test_record_without_actor_is_system():
    log = audit.record("CUSTOM", Area.objects.get(code="IT"))
    assert log.actor is None
    assert log.actor_type == AuditLog.ActorType.SYSTEM


def test_anonymous_actor_is_not_stored():
    log = audit.record("CUSTOM", Area.objects.get(code="IT"), actor=AnonymousUser())
    assert log.actor is None
    assert log.actor_type == AuditLog.ActorType.SYSTEM


def test_explicit_ai_actor_type():
    log = audit.record("CLASSIFY", Area.objects.get(code="IT"), actor_type=AuditLog.ActorType.AI)
    assert log.actor_type == AuditLog.ActorType.AI


def test_audit_log_is_immutable():
    log = audit.record("CUSTOM", Area.objects.get(code="IT"))
    log.action = "CHANGED"
    with pytest.raises(ValidationError):
        log.save()
    with pytest.raises(ValidationError):
        log.delete()
    log.refresh_from_db()
    assert log.action == "CUSTOM"


def test_actor_deletion_keeps_log(make_user):
    user = make_user()
    log = audit.record("CUSTOM", Area.objects.get(code="IT"), actor=user)
    user.delete()
    log.refresh_from_db()
    assert log.actor is None
    assert log.actor_type == AuditLog.ActorType.USER
