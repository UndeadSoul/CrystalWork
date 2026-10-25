from django.shortcuts import get_object_or_404
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.audit import registrar_cambio
from core.models import CambioRegistro
from core.pdf import respuesta_pdf
from core.permissions import EsUsuarioDeEmpresa
from core.serializers import CambioRegistroSerializer

from .cutlist import hoja_de_corte
from .models import Proyecto
from .pagos import anular_pago, registrar_pago
from .pdf import pdf_hoja_corte, pdf_proyecto
from .serializers import (
    AnularPagoSerializer,
    ProyectoListSerializer,
    ProyectoSerializer,
    RegistrarPagoSerializer,
)


class ProyectoViewSet(viewsets.ModelViewSet):
    """Proyectos (cotizaciones aprobadas). No se crean ni borran por API: nacen
    al aprobar una cotizacion. Se consultan, se actualiza su estado de
    fabricacion y se registran/anulan pagos (el estado de pago se deriva)."""

    permission_classes = [EsUsuarioDeEmpresa]
    http_method_names = ["get", "head", "options", "patch", "put", "post"]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["fecha_creacion", "estado_produccion"]

    def get_queryset(self):
        qs = (
            Proyecto.objects.filter(empresa=self.request.user.empresa)
            .select_related("cliente", "cotizacion")
            .prefetch_related("cotizacion__ventanas")
        )

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

    def create(self, request, *args, **kwargs):
        # Los proyectos nacen al aprobar una cotizacion (POST solo para pagos).
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def perform_update(self, serializer):
        Estado = Proyecto.EstadoProduccion
        anterior = serializer.instance.estado_produccion
        nuevo = serializer.validated_data.get("estado_produccion", anterior)
        # Cancelar o reactivar un proyecto es decision del jefe.
        if Estado.CANCELADO in (anterior, nuevo) and anterior != nuevo:
            if not self.request.user.es_jefe:
                raise PermissionDenied("Solo el jefe puede cancelar o reactivar un proyecto.")
        proyecto = serializer.save()
        if anterior != proyecto.estado_produccion:
            valor_nuevo = proyecto.get_estado_produccion_display()
            if proyecto.estado_produccion == Estado.CANCELADO:
                valor_nuevo = f"{valor_nuevo}: {proyecto.motivo_cancelacion}"
            registrar_cambio(
                empresa=proyecto.empresa,
                usuario=self.request.user,
                categoria=CambioRegistro.Categoria.PROYECTO,
                objeto_tipo="proyecto",
                objeto_id=proyecto.pk,
                objeto_label=f"Proyecto #{proyecto.pk}",
                campo="Fabricación",
                valor_anterior=Estado(anterior).label,
                valor_nuevo=valor_nuevo,
            )

    def _detalle(self, proyecto, codigo=status.HTTP_200_OK):
        proyecto.refresh_from_db()
        return Response(self.get_serializer(proyecto).data, status=codigo)

    @action(detail=True, methods=["post"])
    def pagos(self, request, pk=None):
        """Registra un pago. Responde el proyecto actualizado."""
        proyecto = self.get_object()
        s = RegistrarPagoSerializer(data=request.data, context={"proyecto": proyecto})
        s.is_valid(raise_exception=True)
        registrar_pago(proyecto, request.user, **s.validated_data)
        return self._detalle(proyecto, status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"pagos/(?P<pago_id>\d+)/anular",
    )
    def anular_pago(self, request, pk=None, pago_id=None):
        """Anula un pago (solo el jefe). Responde el proyecto actualizado."""
        if not request.user.es_jefe:
            raise PermissionDenied("Solo el jefe puede anular pagos.")
        proyecto = self.get_object()
        pago = get_object_or_404(proyecto.pagos, pk=pago_id)
        s = AnularPagoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        anular_pago(pago, request.user, s.validated_data["motivo"])
        return self._detalle(proyecto)

    @action(detail=True, methods=["get"], url_path="hoja-corte")
    def hoja_corte(self, request, pk=None):
        proyecto = self.get_object()
        return Response({"piezas": hoja_de_corte(proyecto)})

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """Proyecto completo en PDF (estado, cliente, ventanas, hoja de corte
        y pagos)."""
        proyecto = self.get_object()
        return respuesta_pdf(
            pdf_proyecto(proyecto, request.user), f"proyecto-{proyecto.pk}.pdf"
        )

    @action(detail=True, methods=["get"], url_path="hoja-corte/pdf")
    def hoja_corte_pdf(self, request, pk=None):
        """Solo la hoja de corte en PDF (para el taller)."""
        proyecto = self.get_object()
        return respuesta_pdf(
            pdf_hoja_corte(proyecto, request.user),
            f"hoja-corte-proyecto-{proyecto.pk}.pdf",
        )

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
