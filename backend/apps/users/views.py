from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class RegisterView(CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        out = UserSerializer(user, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED)


class MeView(RetrieveUpdateAPIView):
    """Devuelve y permite actualizar el perfil del usuario autenticado."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Permite al usuario cambiar su contraseña proporcionando la actual."""
    current = request.data.get("current_password", "")
    new = request.data.get("new_password", "")

    if not current or not new:
        return Response(
            {"error": "Debes proporcionar current_password y new_password."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = request.user
    if not user.check_password(current):
        return Response(
            {"error": "La contraseña actual no es correcta."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(new) < 8:
        return Response(
            {"error": "La nueva contraseña debe tener al menos 8 caracteres."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(new)
    user.save()
    return Response({"message": "Contraseña actualizada correctamente."})
