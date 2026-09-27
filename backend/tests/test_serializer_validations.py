"""Tests dirigidos a validate() de serializers de tasks."""
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.collaboration.models import ProjectMember
from apps.projects.models import Project
from apps.tasks.models import (
    CustomField,
    Epic,
    Sprint,
    Task,
    TaskActivity,
    TaskRelation,
)
from apps.tasks.serializers import (
    CustomFieldValueSerializer,
    EpicSerializer,
    SprintSerializer,
    TaskCreateUpdateSerializer,
    TaskRelationSerializer,
)

User = get_user_model()
NOW = timezone.now()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="sv_u", defaults={"email": "sv@x.com"}
    )
    return u


@pytest.fixture
def other(db):
    u, _ = User.objects.get_or_create(
        username="sv_o", defaults={"email": "sv_o@x.com"}
    )
    return u


def _ctx(user):
    req = Mock()
    req.user = user
    return {"request": req}


@pytest.mark.django_db
class TestTaskRelationValidate:
    def test_sin_target_error(self, user):
        s = TaskRelationSerializer(data={"relation_type": "blocks"}, context=_ctx(user))
        assert not s.is_valid()

    def test_target_ajeno_rechazado(self, user, other):
        foreign = Task.objects.create(owner=other, title="f")
        own = Task.objects.create(owner=user, title="own")
        s = TaskRelationSerializer(
            data={
                "source": own.id, "target": foreign.id,
                "relation_type": "blocks",
            },
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "permiso" in str(s.errors)

    def test_auto_relacion_rechazada(self, user):
        t = Task.objects.create(owner=user, title="t")
        s = TaskRelationSerializer(
            data={"target": t.id, "relation_type": "related"},
            context={**_ctx(user), "source": t},
        )
        assert not s.is_valid()
        assert "consigo misma" in str(s.errors)

    def test_dependencia_circular_rechazada(self, user):
        a = Task.objects.create(owner=user, title="A")
        b = Task.objects.create(owner=user, title="B")
        TaskRelation.objects.create(source=a, target=b, relation_type="blocks")
        # B depends_on A es la misma arista que A blocks B (duplicado semántico)
        s = TaskRelationSerializer(
            data={"target": a.id, "relation_type": "depends_on"},
            context={**_ctx(user), "source": b},
        )
        assert not s.is_valid()
        assert "duplicada" in str(s.errors).lower()

    def test_ciclo_transitivo_rechazado(self, user):
        # A depends_on B, B depends_on C → C depends_on A cerraría el ciclo
        a = Task.objects.create(owner=user, title="A")
        b = Task.objects.create(owner=user, title="B")
        c = Task.objects.create(owner=user, title="C")
        TaskRelation.objects.create(source=a, target=b, relation_type="depends_on")
        TaskRelation.objects.create(source=b, target=c, relation_type="depends_on")
        s = TaskRelationSerializer(
            data={"target": a.id, "relation_type": "depends_on"},
            context={**_ctx(user), "source": c},
        )
        assert not s.is_valid()
        assert "circular" in str(s.errors).lower()

    def test_ciclo_transitivo_blocks_rechazado(self, user):
        # A blocks B, B blocks C → C blocks A cerraría el ciclo
        a = Task.objects.create(owner=user, title="A")
        b = Task.objects.create(owner=user, title="B")
        c = Task.objects.create(owner=user, title="C")
        TaskRelation.objects.create(source=a, target=b, relation_type="blocks")
        TaskRelation.objects.create(source=b, target=c, relation_type="blocks")
        s = TaskRelationSerializer(
            data={"target": a.id, "relation_type": "blocks"},
            context={**_ctx(user), "source": c},
        )
        assert not s.is_valid()
        assert "circular" in str(s.errors).lower()

    def test_cadena_larga_sin_ciclo_permitida(self, user):
        # A→B→C→D existe; añadir D depends_on E (sin vuelta) debe pasar
        tasks = [
            Task.objects.create(owner=user, title=f"T{i}") for i in range(5)
        ]
        for i in range(3):
            TaskRelation.objects.create(
                source=tasks[i], target=tasks[i + 1], relation_type="depends_on"
            )
        s = TaskRelationSerializer(
            data={"target": tasks[4].id, "relation_type": "depends_on"},
            context={**_ctx(user), "source": tasks[3]},
        )
        assert s.is_valid(), s.errors

    def test_source_ajeno_rechazado(self, user, other):
        foreign = Task.objects.create(owner=other, title="f")
        t = Task.objects.create(owner=user, title="t")
        s = TaskRelationSerializer(
            data={"source": foreign.id, "target": t.id, "relation_type": "related"},
            context=_ctx(user),
        )
        assert not s.is_valid()

    def test_sin_source_error(self, user):
        t = Task.objects.create(owner=user, title="t")
        s = TaskRelationSerializer(
            data={"target": t.id, "relation_type": "related"},
            context=_ctx(user),
        )
        assert not s.is_valid()

    def test_relacion_valida(self, user):
        a = Task.objects.create(owner=user, title="A")
        b = Task.objects.create(owner=user, title="B")
        s = TaskRelationSerializer(
            data={"source": a.id, "target": b.id, "relation_type": "related"},
            context=_ctx(user),
        )
        assert s.is_valid(), s.errors


@pytest.mark.django_db
class TestSprintValidate:
    def test_end_antes_de_start_error(self, user):
        s = SprintSerializer(
            data={
                "name": "S", "start_date": NOW.date(),
                "end_date": NOW.date() - timedelta(days=1),
            },
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "posterior" in str(s.errors)

    def test_solo_un_activo_por_proyecto(self, user):
        p = Project.objects.create(owner=user, name="P")
        Sprint.objects.create(
            owner=user, project=p, name="S1", state="active",
            start_date=NOW.date(), end_date=NOW.date() + timedelta(days=7),
        )
        s = SprintSerializer(
            data={
                "name": "S2", "state": "active", "project": p.id,
                "start_date": NOW.date(), "end_date": NOW.date() + timedelta(days=7),
            },
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "sprint activo" in str(s.errors)

    def test_dos_sprints_planned_ok(self, user):
        p = Project.objects.create(owner=user, name="P2")
        Sprint.objects.create(
            owner=user, project=p, name="S1", state="active",
            start_date=NOW.date(), end_date=NOW.date() + timedelta(days=7),
        )
        s = SprintSerializer(
            data={
                "name": "S3", "state": "planned", "project": p.id,
                "start_date": NOW.date(), "end_date": NOW.date() + timedelta(days=7),
            },
            context=_ctx(user),
        )
        assert s.is_valid(), s.errors

    def test_update_excluye_a_si_mismo(self, user):
        p = Project.objects.create(owner=user, name="P3")
        sprint = Sprint.objects.create(
            owner=user, project=p, name="S1", state="active",
            start_date=NOW.date(), end_date=NOW.date() + timedelta(days=7),
        )
        s = SprintSerializer(
            sprint,
            data={"name": "S1 renombrado"},
            partial=True,
            context=_ctx(user),
        )
        assert s.is_valid(), s.errors

    def test_proyecto_sin_permiso(self, user, other):
        p = Project.objects.create(owner=other, name="Ajeno")
        s = SprintSerializer(
            data={"name": "S", "project": p.id}, context=_ctx(user)
        )
        assert not s.is_valid()

    def test_miembro_editor_puede_usar_proyecto(self, user, other):
        p = Project.objects.create(owner=other, name="Compartido")
        ProjectMember.objects.create(project=p, user=user, role="editor")
        s = SprintSerializer(
            data={
                "name": "S", "project": p.id,
                "start_date": NOW.date(), "end_date": NOW.date() + timedelta(days=7),
            },
            context=_ctx(user),
        )
        assert s.is_valid(), s.errors


@pytest.mark.django_db
class TestEpicValidate:
    def test_end_antes_de_start(self, user):
        s = EpicSerializer(
            data={
                "title": "E", "start_date": NOW.date(),
                "end_date": NOW.date() - timedelta(days=2),
            },
            context=_ctx(user),
        )
        assert not s.is_valid()

    def test_fechas_validas(self, user):
        s = EpicSerializer(
            data={
                "title": "E", "start_date": NOW.date(),
                "end_date": NOW.date() + timedelta(days=30),
            },
            context=_ctx(user),
        )
        assert s.is_valid(), s.errors


@pytest.mark.django_db
class TestTaskCreateUpdateValidate:
    def test_prioridad_fuera_de_rango(self, user):
        s = TaskCreateUpdateSerializer(
            data={"title": "t", "priority": 9}, context=_ctx(user)
        )
        assert not s.is_valid()
        assert "priority" in s.errors

    def test_story_points_negativos(self, user):
        s = TaskCreateUpdateSerializer(
            data={"title": "t", "story_points": -2}, context=_ctx(user)
        )
        assert not s.is_valid()

    def test_due_date_pasado_nueva_tarea(self, user):
        s = TaskCreateUpdateSerializer(
            data={
                "title": "t",
                "due_date": (NOW - timedelta(days=3)).isoformat(),
            },
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "pasado" in str(s.errors)

    def test_due_date_pasado_update_ok(self, user):
        t = Task.objects.create(owner=user, title="t")
        s = TaskCreateUpdateSerializer(
            t,
            data={"due_date": (NOW - timedelta(days=3)).isoformat()},
            partial=True,
            context=_ctx(user),
        )
        assert s.is_valid(), s.errors

    def test_sprint_otro_proyecto(self, user):
        p1 = Project.objects.create(owner=user, name="P1")
        p2 = Project.objects.create(owner=user, name="P2")
        sprint = Sprint.objects.create(
            owner=user, project=p1, name="S",
            start_date=NOW.date(), end_date=NOW.date(),
        )
        s = TaskCreateUpdateSerializer(
            data={"title": "t", "project": p2.id, "sprint": sprint.id},
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "sprint" in str(s.errors).lower()

    def test_epic_otro_proyecto(self, user):
        p1 = Project.objects.create(owner=user, name="P1x")
        p2 = Project.objects.create(owner=user, name="P2x")
        epic = Epic.objects.create(owner=user, project=p1, title="E")
        s = TaskCreateUpdateSerializer(
            data={"title": "t", "project": p2.id, "epic": epic.id},
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "pica" in str(s.errors)

    def test_parent_ajeno(self, user, other):
        parent = Task.objects.create(owner=other, title="p")
        s = TaskCreateUpdateSerializer(
            data={"title": "t", "parent": parent.id}, context=_ctx(user)
        )
        assert not s.is_valid()

    def test_parent_auto_referencia(self, user):
        t = Task.objects.create(owner=user, title="t")
        s = TaskCreateUpdateSerializer(
            t, data={"parent": t.id}, partial=True, context=_ctx(user)
        )
        assert not s.is_valid()
        assert "propia padre" in str(s.errors)

    def test_parent_ciclo(self, user):
        a = Task.objects.create(owner=user, title="A")
        b = Task.objects.create(owner=user, title="B", parent=a)
        s = TaskCreateUpdateSerializer(
            a, data={"parent": b.id}, partial=True, context=_ctx(user)
        )
        assert not s.is_valid()
        assert "Ciclo" in str(s.errors)

    def test_parent_cadena_larga_ciclo(self, user):
        a = Task.objects.create(owner=user, title="A2")
        b = Task.objects.create(owner=user, title="B2", parent=a)
        c = Task.objects.create(owner=user, title="C2", parent=b)
        s = TaskCreateUpdateSerializer(
            a, data={"parent": c.id}, partial=True, context=_ctx(user)
        )
        assert not s.is_valid()


@pytest.mark.django_db
class TestTaskUpdateActivity:
    def test_cambio_estado_registra_actividad(self, user):
        t = Task.objects.create(owner=user, title="t", state="pending")
        s = TaskCreateUpdateSerializer(
            t, data={"state": "in_progress"}, partial=True, context=_ctx(user)
        )
        assert s.is_valid()
        s.save()
        assert TaskActivity.objects.filter(
            task=t, action="state_changed", field="state",
            new_value="in_progress",
        ).exists()

    def test_cambio_prioridad_registra(self, user):
        t = Task.objects.create(owner=user, title="t", priority=3)
        s = TaskCreateUpdateSerializer(
            t, data={"priority": 1}, partial=True, context=_ctx(user)
        )
        s.is_valid()
        s.save()
        assert TaskActivity.objects.filter(
            task=t, action="priority_changed", new_value="1"
        ).exists()

    def test_sin_cambio_no_registra(self, user):
        t = Task.objects.create(owner=user, title="t", state="pending")
        before = TaskActivity.objects.filter(task=t).count()
        s = TaskCreateUpdateSerializer(
            t, data={"title": "t2"}, partial=True, context=_ctx(user)
        )
        s.is_valid()
        s.save()
        assert TaskActivity.objects.filter(task=t).count() == before

    def test_update_tags(self, user):
        from apps.tags.models import Tag
        t = Task.objects.create(owner=user, title="t")
        tag = Tag.objects.create(owner=user, name="x")
        s = TaskCreateUpdateSerializer(
            t, data={"tags": [tag.id]}, partial=True, context=_ctx(user)
        )
        assert s.is_valid(), s.errors
        s.save()
        assert t.tags.filter(id=tag.id).exists()


@pytest.mark.django_db
class TestCustomFieldValueValidate:
    def test_task_ajena_rechazada(self, user, other):
        t = Task.objects.create(owner=other, title="ajena")
        p = Project.objects.create(owner=user, name="PX")
        f = CustomField.objects.create(
            project=p, name="cf", field_type="text"
        )
        s = CustomFieldValueSerializer(
            data={"task": t.id, "field": f.id, "value": "v"},
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "task" in s.errors

    def test_field_ajeno_rechazado(self, user, other):
        t = Task.objects.create(owner=user, title="t")
        p_other = Project.objects.create(owner=other, name="PO")
        f = CustomField.objects.create(
            project=p_other, name="cf", field_type="text"
        )
        s = CustomFieldValueSerializer(
            data={"task": t.id, "field": f.id, "value": "v"},
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "field" in s.errors

    def test_field_de_otro_proyecto(self, user):
        p1 = Project.objects.create(owner=user, name="PA")
        p2 = Project.objects.create(owner=user, name="PB")
        t = Task.objects.create(owner=user, title="t", project=p1)
        f = CustomField.objects.create(project=p2, name="cf", field_type="text")
        s = CustomFieldValueSerializer(
            data={"task": t.id, "field": f.id, "value": "v"},
            context=_ctx(user),
        )
        assert not s.is_valid()
        assert "proyecto de la tarea" in str(s.errors)

    def test_valido(self, user):
        p = Project.objects.create(owner=user, name="PV")
        t = Task.objects.create(owner=user, title="t", project=p)
        f = CustomField.objects.create(project=p, name="cf", field_type="text")
        s = CustomFieldValueSerializer(
            data={"task": t.id, "field": f.id, "value": "v"},
            context=_ctx(user),
        )
        assert s.is_valid(), s.errors
