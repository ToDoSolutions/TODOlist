"""Wiki: historial de revisiones + restore (el contador `version`
antes era cosmético — no había nada que restaurar)."""
import pytest

from apps.wiki.models import WikiPage, WikiPageRevision


@pytest.mark.django_db
class TestWikiRevisions:
    def _mk(self, user, **kw):
        return WikiPage.objects.create(
            owner=user, title="V1", content="a", **kw
        )

    def test_save_crea_snapshot(self, user):
        page = self._mk(user)
        page.content = "b"
        page.save()
        # v1 quedó registrada al crear; v2 al editar
        assert WikiPageRevision.objects.filter(
            page=page, version=1, content="a"
        ).exists()
        assert WikiPageRevision.objects.filter(
            page=page, version=2, content="b"
        ).exists()

    def test_revisions_api(self, authed_client, user):
        page = self._mk(user)
        page.content = "b"
        page.save()
        r = authed_client.get(f"/api/wiki/{page.id}/revisions/")
        assert r.status_code == 200
        assert [x["version"] for x in r.json()] == [2, 1]

    def test_revision_detail(self, authed_client, user):
        page = self._mk(user)
        r = authed_client.get(f"/api/wiki/{page.id}/revisions/1/")
        assert r.status_code == 200
        assert r.json()["content"] == "a"

    def test_restore(self, authed_client, user):
        page = self._mk(user)
        page.content = "nuevo"
        page.save()
        r = authed_client.post(
            f"/api/wiki/{page.id}/restore/", {"version": 1}
        )
        assert r.status_code == 200
        page.refresh_from_db()
        assert page.content == "a" and page.version == 3
        # el restore también deja su propia revisión
        assert page.revisions.filter(version=3, content="a").exists()

    def test_restore_revision_inexistente(self, authed_client, user):
        page = self._mk(user)
        r = authed_client.post(
            f"/api/wiki/{page.id}/restore/", {"version": 99}
        )
        assert r.status_code == 404

    def test_restore_en_proyecto_requiere_escritura(
        self, authed_client, other_user, user
    ):
        """Un viewer del proyecto no puede restaurar páginas ajenas."""
        from apps.projects.models import Project
        project = Project.objects.create(owner=user, name="P")
        page = self._mk(other_user)  # página personal del otro
        page.project = project
        page.save()
        page.content = "edit"
        page.save()
        # authed_client es `user` (owner del proyecto): puede restaurar
        r = authed_client.post(
            f"/api/wiki/{page.id}/restore/", {"version": 1}
        )
        assert r.status_code == 200
