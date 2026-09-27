import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.encryption.models import EncryptedKeyShare, EncryptedTask, UserPublicKey
from apps.tasks.models import Task

User = get_user_model()


@pytest.mark.django_db
class TestEncryptionModels:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="em", email="em@em.com", password="pass")
        self.task = Task.objects.create(owner=self.user, title="T")

    def test_user_public_key_str(self):
        pk = UserPublicKey.objects.create(user=self.user, public_key="pub", key_id="k1")
        assert "em@em.com" in str(pk)
        assert "k1" in str(pk)

    def test_user_public_key_defaults(self):
        pk = UserPublicKey.objects.create(user=self.user, public_key="pub", key_id="k1")
        assert pk.algorithm == "RSA-OA-256"
        assert pk.is_active is True
        assert pk.rotated_at is None

    def test_user_public_key_unique(self):
        UserPublicKey.objects.create(user=self.user, public_key="pub", key_id="k1")
        with pytest.raises(IntegrityError):
            UserPublicKey.objects.create(user=self.user, public_key="pub2", key_id="k1")

    def test_encrypted_task_str(self):
        et = EncryptedTask.objects.create(owner=self.user, task=self.task, encrypted_data="data", encryption_key_id="k1", iv="iv")
        assert "EncryptedTask" in str(et)
        assert "em@em.com" in str(et)

    def test_encrypted_task_defaults(self):
        et = EncryptedTask.objects.create(owner=self.user, task=self.task, encrypted_data="data", encryption_key_id="k1", iv="iv")
        assert et.algorithm == "AES-256-GCM"
        assert et.auth_tag == ""

    def test_encrypted_key_share_str(self):
        pk = UserPublicKey.objects.create(user=self.user, public_key="pub", key_id="k1")
        et = EncryptedTask.objects.create(owner=self.user, task=self.task, encrypted_data="data", encryption_key_id="k1", iv="iv")
        ks = EncryptedKeyShare.objects.create(encrypted_task=et, user=self.user, encrypted_key="key", user_public_key=pk)
        assert "KeyShare" in str(ks)
        assert "em@em.com" in str(ks)

    def test_encrypted_key_share_unique(self):
        pk = UserPublicKey.objects.create(user=self.user, public_key="pub", key_id="k1")
        et = EncryptedTask.objects.create(owner=self.user, task=self.task, encrypted_data="data", encryption_key_id="k1", iv="iv")
        EncryptedKeyShare.objects.create(encrypted_task=et, user=self.user, encrypted_key="key", user_public_key=pk)
        with pytest.raises(IntegrityError):
            EncryptedKeyShare.objects.create(encrypted_task=et, user=self.user, encrypted_key="key2", user_public_key=pk)
