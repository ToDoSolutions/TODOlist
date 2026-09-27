"""Tests de compartición de dashboards (shared_with)."""
import pytest

from apps.dashboards.models import Dashboard
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def dashboard(user):
    return Dashboard.objects.create(
        owner=user, name="Panel compartido",
        widgets=[{"id": "w1", "type": "kpis"}],
    )


class TestDashboardSharing:
    def test_share_por_email(self, authed_client, dashboard, other_user):
        r = authed_client.post(
            f"/api/dashboards/{dashboard.id}/share/", {"email": "other@test.com"}, format="json"
        )
        assert r.status_code == 200
        assert dashboard.shared_with.filter(id=other_user.id).exists()
        assert r.json()["shared_with"] == [{"id": other_user.id, "email": "other@test.com"}]

    def test_share_usuario_inexistente_404(self, authed_client, dashboard):
        r = authed_client.post(
            f"/api/dashboards/{dashboard.id}/share/", {"email": "nadie@test.com"}, format="json"
        )
        assert r.status_code == 404

    def test_share_sin_email_400(self, authed_client, dashboard):
        r = authed_client.post(f"/api/dashboards/{dashboard.id}/share/", {}, format="json")
        assert r.status_code == 400

    def test_share_a_uno_mismo_400(self, authed_client, dashboard, user):
        r = authed_client.post(
            f"/api/dashboards/{dashboard.id}/share/", {"email": user.email}, format="json"
        )
        assert r.status_code == 400

    def test_compartido_lista_y_data(self, authed_client, authed_client_other, dashboard, other_user):
        dashboard.shared_with.add(other_user)
        # Aparece en la lista del destinatario
        r = authed_client_other.get("/api/dashboards/")
        body = r.json()
        ids = [d["id"] for d in (body["results"] if isinstance(body, dict) else body)]
        assert dashboard.id in ids
        # Puede resolver los datos (con SU scope, no el del owner)
        Task.objects.create(owner=other_user, assignee=other_user, title="del otro")
        data = authed_client_other.get(f"/api/dashboards/{dashboard.id}/data/").json()
        assert data["dashboard"] == "Panel compartido"
        assert data["widgets"][0]["data"]["open"] >= 1
        # is_owner false para el destinatario
        detail = authed_client_other.get(f"/api/dashboards/{dashboard.id}/").json()
        assert detail["is_owner"] is False

    def test_compartido_no_puede_editar_ni_borrar(self, authed_client_other, dashboard, other_user):
        dashboard.shared_with.add(other_user)
        r = authed_client_other.patch(
            f"/api/dashboards/{dashboard.id}/", {"name": "hackeado"}, format="json"
        )
        assert r.status_code == 403
        r = authed_client_other.delete(f"/api/dashboards/{dashboard.id}/")
        assert r.status_code == 403
        assert Dashboard.objects.filter(id=dashboard.id).exists()

    def test_compartido_no_puede_reshare(self, authed_client_other, dashboard, other_user):
        dashboard.shared_with.add(other_user)
        r = authed_client_other.post(
            f"/api/dashboards/{dashboard.id}/share/", {"email": "x@x.com"}, format="json"
        )
        assert r.status_code == 403

    def test_unshare(self, authed_client, dashboard, other_user):
        dashboard.shared_with.add(other_user)
        r = authed_client.post(
            f"/api/dashboards/{dashboard.id}/unshare/", {"email": "other@test.com"}, format="json"
        )
        assert r.status_code == 200
        assert not dashboard.shared_with.filter(id=other_user.id).exists()

    def test_no_compartido_no_visible(self, authed_client_other, dashboard):
        r = authed_client_other.get(f"/api/dashboards/{dashboard.id}/")
        assert r.status_code == 404

    def test_owner_ve_is_owner_true(self, authed_client, dashboard):
        detail = authed_client.get(f"/api/dashboards/{dashboard.id}/").json()
        assert detail["is_owner"] is True
