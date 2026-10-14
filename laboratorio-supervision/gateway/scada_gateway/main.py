"""Gateway SCADA: PLC S7-1500 -> base de datos local -> nube, y reportes bajo demanda.

Uso:
    python -m scada_gateway --config config.toml           # PLC real
    python -m scada_gateway --config config.toml --simular # sin PLC (gemelo)
    python -m scada_gateway --config config.toml reporte nube_sup   # reporte manual
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import tomllib
from datetime import datetime, timedelta
from pathlib import Path

from . import layout, reportes
from .database import BaseDatos
from .plc import PlcSimulado, PlcSnap7

log = logging.getLogger("gateway")

TIPOS_REPORTE = {
    # tipo: (campo de solicitud, campo de atención, ¿en la nube?)
    "local": ("ReqCnt_RepLocal", "AckCnt_RepLocal", False),
    "nube_sup": ("ReqCnt_RepNubeSup", "AckCnt_RepNubeSup", True),
    "nube_ger": ("ReqCnt_RepNubeGer", "AckCnt_RepNubeGer", True),
}

CONFIG_POR_DEFECTO = {
    "estacion": {"nombre": "Grupo 1"},
    "plc": {"modo": "snap7", "ip": "192.168.0.1", "rack": 0, "slot": 1, "db_gateway": 100},
    "simulacion": {"factor_tiempo": 1.0, "reportes_cada_s": 0.0},
    "muestreo": {"proceso_s": 1.0, "gerencia_s": 10.0, "sync_s": 5.0},
    "bd_local": {"url": "sqlite:///scada_local.db"},
    "bd_nube": {"url": ""},
    "reportes": {"carpeta": "reportes", "ventana_min": 30, "tolerancia_c": 2.0,
                 "abrir_automaticamente": False},
}


def cargar_config(ruta: str | None) -> dict:
    cfg = {k: dict(v) for k, v in CONFIG_POR_DEFECTO.items()}
    if ruta:
        with open(ruta, "rb") as f:
            for k, v in tomllib.load(f).items():
                cfg.setdefault(k, {}).update(v)
    # La contraseña de la nube no debe quedar en el archivo: se puede dar por variable de entorno.
    if os.environ.get("BD_NUBE_URL"):
        cfg["bd_nube"]["url"] = os.environ["BD_NUBE_URL"]
    return cfg


class Gateway:
    def __init__(self, cfg: dict, plc=None, bd: BaseDatos | None = None):
        self.cfg = cfg
        self.plc = plc or crear_plc(cfg)
        self.bd = bd or BaseDatos(cfg["bd_local"]["url"], cfg["bd_nube"]["url"],
                                  cfg["estacion"]["nombre"])
        self.carpeta = Path(cfg["reportes"]["carpeta"])
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.heartbeat = 0
        self.ack = {t: None for t in TIPOS_REPORTE}
        self.prev: dict | None = None
        self._t_ger = self._t_sync = 0.0
        self.pendientes = 0

    # ------------------------------------------------------------------ ciclo
    def ciclo(self, ahora_mono: float | None = None):
        ahora_mono = time.monotonic() if ahora_mono is None else ahora_mono
        m = self.cfg["muestreo"]
        d = self.plc.leer()
        ts = datetime.now()
        self.bd.guardar_proceso(d, ts)
        if ahora_mono - self._t_ger >= m["gerencia_s"]:
            self._t_ger = ahora_mono
            self.bd.guardar_gerencia(d, ts)
        self._eventos(d, ts)

        for tipo, (req, ack, _nube) in TIPOS_REPORTE.items():
            if self.ack[tipo] is None:      # primer ciclo: tomar el valor que tenga el PLC
                self.ack[tipo] = d[ack]
            if d[req] != self.ack[tipo]:
                try:
                    self.generar_reporte(tipo)
                except Exception:  # noqa: BLE001 - un reporte fallido no tumba el gateway
                    log.exception("No se pudo generar el reporte %s", tipo)
                self.ack[tipo] = d[req]

        if ahora_mono - self._t_sync >= m["sync_s"]:
            self._t_sync = ahora_mono
            self.bd.sincronizar()
            self.pendientes = self.bd.pendientes()

        self.heartbeat = (self.heartbeat + 1) % 30000
        self.plc.escribir_gw({
            "GW_Heartbeat": self.heartbeat,
            "GW_EstadoNube": self.bd.estado_nube,
            "AckCnt_RepLocal": self.ack["local"],
            "AckCnt_RepNubeSup": self.ack["nube_sup"],
            "AckCnt_RepNubeGer": self.ack["nube_ger"],
            "GW_Pendientes": min(self.pendientes, 32767),
        })
        self.prev = d
        return d

    def _eventos(self, d: dict, ts: datetime):
        p = self.prev
        if p is None:
            self.bd.guardar_evento("INICIO", f"Gateway conectado. Estado {layout.ESTADOS.get(d['Estado'])}", ts)
            return
        if d["Estado"] != p["Estado"]:
            self.bd.guardar_evento("ESTADO", f"{layout.ESTADOS.get(p['Estado'])} -> "
                                             f"{layout.ESTADOS.get(d['Estado'])}", ts)
        for bit, texto in layout.BITS_ALARMA.items():
            antes, ahora = (p["Alarmas"] >> bit) & 1, (d["Alarmas"] >> bit) & 1
            if ahora and not antes:
                self.bd.guardar_evento("ALARMA", f"ENTRA: {texto}", ts)
            elif antes and not ahora:
                self.bd.guardar_evento("ALARMA", f"SALE: {texto}", ts)
        if d["Sentido"] != p["Sentido"]:
            nombres = {1: "ADELANTE", -1: "REVERSA", 0: "DETENIDO"}
            self.bd.guardar_evento("VARIADOR", f"Sentido {nombres.get(d['Sentido'])}", ts)
        if d["Lotes_Total"] > p["Lotes_Total"]:
            bueno = d["Lotes_Buenos"] > p["Lotes_Buenos"]
            self.bd.guardar_evento("LOTE", f"Lote #{d['Lotes_Total']} {'CONFORME' if bueno else 'RECHAZADO'}", ts)

    # --------------------------------------------------------------- reportes
    def generar_reporte(self, tipo: str) -> Path:
        _, _, en_nube = TIPOS_REPORTE[tipo]
        hasta = datetime.now()
        desde = hasta - timedelta(minutes=self.cfg["reportes"]["ventana_min"])
        usar_nube = en_nube and self.bd.nube is not None and self.bd.estado_nube == 1
        if en_nube and usar_nube:
            self.bd.sincronizar()  # que la nube tenga lo último antes de consultarla
            usar_nube = self.bd.estado_nube == 1
        origen = "nube" if usar_nube else "local"
        meta = {"estacion": self.bd.estacion, "origen": origen, "generado": hasta,
                "desde": desde, "hasta": hasta}
        tol = self.cfg["reportes"]["tolerancia_c"]
        if tipo == "nube_ger":
            filas = self.bd.consultar("gerencia", desde, hasta, en_nube=usar_nube)
            if not filas and (ult := self.bd.ultima("gerencia", en_nube=usar_nube)):
                filas = [ult]
            pdf, resumen = reportes.reporte_gerencia(filas, meta)
        else:
            filas = self.bd.consultar("proceso", desde, hasta, en_nube=usar_nube)
            ev = self.bd.consultar("eventos", desde, hasta, en_nube=usar_nube)
            pdf, resumen = reportes.reporte_supervisor(filas, ev, meta, tol)
        nombre = reportes.nombre_archivo(tipo, hasta)
        ruta = self.carpeta / nombre
        ruta.write_bytes(pdf)
        # Los reportes de nube quedan en la tabla "reportes" y el ciclo de sincronización
        # los sube (si la nube está caída se suben cuando vuelva).
        self.bd.guardar_reporte(tipo, origen, desde, hasta, reportes.a_json(resumen), nombre,
                                pdf, subir=en_nube, ts=hasta)
        self.bd.guardar_evento("REPORTE", f"Reporte {tipo} generado ({origen}): {nombre}", hasta)
        if en_nube:
            self.bd.sincronizar()
        log.info("Reporte %s -> %s", tipo, ruta)
        if self.cfg["reportes"].get("abrir_automaticamente") and sys.platform == "win32":
            os.startfile(ruta)  # noqa: S606 - abre el PDF en la estación del supervisor
        return ruta

    def correr(self):
        periodo = self.cfg["muestreo"]["proceso_s"]
        log.info("Gateway en marcha (%s). Ctrl+C para salir.", self.bd.estacion)
        errores = 0
        try:
            while True:
                t0 = time.monotonic()
                try:
                    d = self.ciclo(t0)
                    errores = 0
                    log.debug("PV=%.2f SP=%.1f vel=%.0f rpm estado=%s", d["PV_Temp"], d["SP_Temp"],
                              d["Vel_rpm"], layout.ESTADOS.get(d["Estado"]))
                except Exception as exc:  # noqa: BLE001 - reintentar con espera creciente
                    errores += 1
                    espera = min(30, 2 ** min(errores, 5))
                    log.error("Ciclo fallido (%s). Reintento en %d s", exc, espera)
                    time.sleep(espera)
                    continue
                time.sleep(max(0.0, periodo - (time.monotonic() - t0)))
        except KeyboardInterrupt:
            log.info("Detenido por el usuario")
        finally:
            self.plc.cerrar()


def crear_plc(cfg: dict):
    if cfg["plc"]["modo"] == "simulado":
        s = cfg["simulacion"]
        return PlcSimulado(s["factor_tiempo"], s["reportes_cada_s"])
    p = cfg["plc"]
    return PlcSnap7(p["ip"], p["rack"], p["slot"], p["db_gateway"])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gateway SCADA PLC -> BD local -> nube")
    ap.add_argument("--config", default=None, help="archivo TOML (ver config.example.toml)")
    ap.add_argument("--simular", action="store_true", help="usar el gemelo simulado en vez del PLC")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="accion")
    rp = sub.add_parser("reporte", help="generar un reporte ahora, sin esperar al HMI")
    rp.add_argument("tipo", choices=list(TIPOS_REPORTE))
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = cargar_config(a.config)
    if a.simular:
        cfg["plc"]["modo"] = "simulado"
    if a.accion == "reporte":
        gw = Gateway(cfg, plc=_SinPlc())
        print(gw.generar_reporte(a.tipo))
        return
    Gateway(cfg).correr()


class _SinPlc:
    """Para generar reportes desde la base de datos sin conectarse al PLC."""

    def cerrar(self):
        pass


if __name__ == "__main__":
    main()
