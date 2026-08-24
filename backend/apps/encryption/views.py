from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import UserPublicKey, EncryptedTask, EncryptedKeyShare
from .serializers import (
    UserPublicKeySerializer,
    EncryptedTaskSerializer,
    EncryptedKeyShareSerializer,
)
from .services import (
    register_public_key,
    get_active_public_key,
    create_encrypted_task,
    add_key_share,
    list_shared_encrypted_tasks,
)


class UserPublicKeyViewSet(viewsets.ModelViewSet):
    serializer_class = UserPublicKeySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserPublicKey.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        register_public_key(
            user=self.request.user,
            public_key=serializer.validated_data["public_key"],
            key_id=serializer.validated_data["key_id"],
            algorithm=serializer.validated_data.get("algorithm", "RSA-OA-256"),
        )

    @action(detail=False, methods=["get"])
    def active(self, request):
        key = get_active_public_key(request.user)
        if not key:
            return Response({"error": "No active key"}, status=404)
        return Response(UserPublicKeySerializer(key).data)


class EncryptedTaskViewSet(viewsets.ModelViewSet):
    serializer_class = EncryptedTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EncryptedTask.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        """Comparte una tarea cifrada con otro usuario."""
        task = self.get_object()
        user_email = request.data.get("user_email")
        encrypted_key = request.data.get("encrypted_key")
        public_key_id = request.data.get("public_key_id")

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            target_user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        try:
            pk_obj = UserPublicKey.objects.get(id=public_key_id, user=target_user)
        except UserPublicKey.DoesNotExist:
            return Response({"error": "Public key not found"}, status=404)

        share = add_key_share(task, target_user, encrypted_key, pk_obj)
        return Response(EncryptedKeyShareSerializer(share).data, status=201)

    @action(detail=False, methods=["get"])
    def shared(self, request):
        """Tareas cifradas compartidas con el usuario."""
        return Response(list_shared_encrypted_tasks(request.user))
