"""Exportacion a PDF (ReportLab): piezas comunes y PDF de la cotizacion.

Los PDF se generan en el servidor con los mismos permisos y aislamiento por
empresa que la API (las acciones usan get_object del viewset). Las fechas con
hora se muestran en la zona del usuario (core/zona.py), igual que en pantalla.
Todo texto que viene de datos se escapa antes de ir a un Paragraph (que
interpreta un subconjunto de HTML).

PDF del proyecto y de la hoja de corte: projects/pdf.py.
"""

from functools import partial
from io import BytesIO
from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .pricing import desglose_iva
from .zona import formatear_fecha_hora

AZUL = colors.HexColor("#2563eb")
GRIS = colors.HexColor("#64748b")
BORDE = colors.HexColor("#e2e8f0")
FONDO = colors.HexColor("#f1f5f9")
ROJO = colors.HexColor("#b91c1c")

MARGEN = 18 * mm
ANCHO_UTIL = A4[0] - 2 * MARGEN

ESTILOS = {
    "normal": ParagraphStyle("normal", fontName="Helvetica", fontSize=9, leading=12),
    "negrita": ParagraphStyle("negrita", fontName="Helvetica-Bold", fontSize=9, leading=12),
    "chico": ParagraphStyle("chico", fontName="Helvetica", fontSize=7.5, leading=10, textColor=GRIS),
    "h2": ParagraphStyle(
        "h2", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=AZUL,
        spaceBefore=10, spaceAfter=5,
    ),
    "titulo": ParagraphStyle(
        "titulo", fontName="Helvetica-Bold", fontSize=15, leading=19, alignment=TA_RIGHT
    ),
    "derecha": ParagraphStyle("derecha", fontName="Helvetica", fontSize=9, leading=12, alignment=TA_RIGHT),
    "aviso": ParagraphStyle("aviso", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=ROJO),
}


# ------------------------------------------------------------------
# Formato
# ------------------------------------------------------------------


def clp(valor):
    return "$" + f"{int(valor or 0):,}".replace(",", ".")


def milimetros(valor):
    """"500mm" (igual que en pantalla: formatMm del frontend)."""
    return f"{valor}mm"


def medidas(ancho, alto):
    """"500mm × 500mm" (ancho × alto)."""
    return f"{milimetros(ancho)} × {milimetros(alto)}"


def fecha_hora(dt):
    """"24-10-2026 19:15" en la zona del usuario."""
    return formatear_fecha_hora(dt) or "—"


def fecha(dt):
    """Solo el dia ("24-10-2026") en la zona del usuario."""
    return formatear_fecha_hora(dt)[:10] if dt else "—"


def p(texto, estilo="normal"):
    """Paragraph con el texto escapado (datos de usuario)."""
    return Paragraph(escape(str(texto)) if texto not in (None, "") else "—", ESTILOS[estilo])


def h2(texto):
    return Paragraph(escape(texto), ESTILOS["h2"])


# ------------------------------------------------------------------
# Bloques
# ------------------------------------------------------------------


def encabezado(empresa, titulo, lineas):
    """Datos de la empresa (izquierda) y titulo del documento (derecha)."""
    contacto = " · ".join(x for x in (empresa.telefono, empresa.email) if x)
    izquierda = [f"<b>{escape(empresa.nombre)}</b>"] + [
        escape(x)
        for x in (
            f"RUT {empresa.rut}" if empresa.rut else "",
            empresa.direccion,
            contacto,
        )
        if x
    ]
    derecha = [Paragraph(escape(titulo), ESTILOS["titulo"])] + [
        Paragraph(escape(x), ESTILOS["derecha"]) for x in lineas
    ]
    t = Table(
        [[Paragraph("<br/>".join(izquierda), ESTILOS["normal"]), derecha]],
        colWidths=[ANCHO_UTIL * 0.55, ANCHO_UTIL * 0.45],
    )
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 1.2, AZUL),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return [t, Spacer(1, 6)]


def datos(pares, columnas=3):
    """Grilla de datos: etiqueta pequena sobre el valor."""
    celdas = [
        Paragraph(
            f'<font size="7.5" color="#64748b">{escape(etiqueta.upper())}</font><br/>'
            f"{escape(str(valor)) if valor not in (None, '') else '—'}",
            ESTILOS["normal"],
        )
        for etiqueta, valor in pares
    ]
    filas = [celdas[i : i + columnas] for i in range(0, len(celdas), columnas)]
    filas[-1] += [""] * (columnas - len(filas[-1]))
    t = Table(filas, colWidths=[ANCHO_UTIL / columnas] * columnas)
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def tabla(encabezados, filas, anchos, derecha=(), extra=(), repetir=True):
    """Tabla con encabezado gris. `derecha`: columnas alineadas a la derecha.
    Las celdas de texto se envuelven en Paragraph (con escape)."""

    def celda(valor, col, negrita=False):
        if not isinstance(valor, str):
            return valor
        estilo = "derecha" if col in derecha else ("negrita" if negrita else "normal")
        return p(valor, estilo) if valor else ""

    datos_tabla = [[celda(x, i, True) for i, x in enumerate(encabezados)]]
    datos_tabla += [[celda(x, i) for i, x in enumerate(fila)] for fila in filas]
    t = Table(datos_tabla, colWidths=anchos, repeatRows=1 if repetir else 0)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), FONDO),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                *extra,
            ]
        )
    )
    return t


