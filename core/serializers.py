from rest_framework import serializers

from users.models import Empresa

from . import validacion as val
from .rut import formatear_rut

from .models import (
    CambioRegistro,
    Cliente,
    Cotizacion,
    Insumo,
    PerfilSerie,
    PlanchaVidrio,
    PrecioSerie,
    SerieAluminio,
    VentanaCotizada,
)
from .pricing import SERIE_POR_TIPO, desglose_iva, recalcular_cotizacion


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
        extra_kwargs = val.mensajes("nombre", "rut", "telefono", "direccion")

    # Los limites y caracteres permitidos vienen de los validators del modelo
    # (core/validacion.py); aqui solo se normaliza y se valida la unicidad.

    def validate_nombre(self, valor):
        return val.normalizar_espacios(valor)

    def validate_direccion(self, valor):
        return val.normalizar_espacios(valor)

    def validate_telefono(self, valor):
        return val.normalizar_espacios(valor)

    def validate_rut(self, valor):
        rut = formatear_rut(valor)
        user = self.context["request"].user
        qs = Cliente.objects.filter(empresa_id=user.empresa_id, rut=rut)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un cliente con este RUT.")
        return rut


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
            "ancho_mm",
            "alto_mm",
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
        extra_kwargs = val.mensajes("ancho_mm", "alto_mm", "cantidad")



