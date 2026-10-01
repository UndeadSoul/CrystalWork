from rest_framework import filters, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cliente, Cotizacion, VentanaCotizada
from .serializers import (
    ClienteSerializer,
    CotizacionListSerializer,
    CotizacionSerializer,
)


class EmpresaScopedViewSet(viewsets.ModelViewSet):
    """Base: aisla por empresa (el superuser ve todo)."""

    permission_classes = [IsAuthenticated]

    def filtrar_por_empresa(self, qs):
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(empresa=user.empresa)


class ClienteViewSet(EmpresaScopedViewSet):
    """CRUD de clientes, aislado por empresa."""

    serializer_class = ClienteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nombre", "rut", "email", "telefono"]
    ordering_fields = ["nombre", "creado_en"]

    def get_queryset(self):
        return self.filtrar_por_empresa(Cliente.objects.select_related("empresa"))

    def perform_create(self, serializer):
        user = self.request.user
        if user.empresa_id is None:
            raise ValidationError(
                "El usuario no tiene una empresa asignada; no puede crear clientes."
            )
        serializer.save(empresa=user.empresa)


class CotizacionViewSet(EmpresaScopedViewSet):
    """CRUD de cotizaciones, aislado por empresa."""

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


class OpcionesCotizacionView(APIView):
    """Opciones para poblar los desplegables del formulario de cotizacion."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        def opts(choices):
            return [{"value": v, "label": label} for v, label in choices]

        return Response(
            {
                "tipos_ventana": opts(VentanaCotizada.Tipo.choices),
                "colores": opts(VentanaCotizada.Color.choices),
                "vidrios": opts(VentanaCotizada.Vidrio.choices),
                "estados": opts(Cotizacion.Estado.choices),
            }
        )
