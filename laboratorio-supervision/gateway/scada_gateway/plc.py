"""Acceso al PLC: S7-1500 real (python-snap7) o gemelo simulado."""
from __future__ import annotations

import logging
import time

from . import layout
from .simulador import Parametros, PlantaSimulada

log = logging.getLogger(__name__)


class PlcSnap7:
    """Lee/escribe "DB_Gateway" por S7 (puerto 102).

    Requisitos en TIA Portal (ver docs/05_bases_datos_y_reportes.md):
      * CPU > Protección y seguridad > Mecanismos de conexión >
        "Permitir acceso vía comunicación PUT/GET del interlocutor remoto".
      * DB_Gateway con "Acceso optimizado al bloque" DESACTIVADO.
      * S7-1500: rack 0, slot 1.
    """

    def __init__(self, ip: str, rack: int = 0, slot: int = 1, db: int = 100):
        import snap7  # importación tardía: el modo simulado no necesita snap7

        self.ip, self.rack, self.slot, self.db = ip, rack, slot, db
        self.cli = snap7.client.Client()

    def _asegurar_conexion(self):
        if not self.cli.get_connected():
            log.info("Conectando a PLC %s (rack %d, slot %d)", self.ip, self.rack, self.slot)
            self.cli.connect(self.ip, self.rack, self.slot)

    def leer(self) -> dict:
        self._asegurar_conexion()
        return layout.decodificar(self.cli.db_read(self.db, 0, layout.TAMANO_DB))

    def escribir_gw(self, valores: dict):
        self._asegurar_conexion()
        self.cli.db_write(self.db, layout.GW_INICIO, layout.codificar_gw(valores))

    def cerrar(self):
        try:
            self.cli.disconnect()
        except Exception:  # noqa: BLE001 - al cerrar no importa el motivo
            pass


class PlcSimulado:
    """Mismo contrato que PlcSnap7, pero con el gemelo de simulador.py.

    factor_tiempo > 1 acelera la planta (útil para ver lotes completos en minutos).
    """

    def __init__(self, factor_tiempo: float = 1.0, reportes_cada_s: float = 0.0,
                 parametros: Parametros | None = None, paso_s: float = 0.2):
        self.sim = PlantaSimulada(parametros)
        self.factor = factor_tiempo
        self.paso_s = paso_s
        self.reportes_cada_s = reportes_cada_s
        self._t_ult = time.monotonic()
        self._t_rep = 0.0
        self.gw: dict = {}

    def avanzar(self, segundos_sim: float):
        while segundos_sim > 1e-9:
            dt = min(self.paso_s, segundos_sim)
            self.sim.paso(dt)
            segundos_sim -= dt
            if self.reportes_cada_s:
                self._t_rep += dt
                if self._t_rep >= self.reportes_cada_s:
                    self._t_rep = 0.0
                    for k in ("local", "nube_sup", "nube_ger"):
                        self.sim.comando(f"reporte_{k}")

    def leer(self) -> dict:
        ahora = time.monotonic()
        self.avanzar((ahora - self._t_ult) * self.factor)
        self._t_ult = ahora
        # Pasar por bytes ejercita exactamente el mismo camino que con el PLC real.
        valores = self.sim.salidas() | self.gw
        return layout.decodificar(layout.codificar(valores))

    def escribir_gw(self, valores: dict):
        self.gw = {c.nombre: valores.get(c.nombre, 0) for c in layout.GW_CAMPOS}

    def cerrar(self):
        pass
