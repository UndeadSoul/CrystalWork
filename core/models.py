from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Length

from users.models import Empresa

from . import validacion as val

# Permite usar campo__length en las restricciones CHECK.
models.CharField.register_lookup(Length)
models.TextField.register_lookup(Length)


def _largo_opcional(campo, minimo, maximo):
    """CHECK: el texto esta vacio o su largo esta en [minimo, maximo]."""
    return Q(**{campo: ""}) | Q(**{f"{campo}__length__range": (minimo, maximo)})


def _rango(nombre, campo, minimo, maximo, cero=False):
    """CHECK: el valor esta en [minimo, maximo] (o es 0 si cero=True)."""
    condicion = Q(**{f"{campo}__range": (minimo, maximo)})
    if cero:
        condicion |= Q(**{campo: 0})
    return models.CheckConstraint(condition=condicion, name=nombre)


def _opcion_valida(nombre, campo, choices):
    """CHECK: el valor es una de las opciones del campo."""
    return models.CheckConstraint(
        condition=Q(**{f"{campo}__in": choices.values}), name=nombre
    )


# ============================================================
# Opciones compartidas (ventanas y catalogo de precios)
# ============================================================


class TipoVentana(models.TextChoices):
    # El value coincide con la clave de projects/windowstypes.py
    CORREDERA_L20_SIMPLE = "Linea20simple", "Corredera Linea 20 Riel Simple"
    CORREDERA_L20_LLUVIA = "Linea20lluvia", "Corredera Linea 20 Riel Lluvia"
    CORREDERA_L25_SIMPLE = "Linea25simple", "Corredera Linea 25 Riel Simple"
    CORREDERA_L25_LLUVIA = "Linea25lluvia", "Corredera Linea 25 Riel Lluvia"
    FIJO_L42 = "Linea42f", "Fijo (Linea 42)"
    PROYECCION_L42 = "Linea42p", "Proyeccion (Linea 42)"


class ColorAluminio(models.TextChoices):
    BRONCE = "BRONCE", "Bronce (Negro)"
    MATE = "MATE", "Mate (Blanco)"
    ALUMINIO = "ALUMINIO", "Aluminio (Gris)"
    TITANEO = "TITANEO", "Titaneo"
    MADERA = "MADERA", "Madera (Cafe)"


class TipoVidrio(models.TextChoices):
    BRONCE_4 = "BRONCE_4", "Bronce 4mm"
    BRONCE_5 = "BRONCE_5", "Bronce 5mm"
    INCOLORO_4 = "INCOLORO_4", "Incoloro 4mm"
    INCOLORO_5 = "INCOLORO_5", "Incoloro 5mm"
    SOLARCOOL_4 = "SOLARCOOL_4", "SolarCool 4mm"
    SOLARCOOL_5 = "SOLARCOOL_5", "SolarCool 5mm"


# ============================================================
# Clientes
# ============================================================


class Cliente(models.Model):
    """Cliente de una empresa. Todas las cotizaciones y proyectos se ligan
    a un cliente."""

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="clientes",
    )
    nombre = models.CharField(max_length=val.NOMBRE_MAX, validators=val.validar_nombre)
    rut = models.CharField(
        max_length=val.RUT_MAX,
        validators=[val.validar_rut],
        help_text="Formato 12.345.678-9. Unico por empresa.",
    )
    telefono = models.CharField(
        max_length=val.TELEFONO_MAX, blank=True, validators=[val.validar_telefono]
    )
    email = models.EmailField(
        max_length=val.EMAIL_MAX, blank=True, validators=val.validar_email
    )
    direccion = models.CharField(
        max_length=val.DIRECCION_MAX, blank=True, validators=val.validar_direccion
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "rut"],
                name="cliente_rut_unico_por_empresa",
                violation_error_message="Ya existe un cliente con este RUT.",
            ),
            models.CheckConstraint(
                condition=Q(nombre__length__range=(val.NOMBRE_MIN, val.NOMBRE_MAX)),
                name="cliente_nombre_largo",
            ),
            models.CheckConstraint(
                # "1.234.567-8" .. "12.345.678-9"
                condition=Q(rut__length__range=(9, val.RUT_MAX)),
                name="cliente_rut_largo",
            ),
            models.CheckConstraint(
                condition=_largo_opcional(
                    "direccion", val.DIRECCION_MIN, val.DIRECCION_MAX
                ),
                name="cliente_direccion_largo",
            ),
            models.CheckConstraint(
                condition=_largo_opcional(
                    "telefono", val.TELEFONO_DIGITOS_MIN, val.TELEFONO_MAX
                ),
                name="cliente_telefono_largo",
            ),
        ]

    def __str__(self):
        return self.nombre


