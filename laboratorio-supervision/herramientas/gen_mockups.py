"""Genera las maquetas de los 3 paneles del SCADA (scada/mockups/*.html).

Los valores salen del gemelo de la planta, así las pantallas muestran datos coherentes.
Son la referencia para dibujar las pantallas en WinCC (ver docs/04_scada_paneles.md).

    python herramientas/gen_mockups.py
    node herramientas/capturar_mockups.js   # -> docs/img/hmi_*.png
"""
import html
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "gateway"))
from scada_gateway import layout  # noqa: E402
from scada_gateway.simulador import PlantaSimulada  # noqa: E402

SAL = RAIZ / "scada" / "mockups"
SAL.mkdir(parents=True, exist_ok=True)


def simular(minutos, dt=0.5, cada_s=10.0, eventos=None):
    sim = PlantaSimulada(semilla=11)
    hist, t = [], 0.0
    eventos = dict(eventos or {})
    while t < minutos * 60:
        for (te, cmd, val) in list(eventos.values()):
            if abs(t - te * 60) < dt / 2:
                sim.comando(cmd, val)
        sim.paso(dt)
        t += dt
        if abs(t % cada_s) < dt / 2:
            s = sim.salidas()
            hist.append((t / 60, s["PV_Temp"], s["SP_Temp"], s["Vel_rpm"] * (s["Sentido"] or 1)))
    return sim.salidas(), hist


def f(v, d=1):
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


CSS = """
:root{--bg:#d6d6d6;--panel:#e6e6e6;--borde:#9a9a9a;--txt:#1d1d1d;--suave:#5c5c5c;--valor:#0b2e59;
--on:#3b3b3b;--off:#f7f7f7;--alta:#d40000;--media:#f0b400;--baja:#e07000;--ok:#2f6b3a}
*{box-sizing:border-box}body{margin:0;background:#bdbdbd;font-family:Arial,Helvetica,sans-serif;color:var(--txt)}
.pantalla{width:1280px;height:800px;background:var(--bg);display:grid;grid-template-rows:56px 1fr 34px;overflow:hidden}
.top{display:flex;align-items:center;gap:14px;padding:0 14px;background:#c4c4c4;border-bottom:1px solid var(--borde)}
.top h1{font-size:18px;margin:0;font-weight:bold}.top .sub{font-size:12px;color:var(--suave)}
.nav{margin-left:auto;display:flex;gap:6px}.nav span{padding:7px 14px;border:1px solid var(--borde);background:var(--panel);font-size:13px}
.nav span.act{background:#7a7a7a;color:#fff;border-color:#5a5a5a}
.estado-com{display:flex;gap:10px;font-size:12px}.led{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;border:1px solid #444;vertical-align:-1px}
.led.ok{background:#9a9a9a}.led.mal{background:var(--alta)}
.usr{font-size:12px;text-align:right;color:var(--suave)}
.cuerpo{display:grid;gap:10px;padding:10px}
.caja{background:var(--panel);border:1px solid var(--borde);padding:10px;position:relative}
.caja h2{font-size:13px;margin:0 0 8px;color:var(--suave);text-transform:uppercase;letter-spacing:.04em}
.valor{font-size:40px;font-weight:bold;color:var(--valor)}.unid{font-size:16px;color:var(--suave);margin-left:4px}
.fila{display:flex;justify-content:space-between;font-size:14px;padding:4px 0;border-bottom:1px dotted #bdbdbd}
.fila b{color:var(--valor)}
.btn{display:inline-flex;align-items:center;justify-content:center;height:44px;padding:0 16px;border:1px solid #5a5a5a;
background:linear-gradient(#f2f2f2,#d0d0d0);font-weight:bold;font-size:14px;border-radius:3px;min-width:110px}
.btn.marcha{background:linear-gradient(#e9f2ea,#c7d9c9);border-color:#2f6b3a}
.btn.paro{background:linear-gradient(#5a5a5a,#2e2e2e);color:#fff}
.btn.sel{background:#7a7a7a;color:#fff}
.emerg{width:96px;height:96px;border-radius:50%;background:var(--media);display:flex;align-items:center;justify-content:center;border:2px solid #8a6a00}
.emerg span{width:70px;height:70px;border-radius:50%;background:var(--alta);color:#fff;font-size:11px;font-weight:bold;display:flex;align-items:center;justify-content:center;text-align:center;border:2px solid #7a0000}
.barra{position:relative;height:26px;background:#fff;border:1px solid var(--borde);margin:6px 0 2px}
.barra .normal{position:absolute;top:0;bottom:0;background:#c9c9c9}
.barra .pv{position:absolute;top:-4px;bottom:-4px;width:4px;background:var(--valor)}
.barra .sp{position:absolute;top:-8px;width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-top:9px solid #000;transform:translateX(-7px)}
.escala{display:flex;justify-content:space-between;font-size:11px;color:var(--suave)}
.prog{height:16px;background:#fff;border:1px solid var(--borde)}.prog div{height:100%;background:#8c8c8c}
.alarmas{display:flex;align-items:center;gap:12px;padding:0 12px;background:#cfcfcf;border-top:1px solid var(--borde);font-size:13px}
.alarmas .tag{padding:3px 8px;font-weight:bold}.p1{background:var(--alta);color:#fff}.p2{background:var(--media)}.p3{background:var(--baja);color:#fff}
.chip{display:inline-block;padding:3px 8px;border:1px solid var(--borde);background:#f2f2f2;font-size:12px;margin:2px}
.chip.on{background:var(--on);color:#fff}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:4px 6px;border-bottom:1px solid #c9c9c9;text-align:left}th{color:var(--suave);font-weight:normal}
td.n{text-align:right;color:var(--valor);font-weight:bold;white-space:nowrap}
.kpi{display:flex;flex-direction:column;align-items:flex-start}.kpi .valor{font-size:34px}
.nota{font-size:11px;color:var(--suave)}
"""


