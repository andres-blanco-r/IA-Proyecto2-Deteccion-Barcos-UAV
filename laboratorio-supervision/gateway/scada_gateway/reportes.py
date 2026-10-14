"""Generación de reportes PDF (supervisor y gerencia)."""
from __future__ import annotations

import io
import json
import statistics
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer, Table,  # noqa: E402
                                TableStyle)

from . import layout  # noqa: E402

GRIS, AZUL, ROJO = "#6b7280", "#1f4e79", "#b91c1c"
_EST = getSampleStyleSheet()


def _png(fig) -> io.BytesIO:
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    b.seek(0)
    return b


_CELDA = ParagraphStyle("celda", parent=_EST["Normal"], fontSize=8.5, leading=10)


def _tabla(filas, anchos=None):
    # Las celdas largas se envuelven en Paragraph para que hagan salto de línea.
    filas = [[Paragraph(c, _CELDA) if isinstance(c, str) and len(c) > 45 else c for c in f]
             for f in filas]
    t = Table(filas, colWidths=anchos, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9d9d9")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9ca3af")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _encabezado(titulo, meta):
    return [
        Paragraph(titulo, _EST["Title"]),
        Paragraph(f"<b>Estación:</b> {meta['estacion']} &nbsp;&nbsp; <b>Origen de datos:</b> "
                  f"{meta['origen']} &nbsp;&nbsp; <b>Generado:</b> {meta['generado']:%Y-%m-%d %H:%M:%S}",
                  _EST["Normal"]),
        Paragraph(f"<b>Período:</b> {meta['desde']:%Y-%m-%d %H:%M:%S} a {meta['hasta']:%Y-%m-%d %H:%M:%S}",
                  _EST["Normal"]),
        Spacer(1, 0.3 * cm),
    ]


def _pdf(elementos) -> bytes:
    b = io.BytesIO()
    SimpleDocTemplate(b, pagesize=letter, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                      topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                      title="Reporte SCADA", author="Gateway SCADA").build(elementos)
    return b.getvalue()


def _fmt(v, d=2):
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------- supervisor
def resumen_proceso(filas: list[dict], tolerancia: float) -> dict:
    if not filas:
        return {"muestras": 0}
    pv = [f["pv_c"] for f in filas]
    err = [abs(f["error_c"]) for f in filas]
    n = len(filas)
    alarmas = sorted({a for f in filas for a in layout.alarmas_activas(f["alarmas"])})
    return {
        "muestras": n,
        "pv_min": min(pv), "pv_max": max(pv), "pv_media": statistics.fmean(pv),
        "pv_desv": statistics.pstdev(pv),
        "sp_ultimo": filas[-1]["sp_c"],
        "error_abs_medio": statistics.fmean(err),
        "en_tolerancia_pct": 100.0 * sum(e <= tolerancia for e in err) / n,
        "duty_calefactor_pct": 100.0 * sum(bool(f["calefactor"]) for f in filas) / n,
        "vel_media_rpm": statistics.fmean(f["vel_rpm"] for f in filas),
        "adelante_pct": 100.0 * sum(f["sentido"] == 1 for f in filas) / n,
        "reversa_pct": 100.0 * sum(f["sentido"] == -1 for f in filas) / n,
        "detenido_pct": 100.0 * sum(f["sentido"] == 0 for f in filas) / n,
        "alarmas_vistas": alarmas,
    }


