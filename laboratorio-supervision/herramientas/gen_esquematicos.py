"""Dibuja los esquemáticos de la tarjeta de borneras (hardware/pcb/*.png|svg).

    python herramientas/gen_esquematicos.py
"""
from pathlib import Path

import schemdraw
import schemdraw.elements as elm

SAL = Path(__file__).resolve().parents[1] / "hardware" / "pcb"
SAL.mkdir(parents=True, exist_ok=True)
schemdraw.config(fontsize=11, unit=2.5)


def lazo():
    """Lazo 4-20 mA de 2 hilos: +24 V -> transmisor -> R de carga 250 ohm -> 0 V."""
    with schemdraw.Drawing(show=False) as d:
        d += elm.Label().at((-0.3, 0)).label("+24 V\nbanco", halign="right")
        d += elm.Dot(open=True).at((0, 0))
        d += elm.Fuse().right().label("F2  100 mA")
        d += elm.Diode().right().label("D1  1N4007")
        d += elm.Line().right(1)
        d += elm.Dot().label("J2-1", loc="top")
        tx = elm.Ic(pins=[elm.IcPin(name="+", side="left"),
                          elm.IcPin(name="−", side="right"),
                          elm.IcPin(name="RTD1", side="bottom", slot="1/3"),
                          elm.IcPin(name="RTD2", side="bottom", slot="2/3"),
                          elm.IcPin(name="RTD3", side="bottom", slot="3/3")],
                    size=(4.2, 2.6), pinspacing=1.2, label="Transmisor\nPt100 → 4-20 mA\n(XTR105 o comercial)",
                    lblsize=10).anchor("+")
        d += tx
        # RTD de 3 hilos debajo del transmisor
        d += elm.Line().at(tx.RTD1).down(1.4)
        a = d.here
        d += elm.Line().at(tx.RTD3).down(1.4)
        b = d.here
        d += elm.RBox().endpoints(a, b).label("Pt100 (RTD del laboratorio, 3 hilos)", loc="bottom", ofst=0.3)
        d += elm.Line().at(tx.RTD2).down(0.7)
        d += elm.Line().right().tox(b)
        d += elm.Dot()
        # Salida del lazo
        d += elm.Line().at(getattr(tx, "−")).right(1.5)
        d += elm.Dot().label("J2-2 → AI0+", loc="top")
        n = d.here
        y0 = n[1] - 5
        d += elm.Resistor().down().toy(y0).label("RS 250 Ω\n0,1 %", loc="bottom")
        d += elm.Dot()
        d += elm.Line().at(n).right(3)
        d += elm.Zener().down().reverse().toy(y0).label("DZ1\n6,2 V", loc="bottom")
        d += elm.Line().at((n[0] + 3, n[1])).right(3)
        d += elm.Capacitor().down().toy(y0).label("C1\n100 nF", loc="bottom")
        d += elm.Line().left().tox(0)
        d += elm.Dot(open=True)
        d += elm.Label().at((-0.3, y0)).label("0 V (M)\nbanco y\nAI0− (M_ANA)", halign="right")
        d += elm.Label().at((n[0] + 1, y0 - 1.6)).label(
            "4 mA → 1,0 V      12 mA → 3,0 V      20 mA → 5,0 V\n"
            "Canal AI0 configurado en 1..5 V (o 0..10 V). DZ1 limita a 6,2 V si el transmisor satura.",
            halign="center")
    d.save(SAL / "esquema_lazo_4_20mA.svg")
    d.save(SAL / "esquema_lazo_4_20mA.png", dpi=150)


def potencia():
    """Calefactor con cadena de seguridad cableada, ventilador y paro de emergencia."""
    with schemdraw.Drawing(show=False) as d:
        # --- Columna del calefactor (x = 0) ---
        d += elm.Vdd().at((0, 0)).label("+24 V banco")
        d += elm.Fuse().down().label("F1  3 A lento")
        d += elm.Switch(nc=True).down().label("S1a  hongo de\nparo NC")
        d += elm.Switch(nc=True).down().label("TS1  KSD301\n60 °C NC")
        d += elm.Dot()
        cad = d.here
        d += elm.Resistor().down().label("H1  calefactor 24 V\n2 × RH25 15 Ω\nen serie (19 W)")
        d += elm.Dot()
        dr = d.here
        q = elm.NFet(bulk=False).right().reverse().anchor("drain").at(dr).label("Q1\nIRLZ44N", loc="right", ofst=(0.3, 0))
        d += q
        d += elm.Ground().at(q.source)
        # Compuerta: DQ -> R1 -> G ; R2 y DZ2 a tierra
        d += elm.Line().at(q.gate).left(1.2)
        d += elm.Dot()
        g = d.here
        d += elm.Resistor().down().label("R2\n10 kΩ", loc="bottom")
        d += elm.Ground()
        d += elm.Line().at(g).left(2.5)
        d += elm.Dot()
        g2 = d.here
        d += elm.Zener().down().reverse().label("DZ2\n15 V", loc="bottom")
        d += elm.Ground()
        d += elm.Resistor().at(g2).left().label("R1  10 kΩ")
        d += elm.Dot(open=True)
        d += elm.Label().label("J3-1\nDQ_Calefactor\n%Q0.0", loc="left", halign="right")
        # Indicador LED en paralelo con el calefactor
        d += elm.Line().at(cad).right(4)
        d += elm.Dot()
        led = d.here
        d += elm.Resistor().down(2.2).label("R3\n2,2 kΩ")
        d += elm.LED().down().toy(dr).label("LED1")
        d += elm.Line().left().tox(dr)
        # Señal de cadena de seguridad al PLC
        d += elm.Line().at(led).right(3)
        d += elm.Dot(open=True)
        d += elm.Label().label("J4-1 → DI_CadenaSeguridad (%I0.3)", loc="right", halign="left")

        # --- Paro de emergencia, contacto 2 (x = 13) ---
        d += elm.Vdd().at((13, 0)).label("+24 V")
        d += elm.Switch(nc=True).down().label("S1b  hongo de\nparo NC")
        d += elm.Line().down(0.8)
        d += elm.Dot(open=True)
        d += elm.Label().label("J4-2 → DI_ParoEmergencia (%I0.0)", loc="right", halign="left")

        # --- Ventilador (x = 13, abajo) ---
        d += elm.Dot(open=True).at((13, -8))
        d += elm.Label().at((13.3, -8)).label("J3-2  DQ_Ventilador (%Q0.1)", halign="left")
        d += elm.Line().down(0.8)
        d += elm.Dot()
        fv = d.here
        d += elm.Motor().down().label("M1  ventilador\n24 V 40 mm", loc="bottom")
        d += elm.Dot()
        fb = d.here
        d += elm.Ground()
        d += elm.Line().at(fv).left(2.4)
        d += elm.Diode().down().reverse().toy(fb).label("D2\n1N4007", loc="bottom")
        d += elm.Line().right().tox(fb)
        d += elm.Label().at((6.5, -14.5)).label(
            "Todas las tierras = 0 V (M) de la fuente del banco del PLC.   "
            "El calefactor solo enciende si: paro no accionado  Y  termostato cerrado  Y  DQ_Calefactor = 1.",
            halign="center")
    d.save(SAL / "esquema_potencia.svg")
    d.save(SAL / "esquema_potencia.png", dpi=150)


if __name__ == "__main__":
    lazo()
    potencia()
    print("ok", SAL)
