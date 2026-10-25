from django.conf import settings
from django.db import models
from django.db.models import Q

from core import validacion as val
from core.models import Cliente, Cotizacion
from users.models import Empresa


# A nivel de modulo para poder usarlos en el Meta (CHECK); Proyecto.Estado*
# son alias.
class EstadoProduccion(models.TextChoices):
    POR_INICIAR = "POR_INICIAR", "Por iniciar"
    EN_FABRICACION = "EN_FABRICACION", "En fabricación"
    TERMINADO = "TERMINADO", "Terminado"
    ENTREGADO = "ENTREGADO", "Entregado"
    # Se abandono el proyecto por alguna razon (motivo obligatorio).
    CANCELADO = "CANCELADO", "Cancelado"


class EstadoPago(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    ABONADO = "ABONADO", "Abonado"
    PAGADO = "PAGADO", "Pagado"


class Proyecto(models.Model):
    """Una cotizacion aprobada se convierte en un Proyecto (1 a 1), que se
    sigue a lo largo de la fabricacion.

    El pago se lleva con el detalle de cada Pago. `monto_abonado` y
    `estado_pago` se derivan de los pagos vigentes (projects/pagos.py) y se
    guardan para listar y filtrar sin sumar cada vez."""

    EstadoProduccion = EstadoProduccion
    EstadoPago = EstadoPago

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
    motivo_cancelacion = models.CharField(
        max_length=val.PAGO_COMENTARIO_MAX,
        blank=True,
        validators=val.validar_comentario_pago,
        help_text="Obligatorio si el proyecto esta Cancelado; vacio si no.",
    )
    estado_pago = models.CharField(
        max_length=20,
        choices=EstadoPago.choices,
        default=EstadoPago.PENDIENTE,
        help_text="Derivado de los pagos: sin pagos Pendiente, parcial Abonado, "
        "total Pagado.",
    )
    monto_abonado = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Suma de los pagos vigentes (CLP). Derivado de los pagos.",
    )
    # Se incrementa en cada registro/anulacion de pago: ademas de control de
    # concurrencia, el UPDATE bloquea el proyecto mientras se suma el saldo.
    version = models.PositiveIntegerField(default=1)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ["-fecha_creacion"]
        # El tope "<= total bruto" depende de la cotizacion (otra tabla): se
        # valida al registrar el pago (projects/pagos.py).
        constraints = [
            models.CheckConstraint(
                condition=Q(estado_produccion__in=EstadoProduccion.values),
                name="proyecto_estado_produccion_valido",
            ),
            models.CheckConstraint(
                condition=Q(estado_pago__in=EstadoPago.values),
                name="proyecto_estado_pago_valido",
            ),
            models.CheckConstraint(
                condition=Q(estado_pago=EstadoPago.PENDIENTE, monto_abonado=0)
                | Q(estado_pago=EstadoPago.ABONADO, monto_abonado__gt=0)
                | Q(estado_pago=EstadoPago.PAGADO, monto_abonado__gte=0),
                name="proyecto_abono_segun_estado_pago",
            ),
            models.CheckConstraint(
                condition=(
                    Q(estado_produccion=EstadoProduccion.CANCELADO)
                    & ~Q(motivo_cancelacion="")
                )
                | (
                    ~Q(estado_produccion=EstadoProduccion.CANCELADO)
                    & Q(motivo_cancelacion="")
                ),
                name="proyecto_motivo_si_cancelado",
            ),
        ]

    def __str__(self):
        return f"Proyecto #{self.pk} - {self.cliente}"


class Pago(models.Model):
    """Pago (abono) recibido para un proyecto. No se borra: si fue un error se
    anula (queda en el historial con quien, cuando y por que)."""

    proyecto = models.ForeignKey(
        Proyecto, on_delete=models.PROTECT, related_name="pagos"
    )
    monto = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[val.validar_monto_pago],
        help_text="CLP. No puede superar el saldo pendiente del proyecto.",
    )
    fecha = models.DateField(help_text="Fecha en que se recibió el pago.")
    comentario = models.CharField(
        max_length=val.PAGO_COMENTARIO_MAX,
        blank=True,
        validators=val.validar_comentario_pago,
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pagos_registrados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    anulado = models.BooleanField(default=False)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pagos_anulados",
    )
    anulado_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(
        max_length=val.PAGO_COMENTARIO_MAX,
        blank=True,
        validators=val.validar_comentario_pago,
    )

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["fecha", "creado_en"]
        constraints = [
            models.CheckConstraint(
                condition=Q(monto__range=(1, val.PAGO_MAX)),
                name="pago_monto_rango",
            ),
            models.CheckConstraint(
                condition=Q(anulado=False) | Q(anulado_en__isnull=False),
                name="pago_anulado_con_fecha",
            ),
        ]

    def __str__(self):
        return f"Pago #{self.pk} · Proyecto #{self.proyecto_id} · {self.monto}"
