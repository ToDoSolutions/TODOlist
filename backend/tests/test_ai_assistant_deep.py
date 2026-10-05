"""Tests dirigidos a las heurísticas de ai_assistant/services.py."""
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.ai_assistant.services import (
    _days_until_due,
    detect_blockers,
    estimate_priority,
    estimate_story_points,
    improve_description,
)
from apps.tasks.models import Task, TaskRelation

User = get_user_model()
NOW = timezone.now()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="ai_u", defaults={"email": "ai@x.com"}
    )
    return u


def _mk(**kw):
    """Task no persistida (para estimate_*) o persistida según necesidad."""
    t = Mock(spec=Task)
    t.due_date = kw.get("due_date")
    t.priority = kw.get("priority", 3)
    t.state = kw.get("state", "pending")
    t.description = kw.get("description", "")
    t.story_points = kw.get("story_points")
    return t


class TestDaysUntilDue:
    def test_sin_fecha_none(self):
        t = _mk(due_date=None)
        assert _days_until_due(t) is None

    def test_futuro_positivo(self):
        t = _mk(due_date=timezone.now() + timedelta(days=5))
        assert _days_until_due(t) == pytest.approx(5.0, abs=0.01)

    def test_pasado_negativo(self):
        t = _mk(due_date=timezone.now() - timedelta(days=2))
        assert _days_until_due(t) == pytest.approx(-2.0, abs=0.01)


@pytest.mark.django_db
class TestEstimatePriority:
    def test_tarea_inactiva_prioridad_5(self, user):
        t = Task.objects.create(owner=user, title="t", state="completed")
        r = estimate_priority(t)
        assert r["suggested_priority"] == 5
        assert r["confidence"] == 0.9

    def test_vencida_urgencia_maxima(self, user):
        t = Task.objects.create(
            owner=user, title="t",
            due_date=NOW - timedelta(days=1), priority=0, state="blocked",
        )
        r = estimate_priority(t)
        assert r["suggested_priority"] == 0
        assert "tarea vencida" in r["reasons"]
        assert "bloqueada" in r["reasons"]

    def test_vence_hoy(self, user):
        t = Task.objects.create(
            owner=user, title="t",
            due_date=NOW + timedelta(hours=12), priority=5,
        )
        r = estimate_priority(t)
        assert r["suggested_priority"] <= 3
        assert any("1 día" in x for x in r["reasons"])

    def test_vence_3_dias(self, user):
        t = Task.objects.create(
            owner=user, title="t",
            due_date=NOW + timedelta(days=2), priority=5,
        )
        r = estimate_priority(t)
        assert any("3 días" in x for x in r["reasons"])

    def test_vence_7_dias(self, user):
        t = Task.objects.create(
            owner=user, title="t",
            due_date=NOW + timedelta(days=6), priority=5,
        )
        r = estimate_priority(t)
        assert any("7 días" in x for x in r["reasons"])

    def test_bloqueada_suma_urgencia(self, user):
        a = Task.objects.create(owner=user, title="a", state="blocked", priority=5)
        b = Task.objects.create(owner=user, title="b", state="pending", priority=5)
        ra = estimate_priority(a)
        rb = estimate_priority(b)
        assert ra["suggested_priority"] < rb["suggested_priority"]

    def test_en_progreso_mas_urgente_que_pending(self, user):
        a = Task.objects.create(owner=user, title="a", state="in_progress", priority=4)
        b = Task.objects.create(owner=user, title="b", state="pending", priority=4)
        assert estimate_priority(a)["suggested_priority"] <= \
            estimate_priority(b)["suggested_priority"]

    def test_bloquea_otras_sube_urgencia(self, user):
        a = Task.objects.create(owner=user, title="a", priority=4)
        b = Task.objects.create(owner=user, title="b", priority=4)
        c = Task.objects.create(owner=user, title="c", priority=4)
        TaskRelation.objects.create(source=a, target=b, relation_type="blocks")
        TaskRelation.objects.create(source=a, target=c, relation_type="blocks")
        r = estimate_priority(a)
        assert any("bloquea" in x for x in r["reasons"])

    def test_confianza_escala_con_razones(self, user):
        pocas = estimate_priority(
            Task.objects.create(owner=user, title="p", priority=5, state="pending")
        )
        muchas = estimate_priority(
            Task.objects.create(
                owner=user, title="m",
                due_date=NOW - timedelta(days=1), priority=0, state="blocked",
            )
        )
        assert muchas["confidence"] > pocas["confidence"]
        assert muchas["confidence"] <= 0.95

    def test_sin_senales_prioridad_5(self, user):
        t = Task.objects.create(
            owner=user, title="t", priority=5, state="pending"
        )
        r = estimate_priority(t)
        assert r["suggested_priority"] == 5


