"""Ajusta el abono de los proyectos existentes a las reglas nuevas antes de
crear sus restricciones (0005):
  - Pendiente: abono 0.
  - Abonado sin monto (0): vuelve a Pendiente.
  - Abonado con monto >= total bruto: pasa a Pagado.
  - Abono negativo: 0.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations


def _bruto(neto):
    neto = Decimal(neto or 0)
    return neto + (neto * 19 / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def sanear(apps, schema_editor):
    Proyecto = apps.get_model("projects", "Proyecto")
    for p in Proyecto.objects.select_related("cotizacion"):
        estado, abono = p.estado_pago, max(p.monto_abonado or 0, 0)
        if estado == "PENDIENTE":
            abono = 0
        elif estado == "ABONADO":
            if abono == 0:
                estado = "PENDIENTE"
            elif abono >= _bruto(p.cotizacion.total):
                estado = "PAGADO"
        if (estado, abono) != (p.estado_pago, p.monto_abonado):
            p.estado_pago, p.monto_abonado = estado, abono
            p.save(update_fields=["estado_pago", "monto_abonado"])


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0003_proyecto_monto_abonado"),
    ]

    operations = [
        migrations.RunPython(sanear, migrations.RunPython.noop),
    ]
