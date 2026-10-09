# Calculo de perfiles (hoja de corte) por tipo de ventana.
#
# Correderas: se diferencian por linea (20 / 25) y por tipo de riel (simple /
# lluvia). El perfil de riel inferior usado (simple vs estandar) se resuelve en
# core/pricing.py (OVERRIDES_PERFIL).
#
# Reglas de corte:
#   - Jamba: NO lleva descuento; su largo equivale a la altura de la ventana.
#   - Batiente y Traslapo: alto - descuento (depende del tipo).
#   - Riel superior/inferior: ancho - riel.
#   - Zocalo y Cabezal: ancho / 2.

# Offsets (en metros) por tipo de ventana.
#   riel  -> riel sup/inf = ancho - riel
#   alto  -> batiente/traslapo = alto - alto
_OFFSETS = {
    "Linea20simple": {"riel": 0.012, "alto": 0.027},
    "Linea20lluvia": {"riel": 0.012, "alto": 0.035},
    "Linea25simple": {"riel": 0.016, "alto": 0.035},
    "Linea25lluvia": {"riel": 0.016, "alto": 0.045},
}


def calc_windtype_profiles(windtype, width, height):
    # conversion de cm a m
    widthm = round(int(width) / 100, 3)
    heightm = round(int(height) / 100, 3)

    offsets = _OFFSETS.get(windtype)
    if not offsets:
        # Linea 42 (fijo / proyeccion): pendiente de definir.
        return []

    riel = round(widthm - offsets["riel"], 3)
    zocalo = round(widthm / 2, 3)
    batiente = round(heightm - offsets["alto"], 3)
    jamba = heightm  # sin descuento: equivale a la altura de la ventana

    return [
        {"name": "Riel superior", "length": riel, "cant": 1},
        {"name": "Riel Inferior", "length": riel, "cant": 1},
        {"name": "Zocalo", "length": zocalo, "cant": 2},
        {"name": "Cabezal", "length": zocalo, "cant": 2},
        {"name": "Batiente", "length": batiente, "cant": 2},
        {"name": "Traslapo", "length": batiente, "cant": 2},
        {"name": "Jamba", "length": jamba, "cant": 2},
    ]
