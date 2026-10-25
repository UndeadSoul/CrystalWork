"""Hoja de corte: piezas de aluminio a cortar para un proyecto, reutilizando
projects/windowstypes.py. Cada ventana lleva un codigo simple (iniciales del
cliente + numero de ventana) para identificar sus piezas en el taller."""

from core.catalog import PERFIL_ORDEN
from core.models import VentanaCotizada
from core.pricing import OVERRIDES_PERFIL

from .windowstypes import calc_windtype_profiles

TIPO_LABELS = dict(VentanaCotizada._meta.get_field("tipo").choices)
COLOR_LABELS = dict(VentanaCotizada._meta.get_field("color").choices)


def _iniciales(nombre):
    palabras = [p for p in nombre.split() if p]
    if not palabras:
        return "CL"
    iniciales = "".join(p[0] for p in palabras[:3]).upper()
    return iniciales or "CL"


def _orden_perfil(nombre):
    try:
        return PERFIL_ORDEN.index(nombre)
    except ValueError:
        return len(PERFIL_ORDEN)


def hoja_de_corte(proyecto):
    """Filas: [{codigo, tipo_display, color_display, perfil, largo_mm, cantidad}].
    Separadas por ventana fisica: una linea de la cotizacion con cantidad N
    genera N ventanas, cada una con su codigo (iniciales cliente + numero
    correlativo) y sus piezas. Largos en milimetros."""
    iniciales = _iniciales(proyecto.cliente.nombre)
    filas = []
    numero = 0

    for ventana in proyecto.cotizacion.ventanas.order_by("pk"):
        overrides = OVERRIDES_PERFIL.get(ventana.tipo, {})
        perfiles = calc_windtype_profiles(
            ventana.tipo, ventana.ancho_mm, ventana.alto_mm
        )
        perfiles.sort(key=lambda p: _orden_perfil(p["name"]))
        for _ in range(ventana.cantidad):
            numero += 1
            codigo = f"{iniciales}{numero}"
            for p in perfiles:
                filas.append(
                    {
                        "codigo": codigo,
                        "tipo_display": TIPO_LABELS.get(ventana.tipo, ventana.tipo),
                        "color_display": COLOR_LABELS.get(ventana.color, ventana.color),
                        "perfil": overrides.get(p["name"], p["name"]),
                        "largo_mm": round(float(p["length"]) * 1000),
                        "cantidad": p["cant"],
                    }
                )
    return filas
