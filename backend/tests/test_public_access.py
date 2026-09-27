"""Tests de canales públicos de entrada: intake público, share links,
inbound webhooks y email-to-task."""
import pytest

from apps.dashboards.models import ShareLink
from apps.intake.models import IntakeForm, IntakeSubmission
from apps.integrations.models import InboundWebhook
from apps.projects.models import Project
from apps.tasks.models import Comment, Task


def _intake_form(user, project, **kwargs):
    return IntakeForm.objects.create(
        owner=user,
        project=project,
        name="Form público",
        schema=[
            {"name": "title", "label": "Título", "type": "text",
             "required": True},
        ],
        **kwargs,
    )


@pytest.mark.django_db
class TestPublicIntakeSubmit:
    def test_submit_publico_crea_tarea(self, api_client, user, project):
        form = _intake_form(user, project)
        assert form.public_token  # auto-generado en save()
        resp = api_client.post(
            f"/api/intake-forms/public/{form.public_token}/submit/",
            {"data": {"title": "Bug desde la web"}},
            format="json",
        )
        assert resp.status_code == 201
        task = Task.objects.get(id=resp.json()["id"])
        assert task.title == "Bug desde la web"
        assert task.owner == user
        assert task.project == project
        sub = IntakeSubmission.objects.get(task=task)
        assert sub.submitted_by == user  # atribuida al owner del form

    def test_submit_publico_sin_auth(self, api_client, user, project):
        """El endpoint público no requiere credenciales."""
        form = _intake_form(user, project)
        resp = api_client.post(
            f"/api/intake-forms/public/{form.public_token}/submit/",
            {"data": {"title": "Anónimo"}},
            format="json",
        )
        assert resp.status_code == 201

    def test_token_invalido_404(self, api_client):
        resp = api_client.post(
            "/api/intake-forms/public/token-inexistente/submit/",
            {"data": {"title": "x"}},
            format="json",
        )
        assert resp.status_code == 404

    def test_form_deshabilitado_404(self, api_client, user, project):
        form = _intake_form(user, project, enabled=False)
        resp = api_client.post(
            f"/api/intake-forms/public/{form.public_token}/submit/",
            {"data": {"title": "x"}},
            format="json",
        )
        assert resp.status_code == 404

    def test_validacion_schema_aplica(self, api_client, user, project):
        form = _intake_form(user, project)
        resp = api_client.post(
            f"/api/intake-forms/public/{form.public_token}/submit/",
            {"data": {}},
            format="json",
        )
        assert resp.status_code == 400
        assert "errors" in resp.json()

    def test_rotate_public_token(self, authed_client, user, project):
        form = _intake_form(user, project)
        old = form.public_token
        resp = authed_client.post(
            f"/api/intake-forms/{form.id}/rotate_public_token/"
        )
        assert resp.status_code == 200
        new = resp.json()["public_token"]
        assert new and new != old
        # El token viejo deja de resolver
        resp2 = APIClientPost(form, old)
        assert resp2 == 404

    def test_rotate_solo_owner(self, authed_client_other, user, project):
        form = _intake_form(user, project)
        resp = authed_client_other.post(
            f"/api/intake-forms/{form.id}/rotate_public_token/"
        )
        assert resp.status_code == 404

    def test_throttle_intake_public(
        self, api_client, user, project, monkeypatch
    ):
        form = _intake_form(user, project)
        # El rate del scope se resuelve por instancia desde THROTTLE_RATES;
        # bajar el límite para no tener que hacer 20 requests.
        from apps.users.api_auth import IntakePublicRateThrottle
        monkeypatch.setitem(
            IntakePublicRateThrottle.THROTTLE_RATES,
            "intake_public", "2/hour",
        )
        url = f"/api/intake-forms/public/{form.public_token}/submit/"
        payload = {"data": {"title": "x"}}
        assert api_client.post(url, payload, format="json").status_code == 201
        assert api_client.post(url, payload, format="json").status_code == 201
        # Tercera request: bucket agotado
        assert api_client.post(url, payload, format="json").status_code == 429


def APIClientPost(form, token):
    """Helper: POST anónimo al endpoint público devolviendo status."""
    from rest_framework.test import APIClient
    return APIClient().post(
        f"/api/intake-forms/public/{token}/submit/",
        {"data": {"title": "x"}},
        format="json",
    ).status_code