@pytest.mark.django_db
class TestEstimateStoryPoints:
    def test_sin_desc_sin_subtareas_1_punto(self, user):
        t = Task.objects.create(owner=user, title="t", description="")
        r = estimate_story_points(t)
        assert r["suggested_points"] == 1

    def test_descripcion_larga_sube_puntos(self, user):
        corta = Task.objects.create(owner=user, title="c", description="x")
        larga = Task.objects.create(
            owner=user, title="l", description="x" * 600
        )
        assert estimate_story_points(larga)["suggested_points"] > \
            estimate_story_points(corta)["suggested_points"]

    def test_muchas_subtareas_13_puntos(self, user):
        from apps.tasks.models import Subtask
        t = Task.objects.create(owner=user, title="t", description="x" * 600)
        for i in range(8):
            Subtask.objects.create(task=t, title=f"s{i}")
        r = estimate_story_points(t)
        assert r["suggested_points"] == 13

    def test_dependencias_suman(self, user):
        a = Task.objects.create(owner=user, title="a")
        for i in range(4):
            dep = Task.objects.create(owner=user, title=f"d{i}")
            TaskRelation.objects.create(
                source=a, target=dep, relation_type="depends_on"
            )
        r = estimate_story_points(a)
        assert any("depende" in x for x in r["reasons"])

    def test_puntos_en_opciones_fibonacci(self, user):
        t = Task.objects.create(owner=user, title="t", description="x" * 300)
        r = estimate_story_points(t)
        assert r["suggested_points"] in [1, 2, 3, 5, 8, 13]


