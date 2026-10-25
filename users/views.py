from django.db.models import Count
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from core.catalog import asegurar_catalogo

from .auth import empresa_inactiva, error_empresa_inactiva
from .models import Empresa, Usuario
from .serializers import (
    CambioClaveSerializer,
    EmpresaSerializer,
    UsuarioGestionSerializer,
)


class TokenEmpresaActivaSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if empresa_inactiva(self.user):
            raise error_empresa_inactiva()
        return data


class TokenEmpresaActivaView(TokenObtainPairView):
    """Login: ademas de usuario activo, exige que su empresa este activa."""

    serializer_class = TokenEmpresaActivaSerializer


class EsJefeOAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or u.es_jefe))


class EsAdminSistema(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_superuser)


class _ActivableMixin:
    """Acciones activar/desactivar sobre el campo booleano `campo_activo`.
    No hay borrado: se desactiva para conservar el historial."""

    campo_activo = "is_active"

    def _cambiar_activo(self, valor):
        obj = self.get_object()
        self.validar_cambio_activo(obj, valor)
        setattr(obj, self.campo_activo, valor)
        obj.save(update_fields=[self.campo_activo])
        return Response(self.get_serializer(obj).data)

    def validar_cambio_activo(self, obj, valor):
        pass

    @action(detail=True, methods=["post"])
    def activar(self, request, pk=None):
        return self._cambiar_activo(True)

    @action(detail=True, methods=["post"])
    def desactivar(self, request, pk=None):
        return self._cambiar_activo(False)


class UsuarioViewSet(_ActivableMixin, viewsets.ModelViewSet):
    """Usuarios gestionables por quien consulta:
      - Administrador: todos los usuarios de empresas (no otros administradores).
      - Jefe: los operarios de su empresa.
    Filtros: ?empresa=<id>, ?rol=JEFE|OPERARIO, ?activo=true|false, ?search=."""

    serializer_class = UsuarioGestionSerializer
    permission_classes = [EsJefeOAdmin]
    http_method_names = ["get", "post", "patch", "head", "options"]
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "first_name", "last_name", "email"]

    def get_queryset(self):
        user = self.request.user
        qs = Usuario.objects.filter(is_superuser=False).select_related("empresa")
        if not user.is_superuser:
            qs = qs.filter(empresa=user.empresa, rol=Usuario.Rol.OPERARIO)

        params = self.request.query_params
        if params.get("empresa"):
            qs = qs.filter(empresa_id=params["empresa"])
        if params.get("rol"):
            qs = qs.filter(rol=params["rol"])
        if params.get("activo") in ("true", "false"):
            qs = qs.filter(is_active=params["activo"] == "true")
        return qs.order_by("empresa__nombre", "rol", "username")

    def validar_cambio_activo(self, obj, valor):
        if obj.pk == self.request.user.pk:
            raise ValidationError("No puedes desactivar tu propia cuenta.")

    @action(detail=True, methods=["post"])
    def clave(self, request, pk=None):
        """Asigna una nueva contraseña al usuario (la define el jefe/admin)."""
        usuario = self.get_object()
        s = CambioClaveSerializer(data=request.data, context={"usuario": usuario})
        s.is_valid(raise_exception=True)
        usuario.set_password(s.validated_data["password"])
        usuario.save(update_fields=["password"])
        return Response({"detail": "Contraseña actualizada."})


class EmpresaViewSet(_ActivableMixin, viewsets.ModelViewSet):
    """Empresas (solo administrador del sistema). Al crear una se le genera
    el catalogo fijo (series, perfiles e insumos) para que el jefe complete
    precios. Desactivarla impide iniciar sesion a sus usuarios."""

    serializer_class = EmpresaSerializer
    permission_classes = [EsAdminSistema]
    http_method_names = ["get", "post", "patch", "head", "options"]
    campo_activo = "activa"
    filter_backends = [filters.SearchFilter]
    search_fields = ["nombre", "rut"]

    def get_queryset(self):
        return Empresa.objects.annotate(n_usuarios=Count("usuarios"))

    def perform_create(self, serializer):
        empresa = serializer.save()
        asegurar_catalogo(empresa)