def barra(pv, sp, lo, hi, tol):
    p = lambda v: max(0, min(100, 100 * (v - lo) / (hi - lo)))  # noqa: E731
    return (f'<div class="barra"><div class="normal" style="left:{p(sp - tol):.1f}%;width:{p(sp + tol) - p(sp - tol):.1f}%"></div>'
            f'<div class="sp" style="left:{p(sp):.1f}%"></div><div class="pv" style="left:calc({p(pv):.1f}% - 2px)"></div></div>'
            f'<div class="escala"><span>{lo}</span><span>{(lo + hi) / 2:g}</span><span>{hi}</span></div>')


def marco(titulo, activo, cuerpo, alarmas, estilo_cuerpo, usuario):
    nav = "".join(f'<span class="{"act" if n == activo else ""}">{n}</span>' for n in ("Operador", "Supervisor", "Gerencia"))
    if alarmas:
        alm = "".join(f'<span class="tag {c}">{html.escape(t)}</span>' for c, t in alarmas[:3])
        alm = f"<b>Alarmas activas: {len(alarmas)}</b> {alm}"
    else:
        alm = "<b>Sin alarmas activas</b>"
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{titulo}</title><style>{CSS}</style></head>
<body><div class="pantalla">
<div class="top"><div><h1>Incubadora de yogur · Línea 1</h1><div class="sub">{titulo}</div></div>
<div class="estado-com"><span><i class="led ok"></i>PLC</span><span><i class="led ok"></i>Variador</span><span><i class="led ok"></i>Gateway</span><span><i class="led ok"></i>Nube</span></div>
<div class="nav">{nav}</div><div class="usr">Usuario: <b>{usuario}</b><br>2026-10-14 10:42:07</div></div>
<div class="cuerpo" style="{estilo_cuerpo}">{cuerpo}</div>
<div class="alarmas">{alm}<span style="margin-left:auto" class="nota">Alarma: rojo = alta · amarillo = media · naranja = baja (ISA-18.2 / ISA-101)</span></div>
</div></body></html>"""


def proceso_svg(s):
    cal_on = s["Calefactor"]
    vfd_on = s["Vel_rpm"] > 1
    rel = lambda on: "#3b3b3b" if on else "#f7f7f7"  # noqa: E731
    return f"""<svg viewBox="0 0 470 330" width="100%" height="330">