@pytest.mark.django_db
class TestDetectBlockers:
    def test_stale_in_progress(self, user):
        t = Task.objects.create(owner=user, title="t", state="in_progress")
        Task.objects.filter(pk=t.pk).update(
            updated_at=NOW - timedelta(days=10)
        )
        blockers = detect_blockers(user)
        assert any(b["blocker_type"] == "stale_in_progress" for b in blockers)
        assert any("10" in b["detail"] for b in blockers)

    def test_dependencia_no_resuelta(self, user):
        a = Task.objects.create(owner=user, title="a", state="pending")
        b = Task.objects.create(owner=user, title="b", state="in_progress")
        TaskRelation.objects.create(
            source=a, target=b, relation_type="depends_on"
        )
        blockers = detect_blockers(user)
        dep = [x for x in blockers if x["blocker_type"] == "dependency_unresolved"]
        assert len(dep) == 1
        assert dep[0]["severity"] == "high"
        assert dep[0]["blocking_task_id"] == b.id

    def test_blocks_direccion_correcta(self, user):
        # "A blocks B": la bloqueada es B (target), no A (source).
        a = Task.objects.create(owner=user, title="a", state="pending")
        b = Task.objects.create(owner=user, title="b", state="pending")
        TaskRelation.objects.create(
            source=a, target=b, relation_type="blocks"
        )
        dep = [x for x in detect_blockers(user)
               if x["blocker_type"] == "dependency_unresolved"]
        assert len(dep) == 1
        assert dep[0]["task_id"] == b.id
        assert dep[0]["blocking_task_id"] == a.id
        assert dep[0]["detail"].startswith("Bloqueada por")

    def test_dependencia_resuelta_no_bloquea(self, user):
        a = Task.objects.create(owner=user, title="a", state="pending")
        b = Task.objects.create(owner=user, title="b", state="completed")
        TaskRelation.objects.create(
            source=a, target=b, relation_type="depends_on"
        )
        blockers = detect_blockers(user)
        assert not any(
            b["blocker_type"] == "dependency_unresolved" for b in blockers
        )

    def test_overdue_severity_por_dias(self, user):
        Task.objects.create(
            owner=user, title="r", state="pending",
            due_date=NOW - timedelta(days=1),
        )
        Task.objects.create(
            owner=user, title="v", state="pending",
            due_date=NOW - timedelta(days=10),
        )
        blockers = {b["task_title"]: b for b in detect_blockers(user)
                    if b["blocker_type"] == "overdue"}
        assert blockers["r"]["severity"] == "medium"
        assert blockers["v"]["severity"] == "high"

    def test_completadas_ignoradas(self, user):
        Task.objects.create(
            owner=user, title="c", state="completed",
            due_date=NOW - timedelta(days=10),
        )
        assert not any(b["blocker_type"] == "overdue" for b in detect_blockers(user))

    def test_cifradas_excluidas(self, user):
        """E2E: la IA no procesa tareas con contenido cifrado."""
        from apps.encryption.models import EncryptedTask
        t = Task.objects.create(
            owner=user, title="enc", state="pending",
            due_date=NOW - timedelta(days=10),
        )
        EncryptedTask.objects.create(
            owner=user, task=t, encrypted_data="x",
            encryption_key_id="k1", iv="y", auth_tag="z",
        )
        blockers = detect_blockers(user)
        assert not any(b["task_title"] == "enc" for b in blockers)


@pytest.mark.django_db
class TestImproveDescription:
    def test_sin_descripcion(self, user):
        t = Task.objects.create(owner=user, title="t", description="")
        r = improve_description(t)
        assert any("no tiene descripción" in s for s in r["suggestions"])

    def test_descripcion_corta(self, user):
        t = Task.objects.create(owner=user, title="t", description="corta")
        r = improve_description(t)
        assert any("muy corta" in s for s in r["suggestions"])
        assert any("criterios" in s for s in r["suggestions"])

    def test_falta_como_por_que_criterios(self, user):
        t = Task.objects.create(
            owner=user, title="t", description="Hacer el login con OAuth."
        )
        r = improve_description(t)
        assert any("cómo" in s for s in r["suggestions"])
        assert any("por qué" in s for s in r["suggestions"])
        assert any("criterios" in s.lower() for s in r["suggestions"])

    def test_descripcion_completa(self, user):
        desc = (
            "Cómo: implementar OAuth2 con PKCE. "
            "Por qué: seguridad reforzada. "
            "Criterio de aceptación: login funcional. " + "x" * 200
        )
        t = Task.objects.create(owner=user, title="t", description=desc)
        r = improve_description(t)
        assert any("parece completa" in s for s in r["suggestions"])

    def test_dependencias_sugiere_mencionarlas(self, user):
        a = Task.objects.create(owner=user, title="a", description="x" * 60)
        b = Task.objects.create(owner=user, title="b")
        TaskRelation.objects.create(
            source=a, target=b, relation_type="depends_on"
        )
        r = improve_description(a)
        assert any("dependencias" in s for s in r["suggestions"])

    def test_subtareas_sin_desc_sugiere_referenciar(self, user):
        from apps.tasks.models import Subtask
        t = Task.objects.create(owner=user, title="t", description="")
        Subtask.objects.create(task=t, title="sub")
        r = improve_description(t)
        assert any("subtareas" in s for s in r["suggestions"])