# ============================================================
# Catalogo de precios (editable por el jefe)
# ============================================================


class SerieAluminio(models.Model):
    """Paquete de perfiles de aluminio de una linea (p. ej. Serie 20).
    Se vende por serie (1 tira de cada perfil) y en distintos colores."""

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="series_aluminio"
    )
    codigo = models.CharField(
        max_length=10, help_text="Identificador corto, p. ej. L20 o L25."
    )
    nombre = models.CharField(max_length=100)
    peso_total_kg = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=0,
        validators=[val.validar_peso_serie],
        help_text="Peso del paquete (serie completa) en kg. Se usa como "
        "denominador en el calculo de precio de cada perfil. 0 = sin configurar.",
    )

    # Control de concurrencia optimista (edicion en bloque en Precios).
    version = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Serie de aluminio"
        verbose_name_plural = "Series de aluminio"
        unique_together = ("empresa", "codigo")
        ordering = ["codigo"]
        constraints = [
            _rango(
                "serie_peso_total_rango",
                "peso_total_kg",
                val.PESO_SERIE_MIN,
                val.PESO_SERIE_MAX,
                cero=True,
            ),
        ]

    def __str__(self):
        return self.nombre

    @property
    def peso_serie(self):
        """Peso del paquete (editable)."""
        return self.peso_total_kg


class PerfilSerie(models.Model):
    """Perfil (tira) que compone una serie, con su peso y largo de tira.
    El nombre debe coincidir con el que entrega windowstypes.py."""

    serie = models.ForeignKey(
        SerieAluminio, on_delete=models.CASCADE, related_name="perfiles"
    )
    nombre = models.CharField(
        max_length=60, help_text="Debe coincidir con la hoja de corte (ej: Jamba)."
    )
    orden = models.PositiveSmallIntegerField(
        default=0, help_text="Orden de aparicion en listas y hoja de corte."
    )
    peso_kg = models.DecimalField(
        max_digits=7,
        decimal_places=3,
        validators=[val.validar_peso_perfil],
        help_text="0 = sin configurar. No puede superar el peso total de la serie.",
    )
    largo_tira_m = models.DecimalField(
        max_digits=6, decimal_places=3, validators=[val.validar_largo_tira]
    )
    en_paquete = models.BooleanField(
        default=True,
        help_text="Si viene en el paquete (cuenta para el peso de la serie). "
        "El riel inferior simple va fuera del paquete.",
    )

    # Control de concurrencia optimista (edicion en bloque en Precios).
    version = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Perfil de serie"
        verbose_name_plural = "Perfiles de serie"
        unique_together = ("serie", "nombre")
        ordering = ["serie", "orden", "nombre"]
        # El tope "<= peso total de la serie" cruza tablas: se valida en el
        # serializer; aqui solo el rango absoluto.
        constraints = [
            _rango(
                "perfil_peso_rango",
                "peso_kg",
                val.PESO_PERFIL_MIN,
                val.PESO_SERIE_MAX,
                cero=True,
            ),
            _rango(
                "perfil_largo_tira_rango",
                "largo_tira_m",
                val.LARGO_TIRA_MIN,
                val.LARGO_TIRA_MAX,
            ),
        ]

    def __str__(self):
        return f"{self.serie.codigo} · {self.nombre}"


class PrecioSerie(models.Model):
    """Precio del paquete (serie completa) para un color dado."""

    serie = models.ForeignKey(
        SerieAluminio, on_delete=models.CASCADE, related_name="precios"
    )
    color = models.CharField(max_length=20, choices=ColorAluminio.choices)
    precio = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[val.validar_precio],
        help_text="Precio del paquete completo (CLP). 0 = sin precio.",
    )

    # Control de concurrencia optimista (edicion en bloque en Precios).
    version = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Precio de serie"
        verbose_name_plural = "Precios de serie"
        unique_together = ("serie", "color")
        constraints = [
            _rango("precio_serie_rango", "precio", 0, val.PRECIO_MAX),
            _opcion_valida("precio_serie_color_valido", "color", ColorAluminio),
        ]

    def __str__(self):
        return f"{self.serie.codigo} {self.get_color_display()}: {self.precio}"


