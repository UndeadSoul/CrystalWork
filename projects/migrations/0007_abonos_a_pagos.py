"""Convierte el abono de cada proyecto existente en un registro de Pago, para
que monto_abonado y estado_pago pasen a derivarse de los pagos:
  - Abonado: un pago por el monto abonado.
  - Pagado: un pago por el total bruto (antes podia quedar marcado como
    pagado con un abono menor).
  - Pendiente: sin pagos.
La fecha del pago es la de creacion del proyecto (no se conocia la real), en
hora de Chile (settings.TIME_ZONE): fecha_creacion esta en UTC.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations
from django.utils import timezone

COMENTARIO = "Registrado antes del detalle de pagos"


def _bruto(neto):
    neto = Decimal(neto or 0)
    return neto + (neto * 19 / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def convertir(apps, schema_editor):
    Proyecto = apps.get_model("projects", "Proyecto")
    Pago = apps.get_model("projects", "Pago")
    for p in Proyecto.objects.select_related("cotizacion").filter(
        estado_pago__in=["ABONADO", "PAGADO"]
    ):
        bruto = _bruto(p.cotizacion.total)
        monto = bruto if p.estado_pago == "PAGADO" else min(p.monto_abonado, bruto)
        if monto <= 0:
            continue
        Pago.objects.create(
            proyecto=p,
            monto=monto,
            fecha=timezone.localtime(p.fecha_creacion).date(),
            comentario=COMENTARIO,
        )
        p.monto_abonado = monto
        p.estado_pago = "PAGADO" if monto >= bruto else "ABONADO"
        p.save(update_fields=["monto_abonado", "estado_pago"])


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0006_pagos"),
    ]

    operations = [
        migrations.RunPython(convertir, migrations.RunPython.noop),
    ]