<rect x="40" y="40" width="250" height="230" fill="#efefef" stroke="#6a6a6a" stroke-width="3"/>
<text x="165" y="30" text-anchor="middle" font-size="13" fill="#5c5c5c">Cámara de incubación</text>
<line x1="55" y1="150" x2="275" y2="150" stroke="#8a8a8a" stroke-width="3" stroke-dasharray="6 4"/>
<text x="165" y="143" text-anchor="middle" font-size="11" fill="#5c5c5c">bandeja con vasos</text>
<rect x="105" y="225" width="120" height="16" fill="{rel(cal_on)}" stroke="#3b3b3b" stroke-width="2"/>
<text x="165" y="262" text-anchor="middle" font-size="12">Calefactor {'ON' if cal_on else 'OFF'}</text>
<circle cx="80" cy="200" r="16" fill="{rel(s['ProcesoEnMarcha'])}" stroke="#3b3b3b" stroke-width="2"/>
<text x="80" y="232" text-anchor="middle" font-size="11">Ventilador</text>
<line x1="290" y1="95" x2="230" y2="95" stroke="#3b3b3b" stroke-width="4"/><circle cx="300" cy="95" r="10" fill="#fff" stroke="#3b3b3b" stroke-width="2"/>
<text x="300" y="99" text-anchor="middle" font-size="10">TT</text>
<text x="318" y="90" font-size="12">TT-101 (Pt100)</text>
<text x="318" y="108" font-size="16" font-weight="bold" fill="#0b2e59">{f(s['PV_Temp'])} °C</text>
<line x1="165" y1="40" x2="165" y2="10" stroke="#3b3b3b" stroke-width="3"/>
<rect x="340" y="190" width="80" height="60" fill="{rel(vfd_on)}" stroke="#3b3b3b" stroke-width="2"/>
<text x="380" y="215" text-anchor="middle" font-size="12" fill="{'#fff' if vfd_on else '#000'}">G120</text>
<text x="380" y="232" text-anchor="middle" font-size="11" fill="{'#fff' if vfd_on else '#000'}">{f(s['Vel_rpm'], 0)} rpm</text>
<circle cx="380" cy="295" r="18" fill="{rel(vfd_on)}" stroke="#3b3b3b" stroke-width="2"/><text x="380" y="300" text-anchor="middle" font-size="13" fill="{'#fff' if vfd_on else '#000'}">M</text>
<line x1="380" y1="250" x2="380" y2="277" stroke="#3b3b3b" stroke-width="2"/>
<text x="425" y="300" font-size="11">Agitador</text>
<text x="300" y="185" font-size="11" fill="#5c5c5c">PROFINET</text>
</svg>"""


def operador():
    s, _ = simular(9.0)
    s = layout.decodificar(layout.codificar(s))
    estado = layout.ESTADOS[s["Estado"]]
    sentido = {1: "ADELANTE ⟳", -1: "REVERSA ⟲", 0: "DETENIDO"}[s["Sentido"]]
    cuerpo = f"""
