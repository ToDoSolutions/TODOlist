import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.feature_flags.models import FeatureFlag

User = get_user_model()





@pytest.mark.django_db

class TestFeatureFlag:

    def test_str(self):

        flag = FeatureFlag.objects.create(key="flag1", name="Flag 1", is_enabled=True)

        assert "flag1" in str(flag)

        assert "on" in str(flag)

        flag.is_enabled = False

        assert "off" in str(flag)



    def test_defaults(self):

        flag = FeatureFlag.objects.create(key="flag1", name="Flag 1")

        assert flag.is_enabled is False

        assert flag.description == ""

        assert flag.enabled_percentage == 0



    def test_unique_key(self):

        FeatureFlag.objects.create(key="flag1", name="Flag 1")

        with pytest.raises(IntegrityError):

            FeatureFlag.objects.create(key="flag1", name="Flag 2")



    def test_ordering(self):

        f1 = FeatureFlag.objects.create(key="flag1", name="Flag 1")

        f2 = FeatureFlag.objects.create(key="flag2", name="Flag 2")

        # auto_now_add puede asignar el mismo timestamp en SQLite: fijar explícito

        from django.utils import timezone as tz

        FeatureFlag.objects.filter(pk=f1.pk).update(created_at=tz.now() - tz.timedelta(hours=2))

        FeatureFlag.objects.filter(pk=f2.pk).update(created_at=tz.now() - tz.timedelta(hours=1))

        flags = list(FeatureFlag.objects.all())

        assert flags[0] == f2  # ordering by -created_at


@pytest.mark.django_db
class TestFlagGating:
    """Los flags no eran mas que un CRUD: nada los consumia. El
    middleware los aplica de verdad por prefijo de URL."""

    def test_kill_switch_apaga_endpoint(self, client):
        FeatureFlag.objects.create(
            key="ai_assistant", name="AI", is_enabled=False
        )
        r = client.get("/api/ai/suggestions/")
        assert r.status_code == 404

    def test_flag_inexistente_cae_al_default_env(self, client):
        # Sin fila en BD, el default FEATURE_FLAGS (True) deja pasar —
        # el 401 es de auth, no de flag.
        r = client.get("/api/ai/suggestions/")
        assert r.status_code == 401

    def test_rollout_por_usuario(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            email="beta@t.dev", username="beta", password="x" * 20
        )
        other = django_user_model.objects.create_user(
            email="ga@t.dev", username="ga", password="x" * 20
        )
        flag = FeatureFlag.objects.create(
            key="ai_assistant", name="AI", is_enabled=False
        )
        flag.enabled_users.add(u)
        from rest_framework_simplejwt.tokens import RefreshToken
        token_beta = str(RefreshToken.for_user(u).access_token)
        token_ga = str(RefreshToken.for_user(other).access_token)
        # el beta pasa al 401/200 de auth (flag ON para el);
        # el resto recibe 404 aunque traiga token valido
        r = client.get(
            "/api/ai/suggestions/",
            HTTP_AUTHORIZATION=f"Bearer {token_beta}",
        )
        assert r.status_code != 404
        r2 = client.get(
            "/api/ai/suggestions/",
            HTTP_AUTHORIZATION=f"Bearer {token_ga}",
        )
        assert r2.status_code == 404
