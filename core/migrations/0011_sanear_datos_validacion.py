"""Ajusta los datos existentes a las nuevas reglas de validacion antes de crear
las restricciones de la BD (0012). Los valores se copian aqui (y no se importan
de core/validacion.py) para que esta migracion no cambie si las reglas cambian.

Criterios (los datos actuales son de ejemplo):
  - Textos: se quitan los caracteres no permitidos y se recorta al maximo.
    Un nombre que queda corto pasa a "Cliente sin nombre"; una direccion corta
    o un email invalido quedan vacios.
  - RUT invalido, vacio o repetido en la empresa: se asigna uno valido de
    reemplazo (cuerpo 90.000.000 + id) para cumplir "obligatorio y unico".
  - Numeros fuera de rango se acotan al limite mas cercano.
  - Monto agregado sin comentario: se agrega el comentario "Monto agregado
    sin detalle".
"""

import re
from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations

LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
NO_NOMBRE = re.compile(rf"[^{LETRAS} ]")
NO_DIRECCION = re.compile(rf"[^{LETRAS}0-9 .,#°/\-]")
NO_COMENTARIO = re.compile(rf"[^{LETRAS}0-9\s.,:¿?¡!()°#$%+/\-]")
EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\Z")


def _espacios(texto):
    return " ".join(texto.split())


def _limpiar(texto, prohibidos, minimo, maximo):
    limpio = _espacios(prohibidos.sub("", texto or ""))[:maximo].strip()
    return limpio if len(limpio) >= minimo else ""


def _dv(cuerpo):
    suma, mult = 0, 2
    for d in reversed(str(cuerpo)):
        suma += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    resto = 11 - (suma % 11)
    return {11: "0", 10: "K"}.get(resto, str(resto))


def _rut(texto):
    """Devuelve el RUT formateado si es valido, o None."""
    limpio = (texto or "").replace(".", "").replace("-", "").strip().upper()
    if not 2 <= len(limpio) <= 9 or not limpio[:-1].isdigit():
        return None
    cuerpo, dv = limpio[:-1], limpio[-1]
    if _dv(cuerpo) != dv:
        return None
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}"


def _acotar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def sanear(apps, schema_editor):
    Cliente = apps.get_model("core", "Cliente")
    Cotizacion = apps.get_model("core", "Cotizacion")
    Ventana = apps.get_model("core", "VentanaCotizada")

    usados = {}  # empresa_id -> set(rut)
    for c in Cliente.objects.order_by("pk"):
        c.nombre = _limpiar(c.nombre, NO_NOMBRE, 5, 50) or "Cliente sin nombre"
        c.direccion = _limpiar(c.direccion, NO_DIRECCION, 5, 100)
        if not EMAIL.match(c.email or "") or len(c.email) > 100:
            c.email = ""
        ruts = usados.setdefault(c.empresa_id, set())
        rut = _rut(c.rut)
        cuerpo = 90_000_000 + c.pk
        while rut is None or rut in ruts:
            rut = _rut(f"{cuerpo}{_dv(cuerpo)}")
            cuerpo += 1
        ruts.add(rut)
        c.rut = rut
        c.save(update_fields=["nombre", "direccion", "email", "rut"])

    for q in Cotizacion.objects.all():
        q.direccion_entrega = _limpiar(q.direccion_entrega, NO_DIRECCION, 5, 100)
        q.comentarios = NO_COMENTARIO.sub("", q.comentarios or "")[:1000].strip()
        if q.requiere_transporte and q.distancia_transporte_km is not None:
            q.distancia_transporte_km = _acotar(
                Decimal(q.distancia_transporte_km), Decimal("0.1"), Decimal("500")
            ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        else:
            q.requiere_transporte = False
            q.distancia_transporte_km = None
        q.monto_agregado = _acotar(q.monto_agregado or 0, 0, 10_000_000)
        if q.monto_agregado > 0 and not q.comentarios:
            q.comentarios = "Monto agregado sin detalle"
        q.save(
            update_fields=[
                "direccion_entrega",
                "comentarios",
                "requiere_transporte",
                "distancia_transporte_km",
                "monto_agregado",
            ]
        )

    for v in Ventana.objects.all():
        v.ancho_mm = _acotar(v.ancho_mm, 300, 3000)
        v.alto_mm = _acotar(v.alto_mm, 300, 3000)
        v.cantidad = _acotar(v.cantidad, 1, 10)
        v.save(update_fields=["ancho_mm", "alto_mm", "cantidad"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_insumos_por_linea"),
    ]

    operations = [
        migrations.RunPython(sanear, migrations.RunPython.noop),
    ]