@pytest.mark.django_db
class TestShareLinks:
    def test_crear_y_consultar_publico(
        self, authed_client, api_client, user, project, task
    ):
        resp = authed_client.post(
            "/api/share-links/", {"project": project.id}, format="json"
        )
        assert resp.status_code == 201
        token = resp.json()["token"]

        # Tarea archivada no debe aparecer
        Task.objects.create(
            owner=user, project=project, title="vieja", state="archived"
        )
        pub = api_client.get(f"/api/public/share/{token}/")
        assert pub.status_code == 200
        data = pub.json()
        assert data["project"]["id"] == project.id
        assert data["project"]["name"] == project.name
        titles = [t["title"] for t in data["tasks"]]
        assert task.title in titles
        assert "vieja" not in titles
        # Solo lectura: los campos expuestos son los del contrato
        assert set(data["tasks"][0]) == {
            "id", "title", "state", "priority", "due_date",
            "assignee_email",
        }

    def test_publico_solo_lectura(self, authed_client, api_client, project):
        token = authed_client.post(
            "/api/share-links/", {"project": project.id}, format="json"
        ).json()["token"]
        resp = api_client.post(f"/api/public/share/{token}/", {})
        assert resp.status_code == 405

    def test_revocado_404(self, authed_client, api_client, project):
        lid = authed_client.post(
            "/api/share-links/", {"project": project.id}, format="json"
        ).json()["id"]
        link = ShareLink.objects.get(id=lid)
        assert authed_client.delete(f"/api/share-links/{lid}/").status_code == 204
        link.refresh_from_db()
        assert link.is_active is False
        assert api_client.get(
            f"/api/public/share/{link.token}/"
        ).status_code == 404

    def test_proyecto_ajeno_403(
        self, authed_client_other, user, project
    ):
        resp = authed_client_other.post(
            "/api/share-links/", {"project": project.id}, format="json"
        )
        assert resp.status_code == 403

    def test_list_solo_propios(
        self, authed_client, authed_client_other, user, project
    ):
        authed_client.post(
            "/api/share-links/", {"project": project.id}, format="json"
        )
        mine = authed_client.get("/api/share-links/").json()
        other = authed_client_other.get("/api/share-links/").json()
        assert len(mine) == 1
        assert other == []

    def test_token_invalido_404(self, api_client):
        assert api_client.get("/api/public/share/nope/").status_code == 404


@pytest.mark.django_db
class TestInboundWebhooks:
    def test_crud_y_post_crea_tarea(
        self, authed_client, api_client, user, project
    ):
        resp = authed_client.post(
            "/api/inbound-webhooks/",
            {"name": "Zapier", "project": project.id},
            format="json",
        )
        assert resp.status_code == 201
        token = resp.json()["token"]

        pub = api_client.post(
            f"/api/inbound/{token}/",
            {
                "title": "Desde Zapier",
                "description": "payload",
                "priority": 1,
                "due_date": "2030-01-15",
                "tags": ["zap", "auto"],
            },
            format="json",
        )
        assert pub.status_code == 201
        task = Task.objects.get(id=pub.json()["id"])
        assert task.owner == user
        assert task.project == project
        assert task.priority == 1
        assert task.due_date is not None
        assert task.tags.count() == 2
        wh = InboundWebhook.objects.get(token=token)
        assert wh.last_used_at is not None

    def test_proyecto_default_primer_proyecto(
        self, authed_client, api_client, user, project
    ):
        """Sin project, la tarea cae al primer proyecto del usuario."""
        token = authed_client.post(
            "/api/inbound-webhooks/", {"name": "Sin proyecto"},
            format="json",
        ).json()["token"]
        pub = api_client.post(
            f"/api/inbound/{token}/", {"title": "T"}, format="json"
        )
        assert pub.status_code == 201
        assert Task.objects.get(id=pub.json()["id"]).project == project

    def test_token_invalido_404(self, api_client):
        resp = api_client.post(
            "/api/inbound/token-mal/", {"title": "x"}, format="json"
        )
        assert resp.status_code == 404

    def test_inactive_404(self, authed_client, api_client, user):
        wh = InboundWebhook.objects.create(
            user=user, name="off", is_active=False
        )
        resp = api_client.post(
            f"/api/inbound/{wh.token}/", {"title": "x"}, format="json"
        )
        assert resp.status_code == 404

    def test_title_requerido(self, authed_client, api_client, user):
        wh = InboundWebhook.objects.create(user=user, name="w")
        resp = api_client.post(
            f"/api/inbound/{wh.token}/", {}, format="json"
        )
        assert resp.status_code == 400

    def test_priority_fuera_de_rango(
        self, authed_client, api_client, user
    ):
        wh = InboundWebhook.objects.create(user=user, name="w")
        resp = api_client.post(
            f"/api/inbound/{wh.token}/",
            {"title": "x", "priority": 9},
            format="json",
        )
        assert resp.status_code == 400

    def test_owner_scoped(
        self, authed_client, authed_client_other, user
    ):
        wh = InboundWebhook.objects.create(user=user, name="w")
        assert authed_client.get("/api/inbound-webhooks/").json()[0][
            "id"
        ] == wh.id
        assert authed_client_other.get(
            "/api/inbound-webhooks/"
        ).json() == []
        assert authed_client_other.delete(
            f"/api/inbound-webhooks/{wh.id}/"
        ).status_code == 404


