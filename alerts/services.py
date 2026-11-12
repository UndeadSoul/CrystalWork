"""Agrega todas las reglas de alertas de una empresa y las ordena."""

from django.utils import timezone

from . import reglas

# Mas severo primero.
_ORDEN_SEVERIDAD = {reglas.CRITICA: 0, reglas.ADVERTENCIA: 1}


def generar(empresa):
    """Lista de alertas de la empresa, ordenadas por severidad y antiguedad."""
    ahora = timezone.now()
    alertas = []
    for regla in reglas.REGLAS:
        alertas.extend(regla(empresa, ahora))
    alertas.sort(
        key=lambda a: (_ORDEN_SEVERIDAD.get(a["severidad"], 9), -(a["dias"] or 0))
    )
    return alertas


def resumen(alertas=None, empresa=None):
    """Conteos para el indicador (badge). Reusa `alertas` si ya se calcularon."""
    if alertas is None:
        alertas = generar(empresa)
    criticas = sum(1 for a in alertas if a["severidad"] == reglas.CRITICA)
    advertencias = sum(1 for a in alertas if a["severidad"] == reglas.ADVERTENCIA)
    return {"total": len(alertas), "criticas": criticas, "advertencias": advertencias}
