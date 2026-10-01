from django.conf import settings
from django.db import models

from users.models import Empresa


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


class Cotizacion(models.Model):
    """Cotizacion de ventanas. Es el proceso central del sistema.

    Una cotizacion la ingresa un trabajador (empleado), nace en estado
    PENDIENTE y queda a la espera de que un jefe la apruebe o rechace.
    Al aprobarse se convertira en un Proyecto (fase posterior).
    """

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

    # Entrega / instalacion
    direccion_entrega = models.CharField(max_length=255, blank=True)
    requiere_transporte = models.BooleanField(default=False)
    distancia_transporte_km = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    comentarios = models.TextField(blank=True)
    # Costos extra no considerados en las ventanas (CLP, sin decimales).
    monto_agregado = models.DecimalField(max_digits=12, decimal_places=0, default=0)

    # Total calculado. Mientras no existan precios, equivale al monto agregado.
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
        """Suma ventanas + monto agregado + transporte.

        Los precios aun no estan definidos, por lo que los subtotales de las
        ventanas y el costo de transporte son 0. Cuando existan precios, aqui
        se sumara: sum(ventanas.subtotal) + monto_agregado +
        distancia_transporte_km * precio_km.
        """
        subtotal_ventanas = sum((v.subtotal for v in self.ventanas.all()), 0)
        self.total = (self.monto_agregado or 0) + subtotal_ventanas
        return self.total


class VentanaCotizada(models.Model):
    """Una ventana dentro de una cotizacion. El `tipo` usa la misma clave que
    projects/windowstypes.py para poder generar la hoja de corte."""

    class Tipo(models.TextChoices):
        CORREDERA_L20 = "Linea20", "Corredera (Linea 20)"
        CORREDERA_L25S = "Linea25simple", "Corredera (Linea 25 simple)"
        CORREDERA_LLUVIA_L25 = "Linea25lluvia", "Corredera lluvia (Linea 25)"
        FIJO_L42 = "Linea42f", "Fijo (Linea 42)"
        PROYECCION_L42 = "Linea42p", "Proyeccion (Linea 42)"

    class Color(models.TextChoices):
        BRONCE = "BRONCE", "Bronce (Negro)"
        MATE = "MATE", "Mate (Blanco)"
        ALUMINIO = "ALUMINIO", "Aluminio (Gris)"
        TITANEO = "TITANEO", "Titaneo"
        MADERA = "MADERA", "Madera (Cafe)"

    class Vidrio(models.TextChoices):
        BRONCE_4 = "BRONCE_4", "Bronce 4mm"
        BRONCE_5 = "BRONCE_5", "Bronce 5mm"
        INCOLORO_4 = "INCOLORO_4", "Incoloro 4mm"
        INCOLORO_5 = "INCOLORO_5", "Incoloro 5mm"
        SOLARCOOL_4 = "SOLARCOOL_4", "SolarCool 4mm"
        SOLARCOOL_5 = "SOLARCOOL_5", "SolarCool 5mm"

    cotizacion = models.ForeignKey(
        Cotizacion, on_delete=models.CASCADE, related_name="ventanas"
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    color = models.CharField(max_length=20, choices=Color.choices)
    vidrio = models.CharField(max_length=20, choices=Vidrio.choices)
    ancho_cm = models.DecimalField(max_digits=7, decimal_places=1)
    alto_cm = models.DecimalField(max_digits=7, decimal_places=1)
    cantidad = models.PositiveIntegerField(default=1)
    # Subtotal calculado (precio unitario * cantidad). 0 hasta definir precios.
    subtotal = models.DecimalField(max_digits=12, decimal_places=0, default=0)

    class Meta:
        verbose_name = "Ventana cotizada"
        verbose_name_plural = "Ventanas cotizadas"

    def __str__(self):
        return f"{self.get_tipo_display()} {self.ancho_cm}x{self.alto_cm}"
