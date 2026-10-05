from django.conf import settings
from django.db import models

from users.models import Empresa


# ============================================================
# Opciones compartidas (ventanas y catalogo de precios)
# ============================================================


class TipoVentana(models.TextChoices):
    # El value coincide con la clave de projects/windowstypes.py
    CORREDERA_L20 = "Linea20", "Corredera (Linea 20)"
    CORREDERA_L25S = "Linea25simple", "Corredera (Linea 25 simple)"
    CORREDERA_LLUVIA_L25 = "Linea25lluvia", "Corredera lluvia (Linea 25)"
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
    nombre = models.CharField(max_length=150)
    rut = models.CharField(max_length=20, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nombre"]

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

    class Meta:
        verbose_name = "Serie de aluminio"
        verbose_name_plural = "Series de aluminio"
        unique_together = ("empresa", "codigo")
        ordering = ["codigo"]

    def __str__(self):
        return self.nombre

    @property
    def peso_serie(self):
        """Peso total de la serie = suma del peso de sus perfiles (kg)."""
        return sum((p.peso_kg for p in self.perfiles.all()), 0)


class PerfilSerie(models.Model):
    """Perfil (tira) que compone una serie, con su peso y largo de tira.
    El nombre debe coincidir con el que entrega windowstypes.py."""

    serie = models.ForeignKey(
        SerieAluminio, on_delete=models.CASCADE, related_name="perfiles"
    )
    nombre = models.CharField(
        max_length=60, help_text="Debe coincidir con la hoja de corte (ej: Jamba)."
    )
    peso_kg = models.DecimalField(max_digits=7, decimal_places=3)
    largo_tira_m = models.DecimalField(max_digits=6, decimal_places=3)

    class Meta:
        verbose_name = "Perfil de serie"
        verbose_name_plural = "Perfiles de serie"
        unique_together = ("serie", "nombre")
        ordering = ["serie", "nombre"]

    def __str__(self):
        return f"{self.serie.codigo} · {self.nombre}"


class PrecioSerie(models.Model):
    """Precio del paquete (serie completa) para un color dado."""

    serie = models.ForeignKey(
        SerieAluminio, on_delete=models.CASCADE, related_name="precios"
    )
    color = models.CharField(max_length=20, choices=ColorAluminio.choices)
    precio = models.DecimalField(
        max_digits=12, decimal_places=0, help_text="Precio del paquete completo (CLP)."
    )

    class Meta:
        verbose_name = "Precio de serie"
        verbose_name_plural = "Precios de serie"
        unique_together = ("serie", "color")

    def __str__(self):
        return f"{self.serie.codigo} {self.get_color_display()}: {self.precio}"


class PerfilIndividual(models.Model):
    """Perfil que se cotiza con precio propio, fuera del paquete.
    Caso: el riel inferior de la Linea 25 simple."""

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="perfiles_individuales"
    )
    codigo = models.CharField(max_length=30, help_text="Ej: RIEL_INF_SIMPLE.")
    nombre = models.CharField(max_length=80)
    largo_tira_m = models.DecimalField(max_digits=6, decimal_places=3)

    class Meta:
        verbose_name = "Perfil individual"
        verbose_name_plural = "Perfiles individuales"
        unique_together = ("empresa", "codigo")
        ordering = ["codigo"]

    def __str__(self):
        return self.nombre


class PrecioPerfilIndividual(models.Model):
    """Precio de la tira de un perfil individual, por color."""

    perfil = models.ForeignKey(
        PerfilIndividual, on_delete=models.CASCADE, related_name="precios"
    )
    color = models.CharField(max_length=20, choices=ColorAluminio.choices)
    precio = models.DecimalField(
        max_digits=12, decimal_places=0, help_text="Precio de la tira (CLP)."
    )

    class Meta:
        verbose_name = "Precio de perfil individual"
        verbose_name_plural = "Precios de perfil individual"
        unique_together = ("perfil", "color")

    def __str__(self):
        return f"{self.perfil.codigo} {self.get_color_display()}: {self.precio}"


class PlanchaVidrio(models.Model):
    """Plancha de vidrio por tipo, con sus dimensiones y precio."""

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="planchas_vidrio"
    )
    tipo_vidrio = models.CharField(max_length=20, choices=TipoVidrio.choices)
    ancho_plancha_m = models.DecimalField(max_digits=5, decimal_places=3)
    alto_plancha_m = models.DecimalField(max_digits=5, decimal_places=3)
    precio = models.DecimalField(
        max_digits=12, decimal_places=0, help_text="Precio de la plancha (CLP)."
    )

    class Meta:
        verbose_name = "Plancha de vidrio"
        verbose_name_plural = "Planchas de vidrio"
        unique_together = ("empresa", "tipo_vidrio")

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
        max_length=30, help_text="Ej: FELPA, PESTILLO, BURLETE."
    )
    nombre = models.CharField(max_length=80)
    unidad = models.CharField(
        max_length=20, blank=True, help_text="Informativo: m, unidad, etc."
    )
    precio_paquete = models.DecimalField(max_digits=12, decimal_places=0)
    cantidad_paquete = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text="Unidades o metros que trae el paquete/rollo.",
    )

    class Meta:
        verbose_name = "Insumo"
        verbose_name_plural = "Insumos"
        unique_together = ("empresa", "codigo")
        ordering = ["codigo"]

    def __str__(self):
        return self.nombre


# ============================================================
# Cotizaciones
# ============================================================


class Cotizacion(models.Model):
    """Cotizacion de ventanas. Es el proceso central del sistema."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"

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

    direccion_entrega = models.CharField(max_length=255, blank=True)
    requiere_transporte = models.BooleanField(default=False)
    distancia_transporte_km = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    comentarios = models.TextField(blank=True)
    monto_agregado = models.DecimalField(max_digits=12, decimal_places=0, default=0)

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

    class Meta:
        verbose_name = "Cotizacion"
        verbose_name_plural = "Cotizaciones"
        ordering = ["-fecha_ingreso"]

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
    ancho_cm = models.DecimalField(max_digits=7, decimal_places=1)
    alto_cm = models.DecimalField(max_digits=7, decimal_places=1)
    cantidad = models.PositiveIntegerField(default=1)

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

    def __str__(self):
        return f"{self.get_tipo_display()} {self.ancho_cm}x{self.alto_cm}"
