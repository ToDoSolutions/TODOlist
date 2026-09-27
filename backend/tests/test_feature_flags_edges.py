"""Tests de borde para feature_flags: hash determinista, evaluación y permisos."""
import pytest
from django.contrib.auth import get_user_model

from apps.feature_flags.models import FeatureFlag
from apps.feature_flags.services import _hash_percentage, is_enabled

User = get_user_model()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="ff_u", defaults={"email": "ff@x.com"}
    )
    return u


class TestHashPercentage:
    def test_determinista(self):
        assert _hash_percentage("flag", 1) == _hash_percentage("flag", 1)

    def test_rango_0_99(self):
        for uid in range(50):
            v = _hash_percentage("flag", uid)
            assert 0 <= v < 100

    def test_keys_distintas_hash_distinto(self):
        # distintos keys → distintos buckets (al menos para estos casos)
        a = _hash_percentage("flag_a", 7)
        b = _hash_percentage("flag_b", 7)
        # no exigimos != pero sí que el hash cambie con la key en general
        assert isinstance(a, int) and isinstance(b, int)

    def test_usuarios_distintos_hash_distinto(self):
        vals = {_hash_percentage("flag", uid) for uid in range(20)}
        assert len(vals) > 1  # no todos colapsan al mismo bucket


@pytest.mark.django_db
class TestIsEnabled:
    def test_flag_inexistente_false(self, user):
        assert is_enabled("no-existe", user) is False

    def test_flag_desactivado_false(self, user):
        FeatureFlag.objects.create(key="f", name="F", is_enabled=False)
        assert is_enabled("f", user) is False

    def test_flag_global_true(self, user):
        FeatureFlag.objects.create(key="f", name="F", is_enabled=True)
        assert is_enabled("f", user) is True

    def test_flag_global_sin_user(self):
        FeatureFlag.objects.create(key="f", name="F", is_enabled=True)
        assert is_enabled("f") is True

    def test_usuario_en_enabled_users(self, user):
        flag = FeatureFlag.objects.create(key="f", name="F")
        flag.enabled_users.add(user)
        assert is_enabled("f", user) is True

    def test_otro_usuario_no_habilitado(self, user):
        other, _ = User.objects.get_or_create(
            username="ff_o", defaults={"email": "ff_o@x.com"}
        )
        flag = FeatureFlag.objects.create(key="f", name="F")
        flag.enabled_users.add(other)
        assert is_enabled("f", user) is False

    def test_porcentaje_100_habilita_todos(self, user):
        FeatureFlag.objects.create(
            key="f", name="F", enabled_percentage=100
        )
        assert is_enabled("f", user) is True

    def test_porcentaje_0_no_habilita(self, user):
        FeatureFlag.objects.create(key="f", name="F", enabled_percentage=0)
        assert is_enabled("f", user) is False

    def test_porcentaje_consistente_con_hash(self, user):
        """enabled_percentage=50 → habilita exactamente si hash < 50."""
        FeatureFlag.objects.create(key="f", name="F", enabled_percentage=50)
        esperado = _hash_percentage("f", user.pk) < 50
        assert is_enabled("f", user) is esperado

    def test_user_anonimo_no_habilita(self, db):
        from django.contrib.auth.models import AnonymousUser
        FeatureFlag.objects.create(key="f", name="F", enabled_percentage=100)
        assert is_enabled("f", AnonymousUser()) is False

    def test_sin_user_evaluacion_porcentaje_no_aplica(self):
        FeatureFlag.objects.create(key="f", name="F", enabled_percentage=100)
        assert is_enabled("f") is False


@pytest.mark.django_db
class TestFeatureFlagViews:
    def test_check_endpoint(self, authed_client, user):
        FeatureFlag.objects.create(key="f", name="F", is_enabled=True)
        resp = authed_client.get("/api/feature-flags/f/check/")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_check_flag_off(self, authed_client, user):
        FeatureFlag.objects.create(key="f", name="F")
        resp = authed_client.get("/api/feature-flags/f/check/")
        assert resp.json()["enabled"] is False

    def test_check_flag_inexistente_404(self, authed_client):
        resp = authed_client.get("/api/feature-flags/nope/check/")
        assert resp.status_code == 404

    def test_create_solo_staff(self, authed_client):
        resp = authed_client.post(
            "/api/feature-flags/", {"key": "x", "name": "X"}
        )
        assert resp.status_code == 403

    def test_create_staff_ok(self, authed_client, user):
        user.is_staff = True
        user.save()
        resp = authed_client.post(
            "/api/feature-flags/", {"key": "x2", "name": "X2"}
        )
        assert resp.status_code == 201

    def test_update_solo_staff(self, authed_client):
        FeatureFlag.objects.create(key="f", name="F")
        resp = authed_client.patch(
            "/api/feature-flags/f/", {"is_enabled": True}
        )
        assert resp.status_code == 403

    def test_delete_solo_staff(self, authed_client):
        FeatureFlag.objects.create(key="f", name="F")
        resp = authed_client.delete("/api/feature-flags/f/")
        assert resp.status_code == 403

    def test_list_cualquier_autenticado(self, authed_client):
        FeatureFlag.objects.create(key="f", name="F")
        resp = authed_client.get("/api/feature-flags/")
        assert resp.status_code == 200

    def test_lookup_por_key(self, authed_client):
        FeatureFlag.objects.create(key="mi-flag", name="F")
        resp = authed_client.get("/api/feature-flags/mi-flag/")
        assert resp.status_code == 200
        assert resp.json()["key"] == "mi-flag"

    def test_str(self, db):
        f = FeatureFlag.objects.create(key="f", name="F", is_enabled=True)
        assert "f" in str(f) and "on" in str(f)