<div class="caja" style="grid-row:1/3"><h2>Proceso</h2>{proceso_svg(s)}
<div class="fila"><span>Estado del proceso</span><b>{estado}</b></div>
<div class="fila"><span>Lote en curso</span><b>{f(s['ProgresoLote_pct'], 0)} %</b></div><div class="prog"><div style="width:{s['ProgresoLote_pct']:.0f}%"></div></div></div>
<div class="caja"><h2>Temperatura de incubación</h2>
<div><span class="valor">{f(s['PV_Temp'])}</span><span class="unid">°C</span></div>
{barra(s['PV_Temp'], s['SP_Temp'], 0, 70, 2)}
<div class="fila" style="margin-top:10px"><span>Set point</span><span><span class="btn" style="min-width:44px;height:34px">−</span>
<b style="font-size:22px;padding:0 10px;border:1px solid #9a9a9a;background:#fff">{f(s['SP_Temp'])} °C</b>
<span class="btn" style="min-width:44px;height:34px">+</span></span></div>
<div class="fila"><span>Error (SP − PV)</span><b>{f(s['Error_Temp'], 2)} °C</b></div>
<div class="fila"><span>Calefactor</span><b>{'ENCENDIDO' if s['Calefactor'] else 'APAGADO'}</b></div>
<p class="nota">Rango permitido 25–55 °C · ▼ = set point · franja gris = tolerancia ±2 °C</p></div>
<div class="caja"><h2>Agitador · variador G120</h2>
<div><span class="valor">{f(s['Vel_rpm'], 0)}</span><span class="unid">rpm</span></div>
{barra(s['Vel_pct'], 100, 0, 100, 0).replace('class="sp"', 'class="sp" style="display:none"')}
<div class="fila"><span>Referencia automática</span><b>{f(s['VelRef_pct'], 0)} %</b></div>
<div class="fila"><span>Sentido de giro</span><b>{sentido}</b></div>
<div class="fila"><span>Estado</span><span><span class="chip on">LISTO</span><span class="chip {'on' if s['VFD_EnMarcha'] else ''}">EN MARCHA</span><span class="chip">FALLA</span></span></div>
<div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap"><span class="btn marcha">ARRANQUE</span><span class="btn">PARADA</span>
<span class="btn sel">ADELANTE</span><span class="btn">REVERSA</span></div></div>
<div class="caja" style="grid-column:2/4;display:flex;align-items:center;gap:16px"><h2 style="margin:0">Mando del proceso</h2>
<span class="btn marcha" style="height:60px;min-width:150px">▶ START</span><span class="btn paro" style="height:60px;min-width:150px">■ STOP</span>
<span class="btn" style="height:60px">REARME</span><div class="emerg" style="margin-left:auto"><span>PARO DE<br>EMERGENCIA</span></div></div>"""
    return marco("Panel de operador", "Operador", cuerpo, [], "grid-template-columns:480px 1fr 1fr;grid-template-rows:1fr 120px", "operador1 (Operador)")


def tendencia_svg(hist, ancho=760, alto=300):
    t0, t1 = hist[0][0], hist[-1][0]
    X = lambda t: 50 + (ancho - 70) * (t - t0) / (t1 - t0)  # noqa: E731
    Yt = lambda v: alto - 30 - (alto - 50) * (v - 10) / 50  # noqa: E731
    Yv = lambda v: alto - 30 - (alto - 50) * (v + 1800) / 3600  # noqa: E731
    pv = " ".join(f"{X(t):.1f},{Yt(p):.1f}" for t, p, _, _ in hist)
    sp = " ".join(f"{X(t):.1f},{Yt(s):.1f}" for t, _, s, _ in hist)
    vel = " ".join(f"{X(t):.1f},{Yv(v):.1f}" for t, _, _, v in hist)
    grid = "".join(f'<line x1="50" x2="{ancho - 20}" y1="{Yt(v):.0f}" y2="{Yt(v):.0f}" stroke="#c9c9c9"/>'
                   f'<text x="44" y="{Yt(v) + 4:.0f}" font-size="10" text-anchor="end">{v}</text>' for v in range(10, 61, 10))
    gridx = "".join(f'<text x="{X(t):.0f}" y="{alto - 12}" font-size="10" text-anchor="middle">{t:.0f} min</text>'
                    for t in range(int(t0), int(t1) + 1, 5))
    return f"""<svg viewBox="0 0 {ancho} {alto}" width="100%" height="{alto}">{grid}{gridx}
