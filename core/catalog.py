"""Catalogo fijo por empresa.

Las series de aluminio, sus perfiles y los insumos son un conjunto FIJO (no se
agregan ni eliminan desde la interfaz): solo se editan sus valores. Esta funcion
garantiza que ese esqueleto exista para la empresa; el jefe luego completa pesos,
largos y precios.
"""

from decimal import Decimal

from .models import Insumo, PerfilSerie, SerieAluminio

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

INSUMOS_FIJOS = [
    ("FELPA", "Felpa", "m"),
    ("BURLETE", "Burlete", "m"),
    ("PESTILLO", "Pestillo", "unidad"),
    ("CARACOL", "Caracol", "unidad"),
    ("RODAMIENTO", "Rodamiento", "unidad"),
    ("TORNILLO", "Tornillo", "unidad"),
    ("SILICONA", "Silicona", "unidad"),
]


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
                    "largo_tira_m": Decimal("5.8"),
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
