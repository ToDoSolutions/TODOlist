from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import EncryptedKeyShare, EncryptedTask, UserPublicKey
from .serializers import (
    EncryptedKeyShareSerializer,
    EncryptedTaskSerializer,
    UserPublicKeySerializer,
)
from .services import (
    add_key_share,
    get_active_public_key,
    list_shared_encrypted_tasks,
    register_public_key,
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

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        """GET /public-keys/lookup/?email=... — clave pública activa de otro
        usuario. Necesaria para cifrarle un key share; las claves públicas
        son públicas por definición (el modelo de amenaza ya asume que un
        servidor malicioso podría sustituirlas).
        """
        email = (request.query_params.get("email") or "").strip()
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            target = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            target = None
        # Respuesta uniforme: mismo 404 para "no existe" y "sin clave"
        # — distinguirlos permitiría enumerar emails registrados.
        key = get_active_public_key(target) if target else None
        if not key:
            return Response(
                {"error": "El usuario no tiene una clave activa"}, status=404
            )
        return Response(UserPublicKeySerializer(key).data)

    @action(detail=True, methods=["post"])
    def rotate(self, request, pk=None):
        """Rota la clave pública actual: marca rotated_at, crea una nueva clave
        y marca los EncryptedKeyShare que necesitan re-encriptación.

        Los shares se mantienen (marcados como pendientes) hasta que el
        cliente los re-encripte — nunca se borran de forma destructiva.
        """
        old_key = self.get_object()
        new_public_key = request.data.get("public_key")
        new_key_id = request.data.get("key_id")
        new_algorithm = request.data.get("algorithm", old_key.algorithm)

        if not new_public_key or not new_key_id:
            return Response(
                {"error": "public_key and key_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.db import transaction
        with transaction.atomic():
            # Marcar la clave antigua como rotada. register_public_key la
            # desactiva para NUEVOS shares/lookups (is_active=False), pero el
            # registro permanece y los EncryptedKeyShare que la referencian
            # siguen resolviéndose — el descifrado de datos existentes no se
            # ve afectado (la privada solo vive en el dispositivo).
            old_key.rotated_at = timezone.now()
            old_key.save(update_fields=["rotated_at"])

            # Crear la nueva clave activa
            new_key = register_public_key(
                user=request.user,
                public_key=new_public_key,
                key_id=new_key_id,
                algorithm=new_algorithm,
            )

        # Contar shares que necesitan re-encriptación (NO se borran: el
        # servidor no tiene la clave privada; borrarlos destruiría acceso)
        shares = EncryptedKeyShare.objects.filter(user_public_key=old_key)

        return Response(
            {
                "old_key": UserPublicKeySerializer(old_key).data,
                "new_key": UserPublicKeySerializer(new_key).data,
                "pending_reencryption_count": shares.count(),
            },
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        """Elimina una clave pública solo si no hay key shares dependientes
        o si el cliente confirma con force=true."""
        instance = self.get_object()
        force = request.query_params.get("force", "false").lower() == "true"

        dependent_shares = EncryptedKeyShare.objects.filter(
            user_public_key=instance
        ).count()

        if dependent_shares > 0 and not force:
            return Response(
                {
                    "error": "Cannot delete key with dependent encrypted key shares",
                    "dependent_shares": dependent_shares,
                    "hint": "Add ?force=true to confirm deletion",
                },
                status=status.HTTP_409_CONFLICT,
            )

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


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

        if not user_email or not encrypted_key or not public_key_id:
            return Response(
                {"error": "user_email, encrypted_key y public_key_id requeridos"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            # iexact: paridad con /public-keys/lookup — un email en
            # distinto case no debe impedir el share.
            target_user = User.objects.get(email__iexact=user_email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        # La clave debe existir, pertenecer al destinatario y estar activa
        try:
            pk_obj = UserPublicKey.objects.get(
                id=public_key_id, user=target_user, is_active=True
            )
        except UserPublicKey.DoesNotExist:
            return Response({"error": "Public key not found or inactive"}, status=404)

        # Duplicado → error controlado (no sobreescribir shares)
        if EncryptedKeyShare.objects.filter(
            encrypted_task=task, user=target_user
        ).exists():
            return Response(
                {"error": "Ya existe un share para este usuario"},
                status=status.HTTP_409_CONFLICT,
            )

        share = add_key_share(task, target_user, encrypted_key, pk_obj)
        return Response(EncryptedKeyShareSerializer(share).data, status=201)

    @action(detail=False, methods=["get"])
    def shared(self, request):
        """Tareas cifradas compartidas con el usuario."""
        return Response(list_shared_encrypted_tasks(request.user))
