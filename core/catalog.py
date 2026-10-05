"""Catalogo fijo por empresa.

Las series de aluminio y los insumos son un conjunto FIJO (no se agregan ni
eliminan desde la interfaz): solo se editan sus valores. Esta funcion garantiza
que ese esqueleto exista para la empresa; el jefe luego completa perfiles,
pesos, largos y precios.
"""

from decimal import Decimal

from .models import Insumo, PerfilIndividual, SerieAluminio

SERIES_FIJAS = [
    ("L20", "Serie Linea 20"),
    ("L25", "Serie Linea 25"),
]

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
    """Crea (si faltan) las series fijas, los insumos fijos y el perfil
    individual del riel inferior simple. No pisa valores existentes."""
    if empresa is None:
        return

    for codigo, nombre in SERIES_FIJAS:
        SerieAluminio.objects.get_or_create(
            empresa=empresa, codigo=codigo, defaults={"nombre": nombre}
        )

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

    PerfilIndividual.objects.get_or_create(
        empresa=empresa,
        codigo="RIEL_INF_SIMPLE",
        defaults={"nombre": "Riel inferior simple", "largo_tira_m": Decimal("5.8")},
    )
