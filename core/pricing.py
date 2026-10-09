"""Motor de calculo de precios de ventanas.

Costo de una ventana = Aluminio + Vidrio (con merma + burlete) + Agregados.
Los PRECIOS viven en el catalogo editable (modelos de core); las CANTIDADES
y FORMULAS por tipo de ventana viven aqui, en codigo.
"""

from decimal import Decimal, ROUND_HALF_UP

from projects.windowstypes import calc_windtype_profiles

from . import models as m


class PricingError(Exception):
    """Faltan precios en el catalogo para calcular la ventana."""

    def __init__(self, faltantes):
        self.faltantes = faltantes
        super().__init__("; ".join(faltantes))


# Tipo de ventana -> serie de aluminio que usa.
SERIE_POR_TIPO = {
    "Linea20simple": "L20",
    "Linea20lluvia": "L20",
    "Linea25simple": "L25",
    "Linea25lluvia": "L25",
}

# Segun el tipo de ventana, que perfil de la serie usar en lugar del que entrega
# la hoja de corte. Los tipos "riel simple" usan el perfil "Riel inferior
# simple"; los "riel lluvia" usan el "Riel Inferior" estandar. El riel inferior
# simple es un perfil de la serie (fuera de paquete) que se cotiza con el mismo
# calculo por peso.
OVERRIDES_PERFIL = {
    "Linea20simple": {"Riel Inferior": "Riel inferior simple"},
    "Linea25simple": {"Riel Inferior": "Riel inferior simple"},
}

MERMA_VIDRIO = Decimal("1.20")


def _clp(value):
    """Redondea a peso chileno (entero)."""
    return Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def agregados_usados(tipo, ancho_m, alto_m):
    """[(codigo_insumo, cantidad_usada)] para un tipo de ventana.

    Cantidades de la Linea 20; por ahora se asumen iguales para las demas
    correderas hasta definir las propias de cada tipo.
    """
    felpa = (ancho_m * 6 + alto_m * 6) / 10
    if tipo in ("Linea20", "Linea25simple", "Linea25lluvia"):
        return [
            ("FELPA", felpa),
            ("PESTILLO", Decimal(2)),
            ("CARACOL", Decimal(1)),
            ("RODAMIENTO", Decimal(4)),
            ("TORNILLO", Decimal(24)),
            ("SILICONA", Decimal(1)),
        ]
    return []


def _costo_aluminio(empresa, tipo, color, ancho_cm, alto_cm, faltantes):
    serie_codigo = SERIE_POR_TIPO.get(tipo)
    if not serie_codigo:
        faltantes.append(f"No hay serie definida para el tipo {tipo}")
        return Decimal(0)

    serie = m.SerieAluminio.objects.filter(
        empresa=empresa, codigo=serie_codigo
    ).first()
    if not serie:
        faltantes.append(f"Serie {serie_codigo}")
        return Decimal(0)

    peso_serie = serie.peso_serie
    ps = m.PrecioSerie.objects.filter(serie=serie, color=color).first()
    precio_serie = ps.precio if ps else None
    if ps is None:
        faltantes.append(f"Precio de Serie {serie_codigo} en color {color}")
    if not peso_serie:
        faltantes.append(f"Pesos de perfiles de Serie {serie_codigo}")

    perfiles_map = {p.nombre: p for p in serie.perfiles.all()}
    overrides = OVERRIDES_PERFIL.get(tipo, {})

    total = Decimal(0)
    for corte in calc_windtype_profiles(tipo, ancho_cm, alto_cm):
        nombre = overrides.get(corte["name"], corte["name"])
        largo_usado = Decimal(str(corte["length"])) * corte["cant"]

        perfil = perfiles_map.get(nombre)
        if not perfil:
            faltantes.append(f"Perfil '{nombre}' en Serie {serie_codigo}")
            continue
        if precio_serie is None or not peso_serie or not perfil.largo_tira_m:
            continue
        precio_perfil = precio_serie * (perfil.peso_kg / peso_serie)
        total += precio_perfil * (largo_usado / perfil.largo_tira_m)

    return total


