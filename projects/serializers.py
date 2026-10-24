from rest_framework import serializers

from core.serializers import CotizacionSerializer
from core.pricing import desglose_iva

from .models import Proyecto


class ProyectoListSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    estado_display = serializers.CharField(
        source="get_estado_produccion_display", read_only=True
    )
    estado_pago_display = serializers.CharField(
        source="get_estado_pago_display", read_only=True
    )
    total = serializers.DecimalField(
        source="cotizacion.total", max_digits=12, decimal_places=0, read_only=True
    )
    total_bruto = serializers.SerializerMethodField()
    n_ventanas = serializers.IntegerField(
        source="cotizacion.ventanas.count", read_only=True
    )

    class Meta:
        model = Proyecto
        fields = [
            "id",
            "cliente",
            "cliente_nombre",
            "estado_produccion",
            "estado_display",
            "estado_pago",
            "estado_pago_display",
            "total",
            "total_bruto",
            "n_ventanas",
            "fecha_creacion",
        ]

    def get_total_bruto(self, obj):
        return desglose_iva(obj.cotizacion.total)[2]


class ProyectoSerializer(serializers.ModelSerializer):
    """Detalle: permite actualizar solo el estado de produccion."""

    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    cliente_telefono = serializers.CharField(
        source="cliente.telefono", read_only=True
    )
    estado_display = serializers.CharField(
        source="get_estado_produccion_display", read_only=True
    )
    estado_pago_display = serializers.CharField(
        source="get_estado_pago_display", read_only=True
    )
    cotizacion = CotizacionSerializer(read_only=True)

    class Meta:
        model = Proyecto
        fields = [
            "id",
            "cliente",
            "cliente_nombre",
            "cliente_telefono",
            "estado_produccion",
            "estado_display",
            "estado_pago",
            "estado_pago_display",
            "monto_abonado",
            "fecha_creacion",
            "cotizacion",
        ]
        read_only_fields = ["id", "cliente", "fecha_creacion", "cotizacion"]
