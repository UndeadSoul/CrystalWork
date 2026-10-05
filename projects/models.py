from django.db import models

from core.models import Cliente, Cotizacion
from users.models import Empresa


class Proyecto(models.Model):
    """Una cotizacion aprobada se convierte en un Proyecto (1 a 1), que se
    sigue a lo largo de la fabricacion."""

    class EstadoProduccion(models.TextChoices):
        POR_INICIAR = "POR_INICIAR", "Por iniciar"
        EN_FABRICACION = "EN_FABRICACION", "En fabricacion"
        TERMINADO = "TERMINADO", "Terminado"
        ENTREGADO = "ENTREGADO", "Entregado"

    cotizacion = models.OneToOneField(
        Cotizacion, on_delete=models.PROTECT, related_name="proyecto"
    )
    # Denormalizados para filtrar y listar sin recorrer la cotizacion.
    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name="proyectos"
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="proyectos"
    )
    estado_produccion = models.CharField(
        max_length=20,
        choices=EstadoProduccion.choices,
        default=EstadoProduccion.POR_INICIAR,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Proyecto #{self.pk} - {self.cliente}"
