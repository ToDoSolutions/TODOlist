from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    # El token de inbound email es una credencial: el perfil solo expone
    # si existe (rotate/revoke en /users/me/email_token/).
    has_inbound_email = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "avatar", "timezone", "locale",
            "email_verified", "email_verified_at", "has_inbound_email",
            "weekly_capacity_hours",
            "out_of_office", "out_of_office_until",
        ]
        read_only_fields = [
            "id", "email", "email_verified", "email_verified_at",
            "has_inbound_email",
        ]

    def get_has_inbound_email(self, obj):
        return bool(obj.inbound_email_token)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ["email", "username", "password", "password2"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password2": "Las contraseñas no coinciden."}
            )
        if User.objects.filter(email__iexact=attrs["email"]).exists():
            raise serializers.ValidationError(
                {"email": "Ya existe un usuario con este email."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