def _costo_vidrio(empresa, vidrio, ancho_m, alto_m, faltantes):
    total = Decimal(0)

    plancha = m.PlanchaVidrio.objects.filter(
        empresa=empresa, tipo_vidrio=vidrio
    ).first()
    if not plancha:
        faltantes.append(f"Plancha de vidrio {vidrio}")
    elif plancha.area_m2:
        crys_w = ancho_m / 2 - Decimal("0.054")
        crys_h = alto_m - Decimal("0.107")
        crys_m2 = crys_w * crys_h * 2
        total += crys_m2 * (plancha.precio / plancha.area_m2) * MERMA_VIDRIO

    burlete = m.Insumo.objects.filter(empresa=empresa, codigo="BURLETE").first()
    if not burlete:
        faltantes.append("Insumo BURLETE")
    elif burlete.cantidad_paquete:
        m_burlete = ancho_m * 2 + alto_m * 4
        total += m_burlete * (burlete.precio_paquete / burlete.cantidad_paquete)

    return total


def _costo_agregados(empresa, tipo, ancho_m, alto_m, faltantes):
    total = Decimal(0)
    for cod, cant in agregados_usados(tipo, ancho_m, alto_m):
        ins = m.Insumo.objects.filter(empresa=empresa, codigo=cod).first()
        if not ins:
            faltantes.append(f"Insumo {cod}")
            continue
        if ins.cantidad_paquete:
            total += ins.precio_paquete * (Decimal(cant) / ins.cantidad_paquete)
    return total


def calcular_costo_ventana(empresa, tipo, color, vidrio, ancho_cm, alto_cm):
    """Devuelve el desglose de costos. Lanza PricingError si falta algun dato."""
    faltantes = []
    ancho_m = Decimal(ancho_cm) / 100
    alto_m = Decimal(alto_cm) / 100

    costo_aluminio = _costo_aluminio(empresa, tipo, color, ancho_cm, alto_cm, faltantes)
    costo_vidrio = _costo_vidrio(empresa, vidrio, ancho_m, alto_m, faltantes)
    costo_agregados = _costo_agregados(empresa, tipo, ancho_m, alto_m, faltantes)

    if faltantes:
        raise PricingError(faltantes)

    costo_total = costo_aluminio + costo_vidrio + costo_agregados
    return {
        "costo_aluminio": _clp(costo_aluminio),
        "costo_vidrio": _clp(costo_vidrio),
        "costo_agregados": _clp(costo_agregados),
        "costo_total": _clp(costo_total),
    }


def fijar_precio_ventana(ventana, margen_pct):
    """Calcula y asigna costo/precio/subtotal a la ventana (no guarda)."""
    empresa = ventana.cotizacion.empresa
    try:
        r = calcular_costo_ventana(
            empresa,
            ventana.tipo,
            ventana.color,
            ventana.vidrio,
            ventana.ancho_cm,
            ventana.alto_cm,
        )
    except PricingError:
        ventana.costo_unitario = 0
        ventana.precio_unitario = 0
        ventana.subtotal = 0
        ventana.precio_calculado = False
        return ventana

    costo = r["costo_total"]
    factor = 1 + (Decimal(margen_pct) / 100)
    precio = _clp(costo * factor)
    ventana.costo_unitario = costo
    ventana.precio_unitario = precio
    ventana.subtotal = _clp(precio * ventana.cantidad)
    ventana.precio_calculado = True
    return ventana


def recalcular_cotizacion(cotizacion):
    """Recalcula precios de todas las ventanas y el total de la cotizacion."""
    margen = cotizacion.empresa.margen_ganancia_pct
    for v in cotizacion.ventanas.all():
        fijar_precio_ventana(v, margen)
        v.save(
            update_fields=[
                "costo_unitario",
                "precio_unitario",
                "subtotal",
                "precio_calculado",
            ]
        )
    cotizacion.recalcular_total()
    cotizacion.save(update_fields=["total", "costo_transporte"])
    return cotizacion