def reporte_supervisor(filas: list[dict], eventos: list[dict], meta: dict,
                       tolerancia: float = 2.0) -> tuple[bytes, dict]:
    r = resumen_proceso(filas, tolerancia)
    el = _encabezado("Reporte de supervisión – Incubadora de yogur", meta)
    if not filas:
        el.append(Paragraph("No hay muestras en el período solicitado.", _EST["Normal"]))
        return _pdf(el), r

    el.append(_tabla([
        ["Indicador", "Valor"],
        ["Muestras", str(r["muestras"])],
        ["Temperatura mín / media / máx [°C]",
         f"{_fmt(r['pv_min'])} / {_fmt(r['pv_media'])} / {_fmt(r['pv_max'])}"],
        ["Desviación estándar PV [°C]", _fmt(r["pv_desv"], 3)],
        ["Set point actual [°C]", _fmt(r["sp_ultimo"], 1)],
        ["Error absoluto medio [°C]", _fmt(r["error_abs_medio"], 3)],
        [f"Tiempo dentro de ±{_fmt(tolerancia, 1)} °C [%]", _fmt(r["en_tolerancia_pct"], 1)],
        ["Ciclo de trabajo del calefactor [%]", _fmt(r["duty_calefactor_pct"], 1)],
        ["Velocidad media del agitador [rpm]", _fmt(r["vel_media_rpm"], 0)],
        ["Sentido: adelante / reversa / detenido [%]",
         f"{_fmt(r['adelante_pct'], 1)} / {_fmt(r['reversa_pct'], 1)} / {_fmt(r['detenido_pct'], 1)}"],
        ["Alarmas presentadas", ", ".join(r["alarmas_vistas"]) or "Ninguna"],
    ], [8.5 * cm, 9 * cm]))
    el.append(Spacer(1, 0.3 * cm))

    ts = [f["ts"] for f in filas]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 5.6), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 2]})
    sp = [f["sp_c"] for f in filas]
    a1.fill_between(ts, [s - tolerancia for s in sp], [s + tolerancia for s in sp],
                    color="#e5e7eb", label=f"Tolerancia ±{tolerancia:g} °C")
    a1.plot(ts, sp, color=GRIS, ls="--", lw=1.2, label="Set point")
    a1.plot(ts, [f["pv_c"] for f in filas], color=AZUL, lw=1.4, label="Temperatura (PV)")
    a1b = a1.twinx()
    a1b.fill_between(ts, [int(bool(f["calefactor"])) for f in filas], step="post",
                     color=ROJO, alpha=0.12, label="Calefactor ON")
    a1b.set_ylim(0, 4)
    a1b.set_yticks([])
    a1.set_ylabel("°C")
    a1.legend(loc="lower right", fontsize=7)
    a1.grid(alpha=0.3)
    a2.plot(ts, [f["vel_rpm"] * (f["sentido"] or 1) for f in filas], color=AZUL, lw=1.3,
            label="Velocidad real (signo = sentido)")
    a2.plot(ts, [f["vel_ref_pct"] / 100.0 * 1800.0 for f in filas], color=GRIS, ls="--", lw=1,
            label="Referencia (a 1800 rpm = 100 %)")
    a2.axhline(0, color="black", lw=0.6)
    a2.set_ylabel("rpm")
    a2.legend(loc="upper right", fontsize=7)
    a2.grid(alpha=0.3)
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    el.append(Image(_png(fig), width=17 * cm, height=11.9 * cm))

    if eventos:
        el.append(Spacer(1, 0.3 * cm))
        el.append(Paragraph("Eventos del período (últimos 25)", _EST["Heading3"]))
        el.append(_tabla([["Hora", "Tipo", "Descripción"]] +
                         [[f"{e['ts']:%H:%M:%S}", e["tipo"], e["descripcion"]] for e in eventos[-25:]],
                         [2.2 * cm, 2.6 * cm, 12.7 * cm]))
    return _pdf(el), r


