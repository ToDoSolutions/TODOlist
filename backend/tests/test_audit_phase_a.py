"""Tests de regresión Fase A (auditoría): aislamiento multi-tenant en
webhooks GitHub, write-scope en canales que escriben sobre tareas
(AI apply, plan_day, intake submit), rotación de claves E2EE y throttle
en acciones destructivas de cuenta."""
import pytest

from apps.ai_assistant.models import AiSuggestion
from apps.collaboration.models import ProjectMember
from apps.encryption.models import EncryptedKeyShare, UserPublicKey
from apps.intake.models import IntakeForm
from apps.tasks.models import Task
from apps.users.api_auth import SensitiveActionRateThrottle


@pytest.fixture
def viewer_membership(project, other_user):
    """other_user como viewer (solo lectura) del proyecto de user."""
    return ProjectMember.objects.create(
        project=project, user=other_user, role=ProjectMember.Role.VIEWER
    )


# --- AUD-02: ai apply requiere escritura ---

@pytest.mark.django_db
class TestAiApplyWriteScope:
    def test_apply_viewer_no_mutates(self, authed_client_other, other_user, task, viewer_membership):
        suggestion = AiSuggestion.objects.create(
            user=other_user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE,
            output_data={"suggested_priority": 1},
        )
        resp = authed_client_other.post(
            f"/api/ai/suggestions/{suggestion.id}/action/", {"action": "apply"}
        )
        assert resp.status_code == 403
        task.refresh_from_db()
        assert task.priority != 1  # sin mutación

    def test_apply_editor_ok(self, authed_client_other, other_user, task, project):
        ProjectMember.objects.create(
            project=project, user=other_user, role=ProjectMember.Role.EDITOR
        )
        suggestion = AiSuggestion.objects.create(
            user=other_user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE,
            output_data={"suggested_priority": 1},
        )
        resp = authed_client_other.post(
            f"/api/ai/suggestions/{suggestion.id}/action/", {"action": "apply"}
        )
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.priority == 1


# --- AUD-03: plan_day no toca tareas de solo lectura ---

@pytest.mark.django_db
class TestPlanDayWriteScope:
    def test_plan_day_viewer_no_toca_tareas(self, authed_client_other, other_user, task, viewer_membership):
        task.assignee = other_user
        task.save(update_fields=["assignee"])
        version_before = task.version

        resp = authed_client_other.post("/api/tasks/plan-day/", {"limit": 5})
        assert resp.status_code == 200
        assert resp.data["slots"] == []
        task.refresh_from_db()
        assert task.version == version_before
        assert task.start_date is None


# --- AUD-04: intake submit exige escritura ---

@pytest.mark.django_db
class TestIntakeSubmitWriteScope:
    def test_submit_viewer_403(self, authed_client_other, other_user, project, user, viewer_membership):
        form = IntakeForm.objects.create(
            owner=user, project=project, name="Feedback",
            schema=[{"name": "title", "type": "text", "required": True}],
        )
        resp = authed_client_other.post(
            f"/api/intake-forms/{form.id}/submit/",
            {"data": {"title": "Bug report"}}, format="json",
        )
        assert resp.status_code == 403
        assert not Task.objects.filter(title="Bug report").exists()

    def test_submit_editor_201(self, authed_client_other, other_user, project, user):
        ProjectMember.objects.create(
            project=project, user=other_user, role=ProjectMember.Role.EDITOR
        )
        form = IntakeForm.objects.create(
            owner=user, project=project, name="Feedback",
            schema=[{"name": "title", "type": "text", "required": True}],
        )
        resp = authed_client_other.post(
            f"/api/intake-forms/{form.id}/submit/",
            {"data": {"title": "Bug report"}}, format="json",
        )
        assert resp.status_code == 201
        assert Task.objects.filter(title="Bug report", project=project).exists()


# --- AUD-05: rotación de clave pública ---

@pytest.mark.django_db
class TestKeyRotation:
    def test_rotate_preserva_shares_y_registra_nueva(self, authed_client, user):
        from apps.encryption.models import EncryptedTask

        old_key = UserPublicKey.objects.create(
            user=user, key_id="k1", public_key="pk-old", algorithm="RSA-OA-256"
        )
        etask = EncryptedTask.objects.create(
            owner=user, encrypted_data="cipher", encryption_key_id="k1", iv="iv"
        )
        EncryptedKeyShare.objects.create(
            encrypted_task=etask, user=user,
            encrypted_key="wrapped", user_public_key=old_key,
        )

        resp = authed_client.post(
            f"/api/public-keys/{old_key.id}/rotate/",
            {"public_key": "pk-new", "key_id": "k2"},
        )
        assert resp.status_code == 200
        assert resp.data["pending_reencryption_count"] == 1

        old_key.refresh_from_db()
        assert old_key.rotated_at is not None
        assert old_key.is_active is False  # no se usa para nuevos shares

        new_key = UserPublicKey.objects.get(key_id="k2")
        assert new_key.is_active is True
        # El share sigue resolviendo a la clave vieja (descifrado no roto)
        assert EncryptedKeyShare.objects.get(user_public_key=old_key)


# --- AUD-11: oauth state single-use y email no verificado ---

@pytest.mark.django_db
class TestOAuthHardening:
    def test_state_single_use(self):
        from django.core.cache import cache
        from apps.integrations.views import _consume_oauth_state

        cache.set("gh_oauth_state:abc", 1)
        assert _consume_oauth_state("abc") is True
        assert _consume_oauth_state("abc") is False  # consumido

    def test_state_inexistente(self):
        from apps.integrations.views import _consume_oauth_state

        assert _consume_oauth_state("nope") is False


# --- AUD-14: throttle en acciones destructivas ---

@pytest.mark.django_db
class TestSensitiveThrottle:
    def test_throttle_classes_en_acciones(self):
        from apps.users.api_views import UserMeView

        for action_name in ("deactivate", "delete_account"):
            action_kwargs = getattr(UserMeView, action_name).kwargs
            assert SensitiveActionRateThrottle in action_kwargs["throttle_classes"]
