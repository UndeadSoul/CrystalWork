from rest_framework import serializers

from users.models import Empresa

from .rut import rut_valido

from .models import (
    Cliente,
    Cotizacion,
    Insumo,
    PerfilSerie,
    PlanchaVidrio,
    PrecioSerie,
    SerieAluminio,
    VentanaCotizada,
)
from .pricing import recalcular_cotizacion


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = [
            "id",
            "nombre",
            "rut",
            "telefono",
            "email",
            "direccion",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["id", "creado_en", "actualizado_en"]

    def validate_rut(self, valor):
        if valor and not rut_valido(valor):
            raise serializers.ValidationError("El RUT no es válido.")
        return valor


class VentanaCotizadaSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    color_display = serializers.CharField(source="get_color_display", read_only=True)
    vidrio_display = serializers.CharField(source="get_vidrio_display", read_only=True)

    class Meta:
        model = VentanaCotizada
        fields = [
            "id",
            "tipo",
            "tipo_display",
            "color",
            "color_display",
            "vidrio",
            "vidrio_display",
            "ancho_cm",
            "alto_cm",
            "cantidad",
            "costo_unitario",
            "precio_unitario",
            "subtotal",
            "precio_calculado",
        ]
        read_only_fields = [
            "id",
            "costo_unitario",
            "precio_unitario",
            "subtotal",
            "precio_calculado",
        ]

    def _validar_dimension(self, valor, campo):
        if valor is None or not (30 <= valor <= 250):
            raise serializers.ValidationError(
                f"El {campo} debe estar entre 30 y 250 cm."
            )
        return valor

    def validate_ancho_cm(self, valor):
        return self._validar_dimension(valor, "ancho")

    def validate_alto_cm(self, valor):
        return self._validar_dimension(valor, "alto")


class CotizacionSerializer(serializers.ModelSerializer):
    """Serializer de detalle y creacion (con ventanas anidadas)."""

    ventanas = VentanaCotizadaSerializer(many=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    empleado_nombre = serializers.CharField(source="empleado.username", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    resuelta_por_nombre = serializers.CharField(
        source="resuelta_por.username", read_only=True
    )

    class Meta:
        model = Cotizacion
        fields = [
            "id",
            "cliente",
            "cliente_nombre",
            "empleado",
            "empleado_nombre",
            "estado",
            "estado_display",
            "direccion_entrega",
            "requiere_transporte",
            "distancia_transporte_km",
            "comentarios",
            "monto_agregado",
            "costo_transporte",
            "total",
            "fecha_ingreso",
            "fecha_resolucion",
            "resuelta_por",
            "resuelta_por_nombre",
            "ventanas",
        ]
        read_only_fields = [
            "id",
            "empleado",
            "estado",
            "costo_transporte",
            "total",
            "fecha_ingreso",
            "fecha_resolucion",
            "resuelta_por",
        ]

    def validate_cliente(self, cliente):
        user = self.context["request"].user
        if not user.is_superuser and cliente.empresa_id != user.empresa_id:
            raise serializers.ValidationError("El cliente no pertenece a tu empresa.")
        return cliente

    def validate_ventanas(self, ventanas):
        if not ventanas:
            raise serializers.ValidationError("Agrega al menos una ventana.")
        return ventanas

    def create(self, validated_data):
        ventanas_data = validated_data.pop("ventanas", [])
        user = self.context["request"].user
        if user.empresa_id is None:
            raise serializers.ValidationError(
                "El usuario no tiene una empresa asignada; no puede cotizar."
            )

        cotizacion = Cotizacion.objects.create(
            empresa=user.empresa, empleado=user, **validated_data
        )
        VentanaCotizada.objects.bulk_create(
            [VentanaCotizada(cotizacion=cotizacion, **v) for v in ventanas_data]
        )
        recalcular_cotizacion(cotizacion)
        return cotizacion

    def update(self, instance, validated_data):
        ventanas_data = validated_data.pop("ventanas", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if ventanas_data is not None:
            instance.ventanas.all().delete()
            VentanaCotizada.objects.bulk_create(
                [VentanaCotizada(cotizacion=instance, **v) for v in ventanas_data]
            )
        recalcular_cotizacion(instance)
        return instance


class CotizacionListSerializer(serializers.ModelSerializer):
    """Serializer liviano para el listado."""

    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    empleado_nombre = serializers.CharField(source="empleado.username", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    n_ventanas = serializers.IntegerField(source="ventanas.count", read_only=True)

    class Meta:
        model = Cotizacion
        fields = [
            "id",
            "cliente_nombre",
            "empleado_nombre",
            "estado",
            "estado_display",
            "total",
            "n_ventanas",
            "fecha_ingreso",
        ]


# ============================================================
# Catalogo de precios
# ============================================================


class PerfilSerieSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilSerie
        fields = ["id", "serie", "nombre", "peso_kg", "largo_tira_m", "en_paquete"]
        read_only_fields = ["en_paquete"]


class PrecioSerieSerializer(serializers.ModelSerializer):
    color_display = serializers.CharField(source="get_color_display", read_only=True)

    class Meta:
        model = PrecioSerie
        fields = ["id", "serie", "color", "color_display", "precio"]


class SerieAluminioSerializer(serializers.ModelSerializer):
    perfiles = PerfilSerieSerializer(many=True, read_only=True)
    precios = PrecioSerieSerializer(many=True, read_only=True)

    class Meta:
        model = SerieAluminio
        fields = ["id", "codigo", "nombre", "peso_total_kg", "perfiles", "precios"]
        read_only_fields = ["id", "codigo", "nombre"]


class PlanchaVidrioSerializer(serializers.ModelSerializer):
    tipo_vidrio_display = serializers.CharField(
        source="get_tipo_vidrio_display", read_only=True
    )

    class Meta:
        model = PlanchaVidrio
        fields = [
            "id",
            "tipo_vidrio",
            "tipo_vidrio_display",
            "ancho_plancha_m",
            "alto_plancha_m",
            "precio",
        ]


class InsumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insumo
        fields = [
            "id",
            "codigo",
            "nombre",
            "unidad",
            "precio_paquete",
            "cantidad_paquete",
        ]


class EmpresaConfigSerializer(serializers.ModelSerializer):
    """Configuracion de precios de la empresa (margen y transporte)."""

    class Meta:
        model = Empresa
        fields = ["id", "nombre", "margen_ganancia_pct", "precio_transporte_km"]
        read_only_fields = ["id", "nombre"]