# ------------------------------------------------------------------- gerencia
def reporte_gerencia(filas: list[dict], meta: dict) -> tuple[bytes, dict]:
    el = _encabezado("Reporte de gerencia – Línea de yogur", meta)
    if not filas:
        el.append(Paragraph("No hay datos de gerencia en el período solicitado.", _EST["Normal"]))
        return _pdf(el), {"muestras": 0}
    g = filas[-1]
    costo_total = g["costo_materiales"] + g["costo_energia"] + g["costo_paradas"]
    r = {k: g[k] for k in ("lotes_total", "lotes_buenos", "lotes_rechazados", "unidades_producidas",
                           "unidades_vendidas", "inventario_und", "ingresos", "utilidad",
                           "margen_pct", "oee_pct", "costo_unitario", "kwh_por_unidad")}
    r["costo_total"] = costo_total
    cop = lambda v: "$ " + _fmt(v, 0)  # noqa: E731
    el.append(_tabla([
        ["Rubro", "Valor", "Rubro", "Valor"],
        ["Lotes (buenos / rechazados)", f"{g['lotes_buenos']} / {g['lotes_rechazados']}",
         "Leche usada [L]", _fmt(g["leche_l"], 1)],
        ["Unidades producidas", str(g["unidades_producidas"]), "Cultivo usado [g]", _fmt(g["cultivo_g"], 1)],
        ["Unidades vendidas", str(g["unidades_vendidas"]), "Azúcar usada [kg]", _fmt(g["azucar_kg"], 2)],
        ["Inventario producto terminado", str(g["inventario_und"]), "Envases usados", str(g["envases_usados"])],
        ["Ingresos por ventas", cop(g["ingresos"]), "Costo materiales", cop(g["costo_materiales"])],
        ["Energía [kWh]", _fmt(g["energia_kwh"], 2), "Costo energía", cop(g["costo_energia"])],
        ["Tiempo turno / muerto [h]", f"{_fmt(g['t_turno_h'], 2)} / {_fmt(g['t_muerto_h'], 2)}",
         "Costo tiempo muerto", cop(g["costo_paradas"])],
        ["Utilidad", cop(g["utilidad"]), "Costo total", cop(costo_total)],
    ], [5.2 * cm, 3.6 * cm, 4.6 * cm, 4.1 * cm]))
    el.append(Spacer(1, 0.25 * cm))
    el.append(Paragraph("Indicadores clave (KPI)", _EST["Heading3"]))
    el.append(_tabla([
        ["KPI", "Valor", "Fórmula"],
        ["OEE [%]", _fmt(g["oee_pct"], 1), "Disponibilidad × Rendimiento × Calidad"],
        ["Disponibilidad [%]", _fmt(g["disponibilidad_pct"], 1), "(T turno − T muerto) / T turno"],
        ["Rendimiento [%]", _fmt(g["rendimiento_pct"], 1), "Lotes × T ciclo ideal / T operando"],
        ["Calidad [%]", _fmt(g["calidad_pct"], 1), "Lotes buenos / lotes totales"],
        ["Margen sobre ventas [%]", _fmt(g["margen_pct"], 1), "Utilidad / Ingresos"],
        ["Costo unitario [COP/und]", _fmt(g["costo_unitario"], 0), "(Materiales + energía) / unidades buenas"],
        ["Energía específica [kWh/und]", _fmt(g["kwh_por_unidad"], 4), "Energía / unidades buenas"],
    ], [5.2 * cm, 2.6 * cm, 9.7 * cm]))

    ts = [f["ts"] for f in filas]
    fig, ax = plt.subplots(1, 2, figsize=(8, 3))
    ax[0].bar(["Ingresos", "Materiales", "Energía", "Paradas"],
              [g["ingresos"], g["costo_materiales"], g["costo_energia"], g["costo_paradas"]],
              color=[AZUL, GRIS, GRIS, ROJO])
    ax[0].set_title("Ingresos vs costos [COP]", fontsize=9)
    ax[0].tick_params(labelsize=7)
    ax[1].bar(["Disp.", "Rend.", "Calidad", "OEE"],
              [g["disponibilidad_pct"], g["rendimiento_pct"], g["calidad_pct"], g["oee_pct"]],
              color=[GRIS, GRIS, GRIS, AZUL])
    ax[1].set_ylim(0, 100)
    ax[1].set_title("OEE y sus componentes [%]", fontsize=9)
    ax[1].tick_params(labelsize=7)
    el.append(Image(_png(fig), width=17 * cm, height=6.4 * cm))

    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.plot(ts, [f["inventario_und"] for f in filas], color=AZUL, label="Inventario [und]")
    ax.plot(ts, [f["unidades_vendidas"] for f in filas], color=GRIS, ls="--", label="Vendidas acumuladas")
    ax.plot(ts, [f["unidades_producidas"] for f in filas], color="black", lw=0.8, label="Producidas acumuladas")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    el.append(Image(_png(fig), width=17 * cm, height=6 * cm))
    return _pdf(el), r


def a_json(resumen: dict) -> str:
    return json.dumps(resumen, ensure_ascii=False, default=str)


def nombre_archivo(tipo: str, ahora: datetime | None = None) -> str:
    return f"reporte_{tipo}_{(ahora or datetime.now()):%Y%m%d_%H%M%S}.pdf"