<text x="{ancho - 16}" y="{Yv(1800) + 4:.0f}" font-size="10">+1800</text><text x="{ancho - 16}" y="{Yv(0) + 4:.0f}" font-size="10">0</text>
<text x="{ancho - 16}" y="{Yv(-1800) + 4:.0f}" font-size="10">−1800</text>
<polyline points="{vel}" fill="none" stroke="#9a9a9a" stroke-width="1.5"/>
<polyline points="{sp}" fill="none" stroke="#000" stroke-width="1.2" stroke-dasharray="6 4"/>
<polyline points="{pv}" fill="none" stroke="#0b2e59" stroke-width="2"/>
<text x="60" y="16" font-size="11" fill="#0b2e59">— PV [°C]</text><text x="140" y="16" font-size="11">- - SP [°C]</text>
<text x="220" y="16" font-size="11" fill="#7a7a7a">— velocidad [rpm] (eje derecho, signo = sentido)</text></svg>"""


PRIORIDAD = {0: "p1", 2: "p1", 4: "p1", 5: "p1", 10: "p1", 1: "p2", 3: "p2", 6: "p2", 7: "p2", 8: "p3", 9: "p3"}


def alarmas(s):
    """Alarmas activas con su prioridad (bit 11 = modo simulación no es alarma)."""
    return [(PRIORIDAD[b], t) for b, t in layout.BITS_ALARMA.items() if (s["Alarmas"] >> b) & 1 and b in PRIORIDAD]


def supervisor():
    s, hist = simular(34.0, eventos={1: (24, "reversa", True), 2: (26, "sp", 47.0)})
    s = layout.decodificar(layout.codificar(s))
    alm = alarmas(s)
    cuerpo = f"""
