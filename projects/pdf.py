"""PDF del proyecto (completo) y de la hoja de corte. Piezas comunes en
core/pdf.py."""

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Spacer

from core.pdf import (
    ANCHO_UTIL,
    FONDO,
    clp,
    datos,
    documento,
    fecha,
    fecha_hora,
    encabezado,
    h2,
    medidas,
    milimetros,
    p,
    tabla,
    tabla_desglose,
)

from .cutlist import hoja_de_corte
from .models import Proyecto


def _tabla_corte(proyecto, con_marca=False):
    """Piezas a cortar, separadas por ventana (codigo): fondo alterno por
    ventana. `con_marca` agrega una columna vacia para marcar en el taller."""
    piezas = hoja_de_corte(proyecto)
    encabezados = ["Código", "Tipo", "Color", "Perfil", "Largo", "Cant."]
    anchos = [16 * mm, 50 * mm, 28 * mm, 34 * mm, 20 * mm, 12 * mm]
    if con_marca:
        encabezados.append("Listo")
        anchos.append(14 * mm)
    # El resto del ancho util va a la columna Tipo.
    anchos[1] += ANCHO_UTIL - sum(anchos)

    filas, fondos, grupo, anterior = [], [], -1, None
    for i, x in enumerate(piezas, start=1):
        if x["codigo"] != anterior:
            grupo += 1
            anterior = x["codigo"]
            if i > 1:
                fondos.append(("LINEABOVE", (0, i), (-1, i), 1, colors.HexColor("#94a3b8")))
        if grupo % 2:
            fondos.append(("BACKGROUND", (0, i), (-1, i), FONDO))
        fila = [
            x["codigo"],
            x["tipo_display"],
            x["color_display"],
            x["perfil"],
            milimetros(x["largo_mm"]),
            str(x["cantidad"]),
        ]
        if con_marca:
            fila.append("")
        filas.append(fila)
    if con_marca:
        fondos.append(("BOX", (6, 1), (6, -1), 0.5, colors.HexColor("#94a3b8")))
        fondos.append(("INNERGRID", (6, 1), (6, -1), 0.5, colors.HexColor("#94a3b8")))

    resumen = (
        f"{len({x['codigo'] for x in piezas})} ventanas · "
        f"{sum(x['cantidad'] for x in piezas)} piezas"
    )
    if not piezas:
        return [p("Sin piezas (revisa que las ventanas tengan un tipo válido).")]
    return [
        p(resumen, "chico"),
        Spacer(1, 3),
        tabla(encabezados, filas, anchos, derecha=(4, 5), extra=fondos),
    ]


def _estado(proyecto):
    pares = [
        ("Fabricación", proyecto.get_estado_produccion_display()),
        ("Pago", proyecto.get_estado_pago_display()),
        ("Cotización", f"N° {proyecto.cotizacion_id}"),
    ]
    elementos = [datos(pares)]
    if proyecto.estado_produccion == Proyecto.EstadoProduccion.CANCELADO:
        elementos.append(p(f"Proyecto cancelado: {proyecto.motivo_cancelacion}", "aviso"))
    return elementos


def pdf_hoja_corte(proyecto, usuario):
    cot = proyecto.cotizacion
    elementos = encabezado(
        proyecto.empresa,
        "Hoja de corte",
        [f"Proyecto N° {proyecto.pk}", f"Cliente: {proyecto.cliente.nombre}"],
    )
    elementos += [
        datos(
            [
                ("Dirección del proyecto", cot.direccion_entrega),
                ("Fabricación", proyecto.get_estado_produccion_display()),
                ("Creado el", fecha(proyecto.fecha_creacion)),
            ]
        ),
    ]
    if proyecto.estado_produccion == Proyecto.EstadoProduccion.CANCELADO:
        elementos.append(p(f"Proyecto cancelado: {proyecto.motivo_cancelacion}", "aviso"))
    elementos += [h2("Piezas a cortar")] + _tabla_corte(proyecto, con_marca=True)
    return documento(f"Hoja de corte · Proyecto N° {proyecto.pk}", elementos, usuario)


def pdf_proyecto(proyecto, usuario):
    cot = proyecto.cotizacion
    cliente = proyecto.cliente
    elementos = encabezado(
        proyecto.empresa,
        f"Proyecto N° {proyecto.pk}",
        [f"Creado el {fecha(proyecto.fecha_creacion)}", f"Cotización N° {cot.pk}"],
    )
    elementos += [h2("Estado")] + _estado(proyecto)
    elementos += [
        h2("Cliente"),
        datos(
            [
                ("Nombre", cliente.nombre),
                ("RUT", cliente.rut),
                ("Contacto", cliente.telefono),
                ("Email", cliente.email),
                ("Dirección del proyecto", cot.direccion_entrega),
            ]
        ),
        h2("Ventanas"),
        tabla(
            ["#", "Tipo", "Color", "Vidrio", "Medidas", "Cant."],
            [
                [
                    str(i),
                    v.get_tipo_display(),
                    v.get_color_display(),
                    v.get_vidrio_display(),
                    medidas(v.ancho_mm, v.alto_mm),
                    str(v.cantidad),
                ]
                for i, v in enumerate(cot.ventanas.order_by("pk"), start=1)
            ],
            [8 * mm, 52 * mm, 28 * mm, 28 * mm, 40 * mm, ANCHO_UTIL - 156 * mm],
            derecha=(5,),
        ),
        h2("Hoja de corte"),
    ]
    elementos += _tabla_corte(proyecto)

    elementos.append(h2("Información de pagos"))
    detalle, _ = tabla_desglose(cot, pagado=proyecto.monto_abonado)
    # Que los totales no queden separados en otra pagina (si cabe en una).
    elementos.append(KeepTogether(detalle))
    pagos = list(proyecto.pagos.select_related("registrado_por", "anulado_por"))
    if pagos:
        elementos += [
            Spacer(1, 6),
            p("Pagos registrados", "negrita"),
            Spacer(1, 3),
            tabla(
                ["Fecha", "Monto", "Comentario", "Registrado", "Estado"],
                [
                    [
                        f"{pg.fecha:%d-%m-%Y}",
                        clp(pg.monto),
                        pg.comentario,
                        f"{pg.registrado_por.username if pg.registrado_por else '—'} · "
                        f"{fecha_hora(pg.creado_en)}",
                        (
                            f"Anulado por {pg.anulado_por.username if pg.anulado_por else '—'}"
                            f" ({fecha_hora(pg.anulado_en)}): {pg.motivo_anulacion}"
                        )
                        if pg.anulado
                        else "Vigente",
                    ]
                    for pg in pagos
                ],
                [22 * mm, 24 * mm, 45 * mm, 40 * mm, ANCHO_UTIL - 131 * mm],
                derecha=(1,),
            ),
        ]
    else:
        elementos.append(p("Aún no se registran pagos.", "chico"))
    elementos.append(Spacer(1, 6))
    elementos.append(p("Valores en pesos chilenos (CLP). El total incluye IVA (19%).", "chico"))
    return documento(f"Proyecto N° {proyecto.pk}", elementos, usuario)
