from django.utils import timezone
from rest_framework import serializers

from core import validacion as val
from core.serializers import CotizacionSerializer
from core.pricing import desglose_iva

from .models import Pago, Proyecto


def fecha_min_pago(proyecto):
    """Un pago no puede ser anterior al ingreso de la cotizacion (dia en hora
    de Chile; fecha_ingreso se guarda en UTC)."""
    return timezone.localtime(proyecto.cotizacion.fecha_ingreso).date()


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
    pagos = serializers.SerializerMethodField()
    total_bruto = serializers.SerializerMethodField()
    saldo = serializers.SerializerMethodField()
    # Rango de fechas validas para un pago, en hora de Chile (las calcula el
    # servidor para no depender del reloj ni la zona horaria del navegador).
    fecha_hoy = serializers.SerializerMethodField()
    fecha_min_pago = serializers.SerializerMethodField()

    class Meta:
        model = Proyecto
        fields = [
            "id",
            "cliente",
            "cliente_nombre",
            "cliente_telefono",
            "estado_produccion",
            "estado_display",
            "motivo_cancelacion",
            "estado_pago",
            "estado_pago_display",
            "monto_abonado",
            "total_bruto",
            "saldo",
            "pagos",
            "fecha_hoy",
            "fecha_min_pago",
            "fecha_creacion",
            "cotizacion",
        ]
        # Pago (estado y monto abonado) se deriva de los pagos: no se edita
        # aqui, se registran o anulan pagos (projects/pagos.py).
        read_only_fields = [
            "id",
            "cliente",
            "fecha_creacion",
            "cotizacion",
            "estado_pago",
            "monto_abonado",
        ]
        extra_kwargs = {
            "motivo_cancelacion": {
                "error_messages": {
                    "max_length": "Debe tener como máximo {max_length} caracteres.",
                }
            }
        }

    def validate_motivo_cancelacion(self, valor):
        return val.normalizar_espacios(valor)

    def validate(self, attrs):
        """Cancelado exige un motivo; al salir de Cancelado el motivo se
        limpia (queda en el control de cambios)."""
        Estado = Proyecto.EstadoProduccion
        estado = attrs.get("estado_produccion", self.instance.estado_produccion)
        if estado == Estado.CANCELADO:
            motivo = attrs.get("motivo_cancelacion", self.instance.motivo_cancelacion)
            if len(motivo or "") < val.MOTIVO_ANULACION_MIN:
                raise serializers.ValidationError(
                    {
                        "motivo_cancelacion": (
                            "Indica el motivo de la cancelación "
                            f"(al menos {val.MOTIVO_ANULACION_MIN} caracteres)."
                        )
                    }
                )
        else:
            attrs["motivo_cancelacion"] = ""
        return attrs

    def get_pagos(self, obj):
        return PagoSerializer(obj.pagos.select_related("registrado_por", "anulado_por"), many=True).data

    def get_total_bruto(self, obj):
        return desglose_iva(obj.cotizacion.total)[2]

    def get_saldo(self, obj):
        return max(self.get_total_bruto(obj) - int(obj.monto_abonado or 0), 0)

    def get_fecha_hoy(self, obj):
        return timezone.localdate()

    def get_fecha_min_pago(self, obj):
        return fecha_min_pago(obj)


class PagoSerializer(serializers.ModelSerializer):
    registrado_por_nombre = serializers.CharField(
        source="registrado_por.username", read_only=True, default=""
    )
    anulado_por_nombre = serializers.CharField(
        source="anulado_por.username", read_only=True, default=""
    )

    class Meta:
        model = Pago
        fields = [
            "id",
            "monto",
            "fecha",
            "comentario",
            "registrado_por_nombre",
            "creado_en",
            "anulado",
            "anulado_por_nombre",
            "anulado_en",
            "motivo_anulacion",
        ]
        read_only_fields = fields


class RegistrarPagoSerializer(serializers.ModelSerializer):
    """Datos para registrar un pago. El tope por saldo se valida en
    projects/pagos.py (con el proyecto bloqueado)."""

    class Meta:
        model = Pago
        fields = ["monto", "fecha", "comentario"]
        extra_kwargs = val.mensajes("monto", "fecha", "comentario")

    def validate_comentario(self, valor):
        return val.normalizar_espacios(valor)

    def validate_fecha(self, fecha):
        if fecha > timezone.localdate():
            raise serializers.ValidationError("La fecha no puede ser futura.")
        minima = fecha_min_pago(self.context["proyecto"])
        if fecha < minima:
            raise serializers.ValidationError(
                f"No puede ser anterior a la cotización ({minima:%d-%m-%Y})."
            )
        return fecha


class AnularPagoSerializer(serializers.Serializer):
    motivo = serializers.CharField(
        min_length=val.MOTIVO_ANULACION_MIN,
        max_length=val.PAGO_COMENTARIO_MAX,
        validators=val.validar_comentario_pago,
        error_messages={
            "required": "Indica el motivo de la anulación.",
            "blank": "Indica el motivo de la anulación.",
            "min_length": "Debe tener al menos {min_length} caracteres.",
            "max_length": "Debe tener como máximo {max_length} caracteres.",
        },
    )

    def validate_motivo(self, valor):
        return val.normalizar_espacios(valor)
