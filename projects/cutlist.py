"""Hoja de corte: consolida las piezas de aluminio a cortar para un proyecto,
reutilizando projects/windowstypes.py."""

from collections import defaultdict

from core.models import VentanaCotizada

from .windowstypes import calc_windtype_profiles

TIPO_LABELS = dict(VentanaCotizada._meta.get_field("tipo").choices)


def hoja_de_corte(proyecto):
    """Lista consolidada de piezas: [{tipo, tipo_display, perfil, largo_m, cantidad}].
    Agrupa cortes identicos (mismo tipo, perfil y largo) sumando cantidades."""
    agg = defaultdict(int)
    for ventana in proyecto.cotizacion.ventanas.all():
        perfiles = calc_windtype_profiles(
            ventana.tipo, ventana.ancho_cm, ventana.alto_cm
        )
        for p in perfiles:
            largo = round(float(p["length"]), 3)
            key = (ventana.tipo, p["name"], largo)
            agg[key] += p["cant"] * ventana.cantidad

    piezas = [
        {
            "tipo": tipo,
            "tipo_display": TIPO_LABELS.get(tipo, tipo),
            "perfil": perfil,
            "largo_m": largo,
            "cantidad": cantidad,
        }
        for (tipo, perfil, largo), cantidad in sorted(agg.items())
    ]
    return piezas