class PlanchaVidrio(models.Model):
    """Plancha de vidrio por tipo, con sus dimensiones y precio."""

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="planchas_vidrio"
    )
    tipo_vidrio = models.CharField(max_length=20, choices=TipoVidrio.choices)
    ancho_plancha_m = models.DecimalField(
        max_digits=5, decimal_places=3, validators=[val.validar_plancha]
    )
    alto_plancha_m = models.DecimalField(
        max_digits=5, decimal_places=3, validators=[val.validar_plancha]
    )
    precio = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[val.validar_precio],
        help_text="Precio de la plancha (CLP). 0 = sin precio.",
    )

    # Control de concurrencia optimista (edicion en bloque en Precios).
    version = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Plancha de vidrio"
        verbose_name_plural = "Planchas de vidrio"
        unique_together = ("empresa", "tipo_vidrio")
        constraints = [
            _rango("plancha_ancho_rango", "ancho_plancha_m", val.PLANCHA_MIN, val.PLANCHA_MAX),
            _rango("plancha_alto_rango", "alto_plancha_m", val.PLANCHA_MIN, val.PLANCHA_MAX),
            _rango("plancha_precio_rango", "precio", 0, val.PRECIO_MAX),
            _opcion_valida("plancha_tipo_valido", "tipo_vidrio", TipoVidrio),
        ]

    def __str__(self):
        return f"{self.get_tipo_vidrio_display()}"

    @property
    def area_m2(self):
        return self.ancho_plancha_m * self.alto_plancha_m


class Insumo(models.Model):
    """Agregado o consumible con precio por paquete/rollo.
    El costo usado se calcula: precio_paquete * cantidad_usada / cantidad_paquete.
    La cantidad usada por tipo de ventana vive en el motor de calculo."""

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="insumos"
    )
    codigo = models.CharField(
        max_length=30, help_text="Ej: FELPA, PESTILLO_L20, BURLETE."
    )
    nombre = models.CharField(max_length=80)
    unidad = models.CharField(
        max_length=20, blank=True, help_text="Informativo: m, unidad, etc."
    )
    precio_paquete = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[val.validar_precio],
        help_text="0 = sin precio.",
    )
    cantidad_paquete = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[val.validar_cantidad_paquete],
        help_text="Unidades o metros que trae el paquete/rollo (mayor que 0).",
    )

    # Control de concurrencia optimista (edicion en bloque en Precios).
    version = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Insumo"
        verbose_name_plural = "Insumos"
        unique_together = ("empresa", "codigo")
        ordering = ["codigo"]
        constraints = [
            _rango("insumo_precio_rango", "precio_paquete", 0, val.PRECIO_MAX),
            models.CheckConstraint(
                condition=Q(cantidad_paquete__gte=val.CANTIDAD_PAQUETE_MIN),
                name="insumo_cantidad_paquete_positiva",
            ),
        ]

    def __str__(self):
        return self.nombre


# ============================================================
# Cotizaciones
# ============================================================


# A nivel de modulo para poder usarlo en el Meta (CHECK); Cotizacion.Estado
# es un alias.
class EstadoCotizacion(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    APROBADA = "APROBADA", "Aprobada"
    RECHAZADA = "RECHAZADA", "Rechazada"


class Cotizacion(models.Model):
    """Cotizacion de ventanas. Es el proceso central del sistema."""

    Estado = EstadoCotizacion

    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name="cotizaciones"
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="cotizaciones"
    )
    empleado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cotizaciones_creadas",
    )
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )

    direccion_entrega = models.CharField(
        max_length=val.DIRECCION_MAX, blank=True, validators=val.validar_direccion
    )
    requiere_transporte = models.BooleanField(default=False)
    distancia_transporte_km = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=val.validar_distancia,
        help_text="Obligatoria si requiere transporte; vacia si no.",
    )

    comentarios = models.TextField(
        max_length=val.COMENTARIO_MAX, blank=True, validators=val.validar_comentario
    )
    monto_agregado = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=val.validar_monto_agregado,
        help_text="Solo si hay un comentario que lo explique.",
    )

    # Totales calculados (CLP, sin decimales).
    costo_transporte = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=0, default=0)

    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    resuelta_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cotizaciones_resueltas",
    )

    # Control de concurrencia optimista: cada cambio (editar, aprobar,
    # rechazar, recalcular) incrementa la version y exige la version que el
    # usuario tenia en pantalla. Ver core/concurrencia.py.
    version = models.PositiveIntegerField(default=1)
    modificada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cotizaciones_modificadas",
        help_text="Ultimo usuario que la edito o resolvio.",
    )
    modificada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Cotizacion"
        verbose_name_plural = "Cotizaciones"
        ordering = ["-fecha_ingreso"]
        constraints = [
            models.CheckConstraint(
                condition=_largo_opcional(
                    "direccion_entrega", val.DIRECCION_MIN, val.DIRECCION_MAX
                ),
                name="cotizacion_direccion_largo",
            ),
            models.CheckConstraint(
                condition=Q(
                    requiere_transporte=False, distancia_transporte_km__isnull=True
                )
                | Q(
                    requiere_transporte=True,
                    distancia_transporte_km__range=(
                        val.DISTANCIA_MIN,
                        val.DISTANCIA_MAX,
                    ),
                ),
                name="cotizacion_distancia_segun_transporte",
            ),
            models.CheckConstraint(
                condition=Q(comentarios__length__lte=val.COMENTARIO_MAX),
                name="cotizacion_comentarios_largo",
            ),
            models.CheckConstraint(
                condition=Q(monto_agregado__range=(0, val.MONTO_AGREGADO_MAX)),
                name="cotizacion_monto_agregado_rango",
            ),
            models.CheckConstraint(
                condition=Q(monto_agregado=0) | ~Q(comentarios=""),
                name="cotizacion_monto_agregado_con_comentario",
            ),
            _opcion_valida("cotizacion_estado_valido", "estado", EstadoCotizacion),
        ]

    def __str__(self):
        return f"Cotizacion #{self.pk} - {self.cliente}"

    def recalcular_total(self):
        """total = suma de subtotales de ventanas + monto agregado + transporte."""
        subtotal_ventanas = sum((v.subtotal for v in self.ventanas.all()), 0)
        distancia = self.distancia_transporte_km or 0
        self.costo_transporte = (
            distancia * self.empresa.precio_transporte_km
            if self.requiere_transporte
            else 0
        )
        self.total = subtotal_ventanas + (self.monto_agregado or 0) + self.costo_transporte
        return self.total


