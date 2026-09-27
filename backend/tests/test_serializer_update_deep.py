"""Tests dirigidos a update() de TaskSerializer y validaciones de borde."""
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.tasks.models import (
    Comment,
    RecurrenceRule,
    Task,
    TaskActivity,
    TimeEntry,
)
from apps.tasks.serializers import (
    AttachmentSerializer,
    TaskCreateUpdateSerializer,
    TimeEntrySerializer,
)

User = get_user_model()
NOW = timezone.now()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="sud_u", defaults={"email": "sud@x.com"}
    )
    return u


def _file():
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile("f.txt", b"data", content_type="text/plain")


def _ctx(user):
    req = Mock()
    req.user = user
    return {"request": req}


@pytest.mark.django_db
class TestTaskSerializerUpdate:
    def test_cambio_estado_registra_actividad(self, user):
        t = Task.objects.create(owner=user, title="t", state="pending")
        s = TaskCreateUpdateSerializer(instance=t, data={"state": "completed"},
                           partial=True, context=_ctx(user))
        assert s.is_valid(), s.errors
        s.save()
        act = TaskActivity.objects.filter(task=t).get()
        assert act.action == "state_changed"
        assert act.field == "state"
        assert act.new_value == "completed"

    def test_cambio_prioridad_registra_actividad(self, user):
        t = Task.objects.create(owner=user, title="t", priority=3)
        s = TaskCreateUpdateSerializer(instance=t, data={"priority": 1},
                           partial=True, context=_ctx(user))
        assert s.is_valid(), s.errors
        s.save()
        act = TaskActivity.objects.filter(
            task=t, field="priority"
        ).get()
        assert act.action == "priority_changed"
        assert act.old_value == "3"
        assert act.new_value == "1"

    def test_mismo_valor_no_registra(self, user):
        t = Task.objects.create(owner=user, title="t", state="pending")
        s = TaskCreateUpdateSerializer(instance=t, data={"state": "pending"},
                           partial=True, context=_ctx(user))
        assert s.is_valid(), s.errors
        s.save()
        assert TaskActivity.objects.filter(
            task=t, field="state"
        ).count() == 0

    def test_campo_no_trackeado_no_actividad(self, user):
        t = Task.objects.create(owner=user, title="t")
        s = TaskCreateUpdateSerializer(instance=t, data={"title": "nuevo"},
                           partial=True, context=_ctx(user))
        assert s.is_valid(), s.errors
        s.save()
        assert TaskActivity.objects.filter(task=t).count() == 0
        t.refresh_from_db()
        assert t.title == "nuevo"

    def test_update_sin_request_usa_owner(self, user):
        t = Task.objects.create(owner=user, title="t", state="pending")
        s = TaskCreateUpdateSerializer(instance=t, data={"state": "in_progress"},
                           partial=True, context={})
        assert s.is_valid(), s.errors
        s.save()
        act = TaskActivity.objects.get(task=t)
        assert act.actor == user

    def test_update_tags(self, user):
        from apps.tags.models import Tag
        t = Task.objects.create(owner=user, title="t")
        tag = Tag.objects.create(owner=user, name="x")
        s = TaskCreateUpdateSerializer(instance=t, data={"tags": [tag.id]},
                           partial=True, context=_ctx(user))
        assert s.is_valid(), s.errors
        s.save()
        assert list(t.tags.values_list("id", flat=True)) == [tag.id]

    def test_update_recurrencia_existente(self, user):
        rec = RecurrenceRule.objects.create(frequency="daily", interval=1)
        t = Task.objects.create(owner=user, title="t", recurrence=rec)
        s = TaskCreateUpdateSerializer(
            instance=t,
            data={"recurrence_data": {"frequency": "weekly", "interval": 2}},
            partial=True, context=_ctx(user),
        )
        assert s.is_valid(), s.errors
        s.save()
        rec.refresh_from_db()
        assert rec.frequency == "weekly"
        assert rec.interval == 2
        assert RecurrenceRule.objects.count() == 1

    def test_update_crea_recurrencia_nueva(self, user):
        t = Task.objects.create(owner=user, title="t")
        s = TaskCreateUpdateSerializer(
            instance=t,
            data={"recurrence_data": {"frequency": "monthly", "interval": 1}},
            partial=True, context=_ctx(user),
        )
        assert s.is_valid(), s.errors
        s.save()
        t.refresh_from_db()
        assert t.recurrence is not None
        assert t.recurrence.frequency == "monthly"


@pytest.mark.django_db
class TestTaskSerializerCreate:
    def test_create_con_tags(self, user):
        from apps.tags.models import Tag
        tag = Tag.objects.create(owner=user, name="tg")
        s = TaskCreateUpdateSerializer(
            data={"title": "nueva", "tags": [tag.id]}, context=_ctx(user)
        )
        assert s.is_valid(), s.errors
        t = s.save(owner=user)
        assert list(t.tags.values_list("id", flat=True)) == [tag.id]

    def test_create_con_recurrencia(self, user):
        s = TaskCreateUpdateSerializer(
            data={
                "title": "nueva",
                "recurrence_data": {"frequency": "daily", "interval": 1},
            },
            context=_ctx(user),
        )
        assert s.is_valid(), s.errors
        t = s.save(owner=user)
        assert t.recurrence is not None
        assert t.recurrence.frequency == "daily"

    def test_create_registra_actividad_created(self, user):
        s = TaskCreateUpdateSerializer(data={"title": "nueva"}, context=_ctx(user))
        assert s.is_valid(), s.errors
        t = s.save(owner=user)
        act = TaskActivity.objects.get(task=t)
        assert act.action == "created"
        assert act.actor == user


