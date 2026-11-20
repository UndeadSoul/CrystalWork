"""Catalogo fijo por empresa.

Las series de aluminio, sus perfiles y los insumos son un conjunto FIJO (no se
agregan ni eliminan desde la interfaz): solo se editan sus valores. Esta funcion
garantiza que ese esqueleto exista para la empresa; el jefe luego completa pesos,
largos y precios.
"""

from decimal import Decimal

from .models import (
    Insumo,
    PerfilSerie,
    PlanchaVidrio,
    PrecioSerie,
    SerieAluminio,
)
from .validacion import LARGO_TIRA_ESTANDAR

SERIES_FIJAS = [
    ("L20", "Serie Linea 20"),
    ("L25", "Serie Linea 25"),
]

RIEL_INFERIOR_SIMPLE = "Riel inferior simple"

# Perfiles de cada serie: (nombre, en_paquete). El riel inferior simple es un
# perfil alternativo que no cuenta para el peso del paquete.
PERFILES_SERIE = [
    ("Riel superior", True),
    ("Riel Inferior", True),
    ("Jamba", True),
    ("Cabezal", True),
    ("Zocalo", True),
    ("Batiente", True),
    ("Traslapo", True),
    (RIEL_INFERIOR_SIMPLE, False),
]

# Orden canonico de los perfiles (se respeta en listas y hoja de corte).
PERFIL_ORDEN = [nombre for nombre, _ in PERFILES_SERIE]

# Pestillos y rodamientos dependen de la linea (L20 / L25): el codigo lleva el
# sufijo de la serie y core/pricing.py elige el que corresponde al tipo.
INSUMOS_FIJOS = [
    ("FELPA", "Felpa", "m"),
    ("BURLETE", "Burlete", "m"),
    ("PESTILLO_L20", "Pestillo Linea 20", "unidad"),
    ("PESTILLO_L25", "Pestillo Linea 25", "unidad"),
    ("CARACOL", "Caracol", "unidad"),
    ("RODAMIENTO_L20", "Rodamiento Linea 20", "unidad"),
    ("RODAMIENTO_L25", "Rodamiento Linea 25", "unidad"),
    ("TORNILLO", "Tornillo", "unidad"),
    ("SILICONA", "Silicona", "unidad"),
]


# ============================================================
# Valores por defecto (referencia) del catalogo
# ============================================================
# Se aplican al CREAR una empresa (poblar_catalogo_defecto) para que nazca lista
# para cotizar; el jefe los edita despues. No se re-aplican en las llamadas
# perezosas a asegurar_catalogo (que solo garantizan el esqueleto).

# Peso del paquete (kg) por serie.
PESO_SERIE_DEFECTO = {"L20": Decimal("124.99"), "L25": Decimal("145.99")}

# Peso de tira (kg) por perfil, POR SERIE (L20 y L25 difieren).
PESO_PERFIL_DEFECTO = {
    "L20": {
        "Riel superior": Decimal("19.73"),
        "Riel Inferior": Decimal("24.12"),
        "Jamba": Decimal("16.81"),
        "Cabezal": Decimal("14.47"),
        "Zocalo": Decimal("16.13"),
        "Batiente": Decimal("17.10"),
        "Traslapo": Decimal("16.63"),
        RIEL_INFERIOR_SIMPLE: Decimal("20.12"),
    },
    "L25": {
        "Riel superior": Decimal("22.73"),
        "Riel Inferior": Decimal("27.12"),
        "Jamba": Decimal("19.81"),
        "Cabezal": Decimal("17.47"),
        "Zocalo": Decimal("19.13"),
        "Batiente": Decimal("20.10"),
        "Traslapo": Decimal("19.63"),
        RIEL_INFERIOR_SIMPLE: Decimal("23.12"),
    },
}

# Precio del paquete (CLP) por serie y color.
PRECIO_SERIE_DEFECTO = {
    "L20": {
        "ALUMINIO": 101127,
        "BRONCE": 104440,
        "MADERA": 114374,
        "MATE": 103685,
        "TITANEO": 103948,
    },
    "L25": {
        "ALUMINIO": 111127,
        "BRONCE": 114440,
        "MADERA": 124374,
        "MATE": 113685,
        "TITANEO": 113948,
    },
}

