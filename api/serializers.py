from django.contrib.auth import get_user_model
from rest_framework import serializers

Usuario = get_user_model()


class UsuarioSerializer(serializers.ModelSerializer):
    """Representacion del usuario autenticado para el frontend."""

    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "rol",
            "empresa",
            "empresa_nombre",
            "is_staff",
            "is_superuser",
        ]
        read_only_fields = fields
