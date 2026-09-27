"""Tests exhaustivos para modelos de encryption."""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.encryption.models import EncryptedKeyShare, EncryptedTask, UserPublicKey
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="em", email="em@em.com", password="pass")


@pytest.mark.django_db
class TestUserPublicKey:
    def test_str(self, user):
        pk = UserPublicKey.objects.create(user=user, key_id="key1", public_key="abc123")
        assert "key1" in str(pk)
        assert user.username in str(pk) or str(user.id) in str(pk)

    def test_defaults(self, user):
        pk = UserPublicKey.objects.create(user=user, key_id="key1", public_key="abc123")
        assert pk.created_at is not None

    def test_unique_together(self, user):
        UserPublicKey.objects.create(user=user, key_id="key1", public_key="abc123")
        with pytest.raises(IntegrityError):
            UserPublicKey.objects.create(user=user, key_id="key1", public_key="def456")


@pytest.mark.django_db
class TestEncryptedTask:
    def test_str(self, user):
        task = Task.objects.create(owner=user, title="Secret Task")
        et = EncryptedTask.objects.create(task=task, owner=user, encrypted_data="enc", encryption_key_id="k1", iv="iv")
        assert "EncryptedTask" in str(et)
        assert user.email in str(et)

    def test_task_relation(self, user):
        task = Task.objects.create(owner=user, title="Secret Task")
        et = EncryptedTask.objects.create(task=task, owner=user, encrypted_data="enc", encryption_key_id="k1", iv="iv")
        assert et.task == task
        assert task.encrypted_data == et

    def test_defaults(self, user):
        task = Task.objects.create(owner=user, title="Secret Task")
        et = EncryptedTask.objects.create(task=task, owner=user, encrypted_data="enc", encryption_key_id="k1", iv="iv")
        assert et.auth_tag == ""
        assert et.algorithm == "AES-256-GCM"


@pytest.mark.django_db
class TestEncryptedKeyShare:
    def test_str(self, user):
        task = Task.objects.create(owner=user, title="Secret Task")
        pk = UserPublicKey.objects.create(user=user, key_id="k1", public_key="pk")
        et = EncryptedTask.objects.create(task=task, owner=user, encrypted_data="enc", encryption_key_id="k1", iv="iv")
        eks = EncryptedKeyShare.objects.create(encrypted_task=et, user=user, encrypted_key="enc_key", user_public_key=pk)
        assert "KeyShare" in str(eks)
        assert user.email in str(eks)

    def test_defaults(self, user):
        task = Task.objects.create(owner=user, title="Secret Task")
        pk = UserPublicKey.objects.create(user=user, key_id="k1", public_key="pk")
        et = EncryptedTask.objects.create(task=task, owner=user, encrypted_data="enc", encryption_key_id="k1", iv="iv")
        eks = EncryptedKeyShare.objects.create(encrypted_task=et, user=user, encrypted_key="enc_key", user_public_key=pk)
        assert eks.created_at is not None

    def test_unique_together(self, user):
        task = Task.objects.create(owner=user, title="Secret Task")
        pk = UserPublicKey.objects.create(user=user, key_id="k1", public_key="pk")
        et = EncryptedTask.objects.create(task=task, owner=user, encrypted_data="enc", encryption_key_id="k1", iv="iv")
        EncryptedKeyShare.objects.create(encrypted_task=et, user=user, encrypted_key="enc_key", user_public_key=pk)
        with pytest.raises(IntegrityError):
            EncryptedKeyShare.objects.create(encrypted_task=et, user=user, encrypted_key="enc_key2", user_public_key=pk)
