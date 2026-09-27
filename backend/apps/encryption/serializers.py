from rest_framework import serializers

from .models import EncryptedKeyShare, EncryptedTask, UserPublicKey


class UserPublicKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPublicKey
        fields = ["id", "user", "public_key", "key_id", "algorithm", "is_active", "created_at", "rotated_at"]
        read_only_fields = ["id", "user", "is_active", "created_at", "rotated_at"]


class EncryptedTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = EncryptedTask
        fields = ["id", "owner", "task", "encrypted_data", "encryption_key_id", "iv", "auth_tag", "algorithm", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    ALLOWED_ALGORITHMS = {"AES-GCM", "AES-256-GCM", "XChaCha20-Poly1305"}

    def validate_task(self, value):
        """La tarea debe pertenecer al usuario que cifra."""
        request = self.context.get("request")
        if request and value.owner_id != request.user.id:
            raise serializers.ValidationError("La tarea no existe o no te pertenece.")
        return value

    def validate_algorithm(self, value):
        if value not in self.ALLOWED_ALGORITHMS:
            raise serializers.ValidationError(
                f"Algoritmo no soportado: {value}. Permitidos: {sorted(self.ALLOWED_ALGORITHMS)}"
            )
        return value

    def validate_auth_tag(self, value):
        # El ciphertext debe llevar tag de autenticación (AEAD)
        if not value:
            raise serializers.ValidationError("auth_tag requerido (cifrado autenticado).")
        return value

    def validate(self, data):
        # En creación, auth_tag e iv son obligatorios (AEAD autenticado)
        if self.instance is None:
            if not data.get("auth_tag"):
                raise serializers.ValidationError(
                    {"auth_tag": "auth_tag requerido (cifrado autenticado)."}
                )
            if not data.get("iv"):
                raise serializers.ValidationError({"iv": "iv requerido."})
        return data


class EncryptedKeyShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = EncryptedKeyShare
        fields = ["id", "encrypted_task", "user", "encrypted_key", "user_public_key", "created_at"]
        read_only_fields = ["id", "created_at"]
