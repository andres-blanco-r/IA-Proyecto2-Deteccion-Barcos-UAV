"""Gemelo en Python de la lógica del PLC (FB_Planta y sus sub-bloques).

Sirve para tres cosas:
  1. Probar el gateway, la base de datos y los reportes sin PLC (modo "simulado").
  2. Generar las curvas de diseño del informe (herramientas/simular_diseno.py).
  3. Documentar con código ejecutable el mismo algoritmo que está en las fuentes SCL.

Cada bloque lleva el nombre del FB equivalente en plc/fuentes_scl/02_Bloques.scl.
Si cambia la lógica en el PLC, cámbiela también aquí.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from . import layout

PARADO, CALENTANDO, EN_CONSIGNA, EMERGENCIA, FALLA = range(5)


@dataclass
class Parametros:
    """Valores iniciales de "DB_Param" (los mismos que en 03_DB_Globales.db)."""

    # --- Proceso: incubación de yogur ---
    sp: float = 43.0                # set point [°C]
    sp_min: float = 25.0
    sp_max: float = 55.0            # límite por la carcasa impresa (PETG)
    histeresis: float = 1.0         # banda total del ON-OFF [°C] (±0.5)
    tol_consigna: float = 0.5       # |e| para considerar "en consigna" [°C]
    t_estabilizacion_s: float = 30.0
    banda_reinicio: float = 4.0     # si |e| supera esto, el agitador vuelve a arrancar
    t_alta_delta: float = 4.0       # alarma H: PV > SP + delta
    t_baja_delta: float = 2.0       # alarma L (en consigna): PV < SP - delta
    t_disparo: float = 60.0         # alarma HH: apaga todo
    tol_calidad: float = 2.0        # |e| máximo aceptable durante la fermentación
    max_fuera_tol_s: float = 60.0   # tiempo máximo fuera de tolerancia por lote
    t_lote_s: float = 300.0         # duración del lote (5 min de demo; real 4-6 h)
    # --- Variador (agitador) ---
    vmin_pct: float = 20.0
    vmax_pct: float = 100.0
    error_vel_max: float = 15.0     # con |e| >= esto el agitador va a Vmax
    vel_nominal_rpm: float = 1800.0  # p2000 del G120
    rampa_s: float = 5.0            # p1120/p1121 (solo para el simulador)
    # --- Planta simulada (FB_SimPlanta) ---
    sim_potencia_w: float = 20.0    # 2 x RH25 15 ohm en serie a 24 V = 19,2 W
    sim_c_placa: float = 80.0       # capacidad térmica calefactor+placa [J/K]
    sim_r_placa: float = 0.5        # resistencia placa->aire [K/W]
    sim_c_camara: float = 450.0     # aire + paredes PETG + bandeja [J/K]
    sim_r_camara: float = 2.4       # paredes PETG 2,4 mm, área ext. ~0,11 m² [K/W]
    sim_tamb: float = 19.0          # ambiente en Bogotá [°C]
    sim_tau_sensor: float = 15.0    # constante de tiempo de la RTD en vaina [s]
    sim_ruido: float = 0.05         # desviación del ruido de medida [°C]
    # --- Gerencia (UDT_Costos) ---
    und_por_lote: int = 100         # vasos de 200 mL por lote de 20 L
    leche_l_lote: float = 20.0
    precio_leche_l: float = 3200.0
    cultivo_g_lote: float = 5.0
    precio_cultivo_g: float = 3000.0
    azucar_kg_lote: float = 1.6
    precio_azucar_kg: float = 4500.0
    precio_envase: float = 350.0
    potencia_planta_kw: float = 3.0  # calefactor equivalente a escala industrial
    precio_kwh: float = 950.0
    costo_hora_parada: float = 85000.0
    precio_venta_und: float = 3800.0
    t_ciclo_ideal_s: float = 300.0
    inventario_min: int = 50
    t_entre_pedidos_s: float = 60.0
    pedido_max: int = 40


# ----------------------------------------------------------------------------
# Bloques (equivalentes a los FB del PLC)
# ----------------------------------------------------------------------------
class OnOffHisteresis:
    """FB_OnOffHist: salida ON por debajo de SP-H/2, OFF por encima de SP+H/2."""

    def __init__(self):
        self.salida = False

    def __call__(self, pv, sp, h, habilitar, accion_inversa=False):
        if not habilitar:
            self.salida = False
            return False
        e = (pv - sp) if accion_inversa else (sp - pv)
        if e > h / 2:
            self.salida = True
        elif e < -h / 2:
            self.salida = False
        return self.salida


class LeyVelocidad:
    """FB_VelocidadVariador: velocidad proporcional al error, parada al llegar al SP."""

    def __init__(self):
        self.alcanzada = False

    def __call__(self, pv, sp, habilitar, p: Parametros, manual=False, vel_manual=0.0):
        abs_e = abs(sp - pv)
        if not habilitar:
            self.alcanzada = False
            return 0.0
        if abs_e <= p.tol_consigna:
            self.alcanzada = True
        elif abs_e > p.banda_reinicio:
            self.alcanzada = False
        if manual:
            return max(0.0, min(100.0, vel_manual))
        if self.alcanzada:
            return 0.0
        frac = max(0.0, min(1.0, abs_e / p.error_vel_max))
        return p.vmin_pct + (p.vmax_pct - p.vmin_pct) * frac


class SimPlanta:
    """FB_SimPlanta: modelo térmico de 2 nodos (placa calefactora + cámara) + sensor."""

    def __init__(self, p: Parametros, rng: random.Random):
        self.p, self.rng = p, rng
        self.t_placa = self.t_camara = self.t_sensor = p.sim_tamb

    def paso(self, calefactor: bool, dt: float) -> float:
        p = self.p
        q_pc = (self.t_placa - self.t_camara) / p.sim_r_placa
        q_ca = (self.t_camara - p.sim_tamb) / p.sim_r_camara
        self.t_placa += dt * ((p.sim_potencia_w if calefactor else 0.0) - q_pc) / p.sim_c_placa
        self.t_camara += dt * (q_pc - q_ca) / p.sim_c_camara
        self.t_sensor += dt * (self.t_camara - self.t_sensor) / p.sim_tau_sensor
        return self.t_sensor + self.rng.gauss(0.0, p.sim_ruido)


class SimVariador:
    """FB_SimVariador: rampa de velocidad del G120 (telegrama 1)."""

    def __init__(self, p: Parametros):
        self.p, self.vel_pct = p, 0.0

    def paso(self, marcha: bool, ref_pct: float, dt: float) -> float:
        obj = ref_pct if marcha else 0.0
        paso = 100.0 / self.p.rampa_s * dt
        self.vel_pct += max(-paso, min(paso, obj - self.vel_pct))
        return self.vel_pct


# ----------------------------------------------------------------------------
# Planta completa (FB_Planta + FB_Produccion + FB_Alarmas)
# ----------------------------------------------------------------------------
@dataclass
class Produccion:
    turno_activo: bool = False
    t_turno: float = 0.0
    t_muerto: float = 0.0
    t_banda: float = 0.0
    t_lote: float = 0.0
    t_fuera: float = 0.0
    lotes_total: int = 0
    lotes_buenos: int = 0
    lotes_rechazados: int = 0
    unidades: int = 0
    vendidas: int = 0
    inventario: int = 0
    energia_kwh: float = 0.0
    t_pedido: float = 0.0
    rechazo_pendiente: bool = False


class PlantaSimulada:
    def __init__(self, p: Parametros | None = None, semilla: int = 1, auto_arranque: bool = True):
        self.p = p or Parametros()
        self.rng = random.Random(semilla)
        self.planta = SimPlanta(self.p, self.rng)
        self.vfd = SimVariador(self.p)
        self.onoff = OnOffHisteresis()
        self.ley = LeyVelocidad()
        self.prod = Produccion()
        self.estado = PARADO
        self.pv = self.p.sim_tamb
        self.calefactor = False
        self.vfd_habilitado = False
        self.reversa = False
        self.vel_ref = 0.0
        self.duty = 0.0
        self.t_estab = 0.0
        self.paro_hmi = False
        self.req = {"local": 0, "nube_sup": 0, "nube_ger": 0}
        self.t = 0.0
        self._cmd: set[str] = set()
        if auto_arranque:
            self.comando("start")
            self.comando("vfd_arranque")

    # --- Comandos que en el PLC llegan desde el HMI ("DB_HMI".Cmd_*) ---
    def comando(self, nombre: str, valor=None):
        if nombre == "sp":
            self.p.sp = max(self.p.sp_min, min(self.p.sp_max, float(valor)))
        elif nombre == "reversa":
            self.reversa = bool(valor)
        elif nombre == "venta":
            self._vender(int(valor))
        elif nombre.startswith("reporte_"):
            k = nombre.removeprefix("reporte_")
            self.req[k] = (self.req[k] + 1) % 32768
        else:
            self._cmd.add(nombre)

    def _vender(self, q: int):
        q = max(0, min(q, self.prod.inventario))
        self.prod.inventario -= q
        self.prod.vendidas += q

    # --- Un ciclo de PLC ---
    def paso(self, dt: float):
        p, pr, cmd = self.p, self.prod, self._cmd
        self.t += dt
        if "paro_emergencia" in cmd:
            self.paro_hmi = True
        if "rearme" in cmd:
            self.paro_hmi = False
            pr.rechazo_pendiente = False
        emergencia = self.paro_hmi
        sensor_falla = False  # en simulación el lazo 4-20 mA siempre está sano
        falla_critica = sensor_falla or self.pv >= p.t_disparo
        e = p.sp - self.pv

        # Máquina de estados (FB_Planta, región "ESTADOS")
        if emergencia:
            self.estado = EMERGENCIA
        elif self.estado == EMERGENCIA:
            if "rearme" in cmd:
                self.estado = PARADO
        elif self.estado == FALLA:
            if "rearme" in cmd and not falla_critica:
                self.estado = PARADO
        elif falla_critica:
            self.estado = FALLA
        elif "stop" in cmd:
            self.estado = PARADO
        elif self.estado == PARADO and "start" in cmd:
            self.estado = CALENTANDO
        elif self.estado == CALENTANDO:
            self.t_estab = self.t_estab + dt if abs(e) <= p.tol_consigna else 0.0
            if self.t_estab >= p.t_estabilizacion_s:
                self.estado = EN_CONSIGNA
        elif self.estado == EN_CONSIGNA and abs(e) > p.banda_reinicio:
            self.estado = CALENTANDO
        if self.estado != CALENTANDO:
            self.t_estab = 0.0

        en_marcha = self.estado in (CALENTANDO, EN_CONSIGNA)
        if "vfd_arranque" in cmd:
            self.vfd_habilitado = True
        if "vfd_parada" in cmd or self.estado in (EMERGENCIA, FALLA):
            self.vfd_habilitado = False

        # Control ON-OFF y variador
        self.calefactor = self.onoff(self.pv, p.sp, p.histeresis, en_marcha and not falla_critica)
        self.vel_ref = self.ley(self.pv, p.sp, en_marcha and self.vfd_habilitado, p)
        marcha_vfd = self.vfd_habilitado and en_marcha and self.vel_ref > 0
        signo = -1.0 if self.reversa else 1.0
        vel = self.vfd.paso(marcha_vfd, signo * self.vel_ref, dt)
        self.vel_pct = vel
        self.duty += ((100.0 if self.calefactor else 0.0) - self.duty) * min(1.0, dt / 60.0)

        # Planta física
        self.pv = self.planta.paso(self.calefactor, dt)

        # Producción (FB_Produccion)
        if "reset_turno" in cmd:
            self.prod = pr = Produccion()
        if en_marcha:
            pr.turno_activo = True
        if pr.turno_activo:
            pr.t_turno += dt
            if not en_marcha:
                pr.t_muerto += dt
            elif abs(e) <= p.tol_calidad:
                pr.t_banda += dt
        if self.estado == EN_CONSIGNA:
            pr.t_lote += dt
            if abs(e) > p.tol_calidad:
                pr.t_fuera += dt
            if pr.t_lote >= p.t_lote_s:
                pr.lotes_total += 1
                if pr.t_fuera <= p.max_fuera_tol_s:
                    pr.lotes_buenos += 1
                    pr.unidades += p.und_por_lote
                    pr.inventario += p.und_por_lote
                else:
                    pr.lotes_rechazados += 1
                    pr.rechazo_pendiente = True
                pr.t_lote = pr.t_fuera = 0.0
        if self.calefactor:
            pr.energia_kwh += p.potencia_planta_kw * dt / 3600.0
        if pr.turno_activo:
            pr.t_pedido += dt
            if pr.t_pedido >= p.t_entre_pedidos_s:
                pr.t_pedido = 0.0
                self._vender(self.rng.randint(1, p.pedido_max))
        cmd.clear()

    # --- Lo que el PLC copia en "DB_Gateway" ---
    def salidas(self) -> dict:
        p, pr = self.p, self.prod
        e = p.sp - self.pv
        envases = pr.lotes_total * p.und_por_lote
        leche = pr.lotes_total * p.leche_l_lote
        cultivo = pr.lotes_total * p.cultivo_g_lote
        azucar = pr.lotes_total * p.azucar_kg_lote
        c_mat = (leche * p.precio_leche_l + cultivo * p.precio_cultivo_g
                 + azucar * p.precio_azucar_kg + envases * p.precio_envase)
        c_ene = pr.energia_kwh * p.precio_kwh
        c_par = pr.t_muerto / 3600.0 * p.costo_hora_parada
        ingresos = pr.vendidas * p.precio_venta_und
        utilidad = ingresos - c_mat - c_ene - c_par
        t_oper = pr.t_turno - pr.t_muerto
        disp = t_oper / pr.t_turno if pr.t_turno > 0 else 0.0
        rend = min(1.0, pr.lotes_total * p.t_ciclo_ideal_s / t_oper) if t_oper > 0 else 0.0
        cal = pr.lotes_buenos / pr.lotes_total if pr.lotes_total else 1.0
        en_marcha = self.estado in (CALENTANDO, EN_CONSIGNA)
        marcha_vfd = abs(self.vfd.vel_pct) > 0.5

        bits = {
            "ProcesoEnMarcha": en_marcha,
            "Calefactor": self.calefactor,
            "VFD_Habilitado": self.vfd_habilitado,
            "VFD_EnMarcha": marcha_vfd,
            "VFD_Falla": False,
            "EnConsigna": self.estado == EN_CONSIGNA,
            "Emergencia": self.estado == EMERGENCIA,
            "ModoSimulacion": True,
            "Ventilador": en_marcha,
            "VFD_ModoManual": False,
            "TurnoActivo": pr.turno_activo,
        }
        alarmas = {
            0: self.estado == EMERGENCIA,
            1: en_marcha and self.pv > p.sp + p.t_alta_delta,
            2: self.pv >= p.t_disparo,
            3: self.estado == EN_CONSIGNA and self.pv < p.sp - p.t_baja_delta,
            8: pr.rechazo_pendiente,
            9: pr.turno_activo and pr.inventario < p.inventario_min,
            11: True,
        }
        palabra_bits = sum(1 << b for b, n in layout.BITS_ESTADO.items() if bits[n])
        palabra_alm = sum(1 << b for b, v in alarmas.items() if v)
        return {
            "PV_Temp": self.pv,
            "SP_Temp": p.sp,
            "Error_Temp": e,
            "Senal_mA": 4.0 + 16.0 * self.pv / 100.0,
            "Duty_Calefactor_pct": self.duty,
            "TiempoEnBanda_pct": 100.0 * pr.t_banda / t_oper if t_oper > 0 else 0.0,
            "VelRef_pct": self.vel_ref,
            "Vel_pct": abs(self.vfd.vel_pct),
            "Vel_rpm": abs(self.vfd.vel_pct) * p.vel_nominal_rpm / 100.0,
            "ProgresoLote_pct": 100.0 * pr.t_lote / p.t_lote_s,
            "Energia_kWh": pr.energia_kwh,
            "Costo_Energia": c_ene,
            "Leche_L": leche,
            "Cultivo_g": cultivo,
            "Azucar_kg": azucar,
            "Costo_Materiales": c_mat,
            "T_Turno_h": pr.t_turno / 3600.0,
            "T_Muerto_h": pr.t_muerto / 3600.0,
            "Costo_Paradas": c_par,
            "Ingresos": ingresos,
            "Utilidad": utilidad,
            "Margen_pct": 100.0 * utilidad / ingresos if ingresos > 0 else 0.0,
            "OEE_pct": 100.0 * disp * rend * cal,
            "Disponibilidad_pct": 100.0 * disp,
            "Rendimiento_pct": 100.0 * rend,
            "Calidad_pct": 100.0 * cal,
            "Costo_Unitario": (c_mat + c_ene) / pr.unidades if pr.unidades else 0.0,
            "kWh_por_Unidad": pr.energia_kwh / pr.unidades if pr.unidades else 0.0,
            "Lotes_Total": pr.lotes_total,
            "Lotes_Buenos": pr.lotes_buenos,
            "Lotes_Rechazados": pr.lotes_rechazados,
            "Unidades_Producidas": pr.unidades,
            "Unidades_Vendidas": pr.vendidas,
            "Inventario_Und": pr.inventario,
            "Envases_Usados": envases,
            "Estado": self.estado,
            "Sentido": 0 if not marcha_vfd else (-1 if self.vfd.vel_pct < 0 else 1),
            "Bits_Estado": palabra_bits,
            "Alarmas": palabra_alm,
            "ReqCnt_RepLocal": self.req["local"],
            "ReqCnt_RepNubeSup": self.req["nube_sup"],
            "ReqCnt_RepNubeGer": self.req["nube_ger"],
        }