# Planchas de vidrio: tamaño (m) y precio (CLP) por tipo.
PLANCHA_ANCHO_DEFECTO = Decimal("2.50")
PLANCHA_ALTO_DEFECTO = Decimal("1.80")
PRECIO_VIDRIO_DEFECTO = {
    "BRONCE_4": 38000,
    "BRONCE_5": 48000,
    "INCOLORO_4": 24000,
    "INCOLORO_5": 28000,
}

# codigo -> (precio_paquete, cantidad_paquete)
INSUMO_DEFECTO = {
    "FELPA": (22484, Decimal("600")),
    "BURLETE": (18921, Decimal("100")),
    "PESTILLO_L20": (1785, Decimal("1")),
    "PESTILLO_L25": (3808, Decimal("1")),
    "CARACOL": (13290, Decimal("5")),
    "RODAMIENTO_L20": (407, Decimal("1")),
    "RODAMIENTO_L25": (1131, Decimal("1")),
    "TORNILLO": (1900, Decimal("100")),
    "SILICONA": (6990, Decimal("1")),
}


def poblar_catalogo_defecto(empresa):
    """Catalogo completo con valores de referencia (pesos, tamaños y precios de
    aluminio, vidrio y agregados), para que una empresa nueva nazca lista para
    cotizar. Rellena solo lo vacio/faltante (no pisa lo que el jefe haya
    editado). Idempotente. Se llama al crear la empresa, no en cada lectura."""
    if empresa is None:
        return

    asegurar_catalogo(empresa)  # esqueleto fijo

    for serie in SerieAluminio.objects.filter(empresa=empresa):
        pesos = PESO_PERFIL_DEFECTO.get(serie.codigo, {})
        if not serie.peso_total_kg:
            serie.peso_total_kg = PESO_SERIE_DEFECTO.get(serie.codigo, Decimal("124.99"))
            serie.save(update_fields=["peso_total_kg"])
        for perfil in serie.perfiles.all():
            if not perfil.peso_kg:
                perfil.peso_kg = pesos.get(perfil.nombre, Decimal("15"))
                perfil.save(update_fields=["peso_kg"])
        for color, precio in PRECIO_SERIE_DEFECTO.get(serie.codigo, {}).items():
            PrecioSerie.objects.get_or_create(
                serie=serie, color=color, defaults={"precio": precio}
            )

    for tipo, precio in PRECIO_VIDRIO_DEFECTO.items():
        PlanchaVidrio.objects.get_or_create(
            empresa=empresa,
            tipo_vidrio=tipo,
            defaults={
                "ancho_plancha_m": PLANCHA_ANCHO_DEFECTO,
                "alto_plancha_m": PLANCHA_ALTO_DEFECTO,
                "precio": precio,
            },
        )

    for codigo, (precio, cantidad) in INSUMO_DEFECTO.items():
        ins = Insumo.objects.filter(empresa=empresa, codigo=codigo).first()
        if ins and not ins.precio_paquete:
            ins.precio_paquete = precio
            ins.cantidad_paquete = cantidad
            ins.save(update_fields=["precio_paquete", "cantidad_paquete"])


def asegurar_catalogo(empresa):
    """Crea (si faltan) las series fijas con sus 7 perfiles, los insumos fijos y
    el perfil individual del riel inferior simple. No pisa valores existentes,
    pero si fija el orden de los perfiles."""
    if empresa is None:
        return

    for codigo, nombre in SERIES_FIJAS:
        serie, _ = SerieAluminio.objects.get_or_create(
            empresa=empresa, codigo=codigo, defaults={"nombre": nombre}
        )
        for indice, (nombre_perfil, en_paquete) in enumerate(PERFILES_SERIE):
            perfil, _ = PerfilSerie.objects.get_or_create(
                serie=serie,
                nombre=nombre_perfil,
                defaults={
                    "orden": indice,
                    "peso_kg": 0,
                    "largo_tira_m": LARGO_TIRA_ESTANDAR,
                    "en_paquete": en_paquete,
                },
            )
            # Asegura el orden canonico tambien en perfiles ya existentes.
            if perfil.orden != indice:
                perfil.orden = indice
                perfil.save(update_fields=["orden"])

    for codigo, nombre, unidad in INSUMOS_FIJOS:
        Insumo.objects.get_or_create(
            empresa=empresa,
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "unidad": unidad,
                "precio_paquete": 0,
                "cantidad_paquete": 1,
            },
        )
