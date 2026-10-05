from django.utils import timezone
from rest_framework import filters, generics, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .catalog import asegurar_catalogo
from .models import (
    Cliente,
    Cotizacion,
    Insumo,
    PerfilIndividual,
    PerfilSerie,
    PlanchaVidrio,
    PrecioPerfilIndividual,
    PrecioSerie,
    SerieAluminio,
    TipoVentana,
    TipoVidrio,
    VentanaCotizada,
)
from .pricing import SERIE_POR_TIPO, recalcular_cotizacion
from .serializers import (
    ClienteSerializer,
    CotizacionListSerializer,
    CotizacionSerializer,
    EmpresaConfigSerializer,
    InsumoSerializer,
    PerfilIndividualSerializer,
    PerfilSerieSerializer,
    PlanchaVidrioSerializer,
    PrecioPerfilIndividualSerializer,
    PrecioSerieSerializer,
    SerieAluminioSerializer,
)


class IsJefeOrAdmin(BasePermission):
    """Solo el jefe o el administrador del sistema."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and (user.is_superuser or user.es_jefe)
        )


class EmpresaScopedViewSet(viewsets.ModelViewSet):
    """Base: aisla por empresa (el superuser ve todo)."""

    permission_classes = [IsAuthenticated]

    def filtrar_por_empresa(self, qs):
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(empresa=user.empresa)

    def _empresa_requerida(self):
        user = self.request.user
        if user.empresa_id is None:
            raise ValidationError("El usuario no tiene una empresa asignada.")
        return user.empresa


class ClienteViewSet(EmpresaScopedViewSet):
    serializer_class = ClienteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nombre", "rut", "email", "telefono"]
    ordering_fields = ["nombre", "creado_en"]

    def get_queryset(self):
        return self.filtrar_por_empresa(Cliente.objects.select_related("empresa"))

    def perform_create(self, serializer):
        serializer.save(empresa=self._empresa_requerida())


class CotizacionViewSet(EmpresaScopedViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["cliente__nombre", "comentarios"]
    ordering_fields = ["fecha_ingreso", "total", "estado"]

    def get_queryset(self):
        qs = Cotizacion.objects.select_related("cliente", "empleado").prefetch_related(
            "ventanas"
        )
        estado = self.request.query_params.get("estado")
        if estado:
            qs = qs.filter(estado=estado)
        return self.filtrar_por_empresa(qs)

    def get_serializer_class(self):
        if self.action == "list":
            return CotizacionListSerializer
        return CotizacionSerializer

    @action(detail=True, methods=["post"])
    def recalcular(self, request, pk=None):
        """Recalcula precios de la cotizacion con el catalogo actual."""
        cotizacion = self.get_object()
        recalcular_cotizacion(cotizacion)
        serializer = CotizacionSerializer(cotizacion, context={"request": request})
        return Response(serializer.data)

    def _resolver(self, request, nuevo_estado):
        user = request.user
        if not (user.is_superuser or user.es_jefe):
            raise PermissionDenied("Solo el jefe puede aprobar o rechazar cotizaciones.")
        cotizacion = self.get_object()
        if cotizacion.estado != Cotizacion.Estado.PENDIENTE:
            raise ValidationError("La cotizacion ya fue resuelta.")
        cotizacion.estado = nuevo_estado
        cotizacion.fecha_resolucion = timezone.now()
        cotizacion.resuelta_por = user
        cotizacion.save(
            update_fields=["estado", "fecha_resolucion", "resuelta_por"]
        )

        # Al aprobar, la cotizacion se convierte en un Proyecto (1 a 1).
        if nuevo_estado == Cotizacion.Estado.APROBADA:
            from projects.models import Proyecto

            Proyecto.objects.get_or_create(
                cotizacion=cotizacion,
                defaults={
                    "empresa": cotizacion.empresa,
                    "cliente": cotizacion.cliente,
                },
            )

        serializer = CotizacionSerializer(cotizacion, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        return self._resolver(request, Cotizacion.Estado.APROBADA)

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        return self._resolver(request, Cotizacion.Estado.RECHAZADA)


# ============================================================
# Catalogo de precios (solo jefe/admin)
# ============================================================


class SerieAluminioViewSet(EmpresaScopedViewSet):
    """Series fijas (L20, L25): solo lectura/edicion, sin alta ni baja."""

    serializer_class = SerieAluminioSerializer
    permission_classes = [IsJefeOrAdmin]
    http_method_names = ["get", "head", "options", "patch", "put"]

    def get_queryset(self):
        asegurar_catalogo(self.request.user.empresa)
        return self.filtrar_por_empresa(
            SerieAluminio.objects.prefetch_related("perfiles", "precios")
        )


class PerfilIndividualViewSet(EmpresaScopedViewSet):
    serializer_class = PerfilIndividualSerializer
    permission_classes = [IsJefeOrAdmin]

    def get_queryset(self):
        asegurar_catalogo(self.request.user.empresa)
        return self.filtrar_por_empresa(
            PerfilIndividual.objects.prefetch_related("precios")
        )

    def perform_create(self, serializer):
        serializer.save(empresa=self._empresa_requerida())


class PlanchaVidrioViewSet(EmpresaScopedViewSet):
    serializer_class = PlanchaVidrioSerializer
    permission_classes = [IsJefeOrAdmin]

    def get_queryset(self):
        return self.filtrar_por_empresa(PlanchaVidrio.objects.all())

    def perform_create(self, serializer):
        serializer.save(empresa=self._empresa_requerida())


class InsumoViewSet(EmpresaScopedViewSet):
    """Insumos fijos: solo lectura/edicion, sin alta ni baja."""

    serializer_class = InsumoSerializer
    permission_classes = [IsJefeOrAdmin]
    http_method_names = ["get", "head", "options", "patch", "put"]

    def get_queryset(self):
        asegurar_catalogo(self.request.user.empresa)
        return self.filtrar_por_empresa(Insumo.objects.all())


class _HijoDeEmpresaViewSet(viewsets.ModelViewSet):
    """Base para modelos cuyo dueno-empresa es a traves de un padre
    (perfiles y precios dependen de su serie/perfil)."""

    permission_classes = [IsJefeOrAdmin]
    padre_lookup = None  # p. ej. "serie__empresa"

    def get_queryset(self):
        user = self.request.user
        qs = self.model.objects.all()
        if user.is_superuser:
            return qs
        return qs.filter(**{self.padre_lookup: user.empresa})


class PerfilSerieViewSet(_HijoDeEmpresaViewSet):
    serializer_class = PerfilSerieSerializer
    model = PerfilSerie
    padre_lookup = "serie__empresa"


class PrecioSerieViewSet(_HijoDeEmpresaViewSet):
    serializer_class = PrecioSerieSerializer
    model = PrecioSerie
    padre_lookup = "serie__empresa"


class PrecioPerfilIndividualViewSet(_HijoDeEmpresaViewSet):
    serializer_class = PrecioPerfilIndividualSerializer
    model = PrecioPerfilIndividual
    padre_lookup = "perfil__empresa"


class EmpresaConfigView(generics.RetrieveUpdateAPIView):
    """Lee/actualiza la configuracion de precios de la empresa del usuario."""

    serializer_class = EmpresaConfigSerializer
    permission_classes = [IsJefeOrAdmin]

    def get_object(self):
        if self.request.user.empresa_id is None:
            raise ValidationError("El usuario no tiene una empresa asignada.")
        return self.request.user.empresa


class OpcionesCotizacionView(APIView):
    """Opciones para poblar los desplegables del formulario de cotizacion."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        def opts(choices):
            return [{"value": v, "label": label} for v, label in choices]

        user = request.user
        asegurar_catalogo(user.empresa)

        # Tipos con serie configurada (deja fuera L42 mientras no exista).
        if user.empresa_id:
            series = set(
                SerieAluminio.objects.filter(empresa=user.empresa).values_list(
                    "codigo", flat=True
                )
            )
            planchas = list(
                PlanchaVidrio.objects.filter(empresa=user.empresa).values_list(
                    "tipo_vidrio", flat=True
                )
            )
        else:
            series, planchas = set(), []

        vidrio_labels = dict(TipoVidrio.choices)
        tipos_disponibles = [
            {"value": v, "label": label}
            for v, label in TipoVentana.choices
            if SERIE_POR_TIPO.get(v) in series
        ]
        vidrios_disponibles = [
            {"value": tv, "label": vidrio_labels.get(tv, tv)} for tv in planchas
        ]

        return Response(
            {
                "tipos_ventana": opts(TipoVentana.choices),
                "colores": opts(VentanaCotizada._meta.get_field("color").choices),
                "vidrios": opts(TipoVidrio.choices),
                "estados": opts(Cotizacion.Estado.choices),
                "tipos_disponibles": tipos_disponibles,
                "vidrios_disponibles": vidrios_disponibles,
            }
        )