<div class="caja" style="grid-column:1/3"><h2>Tendencia · últimos 34 min</h2>{tendencia_svg(hist)}</div>
<div class="caja"><h2>Estado del proceso</h2>
<div class="fila"><span>Estado</span><b>{layout.ESTADOS[s['Estado']]}</b></div>
<div class="fila"><span>Temperatura / SP</span><b>{f(s['PV_Temp'])} / {f(s['SP_Temp'])} °C</b></div>
<div class="fila"><span>Velocidad / sentido</span><b>{f(s['Vel_rpm'], 0)} rpm · {'REV' if s['Sentido'] == -1 else 'ADEL' if s['Sentido'] == 1 else '—'}</b></div>
<div class="fila"><span>Calefactor</span><b>{'ON' if s['Calefactor'] else 'OFF'}</b></div>
<div class="fila"><span>Lotes buenos / rechazados</span><b>{s['Lotes_Buenos']} / {s['Lotes_Rechazados']}</b></div>
<div style="display:flex;gap:6px;margin-top:10px"><span class="btn marcha">▶ START</span><span class="btn paro">■ STOP</span></div>
<div style="display:flex;gap:10px;align-items:center;margin-top:10px"><div class="emerg" style="width:76px;height:76px"><span style="width:56px;height:56px;font-size:9px">PARO DE<br>EMERG.</span></div><span class="btn">REARME</span></div></div>
<div class="caja"><h2>Indicadores del proceso</h2>
<div class="fila"><span>Error absoluto</span><b>{f(abs(s['Error_Temp']), 2)} °C</b></div>
<div class="fila"><span>Ciclo de trabajo del calefactor (60 s)</span><b>{f(s['Duty_Calefactor_pct'], 0)} %</b></div>
<div class="fila"><span>Tiempo en tolerancia ±2 °C</span><b>{f(s['TiempoEnBanda_pct'], 1)} %</b></div>
<div class="fila"><span>Señal del lazo</span><b>{f(s['Senal_mA'], 2)} mA</b></div>
<div class="fila"><span>Energía del turno</span><b>{f(s['Energia_kWh'], 2)} kWh</b></div>
<div class="fila"><span>Avance del lote</span><b>{f(s['ProgresoLote_pct'], 0)} %</b></div></div>
<div class="caja"><h2>Bases de datos y reportes</h2>
<div class="fila"><span>BD local (SQLite)</span><b>registrando · 1 s</b></div>
<div class="fila"><span>BD en la nube (PostgreSQL)</span><b>sincronizada</b></div>
<div class="fila"><span>Filas pendientes por subir</span><b>0</b></div>
<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap"><span class="btn">REPORTE EN PC</span><span class="btn">REPORTE EN LA NUBE</span></div>
<p class="nota">El botón queda en gris oscuro mientras el gateway genera el PDF (handshake por contadores).</p></div>
<div class="caja"><h2>Puesta en marcha</h2>
<div class="fila"><span>Modo simulación</span><b>NO</b></div>
<div class="fila"><span>Velocidad manual</span><b>NO</b></div>
<div class="fila"><span>Histéresis ON-OFF</span><b>{f(1.0)} °C</b></div>
<div class="fila"><span>Banda de reinicio del agitador</span><b>{f(4.0)} °C</b></div>
<p class="nota">Solo usuarios con permiso «Supervisar».</p></div>"""
    return marco("Panel de supervisor", "Supervisor", cuerpo, alm,
                 "grid-template-columns:1fr 1fr 360px;grid-template-rows:330px 1fr", "supervisor1 (Supervisor)")


def gerencia():
    s, _ = simular(180.0, eventos={1: (95, "paro_emergencia", None), 2: (103, "rearme", None), 3: (103.1, "start", None),
                                   4: (103.2, "vfd_arranque", None)})
    s = layout.decodificar(layout.codificar(s))
    cop = lambda v: "$ " + f(v, 0)  # noqa: E731
    costo_total = s["Costo_Materiales"] + s["Costo_Energia"] + s["Costo_Paradas"]
    mx = max(s["Ingresos"], costo_total, 1)
    barras = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:5px 0"><span style="width:110px;font-size:12px">{n}</span>'
        f'<div style="height:18px;width:{max(2, 300 * v / mx):.0f}px;background:{c}"></div><span style="font-size:12px">{cop(v)}</span></div>'
        for n, v, c in (("Ingresos", s["Ingresos"], "#0b2e59"), ("Materiales", s["Costo_Materiales"], "#8c8c8c"),
                        ("Energía", s["Costo_Energia"], "#8c8c8c"), ("Tiempo muerto", s["Costo_Paradas"], "#e07000")))
    comp = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:2px 0"><span style="width:95px;font-size:12px">{n}</span>'
        f'<div class="prog" style="width:150px"><div style="width:{v:.0f}%"></div></div><b style="font-size:12px;white-space:nowrap">{f(v, 1)} %</b></div>'
        for n, v in (("Disponibilidad", s["Disponibilidad_pct"]), ("Rendimiento", s["Rendimiento_pct"]), ("Calidad", s["Calidad_pct"])))
    cuerpo = f"""
