from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .serializers import UsuarioSerializer


class CurrentUserView(generics.RetrieveAPIView):
    """Devuelve los datos del usuario autenticado (rol, empresa, etc.)."""

    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