@pytest.mark.django_db
class TestInboundEmail:
    def _token(self, authed_client, user):
        resp = authed_client.post("/api/users/me/email_token/")
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.inbound_email_token == resp.json()[
            "inbound_email_token"
        ]
        return user.inbound_email_token

    def test_generar_y_revocar_token(self, authed_client, user):
        token = self._token(authed_client, user)
        # Rotar genera uno nuevo
        resp = authed_client.post("/api/users/me/email_token/")
        assert resp.json()["inbound_email_token"] != token
        # Revocar
        assert authed_client.delete(
            "/api/users/me/email_token/"
        ).status_code == 204
        user.refresh_from_db()
        assert user.inbound_email_token is None

    def test_email_crea_tarea(
        self, authed_client, api_client, user, project
    ):
        token = self._token(authed_client, user)
        resp = api_client.post(
            "/api/inbound-email/",
            {
                "to": f"task-{token}@inbound.todolist.local",
                "from": user.email,
                "subject": "Tarea por email",
                "text": "Cuerpo del email",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.json()["created"] == "task"
        task = Task.objects.get(id=resp.json()["id"])
        assert task.title == "Tarea por email"
        assert task.description == "Cuerpo del email"
        assert task.owner == user
        assert task.project == project

    def test_token_sin_prefijo_task(
        self, authed_client, api_client, user
    ):
        token = self._token(authed_client, user)
        resp = api_client.post(
            "/api/inbound-email/",
            {
                "to": f"{token}@inbound.todolist.local",
                "from": user.email,
                "subject": "Otra",
                "text": "",
            },
            format="json",
        )
        assert resp.status_code == 201

    def test_email_crea_comentario(
        self, authed_client, api_client, user, task
    ):
        token = self._token(authed_client, user)
        resp = api_client.post(
            "/api/inbound-email/",
            {
                "to": f"task-{token}@inbound.todolist.local",
                "from": user.email,
                "subject": f"Re: [task-{task.id}] actualización",
                "text": (
                    "Respuesta real\n\nOn Mon, 1 Jan 2024 someone wrote:\n"
                    "> texto citado"
                ),
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.json()["created"] == "comment"
        comment = Comment.objects.get(id=resp.json()["id"])
        assert comment.task == task
        assert comment.author == user
        assert comment.body == "Respuesta real"

    def test_comentario_remitente_incorrecto_403(
        self, authed_client, api_client, user, task
    ):
        token = self._token(authed_client, user)
        resp = api_client.post(
            "/api/inbound-email/",
            {
                "to": f"task-{token}@inbound.todolist.local",
                "from": "suplantador@evil.com",
                "subject": f"Re: [task-{task.id}] x",
                "text": "intento",
            },
            format="json",
        )
        assert resp.status_code == 403
        assert not Comment.objects.filter(task=task).exists()

    def test_comentario_tarea_inexistente_404(
        self, authed_client, api_client, user
    ):
        token = self._token(authed_client, user)
        resp = api_client.post(
            "/api/inbound-email/",
            {
                "to": f"task-{token}@inbound.todolist.local",
                "from": user.email,
                "subject": "Re: [task-999999] x",
                "text": "x",
            },
            format="json",
        )
        assert resp.status_code == 404

    def test_destinatario_desconocido_404(self, api_client):
        resp = api_client.post(
            "/api/inbound-email/",
            {
                "to": "task-token-que-no-existe@inbound.todolist.local",
                "from": "a@b.com",
                "subject": "x",
                "text": "x",
            },
            format="json",
        )
        assert resp.status_code == 404

    def test_token_expuesto_en_perfil(self, authed_client, user):
        token = self._token(authed_client, user)
        resp = authed_client.get("/api/auth/me/")
        assert resp.json()["inbound_email_token"] == token


@pytest.mark.django_db
class TestProjectPrerequisites:
    def test_project_fixture(self, user, project):
        assert Project.objects.filter(owner=user).first() == project
