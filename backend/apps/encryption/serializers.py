from rest_framework import serializers
from .models import UserPublicKey, EncryptedTask, EncryptedKeyShare


class UserPublicKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPublicKey
        fields = ["id", "user", "public_key", "key_id", "algorithm", "is_active", "created_at"]
        read_only_fields = ["id", "user", "is_active", "created_at"]


class EncryptedTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = EncryptedTask
        fields = ["id", "owner", "encrypted_data", "encryption_key_id", "iv", "auth_tag", "algorithm", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]


class EncryptedKeyShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = EncryptedKeyShare
        fields = ["id", "encrypted_task", "user", "encrypted_key", "user_public_key", "created_at"]
        read_only_fields = ["id", "created_at"]
