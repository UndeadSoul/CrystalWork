from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers

Usuario = get_user_model()


class UsuarioSerializer(serializers.ModelSerializer):
    """Representacion del usuario autenticado para el frontend."""

    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
    # Zona del servidor (fechas de negocio): el frontend la compara con la del
    # navegador para indicar el desfase cuando muestra horas locales.
    zona_horaria_servidor = serializers.SerializerMethodField()

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
            "zona_horaria_servidor",
        ]
        read_only_fields = fields

    def get_zona_horaria_servidor(self, obj):
        return settings.TIME_ZONE
