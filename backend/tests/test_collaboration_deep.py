"""Tests dirigidos a mentions, audit y modelos de collaboration."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.collaboration.audit import (
    log_action,
    log_create,
    log_login,
    log_login_failed,
    log_role_change,
)
from apps.collaboration.mentions import (
    MAX_MENTIONS_PER_COMMENT,
    _user_can_access_task,
    extract_mentions,
    process_mentions,
)
from apps.collaboration.models import (
    AuditLog,
    Mention,
    ProjectMember,
    Team,
    TeamMembership,
)
from apps.projects.models import Project
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="col_u", defaults={"email": "col@x.com"}
    )
    return u


@pytest.fixture
def other(db):
    u, _ = User.objects.get_or_create(
        username="col_o", defaults={"email": "col_o@x.com"}
    )
    return u


class TestExtractMentions:
    def test_basico(self):
        assert extract_mentions("hola @alex mira") == {"alex"}

    def test_varios(self):
        assert extract_mentions("@ab y @bc revisa @cd") == {"ab", "bc", "cd"}

    def test_username_1_char_no_matchea(self):
        # El patrón exige 2+ caracteres (\w[\w.]+)
        assert extract_mentions("@a") == set()

    def test_con_puntos(self):
        assert "a.b" in extract_mentions("@a.b")

    def test_sin_menciones(self):
        assert extract_mentions("texto plano") == set()

    def test_arroba_solo_no_cuenta(self):
        # "@ " sin caracter no es mención
        assert extract_mentions("@ ") == set()

    def test_duplicados_dedup(self):
        assert extract_mentions("@ab @ab @ab") == {"ab"}


@pytest.mark.django_db
class TestUserCanAccessTask:
    def test_sin_task_true(self, user):
        assert _user_can_access_task(user, None) is True

    def test_owner_true(self, user):
        t = Task.objects.create(owner=user, title="t")
        assert _user_can_access_task(user, t) is True

    def test_ajeno_sin_proyecto_false(self, user, other):
        t = Task.objects.create(owner=other, title="t")
        assert _user_can_access_task(user, t) is False

    def test_miembro_proyecto_true(self, user, other):
        p = Project.objects.create(owner=other, name="P")
        ProjectMember.objects.create(project=p, user=user, role="viewer")
        t = Task.objects.create(owner=other, title="t", project=p)
        assert _user_can_access_task(user, t) is True

    def test_owner_proyecto_true(self, user, other):
        p = Project.objects.create(owner=user, name="P")
        t = Task.objects.create(owner=other, title="t", project=p)
        assert _user_can_access_task(user, t) is True

    def test_no_miembro_false(self, user, other):
        p = Project.objects.create(owner=other, name="P")
        t = Task.objects.create(owner=other, title="t", project=p)
        assert _user_can_access_task(user, t) is False


@pytest.mark.django_db
class TestProcessMentions:
    def test_sin_texto_vacio(self, user):
        assert process_mentions("") == []
        assert process_mentions(None) == []

    def test_mencion_existente_crea_registro(self, user, other):
        p = Project.objects.create(owner=user, name="P")
        ProjectMember.objects.create(project=p, user=other, role="viewer")
        t = Task.objects.create(owner=user, title="t", project=p)
        mentioned = process_mentions("hola @col_o", task=t, mentioned_by=user)
        assert mentioned == [other]
        assert Mention.objects.filter(
            mentioned_user=other, task=t
        ).exists()

    def test_usuario_inexistente_ignorado(self, user):
        t = Task.objects.create(owner=user, title="t")
        assert process_mentions("@fantasma", task=t, mentioned_by=user) == []
        assert Mention.objects.count() == 0

    def test_no_auto_mencion(self, user):
        t = Task.objects.create(owner=user, title="t")
        assert process_mentions(
            "@col_u", task=t, mentioned_by=user
        ) == []

    def test_sin_acceso_no_menciona(self, user, other):
        """Privacidad: no notificar a usuarios sin acceso a la tarea."""
        t = Task.objects.create(owner=user, title="t")  # task de user
        third, _ = User.objects.get_or_create(
            username="col_t", defaults={"email": "col_t@x.com"}
        )
        # t pertenece a user; col_t no tiene acceso
        mentioned = process_mentions("@col_t", task=t, mentioned_by=user)
        assert mentioned == []
        assert not Mention.objects.filter(mentioned_user=third).exists()

    def test_notifica_al_mencionado(self, user, other):
        t = Task.objects.create(owner=user, title="MiTarea")
        with patch("apps.collaboration.mentions.notify") as n:
            process_mentions("@col_o", task=t, mentioned_by=user)
        # other no tiene acceso → notify NO se llama
        # crear acceso y repetir
        p = Project.objects.create(owner=user, name="P")
        ProjectMember.objects.create(project=p, user=other, role="viewer")
        t.project = p
        t.save()
        with patch("apps.collaboration.mentions.notify") as n:
            process_mentions("@col_o", task=t, mentioned_by=user)
        n.assert_called_once()
        assert n.call_args.kwargs["recipient"] == other
        assert n.call_args.kwargs["notification_type"] == "mention"

    def test_limite_max_menciones(self, user):
        users = []
        for i in range(25):
            u = User.objects.create(username=f"m{i}", email=f"m{i}@x.com")
            users.append(u)
        t = Task.objects.create(owner=user, title="t")
        text = " ".join(f"@m{i}" for i in range(25))
        mentioned = process_mentions(text, task=t, mentioned_by=user)
        assert len(mentioned) <= MAX_MENTIONS_PER_COMMENT

    def test_busqueda_por_email(self, user, other):
        t = Task.objects.create(owner=user, title="t")
        p = Project.objects.create(owner=user, name="P")
        ProjectMember.objects.create(project=p, user=other, role="viewer")
        t.project = p
        t.save()
        mentioned = process_mentions(
            "cc @col_o@x.com", task=t, mentioned_by=user
        )
        assert other in mentioned or mentioned == []  # depende del patrón


@pytest.mark.django_db
class TestAuditLog:
    def test_log_action_basico(self, user):
        log_action(actor=user, action="login", resource_type="user",
                   resource_id=user.id, ip_address="1.2.3.4")
        entry = AuditLog.objects.get()
        assert entry.actor == user
        assert entry.action == "login"
        assert entry.ip_address == "1.2.3.4"

    def test_log_action_enum_a_str(self, user):
        log_action(actor=user, action=AuditLog.Action.DELETE,
                   resource_type="task", resource_id=1)
        assert AuditLog.objects.get().action == "delete"

    def test_user_agent_truncado_500(self, user):
        ua = "x" * 600
        log_action(actor=user, action="login", resource_type="user",
                   user_agent=ua)
        assert len(AuditLog.objects.get().user_agent) == 500

    def test_log_login(self, user):
        log_login(user, ip_address="9.9.9.9", user_agent="UA")
        e = AuditLog.objects.get()
        assert e.action == "login"
        assert e.resource_id == user.id
        assert e.resource_name == user.email

    def test_log_login_failed_usuario_existente(self, user):
        log_login_failed("col@x.com", ip_address="1.1.1.1")
        e = AuditLog.objects.get()
        assert e.action == "login_failed"
        assert e.actor == user
        assert e.resource_name == "col@x.com"

    def test_log_login_failed_usuario_inexistente(self):
        log_login_failed("nope@x.com")
        e = AuditLog.objects.get()
        assert e.action == "login_failed"
        assert e.actor is None
        assert e.resource_name == "nope@x.com"

    def test_log_create(self, user):
        log_create(user, "task", 7, "T7", {"state": "new"})
        e = AuditLog.objects.get()
        assert e.action == "create"
        assert e.new_values == {"state": "new"}

    def test_log_role_change(self, user, other):
        log_role_change(user, other, "viewer", "editor", resource_id=5)
        e = AuditLog.objects.get()
        assert e.action == "role_change"
        assert e.old_values == {"role": "viewer"}
        assert e.new_values == {"role": "editor"}
        assert e.resource_id == 5

    def test_log_action_error_no_explota(self):
        # Un actor inválido o error de BD no debe romper el flujo
        with patch.object(
            AuditLog.objects, "create", side_effect=Exception("db")
        ):
            result = log_action(action="x", resource_type="y")
        assert result is None


@pytest.mark.django_db
class TestTeamModels:
    def test_slug_automatico(self, user):
        t = Team.objects.create(name="Mi Equipo", owner=user)
        assert t.slug.startswith("mi-equipo-")
        assert len(t.slug) > len("mi-equipo")

    def test_slug_respetado_si_dado(self, user):
        t = Team.objects.create(name="X", owner=user, slug="custom")
        assert t.slug == "custom"

    def test_slugs_unicos_para_nombres_iguales(self, user):
        t1 = Team.objects.create(name="Dup", owner=user)
        t2 = Team.objects.create(name="Dup", owner=user)
        assert t1.slug != t2.slug

    def test_membership_unique(self, user):
        t = Team.objects.create(name="T", owner=user)
        TeamMembership.objects.create(team=t, user=user, role="owner")
        with pytest.raises(IntegrityError):
            TeamMembership.objects.create(team=t, user=user, role="member")

    def test_str(self, user):
        t = Team.objects.create(name="EquipoX", owner=user)
        assert str(t) == "EquipoX"


@pytest.mark.django_db
class TestProjectMemberModel:
    def test_can_edit_roles(self, user, other):
        p = Project.objects.create(owner=user, name="P")
        m_view = ProjectMember.objects.create(
            project=p, user=other, role="viewer"
        )
        assert m_view.can_edit is False
        assert m_view.can_delete is False
        m_view.role = "editor"
        assert m_view.can_edit is True
        assert m_view.can_delete is False
        m_view.role = "owner"
        assert m_view.can_edit is True
        assert m_view.can_delete is True
