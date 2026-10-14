"""Base de datos local (SQLite por defecto) y en la nube (PostgreSQL, p. ej. Supabase).

La base local es la fuente de verdad: cada muestra se guarda primero en local con
sincronizado = False y un ciclo aparte la sube a la nube en lotes. Si se cae
Internet, las filas se acumulan y se suben cuando vuelve la conexión.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, Float, Integer, LargeBinary, MetaData,
                        String, Table, Text, create_engine, insert, select, update)

log = logging.getLogger(__name__)

# columna_bd -> campo de layout.py
COLS_PROCESO = {
    "estado": "Estado",
    "pv_c": "PV_Temp",
    "sp_c": "SP_Temp",
    "error_c": "Error_Temp",
    "senal_ma": "Senal_mA",
    "calefactor": "Calefactor",
    "duty_calefactor_pct": "Duty_Calefactor_pct",
    "tiempo_en_banda_pct": "TiempoEnBanda_pct",
    "vel_ref_pct": "VelRef_pct",
    "vel_pct": "Vel_pct",
    "vel_rpm": "Vel_rpm",
    "sentido": "Sentido",
    "vfd_en_marcha": "VFD_EnMarcha",
    "vfd_falla": "VFD_Falla",
    "en_consigna": "EnConsigna",
    "progreso_lote_pct": "ProgresoLote_pct",
    "alarmas": "Alarmas",
}
COLS_GERENCIA = {
    "lotes_total": "Lotes_Total",
    "lotes_buenos": "Lotes_Buenos",
    "lotes_rechazados": "Lotes_Rechazados",
    "unidades_producidas": "Unidades_Producidas",
    "unidades_vendidas": "Unidades_Vendidas",
    "inventario_und": "Inventario_Und",
    "leche_l": "Leche_L",
    "cultivo_g": "Cultivo_g",
    "azucar_kg": "Azucar_kg",
    "envases_usados": "Envases_Usados",
    "costo_materiales": "Costo_Materiales",
    "energia_kwh": "Energia_kWh",
    "costo_energia": "Costo_Energia",
    "t_turno_h": "T_Turno_h",
    "t_muerto_h": "T_Muerto_h",
    "costo_paradas": "Costo_Paradas",
    "ingresos": "Ingresos",
    "utilidad": "Utilidad",
    "margen_pct": "Margen_pct",
    "oee_pct": "OEE_pct",
    "disponibilidad_pct": "Disponibilidad_pct",
    "rendimiento_pct": "Rendimiento_pct",
    "calidad_pct": "Calidad_pct",
    "costo_unitario": "Costo_Unitario",
    "kwh_por_unidad": "kWh_por_Unidad",
}
_ENTEROS = {"estado", "sentido", "alarmas", "lotes_total", "lotes_buenos", "lotes_rechazados",
            "unidades_producidas", "unidades_vendidas", "inventario_und", "envases_usados"}
_BOOLS = {"calefactor", "vfd_en_marcha", "vfd_falla", "en_consigna"}

TABLAS_SINCRONIZABLES = ("proceso", "gerencia", "eventos", "reportes")


def _tipo(col):
    if col in _BOOLS:
        return Boolean
    return Integer if col in _ENTEROS else Float


def definir_tablas(local: bool) -> MetaData:
    md = MetaData()

    def extra():
        if local:
            return [Column("sincronizado", Boolean, nullable=False, default=False, index=True)]
        return [Column("estacion", String(60), index=True)]

    def tabla(nombre, *cols):
        Table(nombre, md, Column("id", Integer, primary_key=True, autoincrement=True),
              Column("ts", DateTime, nullable=False, index=True), *cols, *extra())

    tabla("proceso", *[Column(c, _tipo(c)) for c in COLS_PROCESO])
    tabla("gerencia", *[Column(c, _tipo(c)) for c in COLS_GERENCIA])
    tabla("eventos", Column("tipo", String(20)), Column("descripcion", String(200)))
    tabla("reportes", Column("tipo", String(20)), Column("origen_datos", String(10)),
          Column("desde", DateTime), Column("hasta", DateTime), Column("resumen", Text),
          Column("nombre_archivo", String(120)), Column("archivo", LargeBinary))
    return md


def fila_desde_plc(datos: dict, columnas: dict) -> dict:
    fila = {}
    for col, campo in columnas.items():
        v = datos[campo]
        fila[col] = bool(v) if col in _BOOLS else (int(v) if col in _ENTEROS else float(v))
    return fila


class BaseDatos:
    def __init__(self, url_local: str, url_nube: str = "", estacion: str = "Grupo"):
        self.estacion = estacion
        self.md_local = definir_tablas(local=True)
        self.local = create_engine(url_local, future=True)
        self.md_local.create_all(self.local)
        self.md_nube = definir_tablas(local=False)
        self.nube = None
        self.estado_nube = 0  # 0 sin nube, 1 OK, 2 error
        if url_nube:
            self.nube = create_engine(url_nube, future=True, pool_pre_ping=True,
                                      connect_args=_args_conexion(url_nube))
            self._crear_tablas_nube()

    def _crear_tablas_nube(self) -> bool:
        try:
            self.md_nube.create_all(self.nube)
            self.estado_nube = 1
            return True
        except Exception as exc:  # noqa: BLE001 - sin red no se detiene el gateway
            log.warning("Nube no disponible: %s", exc)
            self.estado_nube = 2
            return False

    # ---------------------------------------------------------------- escrituras
    def _insertar(self, tabla: str, fila: dict, ts: datetime | None = None, sincronizado=False):
        t = self.md_local.tables[tabla]
        with self.local.begin() as cx:
            r = cx.execute(insert(t).values(ts=ts or datetime.now(), sincronizado=sincronizado, **fila))
            return r.inserted_primary_key[0]

    def guardar_proceso(self, datos: dict, ts=None):
        return self._insertar("proceso", fila_desde_plc(datos, COLS_PROCESO), ts)

    def guardar_gerencia(self, datos: dict, ts=None):
        return self._insertar("gerencia", fila_desde_plc(datos, COLS_GERENCIA), ts)

    def guardar_evento(self, tipo: str, descripcion: str, ts=None):
        return self._insertar("eventos", {"tipo": tipo, "descripcion": descripcion[:200]}, ts)

    def guardar_reporte(self, tipo, origen, desde, hasta, resumen, nombre, archivo: bytes,
                        subir: bool, ts=None):
        """Los reportes locales no se suben (sincronizado=True desde el inicio)."""
        return self._insertar("reportes", dict(tipo=tipo, origen_datos=origen, desde=desde,
                                               hasta=hasta, resumen=resumen,
                                               nombre_archivo=nombre, archivo=archivo),
                              ts, sincronizado=not subir)

    # ------------------------------------------------------------------ lecturas
    def consultar(self, tabla: str, desde: datetime, hasta: datetime, en_nube=False) -> list[dict]:
        if en_nube:
            t, eng = self.md_nube.tables[tabla], self.nube
            q = select(t).where(t.c.ts >= desde, t.c.ts <= hasta, t.c.estacion == self.estacion)
        else:
            t, eng = self.md_local.tables[tabla], self.local
            q = select(t).where(t.c.ts >= desde, t.c.ts <= hasta)
        with eng.connect() as cx:
            return [dict(r._mapping) for r in cx.execute(q.order_by(t.c.ts))]

    def ultima(self, tabla: str, en_nube=False) -> dict | None:
        md, eng = (self.md_nube, self.nube) if en_nube else (self.md_local, self.local)
        t = md.tables[tabla]
        q = select(t)
        if en_nube:
            q = q.where(t.c.estacion == self.estacion)
        with eng.connect() as cx:
            r = cx.execute(q.order_by(t.c.id.desc()).limit(1)).first()
        return dict(r._mapping) if r else None

    def pendientes(self) -> int:
        n = 0
        with self.local.connect() as cx:
            for nombre in TABLAS_SINCRONIZABLES:
                t = self.md_local.tables[nombre]
                n += len(cx.execute(select(t.c.id).where(t.c.sincronizado.is_(False))).all())
        return n

    # ------------------------------------------------------------ sincronización
    def sincronizar(self, max_filas: int = 500) -> int:
        """Sube filas pendientes a la nube. Devuelve cuántas subió."""
        if self.nube is None:
            self.estado_nube = 0
            return 0
        if self.estado_nube != 1 and not self._crear_tablas_nube():
            return 0
        subidas = 0
        try:
            for nombre in TABLAS_SINCRONIZABLES:
                tl, tn = self.md_local.tables[nombre], self.md_nube.tables[nombre]
                with self.local.connect() as cx:
                    filas = [dict(r._mapping) for r in cx.execute(
                        select(tl).where(tl.c.sincronizado.is_(False)).order_by(tl.c.id).limit(max_filas))]
                if not filas:
                    continue
                ids = [f.pop("id") for f in filas]
                for f in filas:
                    f.pop("sincronizado")
                    f["estacion"] = self.estacion
                with self.nube.begin() as cx:
                    cx.execute(insert(tn), filas)
                with self.local.begin() as cx:
                    cx.execute(update(tl).where(tl.c.id.in_(ids)).values(sincronizado=True))
                subidas += len(filas)
            self.estado_nube = 1
        except Exception as exc:  # noqa: BLE001
            log.warning("Error subiendo a la nube (se reintenta): %s", exc)
            self.estado_nube = 2
        return subidas


def _args_conexion(url: str) -> dict:
    if url.startswith("postgresql"):
        return {"connect_timeout": 5}
    return {}
