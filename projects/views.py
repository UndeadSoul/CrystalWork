from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .cutlist import hoja_de_corte
from .models import Proyecto
from .serializers import ProyectoListSerializer, ProyectoSerializer


class ProyectoViewSet(viewsets.ModelViewSet):
    """Proyectos (cotizaciones aprobadas). No se crean ni borran por API: nacen
    al aprobar una cotizacion. Solo se consultan y se actualiza su estado."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options", "patch", "put"]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["fecha_creacion", "estado_produccion"]

    def get_queryset(self):
        user = self.request.user
        qs = Proyecto.objects.select_related("cliente", "cotizacion").prefetch_related(
            "cotizacion__ventanas"
        )
        if not user.is_superuser:
            qs = qs.filter(empresa=user.empresa)

        estado = self.request.query_params.get("estado")
        if estado:
            qs = qs.filter(estado_produccion=estado)
        cliente = self.request.query_params.get("cliente")
        if cliente:
            qs = qs.filter(cliente_id=cliente)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ProyectoListSerializer
        return ProyectoSerializer

    @action(detail=True, methods=["get"], url_path="hoja-corte")
    def hoja_corte(self, request, pk=None):
        proyecto = self.get_object()
        return Response({"piezas": hoja_de_corte(proyecto)})