def tabla_desglose(cot, pagado=None):
    """Desglose del precio: ventanas, transporte, costo adicional, neto, IVA
    y total (y, si se indica `pagado`, lo pagado y el saldo)."""
    filas = []
    sin_precio = False
    for i, v in enumerate(cot.ventanas.order_by("pk"), start=1):
        descripcion = (
            f"Ventana {i} · {v.get_tipo_display()} — "
            f"{medidas(v.ancho_mm, v.alto_mm)} · {v.get_color_display()} · {v.get_vidrio_display()}"
        )
        if v.precio_calculado:
            filas.append([descripcion, str(v.cantidad), clp(v.precio_unitario), clp(v.subtotal)])
        else:
            sin_precio = True
            filas.append([descripcion, str(v.cantidad), "Sin precio", "—"])
    if cot.requiere_transporte:
        filas.append(
            [f"Transporte e instalación ({cot.distancia_transporte_km} km)", "", "", clp(cot.costo_transporte)]
        )
    if cot.monto_agregado or cot.comentarios:
        filas.append(
            [f"Costo adicional: {cot.comentarios or 'sin descripción'}", "", "", clp(cot.monto_agregado)]
        )

    neto, iva, bruto = desglose_iva(cot.total)
    # (etiqueta, monto, en negrita)
    totales = [("Neto", neto, False), ("IVA (19%)", iva, False), ("Total (bruto)", bruto, True)]
    if pagado is not None:
        totales += [("Pagado", pagado, False), ("Saldo", max(bruto - int(pagado), 0), True)]
    inicio = len(filas) + 1  # fila de la tabla donde empiezan los totales

    def total(texto, negrita):
        return Paragraph(f"<b>{escape(texto)}</b>" if negrita else escape(texto), ESTILOS["derecha"])

    filas += [
        ["", "", total(etiqueta, negrita), total(clp(monto), negrita)]
        for etiqueta, monto, negrita in totales
    ]
    t = tabla(
        ["Descripción", "Cant.", "Precio unit.", "Subtotal"],
        filas,
        [ANCHO_UTIL - 3 * 28 * mm, 28 * mm, 28 * mm, 28 * mm],
        derecha=(1, 2, 3),
        extra=[
            ("LINEABOVE", (0, inicio), (-1, inicio), 1, GRIS),
            ("LINEBELOW", (0, inicio), (-1, -1), 0, colors.white),
        ],
    )
    return t, sin_precio


# ------------------------------------------------------------------
# Documento
# ------------------------------------------------------------------


class _CanvasNumerado(canvas.Canvas):
    """Pie de pagina con texto y "Pagina X de Y" (el total se conoce al final)."""

    def __init__(self, *args, pie="", **kwargs):
        super().__init__(*args, **kwargs)
        self._pie = pie
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self.setFont("Helvetica", 7.5)
            self.setFillColor(GRIS)
            self.drawString(MARGEN, 10 * mm, self._pie)
            self.drawRightString(A4[0] - MARGEN, 10 * mm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


def documento(titulo, elementos, usuario):
    """Arma el PDF y devuelve sus bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=titulo,
        author="CrystalWork",
    )
    pie = f"CrystalWork · Generado el {fecha_hora(timezone.now())} por {usuario.username}"
    doc.build(elementos, canvasmaker=partial(_CanvasNumerado, pie=pie))
    return buffer.getvalue()


def respuesta_pdf(contenido, nombre_archivo):
    respuesta = HttpResponse(contenido, content_type="application/pdf")
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    return respuesta


# ------------------------------------------------------------------
# Cotizacion
# ------------------------------------------------------------------


def pdf_cotizacion(cot, usuario):
    cliente = cot.cliente
    elementos = encabezado(
        cot.empresa,
        f"Cotización N° {cot.pk}",
        [f"Fecha: {fecha(cot.fecha_ingreso)}", f"Estado: {cot.get_estado_display()}"],
    )
    elementos += [
        h2("Cliente"),
        datos(
            [
                ("Nombre", cliente.nombre),
                ("RUT", cliente.rut),
                ("Teléfono", cliente.telefono),
                ("Email", cliente.email),
                ("Dirección", cliente.direccion),
            ]
        ),
        h2("Entrega"),
        datos(
            [
                ("Dirección de entrega", cot.direccion_entrega),
                (
                    "Transporte e instalación",
                    f"Sí ({cot.distancia_transporte_km} km)" if cot.requiere_transporte else "No",
                ),
            ],
            columnas=2,
        ),
        h2("Detalle"),
    ]
    detalle, sin_precio = tabla_desglose(cot)
    elementos.append(detalle)
    elementos.append(Spacer(1, 8))
    if sin_precio:
        elementos.append(
            p("Hay ventanas sin precio: falta completar el catálogo de precios.", "aviso")
        )
    elementos.append(p("Valores en pesos chilenos (CLP). El total incluye IVA (19%).", "chico"))
    return documento(f"Cotización N° {cot.pk}", elementos, usuario)
