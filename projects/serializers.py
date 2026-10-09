from rest_framework import serializers

from core.serializers import CotizacionSerializer

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
            "n_ventanas",
            "fecha_creacion",
        ]


class ProyectoSerializer(serializers.ModelSerializer):
    """Detalle: permite actualizar solo el estado de produccion."""

    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
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
            "estado_produccion",
            "estado_display",
            "estado_pago",
            "estado_pago_display",
            "fecha_creacion",
            "cotizacion",
        ]
        read_only_fields = ["id", "cliente", "fecha_creacion", "cotizacion"]
