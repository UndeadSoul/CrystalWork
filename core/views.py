from django.db import transaction
from django.utils import timezone
from rest_framework import filters, generics, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .audit import AuditaValoresMixin
from .catalog import asegurar_catalogo
from .concurrencia import ControlVersionMixin, tomar_cotizacion, version_esperada
from .pdf import pdf_cotizacion, respuesta_pdf
from .permissions import EsJefe, EsUsuarioDeEmpresa
from .models import (
    CambioRegistro,
    Cliente,
    Cotizacion,
    Insumo,
    PerfilSerie,
    PlanchaVidrio,
    PrecioSerie,
    SerieAluminio,
    TipoVentana,
    TipoVidrio,
    VentanaCotizada,
)
from .pricing import SERIE_POR_TIPO, recalcular_cotizacion
from .serializers import (
    CambioRegistroSerializer,
    ClienteSerializer,
    CotizacionListSerializer,
    CotizacionSerializer,
    EmpresaConfigSerializer,
    InsumoSerializer,
    PerfilSerieSerializer,
    PlanchaVidrioSerializer,
    PrecioSerieSerializer,
    SerieAluminioSerializer,
)


class EmpresaScopedViewSet(viewsets.ModelViewSet):
    """Base: aisla por empresa. Solo usuarios de una empresa (el
    administrador del sistema no ve datos operativos)."""

    permission_classes = [EsUsuarioDeEmpresa]

    def filtrar_por_empresa(self, qs):
        return qs.filter(empresa=self.request.user.empresa)

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

    # Crear y editar recrean ventanas y recalculan: todo o nada.
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Solo pendientes y con la version que el usuario estaba viendo
        (409 si otro usuario la edito o resolvio entre medio)."""
        cotizacion = self.get_object()
        tomar_cotizacion(cotizacion, version_esperada(request), request.user)
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        """Cotizacion en PDF (descarga)."""
        cotizacion = self.get_object()
        return respuesta_pdf(
            pdf_cotizacion(cotizacion, request.user), f"cotizacion-{cotizacion.pk}.pdf"
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def recalcular(self, request, pk=None):
        """Recalcula precios con el catalogo actual. Solo pendientes: una
        aprobada no cambia (su monto es el del proyecto)."""
        cotizacion = self.get_object()
        tomar_cotizacion(cotizacion, version_esperada(request), request.user)
        recalcular_cotizacion(cotizacion)
        serializer = CotizacionSerializer(cotizacion, context={"request": request})
        return Response(serializer.data)

    def _resolver(self, request, nuevo_estado):
        user = request.user
        if not user.es_jefe:
            raise PermissionDenied("Solo el jefe puede aprobar o rechazar cotizaciones.")
        with transaction.atomic():
            cotizacion = self.get_object()
            # El estado cambia en la misma sentencia que verifica la version:
            # nadie aprueba una version que no vio, ni se resuelve dos veces.
            tomar_cotizacion(
                cotizacion,
                version_esperada(request),
                user,
                estado=nuevo_estado,
                fecha_resolucion=timezone.now(),
                resuelta_por=user,
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


class SerieAluminioViewSet(ControlVersionMixin, AuditaValoresMixin, EmpresaScopedViewSet):
    """Series fijas (L20, L25): solo lectura/edicion, sin alta ni baja."""

    serializer_class = SerieAluminioSerializer
    permission_classes = [EsJefe]
    http_method_names = ["get", "head", "options", "patch", "put"]
    campos_auditados = {"peso_total_kg": "Peso total (kg)"}

    def audit_objeto(self, instance):
        return ("serie", f"Serie {instance.codigo}")

    def get_queryset(self):
        asegurar_catalogo(self.request.user.empresa)
        return self.filtrar_por_empresa(
            SerieAluminio.objects.prefetch_related("perfiles", "precios")
        )


class PlanchaVidrioViewSet(ControlVersionMixin, AuditaValoresMixin, EmpresaScopedViewSet):
    serializer_class = PlanchaVidrioSerializer
    permission_classes = [EsJefe]
    campos_auditados = {
        "ancho_plancha_m": "Ancho (m)",
        "alto_plancha_m": "Alto (m)",
        "precio": "Precio",
    }

    def audit_objeto(self, instance):
        return ("plancha", f"Plancha {instance.get_tipo_vidrio_display()}")

    def get_queryset(self):
        return self.filtrar_por_empresa(PlanchaVidrio.objects.all())

    def perform_create(self, serializer):
        serializer.save(empresa=self._empresa_requerida())


class InsumoViewSet(ControlVersionMixin, AuditaValoresMixin, EmpresaScopedViewSet):
    """Insumos fijos: solo lectura/edicion, sin alta ni baja."""

    serializer_class = InsumoSerializer
    permission_classes = [EsJefe]
    http_method_names = ["get", "head", "options", "patch", "put"]
    campos_auditados = {
        "precio_paquete": "Precio paquete",
        "cantidad_paquete": "Cant. paquete",
    }

    def audit_objeto(self, instance):
        return ("insumo", instance.nombre)

    def get_queryset(self):
        asegurar_catalogo(self.request.user.empresa)
        return self.filtrar_por_empresa(Insumo.objects.all())


class _HijoDeEmpresaViewSet(ControlVersionMixin, AuditaValoresMixin, viewsets.ModelViewSet):
    """Base para modelos cuyo dueno-empresa es a traves de un padre
    (perfiles y precios dependen de su serie/perfil)."""

    permission_classes = [EsJefe]
    padre_lookup = None  # p. ej. "serie__empresa"

    def audit_empresa(self, instance):
        return instance.serie.empresa

    def get_queryset(self):
        return self.model.objects.filter(
            **{self.padre_lookup: self.request.user.empresa}
        )


class PerfilSerieViewSet(_HijoDeEmpresaViewSet):
    serializer_class = PerfilSerieSerializer
    model = PerfilSerie
    padre_lookup = "serie__empresa"
    campos_auditados = {"peso_kg": "Peso (kg)", "largo_tira_m": "Largo tira (m)"}

    def audit_objeto(self, instance):
        return ("perfil", f"{instance.serie.codigo} · {instance.nombre}")


class PrecioSerieViewSet(_HijoDeEmpresaViewSet):
    serializer_class = PrecioSerieSerializer
    model = PrecioSerie
    padre_lookup = "serie__empresa"
    campos_auditados = {"precio": "Precio paquete"}

    def audit_objeto(self, instance):
        return (
            "precio-serie",
            f"{instance.serie.codigo} · {instance.get_color_display()}",
        )


class EmpresaConfigView(ControlVersionMixin, AuditaValoresMixin, generics.RetrieveUpdateAPIView):
    """Lee/actualiza la configuracion de precios de la empresa del usuario."""

    serializer_class = EmpresaConfigSerializer
    permission_classes = [EsJefe]
    campo_version = "version_config"
    campos_auditados = {
        "margen_ganancia_pct": "Margen de ganancia (%)",
        "precio_transporte_km": "Precio transporte por km",
    }

    def audit_objeto(self, instance):
        return ("config", "Configuración general")

    def audit_empresa(self, instance):
        return instance  # el objeto es la propia Empresa

    def get_object(self):
        if self.request.user.empresa_id is None:
            raise ValidationError("El usuario no tiene una empresa asignada.")
        return self.request.user.empresa


class CambioPrecioListView(generics.ListAPIView):
    """Historial de cambios de precios de la empresa del usuario."""

    serializer_class = CambioRegistroSerializer
    permission_classes = [EsJefe]

    def get_queryset(self):
        return CambioRegistro.objects.filter(
            categoria=CambioRegistro.Categoria.PRECIO,
            empresa=self.request.user.empresa,
        ).select_related("usuario")


class OpcionesCotizacionView(APIView):
    """Opciones para poblar los desplegables del formulario de cotizacion."""

    permission_classes = [EsUsuarioDeEmpresa]

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