<div class="caja kpi"><h2>OEE</h2><div><span class="valor" style="font-size:30px">{f(s['OEE_pct'], 1)}</span><span class="unid">%</span></div>{comp}</div>
<div class="caja kpi"><h2>Margen sobre ventas</h2><div><span class="valor">{f(s['Margen_pct'], 1)}</span><span class="unid">%</span></div>
<p class="nota">Utilidad: {cop(s['Utilidad'])}</p></div>
<div class="caja kpi"><h2>Costo unitario</h2><div><span class="valor">{f(s['Costo_Unitario'], 0)}</span><span class="unid">COP/vaso</span></div>
<p class="nota">Precio de venta: $ 3.800</p></div>
<div class="caja kpi"><h2>Energía específica</h2><div><span class="valor">{f(s['kWh_por_Unidad'] * 1000, 1)}</span><span class="unid">Wh/vaso</span></div>
<p class="nota">Total: {f(s['Energia_kWh'], 2)} kWh</p></div>
<div class="caja" style="grid-column:1/2"><h2>Material utilizado</h2><table>
<tr><th>Material</th><th>Cantidad</th><th>Costo</th></tr>
<tr><td>Leche</td><td class="n">{f(s['Leche_L'], 0)} L</td><td class="n">{cop(s['Leche_L'] * 3200)}</td></tr>
<tr><td>Cultivo láctico</td><td class="n">{f(s['Cultivo_g'], 0)} g</td><td class="n">{cop(s['Cultivo_g'] * 3000)}</td></tr>
<tr><td>Azúcar</td><td class="n">{f(s['Azucar_kg'], 1)} kg</td><td class="n">{cop(s['Azucar_kg'] * 4500)}</td></tr>
<tr><td>Envases</td><td class="n">{s['Envases_Usados']}</td><td class="n">{cop(s['Envases_Usados'] * 350)}</td></tr>
<tr><td><b>Total materiales</b></td><td></td><td class="n">{cop(s['Costo_Materiales'])}</td></tr></table></div>
<div class="caja"><h2>Producción e inventario</h2><table>
<tr><td>Lotes buenos / rechazados</td><td class="n">{s['Lotes_Buenos']} / {s['Lotes_Rechazados']}</td></tr>
<tr><td>Vasos producidos</td><td class="n">{s['Unidades_Producidas']}</td></tr>
<tr><td>Inventario producto terminado</td><td class="n">{s['Inventario_Und']}</td></tr>
<tr><td>Vasos vendidos</td><td class="n">{s['Unidades_Vendidas']}</td></tr>
<tr><td>Ingresos por ventas</td><td class="n">{cop(s['Ingresos'])}</td></tr></table></div>
<div class="caja"><h2>Tiempos muertos</h2><table>
<tr><td>Tiempo de turno</td><td class="n">{f(s['T_Turno_h'], 2)} h</td></tr>
<tr><td>Tiempo muerto</td><td class="n">{f(s['T_Muerto_h'] * 60, 1)} min</td></tr>
<tr><td>Costo del tiempo muerto</td><td class="n">{cop(s['Costo_Paradas'])}</td></tr>
<tr><td>Costo hora de parada</td><td class="n">$ 85.000</td></tr></table></div>
<div class="caja"><h2>Acciones de gerencia</h2>
<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><span>Venta:</span><b style="border:1px solid #9a9a9a;background:#fff;padding:6px 12px">10</b><span class="btn">REGISTRAR VENTA</span></div>
<div style="display:flex;gap:8px;flex-wrap:wrap"><span class="btn">REPORTE EN LA NUBE</span><span class="btn">REINICIAR TURNO</span><span class="btn sel">DEMANDA AUTO</span></div></div>
<div class="caja" style="grid-column:1/3"><h2>Ingresos vs costos del turno</h2>{barras}</div>
<div class="caja" style="grid-column:3/5"><h2>Costos parametrizables (DB_Param.Costos)</h2>
<p class="nota" style="font-size:13px">Precio de venta, costo de leche, cultivo, azúcar, envase, kWh y hora de parada se editan aquí con campos de E/S
(permiso «Gerencia»). Cada grupo debe usar sus propios valores.</p></div>"""
    return marco("Panel de gerencia", "Gerencia", cuerpo, alarmas(s), "grid-template-columns:repeat(4,1fr);grid-template-rows:180px 1fr 170px",
                 "gerente1 (Gerencia)")


if __name__ == "__main__":
    for nombre, fn in (("operador", operador), ("supervisor", supervisor), ("gerencia", gerencia)):
        (SAL / f"panel_{nombre}.html").write_text(fn(), encoding="utf-8")
        print(SAL / f"panel_{nombre}.html")
