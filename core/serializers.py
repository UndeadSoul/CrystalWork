from rest_framework import serializers

from .models import Cliente, Cotizacion, VentanaCotizada


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
        # La empresa se asigna en el servidor segun el usuario autenticado.


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
            "subtotal",
        ]
        read_only_fields = ["id", "subtotal"]


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
        cotizacion.recalcular_total()
        cotizacion.save(update_fields=["total"])
        return cotizacion


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
