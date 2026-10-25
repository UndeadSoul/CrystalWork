"""Pagos de proyectos: registrar y anular, recalculando el estado de pago.

Reglas:
  - monto_abonado = suma de los pagos vigentes (no anulados).
  - estado_pago: 0 -> Pendiente; menos que el total bruto -> Abonado;
    total bruto -> Pagado.
  - Un pago no puede superar el saldo pendiente.
  - Un pago no se borra: se anula con un motivo.

Concurrencia: antes de leer el saldo se "toma" el proyecto con un UPDATE de
su version. Ese UPDATE bloquea la fila (Postgres) o la base (SQLite) hasta el
fin de la transaccion, asi dos pagos simultaneos no pueden superar juntos el
total. Todo ocurre dentro de transaction.atomic.
"""

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.audit import registrar_cambio
from core.concurrencia import Conflicto
from core.models import CambioRegistro
from core.pricing import desglose_iva

from .models import Pago, Proyecto


def total_bruto(proyecto):
    return desglose_iva(proyecto.cotizacion.total)[2]


def _clp(valor):
    return "$" + f"{int(valor):,}".replace(",", ".")


def _tomar(proyecto):
    """Bloquea el proyecto hasta el fin de la transaccion y lo refresca."""
    Proyecto.objects.filter(pk=proyecto.pk).update(version=F("version") + 1)
    proyecto.refresh_from_db()
    return proyecto


def _registrar(proyecto, usuario, campo, antes, despues):
    registrar_cambio(
        empresa=proyecto.empresa,
        usuario=usuario,
        categoria=CambioRegistro.Categoria.PROYECTO,
        objeto_tipo="proyecto",
        objeto_id=proyecto.pk,
        objeto_label=f"Proyecto #{proyecto.pk}",
        campo=campo,
        valor_anterior=antes,
        valor_nuevo=despues,
    )


def _recalcular(proyecto, usuario):
    """Deriva monto_abonado y estado_pago de los pagos vigentes y registra el
    cambio de estado en el control de cambios."""
    pagado = (
        proyecto.pagos.filter(anulado=False).aggregate(s=Sum("monto"))["s"] or 0
    )
    bruto = total_bruto(proyecto)
    if pagado == 0:
        estado = Proyecto.EstadoPago.PENDIENTE
    elif pagado >= bruto:
        estado = Proyecto.EstadoPago.PAGADO
    else:
        estado = Proyecto.EstadoPago.ABONADO

    if estado != proyecto.estado_pago:
        _registrar(
            proyecto,
            usuario,
            "Pago",
            proyecto.get_estado_pago_display(),
            Proyecto.EstadoPago(estado).label,
        )
    proyecto.monto_abonado = pagado
    proyecto.estado_pago = estado
    proyecto.save(update_fields=["monto_abonado", "estado_pago"])


@transaction.atomic
def registrar_pago(proyecto, usuario, monto, fecha, comentario=""):
    _tomar(proyecto)
    if proyecto.estado_produccion == Proyecto.EstadoProduccion.CANCELADO:
        raise ValidationError(
            {"detail": ["El proyecto está cancelado: no se registran pagos nuevos."]}
        )
    saldo = total_bruto(proyecto) - proyecto.monto_abonado
    # Listas: mismo formato {campo: [mensaje]} que los errores de serializers.
    if saldo <= 0:
        raise ValidationError({"monto": ["El proyecto ya está pagado por completo."]})
    if monto > saldo:
        raise ValidationError(
            {"monto": [f"Supera el saldo pendiente ({_clp(saldo)})."]}
        )
    pago = Pago.objects.create(
        proyecto=proyecto,
        monto=monto,
        fecha=fecha,
        comentario=comentario,
        registrado_por=usuario,
    )
    _registrar(
        proyecto, usuario, "Pago registrado", "", f"{_clp(monto)} ({fecha:%d-%m-%Y})"
    )
    _recalcular(proyecto, usuario)
    return pago


@transaction.atomic
def anular_pago(pago, usuario, motivo):
    proyecto = _tomar(pago.proyecto)
    pago.refresh_from_db()
    if pago.anulado:
        quien = pago.anulado_por.username if pago.anulado_por else "otro usuario"
        raise Conflicto(f"Este pago ya fue anulado por {quien}.")
    pago.anulado = True
    pago.anulado_por = usuario
    pago.anulado_en = timezone.now()
    pago.motivo_anulacion = motivo
    pago.save(
        update_fields=["anulado", "anulado_por", "anulado_en", "motivo_anulacion"]
    )
    _registrar(
        proyecto,
        usuario,
        "Pago anulado",
        f"{_clp(pago.monto)} ({pago.fecha:%d-%m-%Y})",
        f"Anulado: {motivo}",
    )
    _recalcular(proyecto, usuario)
    return pago
