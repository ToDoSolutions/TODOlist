"""SCIM 2.0: provisión de usuarios y grupos (orgs) desde el IdP +
enforcement de SSO por dominio en el login por contraseña."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.collaboration.models import (
    Organization,
    OrganizationMembership,
)

pytestmark = pytest.mark.django_db
User = get_user_model()

TOKEN = "test-scim-token-0123456789abcdef"
SCIM_CT = "application/scim+json"


def _scim():
    c = Client()
    c.defaults["HTTP_AUTHORIZATION"] = f"Bearer {TOKEN}"
    return c


def _user(email="scim@t.dev", username="scim"):
    return User.objects.create_user(email=email, username=username, password="x" * 20)


class TestScimAuth:
    def test_users_sin_token_401(self):
        assert Client().get("/scim/v2/Users").status_code == 401

    def test_token_invalido_401(self):
        c = Client()
        r = c.get("/scim/v2/Users", HTTP_AUTHORIZATION="Bearer nope")
        assert r.status_code == 401

    def test_token_scim_no_sirve_para_api_normal(self):
        """El bearer SCIM no escala a credencial de la API REST."""
        r = _scim().get("/api/auth/me/")
        assert r.status_code in (401, 403)

    def test_service_provider_config(self):
        r = _scim().get("/scim/v2/ServiceProviderConfig")
        assert r.status_code == 200
        assert "authenticationSchemes" in json.loads(r.content)


class TestScimUsers:
    def test_crear_usuario_provisionado(self):
        r = _scim().post(
            "/scim/v2/Users",
            data=json.dumps({
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": "nuevo@acme.dev",
                "name": {"givenName": "Nuevo", "familyName": "User"},
                "emails": [{"value": "nuevo@acme.dev", "primary": True}],
                "active": True,
            }),
            content_type=SCIM_CT,
        )
        assert r.status_code == 201, r.content
        u = User.objects.get(email="nuevo@acme.dev")
        assert u.is_active
        # Cuenta provisionada sin password: solo entra por SSO
        assert not u.has_usable_password()
        assert u.scim_id == str(u.pk)
        body = json.loads(r.content)
        assert body["userName"] == "nuevo@acme.dev"

    def test_desprovisionar_desactiva_no_borra(self):
        u = _user()
        u.refresh_from_db()
        r = _scim().delete(f"/scim/v2/Users/{u.scim_id}")
        assert r.status_code == 204
        u.refresh_from_db()
        assert u.is_active is False

    def test_patch_active_false(self):
        u = _user()
        u.refresh_from_db()
        r = _scim().patch(
            f"/scim/v2/Users/{u.scim_id}",
            data=json.dumps({
                "schemas": [
                    "urn:ietf:params:scim:api:messages:2.0:PatchOp"
                ],
                "Operations": [
                    {"op": "replace", "value": {"active": False}}
                ],
            }),
            content_type=SCIM_CT,
        )
        assert r.status_code == 200, r.content
        u.refresh_from_db()
        assert u.is_active is False


class TestScimGroups:
    def test_group_put_sincroniza_membresias(self):
        org = Organization.objects.create(owner=_user("o@t.dev", "o"), name="Acme")
        org.refresh_from_db()
        m1, m2 = _user("m1@t.dev", "m1"), _user("m2@t.dev", "m2")
        r = _scim().put(
            f"/scim/v2/Groups/{org.scim_id}",
            data=json.dumps({
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": "Acme",
                "members": [
                    {"value": str(m1.id)},
                    {"value": str(m2.id)},
                ],
            }),
            content_type=SCIM_CT,
        )
        assert r.status_code == 200, r.content
        members = set(
            org.memberships.values_list("user_id", flat=True)
        )
        assert {m1.id, m2.id} <= members
        # La provisión nunca otorga admin
        assert not org.memberships.exclude(
            role=OrganizationMembership.Role.MEMBER
        ).exclude(user_id=org.owner_id).exists()

    def test_group_patch_remove_member(self):
        owner = _user("ow@t.dev", "ow")
        org = Organization.objects.create(owner=owner, name="O2")
        org.refresh_from_db()
        m = _user("mm@t.dev", "mm")
        OrganizationMembership.objects.create(
            organization=org, user=m,
            role=OrganizationMembership.Role.MEMBER,
        )
        r = _scim().patch(
            f"/scim/v2/Groups/{org.scim_id}",
            data=json.dumps({
                "schemas": [
                    "urn:ietf:params:scim:api:messages:2.0:PatchOp"
                ],
                "Operations": [
                    {
                        "op": "remove",
                        "path": "members",
                        "value": [{"value": str(m.id)}],
                    }
                ],
            }),
            content_type=SCIM_CT,
        )
        assert r.status_code == 200, r.content
        assert not org.memberships.filter(user=m).exists()


class TestSSODomainEnforcement:
    """sso_required bloquea el login por contraseña para el dominio
    reclamado, aunque las credenciales sean válidas."""

    def _org_sso(self, owner):
        org = Organization.objects.create(owner=owner, name="Corp")
        org.sso_domain = "corp.dev"
        org.sso_required = True
        org.save()
        return org

    def test_password_login_bloqueado(self):
        self._org_sso(_user("boss@corp.dev", "boss"))
        _user("emp@corp.dev", "emp")
        r = Client().post(
            "/api/auth/login/",
            data=json.dumps({"email": "emp@corp.dev", "password": "x" * 20}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "sso_required" in json.loads(r.content)

    def test_otro_dominio_no_afectado(self):
        self._org_sso(_user("boss2@corp.dev", "boss2"))
        _user("free@other.dev", "free")
        r = Client().post(
            "/api/auth/login/",
            data=json.dumps({"email": "free@other.dev", "password": "x" * 20}),
            content_type="application/json",
        )
        assert r.status_code == 200

    def test_sso_no_requerido_permite_password(self):
        owner = _user("o3@corp.dev", "o3")
        org = Organization.objects.create(owner=owner, name="C2")
        org.sso_domain = "corp2.dev"
        org.save()  # sso_required=False
        _user("u@corp2.dev", "u2")
        r = Client().post(
            "/api/auth/login/",
            data=json.dumps({"email": "u@corp2.dev", "password": "x" * 20}),
            content_type="application/json",
        )
        assert r.status_code == 200