class VentanaCotizada(models.Model):
    """Una ventana dentro de una cotizacion. El `tipo` usa la misma clave que
    projects/windowstypes.py para poder generar la hoja de corte."""

    cotizacion = models.ForeignKey(
        Cotizacion, on_delete=models.CASCADE, related_name="ventanas"
    )
    tipo = models.CharField(max_length=20, choices=TipoVentana.choices)
    color = models.CharField(max_length=20, choices=ColorAluminio.choices)
    vidrio = models.CharField(max_length=20, choices=TipoVidrio.choices)
    ancho_mm = models.PositiveIntegerField(
        help_text="Ancho de la ventana en mm.", validators=val.validar_dimension
    )
    alto_mm = models.PositiveIntegerField(
        help_text="Alto de la ventana en mm.", validators=val.validar_dimension
    )
    cantidad = models.PositiveIntegerField(default=1, validators=val.validar_cantidad)

    # Calculados por el motor de precios (CLP, sin decimales).
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    precio_calculado = models.BooleanField(
        default=False, help_text="False si falto algun precio en el catalogo."
    )

    class Meta:
        verbose_name = "Ventana cotizada"
        verbose_name_plural = "Ventanas cotizadas"
        constraints = [
            models.CheckConstraint(
                condition=Q(ancho_mm__range=(val.DIMENSION_MIN, val.DIMENSION_MAX))
                & Q(alto_mm__range=(val.DIMENSION_MIN, val.DIMENSION_MAX)),
                name="ventana_dimensiones_rango",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__range=(val.CANTIDAD_MIN, val.CANTIDAD_MAX)),
                name="ventana_cantidad_rango",
            ),
            _opcion_valida("ventana_tipo_valido", "tipo", TipoVentana),
            _opcion_valida("ventana_color_valido", "color", ColorAluminio),
            _opcion_valida("ventana_vidrio_valido", "vidrio", TipoVidrio),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.ancho_mm}x{self.alto_mm}mm"


# ============================================================
# Control de cambios (auditoria)
# ============================================================


class CambioRegistro(models.Model):
    """Registro de cambios para auditoria. Cubre cambios de estado en
    proyectos (fabricacion/pago) y cambios de valores en el catalogo de
    precios. Guarda valor anterior/nuevo, quien y cuando."""

    class Categoria(models.TextChoices):
        PROYECTO = "PROYECTO", "Proyecto"
        PRECIO = "PRECIO", "Precio"

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="cambios"
    )
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    # objeto_tipo/objeto_id permiten filtrar sin dependencia circular con projects.
    objeto_tipo = models.CharField(
        max_length=30, help_text="Ej: proyecto, serie, perfil, precio-serie, plancha, insumo, config."
    )
    objeto_id = models.PositiveIntegerField(null=True, blank=True)
    objeto_label = models.CharField(max_length=120)
    campo = models.CharField(max_length=60)
    valor_anterior = models.CharField(max_length=120, blank=True)
    valor_nuevo = models.CharField(max_length=120, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cambios_realizados",
    )
    usuario_nombre = models.CharField(
        max_length=150, blank=True, help_text="Snapshot del usuario por si se elimina."
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de cambio"
        verbose_name_plural = "Registros de cambios"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["empresa", "categoria", "objeto_tipo", "objeto_id"]),
        ]

    def __str__(self):
        return f"{self.objeto_label} · {self.campo}: {self.valor_anterior} → {self.valor_nuevo}"
