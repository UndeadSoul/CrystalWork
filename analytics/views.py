from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Cliente,
    ColorAluminio,
    Cotizacion,
    TipoVentana,
    VentanaCotizada,
)
from core.permissions import EsJefe, EsUsuarioDeEmpresa
from core.pricing import desglose_iva
from projects.models import Proyecto

MESES_ABR = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
]

# Rangos de tiempo soportados por el gráfico de ingresos (en orden).
RANGOS_ORDEN = ["semana", "mes", "6meses", "anio", "3anios", "historico"]


def _bruto(neto):
    return desglose_iva(neto or 0)[2]


def _choices_breakdown(qs, campo, choices):
    """Cuenta registros por valor de `campo` respetando el orden de choices."""
    conteo = dict(
        qs.values_list(campo).annotate(n=Count("id")).values_list(campo, "n")
    )
    return [
        {"valor": v, "label": label, "n": conteo.get(v, 0)}
        for v, label in choices
    ]


def _ultimos_meses(n):
    """(anio, mes) de los ultimos n meses, del mas antiguo al actual."""
    hoy = timezone.localdate()
    out = []
    y, mnum = hoy.year, hoy.month
    for _ in range(n):
        out.append((y, mnum))
        mnum -= 1
        if mnum == 0:
            mnum = 12
            y -= 1
    return list(reversed(out))


def _ultimos_trimestres(n):
    """(anio, trimestre) de los ultimos n trimestres, del mas antiguo al actual."""
    hoy = timezone.localdate()
    out = []
    y, q = hoy.year, (hoy.month - 1) // 3 + 1
    for _ in range(n):
        out.append((y, q))
        q -= 1
        if q == 0:
            q = 4
            y -= 1
    return list(reversed(out))


