"""Diagramas de arquitectura, máquina de estados y P&ID simplificado (docs/img/*.png).

    python herramientas/gen_diagramas.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle  # noqa: E402

IMG = Path(__file__).resolve().parents[1] / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)
GRIS, AZUL, OSC = "#e5e7eb", "#1f4e79", "#374151"


def caja(ax, x, y, w, h, titulo, texto="", color=GRIS):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=color, ec=OSC, lw=1.4))
    ax.text(x + w / 2, y + h - 0.18, titulo, ha="center", va="top", fontsize=10.5, weight="bold")
    if texto:
        ax.text(x + w / 2, y + h - 0.55, texto, ha="center", va="top", fontsize=8.6, linespacing=1.35)


def flecha(ax, p, q, txt="", dos=False, estilo="-|>", color=OSC, rad=0.0, dy=0.12):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=("<|-|>" if dos else estilo), mutation_scale=13,
                                 lw=1.4, color=color, connectionstyle=f"arc3,rad={rad}"))
    if txt:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + dy, txt, ha="center", va="bottom", fontsize=8.4,
                color=color, bbox=dict(fc="white", ec="none", pad=0.6))


def arquitectura():
    fig, ax = plt.subplots(figsize=(12, 6.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.6)
    ax.axis("off")
    caja(ax, 0.2, 3.5, 3.2, 2.8, "Planta (diseño del grupo)",
         "Cámara impresa en PETG\nRTD Pt100 (TT-101)\nCalefactor 24 V ~19 W\nVentilador de recirculación\n"
         "Termostato KSD301 60 °C\nHongo de paro de emergencia")
    caja(ax, 0.2, 0.4, 3.2, 2.5, "Tarjeta de borneras (PCB)",
         "Transmisor 4-20 mA + R 250 Ω\nMOSFET del calefactor\nCadena de seguridad cableada\nFusibles, LED, protección")
    caja(ax, 4.4, 2.3, 3.0, 2.6, "PLC S7-1500",
         "FB_Planta (estados, ON-OFF)\nFB_VelocidadVariador\nFB_G120_Telegrama1\nFB_Produccion (KPI)\nDB_HMI · DB_Gateway",
         color="#dbe7f3")
    caja(ax, 4.4, 0.2, 3.0, 1.5, "SINAMICS G120", "Telegrama estándar 1\nMotor del agitador (M-101)")
    caja(ax, 8.5, 3.6, 3.3, 2.7, "PC de supervisión",
         "WinCC Runtime: paneles de\nOperador · Supervisor · Gerencia\n(usuarios por rol)\n\n"
         "Gateway Python (snap7)\nreportes PDF bajo demanda", color="#dbe7f3")
    caja(ax, 8.5, 1.9, 3.3, 1.2, "BD local", "SQLite (o SQL Server)\nfuente de verdad + cola")
    caja(ax, 8.5, 0.2, 3.3, 1.2, "Nube", "PostgreSQL (Supabase)\ntablas + reportes PDF")
    flecha(ax, (1.8, 3.5), (1.8, 2.9), "señales de campo", dos=True)
    flecha(ax, (3.4, 1.6), (4.4, 3.0), "4-20 mA → AI\nDQ 24 V / DI 24 V", dos=True, dy=-0.05)
    flecha(ax, (5.9, 2.3), (5.9, 1.7), "PROFINET", dos=True)
    flecha(ax, (7.4, 4.1), (8.5, 4.7), "Ethernet (S7)\nWinCC + snap7", dos=True)
    flecha(ax, (10.15, 3.6), (10.15, 3.1), "", dos=True)
    flecha(ax, (11.2, 1.9), (11.2, 1.4), "Internet TLS\nsincronización", dos=False, dy=-0.12)
    ax.text(6, 6.35, "Arquitectura del sistema de supervisión local y remota", ha="center", fontsize=13, weight="bold")
    fig.savefig(IMG / "arquitectura.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def estados():
    fig, ax = plt.subplots(figsize=(11, 6.6))
    ax.set_xlim(0, 11)
    ax.set_ylim(-0.4, 6.7)
    ax.set_aspect("equal")
    ax.axis("off")
    pos = {0: (1.4, 4.3, "0\nPARADO"), 1: (5.5, 4.3, "1\nCALENTANDO"), 2: (9.6, 4.3, "2\nEN CONSIGNA\n(fermentación)"),
           3: (1.4, 0.7, "3\nEMERGENCIA"), 4: (5.5, 0.7, "4\nFALLA")}
    for k, (x, y, t) in pos.items():
        ax.add_patch(Circle((x, y), 0.85, fc="#fde2e2" if k >= 3 else ("#dbe7f3" if k else GRIS), ec=OSC, lw=1.5))
        ax.text(x, y, t, ha="center", va="center", fontsize=9.5, weight="bold")
    rojo = "#b91c1c"
    flecha(ax, (2.25, 4.5), (4.65, 4.5), "Start (HMI o pulsador)")
    flecha(ax, (4.65, 4.05), (2.25, 4.05), "Stop", dy=-0.42)
    flecha(ax, (6.35, 4.5), (8.75, 4.5), "|e| ≤ 0,5 °C durante 30 s")
    flecha(ax, (8.75, 4.05), (6.35, 4.05), "|e| > banda de reinicio (4 °C)", dy=-0.42)
    flecha(ax, (9.6, 5.15), (1.4, 5.15), "", rad=0.22)
    ax.text(5.5, 5.92, "Stop", ha="center", va="top", fontsize=8.4, color=OSC)
    flecha(ax, (1.1, 3.45), (1.1, 1.55), "", color=rojo)
    ax.text(0.95, 2.5, "paro de\nemergencia\n(cualquier\nestado)", ha="right", va="center", fontsize=8.2, color=rojo)
    flecha(ax, (1.7, 1.55), (1.7, 3.45), "", color=rojo)
    ax.text(1.85, 2.5, "Rearme sin\nparo activo", ha="left", va="center", fontsize=8.2, color=rojo)
    flecha(ax, (5.5, 3.45), (5.5, 1.55), "", color=rojo)
    ax.text(5.65, 2.5, "falla del sensor ·\nPV ≥ 60 °C ·\ntermostato abierto", ha="left", va="center", fontsize=8.2, color=rojo)
    flecha(ax, (4.85, 1.25), (2.05, 3.75), "", color=rojo)
    ax.text(3.75, 2.25, "Rearme con la\nfalla corregida", ha="left", va="center", fontsize=8.2, color=rojo)
    ax.text(5.5, 6.55, "Máquina de estados de FB_Planta", ha="center", fontsize=13, weight="bold")
    ax.text(0.1, -0.35, "En 3 y 4: calefactor OFF, variador OFF1. En 2 el agitador está detenido y corre el temporizador del lote.",
            fontsize=8.4, color=OSC)
    fig.savefig(IMG / "maquina_estados.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def pid():
    """P&ID simplificado con nomenclatura ISA-5.1."""
    fig, ax = plt.subplots(figsize=(11, 5.8))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5.8)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((1.0, 0.8), 4.2, 3.4, boxstyle="round,pad=0.02,rounding_size=0.15", fc="#f3f4f6", ec=OSC, lw=2))
    ax.text(3.1, 4.35, "INC-101 Cámara de incubación", ha="center", fontsize=10, weight="bold")
    ax.add_patch(plt.Rectangle((2.1, 1.1), 2.0, 0.25, fc=OSC))
    ax.text(3.1, 0.95, "E-101 calefactor", ha="center", va="top", fontsize=8.5)
    ax.add_patch(Circle((1.6, 1.9), 0.28, fc="white", ec=OSC, lw=1.5))
    ax.text(1.6, 1.9, "F", ha="center", va="center", fontsize=9)
    ax.text(1.6, 1.5, "K-101", ha="center", fontsize=8)

    def instr(x, y, tag1, tag2, linea_a=None, campo=True):
        ax.add_patch(Circle((x, y), 0.36, fc="white", ec=OSC, lw=1.5, zorder=3))
        if not campo:
            ax.plot([x - 0.36, x + 0.36], [y, y], color=OSC, lw=1.2, zorder=4)
        ax.text(x, y + (0.15 if not campo else 0.08), tag1, ha="center", va="center", fontsize=8.5, weight="bold", zorder=5)
        ax.text(x, y - 0.17, tag2, ha="center", va="center", fontsize=7.5, zorder=5)
        if linea_a:
            ax.plot([x, linea_a[0]], [y, linea_a[1]], color=OSC, lw=1.2, ls=(0, (4, 2)), zorder=1)

    instr(6.3, 3.2, "TT", "101")
    ax.plot([5.2, 5.94], [3.2, 3.2], color=OSC, lw=1.6)
    instr(8.0, 3.2, "TIC", "101", linea_a=(6.66, 3.2), campo=False)
    instr(8.0, 4.7, "TAH", "101", linea_a=(8.0, 3.56), campo=False)
    instr(9.5, 4.7, "TAHH", "101", linea_a=(8.36, 4.7), campo=False)
    instr(6.3, 1.9, "TSH", "102")
    ax.plot([5.2, 5.94], [1.9, 1.9], color=OSC, lw=1.6)
    ax.text(6.3, 1.35, "KSD301 60 °C", ha="center", fontsize=7.5)
    ax.plot([8.0, 8.0, 3.1], [2.84, 0.4, 0.4], color=OSC, lw=1.2, ls=(0, (4, 2)), zorder=1)
    ax.plot([3.1, 3.1], [0.4, 1.1], color=OSC, lw=1.2, ls=(0, (4, 2)))
    ax.text(5.6, 0.48, "ON-OFF (DQ_Calefactor)", fontsize=8)
    instr(9.5, 3.2, "SC", "101", linea_a=(8.36, 3.2), campo=False)
    ax.add_patch(Circle((9.5, 1.6), 0.36, fc="white", ec=OSC, lw=1.5))
    ax.text(9.5, 1.6, "M", ha="center", va="center", fontsize=10, weight="bold")
    ax.text(9.5, 1.08, "M-101 agitador", ha="center", fontsize=8)
    ax.plot([9.5, 9.5], [2.84, 1.96], color=OSC, lw=1.2)
    ax.text(9.62, 2.35, "G120", fontsize=7.5)
    instr(6.3, 4.7, "HS", "101")
    ax.text(6.3, 5.2, "paro de emergencia", ha="center", fontsize=7.5)
    ax.text(5.5, 5.55, "P&ID simplificado (ISA-5.1)", ha="center", fontsize=13, weight="bold")
    ax.text(0.1, 0.05, "Círculo sin línea = instrumento de campo; con línea = función en el PLC/HMI. "
            "Línea discontinua = señal eléctrica.", fontsize=8, color=OSC)
    fig.savefig(IMG / "pid.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    arquitectura()
    estados()
    pid()
    print("ok", IMG)
