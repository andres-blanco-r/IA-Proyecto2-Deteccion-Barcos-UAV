"""Curvas de diseño (respuesta ESPERADA según el modelo, no son mediciones).

    python herramientas/simular_diseno.py

Escenario de 70 min: arranque en frío con SP = 43 °C, inversión de giro a los 30 min,
cambio de SP a 48 °C a los 40 min y apertura de la tapa (pérdidas x2) de 55 a 57 min.
Genera docs/img/sim_respuesta.png y docs/img/sim_metricas.md
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "gateway"))
from scada_gateway.simulador import EN_CONSIGNA, PlantaSimulada  # noqa: E402

DT = 0.2
sim = PlantaSimulada(semilla=7)
r_base = sim.p.sim_r_camara
t, pv, sp, cal, vel, est, lotes = [], [], [], [], [], [], []
for k in range(int(70 * 60 / DT)):
    s = k * DT
    if abs(s - 30 * 60) < DT / 2:
        sim.comando("reversa", True)
    if abs(s - 40 * 60) < DT / 2:
        sim.comando("sp", 48.0)
    sim.p.sim_r_camara = r_base / 2 if 55 * 60 <= s < 57 * 60 else r_base
    sim.paso(DT)
    t.append(s / 60)
    pv.append(sim.pv)
    sp.append(sim.p.sp)
    cal.append(sim.calefactor)
    vel.append(sim.vfd.vel_pct * sim.p.vel_nominal_rpm / 100)
    est.append(sim.estado)
    lotes.append(sim.prod.lotes_total)

# --- métricas del tramo SP = 43 °C ---
i_sp = next(i for i, v in enumerate(pv) if v >= 43 - 0.5)
i_cons = next(i for i, e in enumerate(est) if e == EN_CONSIGNA)
tramo = [v for ti, v in zip(t, pv) if 20 <= ti < 30]
cal_tramo = [c for ti, c in zip(t, cal) if 20 <= ti < 30]
cambios = sum(1 for a, b in zip(cal_tramo, cal_tramo[1:]) if b and not a)
sobrepico = max(v for ti, v in zip(t, pv) if ti < 30) - 43
metricas = {
    "Tiempo hasta SP − 0,5 °C (arranque en frío)": f"{t[i_sp]:.1f} min",
    "Tiempo hasta estado EN CONSIGNA": f"{t[i_cons]:.1f} min",
    "Sobrepico máximo sobre 43 °C": f"{sobrepico:.2f} °C",
    "Oscilación en régimen (pico a pico, min 20–30)": f"{max(tramo) - min(tramo):.2f} °C",
    "Período del ciclo ON-OFF en régimen": f"{10 * 60 / max(cambios, 1):.0f} s",
    "Ciclo de trabajo del calefactor en régimen": f"{100 * sum(cal_tramo) / len(cal_tramo):.0f} %",
    "Lotes terminados en 70 min (lote de 5 min)": f"{lotes[-1]}",
}
lineas = ["| Métrica (modelo) | Valor esperado |", "|---|---|"] + [f"| {k} | {v} |" for k, v in metricas.items()]
(RAIZ / "docs" / "img" / "sim_metricas.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
print("\n".join(lineas))

fig, ax = plt.subplots(3, 1, figsize=(10, 7.5), sharex=True, gridspec_kw={"height_ratios": [3, 1, 2]})
ax[0].plot(t, sp, "--", color="#6b7280", label="Set point")
ax[0].plot(t, pv, color="#1f4e79", lw=1.2, label="Temperatura medida (modelo)")
ax[0].axvspan(55, 57, color="#fde68a", alpha=0.5, label="Tapa abierta (perturbación)")
ax[0].set_ylabel("°C")
ax[0].legend(loc="lower right", fontsize=8)
ax[0].grid(alpha=0.3)
ax[0].set_title("Respuesta esperada de la incubadora (gemelo del PLC)")
ax[1].fill_between(t, cal, step="post", color="#b91c1c", alpha=0.6)
ax[1].set_ylabel("Calefactor")
ax[1].set_yticks([0, 1], ["OFF", "ON"])
ax[2].plot(t, vel, color="#1f4e79")
ax[2].axhline(0, color="black", lw=0.6)
ax[2].set_ylabel("Agitador [rpm]\n(+ adelante / − reversa)")
ax[2].set_xlabel("Tiempo [min]")
ax[2].grid(alpha=0.3)
for x, txt in ((30, "inversión\nde giro"), (40, "SP 43→48 °C")):
    for a in ax:
        a.axvline(x, color="#9ca3af", lw=0.8, ls=":")
    ax[2].annotate(txt, (x, 1200), fontsize=8, ha="left", xytext=(x + 0.4, 1200))
fig.tight_layout()
salida = RAIZ / "docs" / "img" / "sim_respuesta.png"
fig.savefig(salida, dpi=130)
print(salida)