def serie_ingresos(rango, filas):
    """Serie [{label, total(bruto)}] agrupada segun el rango de tiempo.
    `filas` son dicts con cotizacion__total y fecha_creacion.

    Fechas en la zona horaria del sistema (settings.TIME_ZONE, Chile): las
    guardadas estan en UTC y d.date() daria el dia UTC (un proyecto de las
    22:00 se contaria al dia/mes siguiente)."""
    hoy = timezone.localdate()

    def fecha(f):
        d = f["fecha_creacion"]
        return timezone.localtime(d).date() if d is not None else None

    if rango == "semana":
        dias = [hoy - timedelta(days=i) for i in range(6, -1, -1)]
        agg = defaultdict(int)
        for f in filas:
            d = fecha(f)
            if d is not None:
                agg[d] += _bruto(f["cotizacion__total"])
        return [
            {"label": f"{d.day}/{d.month}", "total": agg.get(d, 0)} for d in dias
        ]

    if rango == "mes":
        # 4 semanas (ventanas de 7 días), de la más antigua a la actual.
        semanas = []
        for k in range(3, -1, -1):
            fin = hoy - timedelta(days=7 * k)
            ini = fin - timedelta(days=6)
            semanas.append((ini, fin))
        out = []
        for ini, fin in semanas:
            total = sum(
                _bruto(f["cotizacion__total"])
                for f in filas
                if fecha(f) is not None and ini <= fecha(f) <= fin
            )
            out.append({"label": f"{ini.day}/{ini.month}", "total": total})
        return out

    if rango in ("6meses", "anio"):
        meses = _ultimos_meses(6 if rango == "6meses" else 12)
        agg = defaultdict(int)
        for f in filas:
            d = fecha(f)
            if d is not None:
                agg[(d.year, d.month)] += _bruto(f["cotizacion__total"])
        return [
            {
                "label": f"{MESES_ABR[m - 1]} {str(y)[2:]}",
                "total": agg.get((y, m), 0),
            }
            for (y, m) in meses
        ]

    if rango == "3anios":
        trimestres = _ultimos_trimestres(12)
        agg = defaultdict(int)
        for f in filas:
            d = fecha(f)
            if d is not None:
                agg[(d.year, (d.month - 1) // 3 + 1)] += _bruto(
                    f["cotizacion__total"]
                )
        return [
            {"label": f"T{q} {str(y)[2:]}", "total": agg.get((y, q), 0)}
            for (y, q) in trimestres
        ]

    # historico: por anio, desde el primer proyecto hasta hoy
    agg = defaultdict(int)
    anios = set()
    for f in filas:
        d = fecha(f)
        if d is not None:
            agg[d.year] += _bruto(f["cotizacion__total"])
            anios.add(d.year)
    desde = min(anios) if anios else hoy.year
    return [
        {"label": str(y), "total": agg.get(y, 0)}
        for y in range(desde, hoy.year + 1)
    ]


def _proyectos_empresa(user):
    """Proyectos que cuentan como ingreso (los cancelados no)."""
    return Proyecto.objects.filter(empresa=user.empresa).exclude(
        estado_produccion=Proyecto.EstadoProduccion.CANCELADO
    )


class ResumenView(APIView):
    """Metricas agregadas para el dashboard, aisladas por empresa."""

    permission_classes = [EsUsuarioDeEmpresa]

    def get(self, request):
        user = request.user
        ver_finanzas = user.es_jefe
        empresa = user.empresa

        cotizaciones = Cotizacion.objects.filter(empresa=empresa)
        proyectos = Proyecto.objects.filter(empresa=empresa)
        clientes = Cliente.objects.filter(empresa=empresa)
        ventanas = VentanaCotizada.objects.filter(
            cotizacion__estado=Cotizacion.Estado.APROBADA,
            cotizacion__empresa=empresa,
        ).exclude(
            # Proyectos cancelados: sus ventanas no se fabrican.
            cotizacion__proyecto__estado_produccion=Proyecto.EstadoProduccion.CANCELADO
        )

        # --- KPIs ---
        pendientes = cotizaciones.filter(
            estado=Cotizacion.Estado.PENDIENTE
        ).count()
        activos = proyectos.filter(
            estado_produccion__in=[
                Proyecto.EstadoProduccion.POR_INICIAR,
                Proyecto.EstadoProduccion.EN_FABRICACION,
            ]
        ).count()
        # Montos en BRUTO (neto + IVA), por proyecto para cuadrar con las listas.
        # Los proyectos cancelados no se facturan ni quedan por cobrar.
        filas = list(
            proyectos.exclude(estado_produccion=Proyecto.EstadoProduccion.CANCELADO)
            .values("cotizacion__total", "estado_pago", "monto_abonado")
        )
        facturado = sum(_bruto(f["cotizacion__total"]) for f in filas)
        # "Por cobrar" = bruto adeudado menos abonos, de los proyectos no pagados.
        por_cobrar = sum(
            max(_bruto(f["cotizacion__total"]) - int(f["monto_abonado"] or 0), 0)
            for f in filas
            if f["estado_pago"] != Proyecto.EstadoPago.PAGADO
        )
        kpis = {
            "cotizaciones_pendientes": pendientes,
            "proyectos_activos": activos,
            "clientes": clientes.count(),
        }
        if ver_finanzas:
            kpis["facturado"] = facturado
            kpis["por_cobrar"] = por_cobrar

        # --- Desgloses de estado ---
        cot_estado = _choices_breakdown(
            cotizaciones, "estado", Cotizacion.Estado.choices
        )
        proy_prod = _choices_breakdown(
            proyectos, "estado_produccion", Proyecto.EstadoProduccion.choices
        )
        proy_pago = _choices_breakdown(
            proyectos, "estado_pago", Proyecto.EstadoPago.choices
        )

        # --- Ventanas fabricadas: por tipo y por color (aprobadas) ---
        ventanas_por_tipo = _ventanas_agrupadas(ventanas, "tipo", TipoVentana)
        ventanas_por_color = _ventanas_agrupadas(ventanas, "color", ColorAluminio)

        return Response(
            {
                "ver_finanzas": ver_finanzas,
                "kpis": kpis,
                "cotizaciones_por_estado": cot_estado,
                "proyectos_por_produccion": proy_prod,
                "proyectos_por_pago": proy_pago,
                "ventanas_por_tipo": ventanas_por_tipo,
                "ventanas_por_color": ventanas_por_color,
            }
        )


def _ventanas_agrupadas(ventanas, campo, choices_cls):
    labels = dict(choices_cls.choices)
    filas = (
        ventanas.values(campo)
        .annotate(cantidad=Sum("cantidad"))
        .order_by("-cantidad")
    )
    return [
        {
            "valor": r[campo],
            "label": labels.get(r[campo], r[campo]),
            "cantidad": r["cantidad"] or 0,
        }
        for r in filas
    ]


class IngresosView(APIView):
    """Series de ingresos (bruto) para TODOS los rangos, en una sola llamada,
    para que el front cambie de rango sin recargar. Solo el jefe."""

    permission_classes = [EsJefe]

    def get(self, request):
        filas = list(
            _proyectos_empresa(request.user).values(
                "cotizacion__total", "fecha_creacion"
            )
        )
        series = {r: serie_ingresos(r, filas) for r in RANGOS_ORDEN}
        return Response({"series": series})
