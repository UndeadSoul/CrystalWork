from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.audit import registrar_cambio
from core.models import CambioRegistro
from core.serializers import CambioRegistroSerializer

from .cutlist import hoja_de_corte
from .models import Proyecto
from .serializers import ProyectoListSerializer, ProyectoSerializer

# Campos de estado auditados: nombre de campo -> etiqueta visible.
ESTADOS_AUDITADOS = {
    "estado_produccion": "Fabricación",
    "estado_pago": "Pago",
}


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
        pago = self.request.query_params.get("pago")
        if pago:
            qs = qs.filter(estado_pago=pago)
        cliente = self.request.query_params.get("cliente")
        if cliente:
            qs = qs.filter(cliente_id=cliente)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ProyectoListSerializer
        return ProyectoSerializer

    def perform_update(self, serializer):
        instance = serializer.instance
        antes = {campo: getattr(instance, campo) for campo in ESTADOS_AUDITADOS}
        antes_abono = instance.monto_abonado
        proyecto = serializer.save()

        for campo, etiqueta in ESTADOS_AUDITADOS.items():
            anterior = antes[campo]
            nuevo = getattr(proyecto, campo)
            if anterior == nuevo:
                continue
            etiqueta_valor = f"get_{campo}_display"
            registrar_cambio(
                empresa=proyecto.empresa,
                usuario=self.request.user,
                categoria=CambioRegistro.Categoria.PROYECTO,
                objeto_tipo="proyecto",
                objeto_id=proyecto.pk,
                objeto_label=f"Proyecto #{proyecto.pk}",
                campo=etiqueta,
                valor_anterior=dict(
                    proyecto._meta.get_field(campo).choices
                ).get(anterior, anterior),
                valor_nuevo=getattr(proyecto, etiqueta_valor)(),
            )

        if antes_abono != proyecto.monto_abonado:
            registrar_cambio(
                empresa=proyecto.empresa,
                usuario=self.request.user,
                categoria=CambioRegistro.Categoria.PROYECTO,
                objeto_tipo="proyecto",
                objeto_id=proyecto.pk,
                objeto_label=f"Proyecto #{proyecto.pk}",
                campo="Monto abonado",
                valor_anterior=int(antes_abono or 0),
                valor_nuevo=int(proyecto.monto_abonado or 0),
            )

    @action(detail=True, methods=["get"], url_path="hoja-corte")
    def hoja_corte(self, request, pk=None):
        proyecto = self.get_object()
        return Response({"piezas": hoja_de_corte(proyecto)})

    @action(detail=True, methods=["get"])
    def cambios(self, request, pk=None):
        proyecto = self.get_object()
        qs = CambioRegistro.objects.filter(
            categoria=CambioRegistro.Categoria.PROYECTO,
            objeto_tipo="proyecto",
            objeto_id=proyecto.pk,
            empresa=proyecto.empresa,
        ).select_related("usuario")
        return Response(CambioRegistroSerializer(qs, many=True).data)