class CotizacionSerializer(serializers.ModelSerializer):
    """Serializer de detalle y creacion (con ventanas anidadas)."""

    ventanas = VentanaCotizadaSerializer(many=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    empleado_nombre = serializers.CharField(source="empleado.username", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    resuelta_por_nombre = serializers.CharField(
        source="resuelta_por.username", read_only=True
    )
    modificada_por_nombre = serializers.CharField(
        source="modificada_por.username", read_only=True
    )
    iva = serializers.SerializerMethodField()
    total_bruto = serializers.SerializerMethodField()

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
            "iva",
            "total_bruto",
            "fecha_ingreso",
            "fecha_resolucion",
            "resuelta_por",
            "resuelta_por_nombre",
            "version",
            "modificada_por_nombre",
            "modificada_en",
            "ventanas",
        ]
        # version: la envia el cliente para editar/aprobar/rechazar, pero la
        # valida y la incrementa la vista (core/concurrencia.py).
        read_only_fields = [
            "id",
            "empleado",
            "estado",
            "costo_transporte",
            "total",
            "fecha_ingreso",
            "fecha_resolucion",
            "resuelta_por",
            "version",
            "modificada_en",
        ]
        extra_kwargs = val.mensajes(
            "direccion_entrega",
            "comentarios",
            "distancia_transporte_km",
            "monto_agregado",
        )

    def get_iva(self, obj):
        return desglose_iva(obj.total)[1]

    def get_total_bruto(self, obj):
        return desglose_iva(obj.total)[2]

    def validate_cliente(self, cliente):
        user = self.context["request"].user
        if cliente.empresa_id != user.empresa_id:
            raise serializers.ValidationError("El cliente no pertenece a tu empresa.")
        return cliente

    def validate_ventanas(self, ventanas):
        if not ventanas:
            raise serializers.ValidationError("Agrega al menos una ventana.")
        if len(ventanas) > val.VENTANAS_MAX:
            raise serializers.ValidationError(
                f"Una cotización admite como máximo {val.VENTANAS_MAX} ventanas."
            )

        # El tipo debe tener su serie de aluminio y el vidrio su plancha
        # configurada en la empresa (si no, no se puede calcular el precio).
        empresa_id = self.context["request"].user.empresa_id
        series = set(
            SerieAluminio.objects.filter(empresa_id=empresa_id).values_list(
                "codigo", flat=True
            )
        )
        vidrios = set(
            PlanchaVidrio.objects.filter(empresa_id=empresa_id).values_list(
                "tipo_vidrio", flat=True
            )
        )
        errores = []
        for v in ventanas:
            e = {}
            if SERIE_POR_TIPO.get(v["tipo"]) not in series:
                e["tipo"] = ["Este tipo de ventana aún no está disponible."]
            if v["vidrio"] not in vidrios:
                e["vidrio"] = ["Este vidrio no tiene plancha configurada en Precios."]
            errores.append(e)
        if any(errores):
            raise serializers.ValidationError(errores)
        return ventanas

    def validate_direccion_entrega(self, valor):
        return val.normalizar_espacios(valor)

    def validate(self, attrs):
        """Reglas entre campos (en PATCH se completan con la instancia)."""

        def actual(campo, defecto):
            if campo in attrs:
                return attrs[campo]
            return getattr(self.instance, campo, defecto)

        errores = {}
        if actual("requiere_transporte", False):
            if actual("distancia_transporte_km", None) is None:
                errores["distancia_transporte_km"] = "Ingresa la distancia de transporte."
        else:
            attrs["distancia_transporte_km"] = None

        monto = actual("monto_agregado", 0) or 0
        if monto > 0 and not (actual("comentarios", "") or "").strip():
            errores["monto_agregado"] = (
                "Agrega un comentario que explique el monto agregado."
            )

        if errores:
            raise serializers.ValidationError(errores)
        return attrs

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
    total_bruto = serializers.SerializerMethodField()

    class Meta:
        model = Cotizacion
        fields = [
            "id",
            "cliente_nombre",
            "empleado_nombre",
            "estado",
            "estado_display",
            "total",
            "total_bruto",
            "n_ventanas",
            "fecha_ingreso",
        ]

    def get_total_bruto(self, obj):
        return desglose_iva(obj.total)[2]


# ============================================================
# Catalogo de precios
# ============================================================


class PerfilSerieSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilSerie
        fields = ["id", "serie", "nombre", "peso_kg", "largo_tira_m", "en_paquete", "version"]
        read_only_fields = ["en_paquete", "version"]
        extra_kwargs = val.mensajes("peso_kg", "largo_tira_m")

    def validate(self, attrs):
        # Un perfil no puede pesar mas que el paquete completo de su serie
        # (solo si ambos estan configurados: 0 = sin configurar).
        serie = attrs.get("serie") or self.instance.serie
        peso = attrs.get("peso_kg", getattr(self.instance, "peso_kg", 0))
        total = serie.peso_total_kg
        if peso and total and peso > total:
            raise serializers.ValidationError(
                {"peso_kg": f"No puede superar el peso total de la serie ({total} kg)."}
            )
        return attrs


class PrecioSerieSerializer(serializers.ModelSerializer):
    color_display = serializers.CharField(source="get_color_display", read_only=True)

    class Meta:
        model = PrecioSerie
        fields = ["id", "serie", "color", "color_display", "precio", "version"]
        read_only_fields = ["version"]
        extra_kwargs = val.mensajes("precio")


class SerieAluminioSerializer(serializers.ModelSerializer):
    perfiles = PerfilSerieSerializer(many=True, read_only=True)
    precios = PrecioSerieSerializer(many=True, read_only=True)

    class Meta:
        model = SerieAluminio
        fields = ["id", "codigo", "nombre", "peso_total_kg", "perfiles", "precios", "version"]
        read_only_fields = ["id", "codigo", "nombre", "version"]
        extra_kwargs = val.mensajes("peso_total_kg")

    def validate_peso_total_kg(self, total):
        # El paquete no puede pesar menos que su perfil mas pesado.
        if total and self.instance is not None:
            maximo = max(
                (p.peso_kg for p in self.instance.perfiles.all()), default=0
            )
            if maximo > total:
                raise serializers.ValidationError(
                    f"No puede ser menor que el perfil más pesado ({maximo} kg)."
                )
        return total


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
            "version",
        ]
        read_only_fields = ["version"]
        extra_kwargs = val.mensajes("ancho_plancha_m", "alto_plancha_m", "precio")


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
            "version",
        ]
        read_only_fields = ["version"]
        extra_kwargs = val.mensajes("precio_paquete", "cantidad_paquete")


class EmpresaConfigSerializer(serializers.ModelSerializer):
    """Configuracion de precios de la empresa (margen y transporte)."""

    # Version de la configuracion (control de concurrencia en Precios).
    version = serializers.IntegerField(source="version_config", read_only=True)

    class Meta:
        model = Empresa
        fields = ["id", "nombre", "margen_ganancia_pct", "precio_transporte_km", "version"]
        read_only_fields = ["id", "nombre"]
        extra_kwargs = val.mensajes("margen_ganancia_pct", "precio_transporte_km")


class CambioRegistroSerializer(serializers.ModelSerializer):
    usuario_display = serializers.SerializerMethodField()

    class Meta:
        model = CambioRegistro
        fields = [
            "id",
            "categoria",
            "objeto_tipo",
            "objeto_id",
            "objeto_label",
            "campo",
            "valor_anterior",
            "valor_nuevo",
            "usuario_display",
            "creado_en",
        ]

    def get_usuario_display(self, obj):
        if obj.usuario_id and obj.usuario:
            return obj.usuario.username
        return obj.usuario_nombre or "—"
