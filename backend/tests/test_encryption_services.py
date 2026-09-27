import pytest
from django.contrib.auth import get_user_model

from apps.encryption.models import UserPublicKey
from apps.encryption.services import (
    add_key_share,
    create_encrypted_task,
    get_active_public_key,
    list_shared_encrypted_tasks,
    register_public_key,
)

User = get_user_model()


@pytest.mark.django_db
class TestEncryptionServices:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="e1", email="e1@e.com", password="pass")
        self.other = User.objects.create_user(username="e2", email="e2@e.com", password="pass")

    def test_register_public_key(self):
        key = register_public_key(self.user, "pubkey1", "kid1")
        assert key.public_key == "pubkey1"
        assert key.key_id == "kid1"
        assert key.is_active is True
        assert UserPublicKey.objects.filter(user=self.user, is_active=True).count() == 1

    def test_register_public_key_deactivates_old(self):
        register_public_key(self.user, "pubkey1", "kid1")
        key2 = register_public_key(self.user, "pubkey2", "kid2")
        assert UserPublicKey.objects.filter(user=self.user, is_active=True).count() == 1
        assert key2.is_active is True

    def test_get_active_public_key(self):
        register_public_key(self.user, "pubkey1", "kid1")
        key = get_active_public_key(self.user)
        assert key.public_key == "pubkey1"
        assert get_active_public_key(self.other) is None

    def test_create_encrypted_task(self):
        task = create_encrypted_task(self.user, "encrypted", "kid1", "iv123", "tag", "AES-256-GCM")
        assert task.encrypted_data == "encrypted"
        assert task.encryption_key_id == "kid1"
        assert task.iv == "iv123"
        assert task.auth_tag == "tag"
        assert task.algorithm == "AES-256-GCM"

    def test_add_key_share(self):
        task = create_encrypted_task(self.user, "encrypted", "kid1", "iv123")
        pubkey = register_public_key(self.other, "pubkey", "kid2")
        share = add_key_share(task, self.other, "enckey", pubkey)
        assert share.encrypted_task == task
        assert share.user == self.other
        assert share.encrypted_key == "enckey"
        assert share.user_public_key == pubkey

    def test_list_shared_encrypted_tasks(self):
        task = create_encrypted_task(self.user, "encrypted", "kid1", "iv123", "tag")
        pubkey = register_public_key(self.other, "pubkey", "kid2")
        add_key_share(task, self.other, "enckey", pubkey)
        shares = list_shared_encrypted_tasks(self.other)
        assert len(shares) == 1
        assert shares[0]["id"] == task.id
        assert shares[0]["encrypted_data"] == "encrypted"
        assert shares[0]["encrypted_key"] == "enckey"
        assert shares[0]["shared_by"] == self.user.email
        assert list_shared_encrypted_tasks(self.user) == []


@pytest.mark.django_db
class TestPublicKeyLookup:
    """GET /api/public-keys/lookup/?email=... — pública activa de otro usuario."""

    def test_lookup_returns_active_key(self, authed_client, user, other_user):
        key = register_public_key(other_user, "PUBKEY_B64", "kid-x")
        resp = authed_client.get("/api/public-keys/lookup/", {"email": other_user.email})
        assert resp.status_code == 200
        assert resp.data["id"] == key.id
        assert resp.data["public_key"] == "PUBKEY_B64"
        assert resp.data["key_id"] == "kid-x"

    def test_lookup_case_insensitive(self, authed_client, user, other_user):
        register_public_key(other_user, "PUB", "k1")
        resp = authed_client.get(
            "/api/public-keys/lookup/", {"email": other_user.email.upper()}
        )
        assert resp.status_code == 200

    def test_lookup_unknown_user_404(self, authed_client, user):
        resp = authed_client.get(
            "/api/public-keys/lookup/", {"email": "nadie@x.com"}
        )
        assert resp.status_code == 404

    def test_lookup_user_without_key_404(self, authed_client, user, other_user):
        resp = authed_client.get(
            "/api/public-keys/lookup/", {"email": other_user.email}
        )
        assert resp.status_code == 404

    def test_lookup_missing_email_404(self, authed_client, user):
        resp = authed_client.get("/api/public-keys/lookup/")
        assert resp.status_code == 404

    def test_lookup_requires_auth(self, api_client, other_user):
        resp = api_client.get(
            "/api/public-keys/lookup/", {"email": other_user.email}
        )
        assert resp.status_code in (401, 403)
