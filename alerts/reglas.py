"""Reglas de alertas: cada funcion recibe la empresa y el instante actual y
devuelve una lista de alertas (dicts). Son de solo lectura: no guardan nada,
se calculan a partir de los datos vigentes.

Para agregar una alerta nueva: escribe una funcion con esta misma firma y
agregala a REGLAS.
"""

from datetime import timedelta

from core.models import Cotizacion
from projects.models import Proyecto

CRITICA = "critica"
ADVERTENCIA = "advertencia"


def _alerta(tipo, severidad, titulo, detalle, ruta, dias=None):
    return {
        # Identifica la alerta de forma estable (el frontend recuerda cuáles
        # fueron pospuestas usando esta clave).
        "clave": f"{tipo}:{ruta}",
        "tipo": tipo,
        "severidad": severidad,
        "titulo": titulo,
        "detalle": detalle,
        "ruta": ruta,
        "dias": dias,
    }


def cotizaciones_pendientes(empresa, ahora):
    """Cotizaciones en estado PENDIENTE sin resolver hace demasiado."""
    umbral = empresa.alerta_cotizacion_dias
    limite = ahora - timedelta(days=umbral)
    qs = (
        Cotizacion.objects.filter(
            empresa=empresa,
            estado=Cotizacion.Estado.PENDIENTE,
            fecha_ingreso__lte=limite,
        )
        .select_related("cliente")
        .order_by("fecha_ingreso")
    )
    alertas = []
    for c in qs:
        dias = (ahora - c.fecha_ingreso).days
        severidad = CRITICA if dias >= 2 * umbral else ADVERTENCIA
        alertas.append(
            _alerta(
                "cotizacion_pendiente",
                severidad,
                f"Cotización #{c.id} sin aprobar",
                f"{c.cliente.nombre} · hace {dias} días",
                f"/cotizaciones/{c.id}",
                dias,
            )
        )
    return alertas


def proyectos_estancados(empresa, ahora):
    """Proyectos activos que no cambian de estado de fabricacion."""
    Estado = Proyecto.EstadoProduccion
    limite = ahora - timedelta(days=empresa.alerta_estancado_dias)
    qs = (
        Proyecto.objects.filter(empresa=empresa, estado_actualizado_en__lte=limite)
        .exclude(estado_produccion__in=[Estado.ENTREGADO, Estado.CANCELADO])
        .select_related("cliente")
        .order_by("estado_actualizado_en")
    )
    alertas = []
    for p in qs:
        dias = (ahora - p.estado_actualizado_en).days
        alertas.append(
            _alerta(
                "proyecto_estancado",
                ADVERTENCIA,
                f"Proyecto #{p.id} estancado en {p.get_estado_produccion_display()}",
                f"{p.cliente.nombre} · {dias} días sin avanzar",
                f"/proyectos/{p.id}",
                dias,
            )
        )
    return alertas


def proyectos_sin_pago(empresa, ahora):
    """Proyectos en marcha con saldo y sin ningun abono tras varios dias.
    Los entregados sin pagar los cubre `entregados_sin_cobrar` (critica)."""
    EstadoProd = Proyecto.EstadoProduccion
    limite = ahora - timedelta(days=empresa.alerta_sin_pago_dias)
    qs = (
        Proyecto.objects.filter(
            empresa=empresa,
            estado_pago=Proyecto.EstadoPago.PENDIENTE,
            fecha_creacion__lte=limite,
        )
        .exclude(estado_produccion__in=[EstadoProd.ENTREGADO, EstadoProd.CANCELADO])
        .select_related("cliente")
        .order_by("fecha_creacion")
    )
    alertas = []
    for p in qs:
        dias = (ahora - p.fecha_creacion).days
        alertas.append(
            _alerta(
                "proyecto_sin_pago",
                ADVERTENCIA,
                f"Proyecto #{p.id} sin abonos",
                f"{p.cliente.nombre} · {dias} días sin pagos",
                f"/proyectos/{p.id}",
                dias,
            )
        )
    return alertas


def entregados_sin_cobrar(empresa, ahora):
    """Proyectos ya entregados que siguen sin pago total."""
    qs = (
        Proyecto.objects.filter(
            empresa=empresa,
            estado_produccion=Proyecto.EstadoProduccion.ENTREGADO,
        )
        .exclude(estado_pago=Proyecto.EstadoPago.PAGADO)
        .select_related("cliente")
        .order_by("estado_actualizado_en")
    )
    alertas = []
    for p in qs:
        dias = (ahora - p.estado_actualizado_en).days
        alertas.append(
            _alerta(
                "entregado_sin_cobrar",
                CRITICA,
                f"Proyecto #{p.id} entregado sin cobro total",
                f"{p.cliente.nombre} · pago {p.get_estado_pago_display().lower()}",
                f"/proyectos/{p.id}",
                dias,
            )
        )
    return alertas


# Todas las reglas activas. Agregar una alerta nueva = sumar su funcion aqui.
REGLAS = [
    cotizaciones_pendientes,
    proyectos_estancados,
    proyectos_sin_pago,
    entregados_sin_cobrar,
]
