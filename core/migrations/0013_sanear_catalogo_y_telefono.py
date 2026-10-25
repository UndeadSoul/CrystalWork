"""Ajusta los datos existentes a las reglas del catalogo, la configuracion de
la empresa y el telefono del cliente antes de crear sus restricciones (0014 y
users.0003). Valores copiados aqui a proposito (ver 0011).

  - Numeros fuera de rango se acotan al limite mas cercano. En precios y
    pesos el 0 se conserva ("sin configurar").
  - Telefono: se dejan solo digitos, espacios y "+"; si no queda un numero de
    8 a 12 digitos, queda vacio.
"""

import re
from decimal import Decimal

from django.db import migrations


def _acotar(valor, minimo, maximo, cero=False):
    if valor is None:
        return valor
    if cero and valor == 0:
        return valor
    return max(minimo, min(maximo, valor))


def _telefono(texto):
    limpio = " ".join(re.sub(r"[^0-9 +]", "", texto or "").split())
    limpio = limpio[:1] + limpio[1:].replace("+", "")
    digitos = sum(ch.isdigit() for ch in limpio)
    return limpio if 8 <= digitos <= 12 and len(limpio) <= 20 else ""


def _ajustar(qs, campos):
    """campos: {campo: (min, max, cero)}"""
    for obj in qs:
        cambios = []
        for campo, (minimo, maximo, cero) in campos.items():
            antes = getattr(obj, campo)
            despues = _acotar(antes, minimo, maximo, cero)
            if despues != antes:
                setattr(obj, campo, despues)
                cambios.append(campo)
        if cambios:
            obj.save(update_fields=cambios)


def sanear(apps, schema_editor):
    m = lambda nombre: apps.get_model("core", nombre)  # noqa: E731
    D = Decimal

    _ajustar(
        apps.get_model("users", "Empresa").objects.all(),
        {
            "margen_ganancia_pct": (D("0"), D("200"), False),
            "precio_transporte_km": (D("0"), D("50000"), False),
        },
    )
    _ajustar(
        m("SerieAluminio").objects.all(),
        {"peso_total_kg": (D("0.1"), D("100"), True)},
    )
    _ajustar(
        m("PerfilSerie").objects.all(),
        {
            "peso_kg": (D("0.001"), D("100"), True),
            "largo_tira_m": (D("1"), D("7"), False),
        },
    )
    _ajustar(m("PrecioSerie").objects.all(), {"precio": (D("0"), D("10000000"), False)})
    _ajustar(
        m("PlanchaVidrio").objects.all(),
        {
            "ancho_plancha_m": (D("0.5"), D("4"), False),
            "alto_plancha_m": (D("0.5"), D("4"), False),
            "precio": (D("0"), D("10000000"), False),
        },
    )
    _ajustar(
        m("Insumo").objects.all(),
        {
            "precio_paquete": (D("0"), D("10000000"), False),
            "cantidad_paquete": (D("0.001"), D("999999999"), False),
        },
    )

    for c in m("Cliente").objects.exclude(telefono=""):
        nuevo = _telefono(c.telefono)
        if nuevo != c.telefono:
            c.telefono = nuevo
            c.save(update_fields=["telefono"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_validaciones"),
        ("users", "0002_empresa_margen_ganancia_pct_and_more"),
    ]

    operations = [
        migrations.RunPython(sanear, migrations.RunPython.noop),
    ]