@pytest.mark.django_db
class TestTimeEntrySerializer:
    def test_task_none_error(self, user):
        s = TimeEntrySerializer(data={"task": None}, context=_ctx(user))
        assert not s.is_valid()

    def test_task_ajena_error(self, user):
        other, _ = User.objects.get_or_create(
            username="sud_o", defaults={"email": "sud_o@x.com"}
        )
        t = Task.objects.create(owner=other, title="t")
        s = TimeEntrySerializer(
            data={"task": t.id, "duration_seconds": 60},
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "permiso" in str(s.errors).lower() or "existe" in str(s.errors)

    def test_duracion_cero_error(self, user):
        t = Task.objects.create(owner=user, title="t")
        s = TimeEntrySerializer(
            data={"task": t.id, "duration_seconds": 0}, context=_ctx(user)
        )
        assert not s.is_valid()
        assert "mayor que cero" in str(s.errors)

    def test_duracion_negativa_error(self, user):
        t = Task.objects.create(owner=user, title="t")
        s = TimeEntrySerializer(
            data={"task": t.id, "duration_seconds": -50}, context=_ctx(user)
        )
        assert not s.is_valid()

    def test_duracion_none_ok(self, user):
        t = Task.objects.create(owner=user, title="t")
        s = TimeEntrySerializer(
            data={"task": t.id, "started_at": NOW.isoformat()},
            context=_ctx(user),
        )
        assert s.is_valid(), s.errors

    def test_started_at_futuro_error(self, user):
        t = Task.objects.create(owner=user, title="t")
        futuro = NOW + timedelta(hours=2)
        s = TimeEntrySerializer(
            data={"task": t.id, "started_at": futuro.isoformat()},
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "futuro" in str(s.errors)

    def test_started_at_margen_5min(self, user):
        t = Task.objects.create(owner=user, title="t")
        dentro = NOW + timedelta(minutes=4)
        s = TimeEntrySerializer(
            data={"task": t.id, "started_at": dentro.isoformat()},
            context=_ctx(user),
        )
        assert s.is_valid(), s.errors

    def test_started_at_update_no_valida_futuro(self, user):
        t = Task.objects.create(owner=user, title="t")
        entry = TimeEntry.objects.create(
            task=t, user=user, started_at=NOW
        )
        futuro = NOW + timedelta(days=1)
        s = TimeEntrySerializer(
            instance=entry,
            data={"started_at": futuro.isoformat()},
            partial=True, context=_ctx(user),
        )
        # en update (instance) la validación de futuro no aplica
        assert s.is_valid(), s.errors


@pytest.mark.django_db
class TestAttachmentSerializer:
    def test_sin_request_ok(self, user):
        t = Task.objects.create(owner=user, title="t")
        s = AttachmentSerializer(
            data={"task": t.id, "filename": "f.txt", "file": _file()},
            context={},
        )
        assert s.is_valid(), s.errors

    def test_task_ajena_error(self, user):
        other, _ = User.objects.get_or_create(
            username="sud_o2", defaults={"email": "sud_o2@x.com"}
        )
        t = Task.objects.create(owner=other, title="t")
        s = AttachmentSerializer(
            data={"task": t.id, "filename": "f.txt", "file": _file()},
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "task" in s.errors

    def test_comment_ajeno_error(self, user):
        other, _ = User.objects.get_or_create(
            username="sud_o3", defaults={"email": "sud_o3@x.com"}
        )
        t_mio = Task.objects.create(owner=user, title="mio")
        t_ajena = Task.objects.create(owner=other, title="ajena")
        c_ajeno = Comment.objects.create(
            task=t_ajena, author=other, body="x"
        )
        s = AttachmentSerializer(
            data={
                "task": t_mio.id, "comment": c_ajeno.id,
                "filename": "f.txt", "file": _file(),
            },
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "comment" in s.errors

    def test_comment_de_otra_tarea_error(self, user):
        t1 = Task.objects.create(owner=user, title="t1")
        t2 = Task.objects.create(owner=user, title="t2")
        c = Comment.objects.create(task=t2, author=user, body="x")
        s = AttachmentSerializer(
            data={
                "task": t1.id, "comment": c.id,
                "filename": "f.txt", "file": _file(),
            }, context=_ctx(user)
        )
        assert not s.is_valid()
        assert "no pertenece" in str(s.errors)

    def test_comment_y_task_misma_ok(self, user):
        t = Task.objects.create(owner=user, title="t")
        c = Comment.objects.create(task=t, author=user, body="x")
        s = AttachmentSerializer(
            data={
                "task": t.id, "comment": c.id,
                "filename": "f.txt", "file": _file(),
            }, context=_ctx(user)
        )
        assert s.is_valid(), s.errors
