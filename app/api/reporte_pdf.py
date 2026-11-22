"""Reporte de ventas en PDF (semana 15). Recibe el ReporteVentas ya calculado por el servicio
y solo se encarga de dibujarlo (presentación). Usa reportlab."""
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.gestion import ReporteVentas

NEGRO = colors.HexColor("#111111")
GRIS = colors.HexColor("#6b6b6b")
LINEA = colors.HexColor("#e5e5e5")
FONDO = colors.HexColor("#f5f5f5")
ACENTO = colors.HexColor("#2563eb")


def cop(valor: Decimal | int) -> str:
    """200000 -> $200.000 (formato colombiano, sin decimales si no los hay)."""
    v = Decimal(valor)
    entero = f"{int(v):,}".replace(",", ".")
    centavos = int((v - int(v)) * 100)
    return f"${entero}" + (f",{centavos:02d}" if centavos else "")


def _f(d) -> str:
    return d.strftime("%d/%m/%Y")


def _tabla(filas, anchos, alinear_derecha=(), total=False):
    t = Table(filas, colWidths=anchos, repeatRows=1, hAlign="LEFT")
    estilo = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), GRIS),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, NEGRO),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for c in alinear_derecha:
        estilo.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    if total:
        estilo += [("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("LINEABOVE", (0, -1), (-1, -1), 0.8, NEGRO),
                   ("BACKGROUND", (0, -1), (-1, -1), FONDO)]
    t.setStyle(TableStyle(estilo))
    return t


def generar_pdf(rep: ReporteVentas) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                            title="Reporte de ventas — Marea Dorada Resort", author="MareaDorada Pro")
    base = getSampleStyleSheet()
    titulo = ParagraphStyle("t", parent=base["Title"], fontSize=18, alignment=0, textColor=NEGRO, spaceAfter=2)
    sub = ParagraphStyle("s", parent=base["Normal"], fontSize=9.5, textColor=GRIS)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=11.5, textColor=NEGRO, spaceBefore=12, spaceAfter=6)

    e = [
        Paragraph("Reporte de ventas", titulo),
        Paragraph(f"Marea Dorada Resort · Reservas con entrada del {_f(rep.desde)} al {_f(rep.hasta)} · "
                  f"Generado el {_f(rep.generado)}", sub),
        Spacer(1, 12),
    ]

    # Indicadores
    kpi = Table([["Ingresos", "Reservas", "Noches vendidas", "Canceladas (no suman)"],
                 [cop(rep.total), str(len(rep.reservas)), str(rep.noches), str(rep.canceladas)]],
                colWidths=[6.4 * cm] * 4, hAlign="LEFT")
    kpi.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, 0), 8.5), ("TEXTCOLOR", (0, 0), (-1, 0), GRIS),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"), ("FONTSIZE", (0, 1), (-1, 1), 15),
        ("TEXTCOLOR", (0, 1), (0, 1), ACENTO),
        ("BACKGROUND", (0, 0), (-1, -1), FONDO), ("BOX", (0, 0), (-1, -1), 0.5, LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 1), (-1, 1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    e.append(kpi)

    if not rep.reservas:
        e += [Spacer(1, 18), Paragraph("No hay ventas en el rango seleccionado.", sub)]
    else:
        e.append(Paragraph("Resumen por tipo de habitación", h2))
        filas = [["Tipo", "Reservas", "Noches", "Ingresos", "% del total"]]
        for l in rep.por_tipo:
            pct = f"{(100 * l.total / rep.total):.1f} %" if rep.total else "—"
            filas.append([l.grupo, l.reservas, l.noches, cop(l.total), pct])
        filas.append(["Total", len(rep.reservas), rep.noches, cop(rep.total), "100 %"])
        e.append(_tabla(filas, [7 * cm, 3 * cm, 3 * cm, 4.5 * cm, 3 * cm], (1, 2, 3, 4), total=True))

        e.append(Paragraph("Detalle de reservas", h2))
        filas = [["#", "Huésped", "Hab.", "Tipo", "Entrada", "Salida", "Noches", "Pers.", "Tarifa/noche", "Total", "Estado"]]
        for f in rep.reservas:
            filas.append([f.id_reserva, f.huesped[:32], f.habitacion, f.tipo, _f(f.fecha_entrada), _f(f.fecha_salida),
                          f.noches, f.numero_personas, cop(f.tarifa_noche), cop(f.total), f.estado.replace("_", " ").title()])
        filas.append(["", "Total", "", "", "", "", rep.noches, "", "", cop(rep.total), ""])
        e.append(_tabla(filas, [1.2 * cm, 5.4 * cm, 1.4 * cm, 2.3 * cm, 2.3 * cm, 2.3 * cm, 1.6 * cm, 1.4 * cm, 2.8 * cm, 3 * cm, 2.6 * cm],
                        (0, 6, 7, 8, 9), total=True))

    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawString(1.6 * cm, 0.8 * cm, "MareaDorada Pro · Ventas = reservas no canceladas con fecha de entrada en el rango.")
        canvas.drawRightString(landscape(A4)[0] - 1.6 * cm, 0.8 * cm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(e, onFirstPage=pie, onLaterPages=pie)
    return buffer.getvalue()
