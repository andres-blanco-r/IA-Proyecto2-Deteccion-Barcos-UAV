"""Mapa de memoria del bloque "DB_Gateway" (DB no optimizado del S7-1500).

Esta lista es la ÚNICA fuente de verdad del intercambio PLC <-> gateway:
  * herramientas/gen_db_gateway.py genera con ella plc/fuentes_scl/03_DB_Gateway.db
  * el gateway la usa para decodificar los bytes leídos con snap7.

Reglas del DB no optimizado (S7 estándar, big-endian):
  * Real y DInt ocupan 4 bytes, Int y Word 2 bytes.
  * No se usan Bool: los estados binarios viajan empaquetados en Words
    (bit n del Word = "Tag".%Xn en SCL), así no hay escrituras de bit
    que compitan con el PLC en el mismo byte.
  * Los campos que escribe el gateway están al final y son contiguos, de modo
    que el gateway escribe un único bloque sin tocar los bytes del PLC.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

TAM = {"Real": 4, "DInt": 4, "Int": 2, "Word": 2}
FMT = {"Real": ">f", "DInt": ">i", "Int": ">h", "Word": ">H"}


@dataclass(frozen=True)
class Campo:
    nombre: str
    tipo: str
    comentario: str
    dueno: str = "plc"  # "plc" = lo escribe el PLC; "gw" = lo escribe el gateway
    offset: int = 0


_DEF = [
    # --- Proceso (Real) ---
    ("PV_Temp", "Real", "Temperatura medida [°C]"),
    ("SP_Temp", "Real", "Set point de temperatura [°C]"),
    ("Error_Temp", "Real", "Error SP - PV [°C]"),
    ("Senal_mA", "Real", "Corriente del lazo 4-20 mA [mA]"),
    ("Duty_Calefactor_pct", "Real", "Ciclo de trabajo del calefactor (media móvil 60 s) [%]"),
    ("TiempoEnBanda_pct", "Real", "Tiempo del turno con |e| <= tolerancia de calidad [%]"),
    ("VelRef_pct", "Real", "Referencia de velocidad enviada al variador [%]"),
    ("Vel_pct", "Real", "Velocidad real del variador [%]"),
    ("Vel_rpm", "Real", "Velocidad real del motor [rpm]"),
    ("ProgresoLote_pct", "Real", "Avance del lote en fermentación [%]"),
    # --- Gerencia (Real) ---
    ("Energia_kWh", "Real", "Energía consumida en el turno [kWh]"),
    ("Costo_Energia", "Real", "Costo de la energía [COP]"),
    ("Leche_L", "Real", "Leche consumida [L]"),
    ("Cultivo_g", "Real", "Cultivo láctico consumido [g]"),
    ("Azucar_kg", "Real", "Azúcar consumida [kg]"),
    ("Costo_Materiales", "Real", "Costo de materias primas y envases [COP]"),
    ("T_Turno_h", "Real", "Tiempo de turno [h]"),
    ("T_Muerto_h", "Real", "Tiempo muerto (parado/emergencia/falla) [h]"),
    ("Costo_Paradas", "Real", "Costo del tiempo muerto [COP]"),
    ("Ingresos", "Real", "Ingresos por ventas [COP]"),
    ("Utilidad", "Real", "Ingresos - costos [COP]"),
    ("Margen_pct", "Real", "Margen sobre ventas [%]"),
    ("OEE_pct", "Real", "OEE = D x R x C [%]"),
    ("Disponibilidad_pct", "Real", "Disponibilidad [%]"),
    ("Rendimiento_pct", "Real", "Rendimiento [%]"),
    ("Calidad_pct", "Real", "Calidad (lotes buenos / lotes) [%]"),
    ("Costo_Unitario", "Real", "Costo variable por unidad buena [COP/und]"),
    ("kWh_por_Unidad", "Real", "Energía específica [kWh/und]"),
    # --- Contadores (DInt) ---
    ("Lotes_Total", "DInt", "Lotes terminados"),
    ("Lotes_Buenos", "DInt", "Lotes conformes"),
    ("Lotes_Rechazados", "DInt", "Lotes rechazados por calidad"),
    ("Unidades_Producidas", "DInt", "Vasos producidos (conformes)"),
    ("Unidades_Vendidas", "DInt", "Vasos vendidos"),
    ("Inventario_Und", "DInt", "Inventario de producto terminado [und]"),
    ("Envases_Usados", "DInt", "Envases consumidos [und]"),
    # --- Estados (Int / Word) ---
    ("Estado", "Int", "0 Parado, 1 Calentando, 2 En consigna, 3 Emergencia, 4 Falla"),
    ("Sentido", "Int", "1 adelante, -1 reversa, 0 detenido"),
    ("Bits_Estado", "Word", "Ver BITS_ESTADO"),
    ("Alarmas", "Word", "Ver BITS_ALARMA"),
    ("ReqCnt_RepLocal", "Int", "Contador de solicitudes de reporte local (PC)"),
    ("ReqCnt_RepNubeSup", "Int", "Contador de solicitudes de reporte supervisor en la nube"),
    ("ReqCnt_RepNubeGer", "Int", "Contador de solicitudes de reporte de gerencia en la nube"),
    # --- Escritos por el gateway ---
    ("GW_Heartbeat", "Int", "Latido del gateway (cambia en cada ciclo)", "gw"),
    ("GW_EstadoNube", "Int", "0 sin nube, 1 nube OK, 2 error de nube", "gw"),
    ("AckCnt_RepLocal", "Int", "Último reporte local atendido", "gw"),
    ("AckCnt_RepNubeSup", "Int", "Último reporte supervisor atendido", "gw"),
    ("AckCnt_RepNubeGer", "Int", "Último reporte gerencia atendido", "gw"),
    ("GW_Pendientes", "Int", "Filas pendientes de subir a la nube", "gw"),
]

BITS_ESTADO = {
    0: "ProcesoEnMarcha",
    1: "Calefactor",
    2: "VFD_Habilitado",
    3: "VFD_EnMarcha",
    4: "VFD_Falla",
    5: "EnConsigna",
    6: "Emergencia",
    7: "ModoSimulacion",
    8: "Ventilador",
    9: "VFD_ModoManual",
    10: "TurnoActivo",
}

BITS_ALARMA = {
    0: "Paro de emergencia activo",
    1: "Temperatura alta (H)",
    2: "Temperatura muy alta (HH) - disparo",
    3: "Temperatura baja en fermentación (L)",
    4: "Falla del sensor RTD / lazo 4-20 mA",
    5: "Falla del variador",
    6: "Advertencia del variador",
    7: "Gateway sin comunicación",
    8: "Lote rechazado por calidad",
    9: "Inventario de producto bajo",
    10: "Cadena de seguridad abierta (termostato / paro físico)",
    11: "Modo simulación activo",
}

ESTADOS = {0: "PARADO", 1: "CALENTANDO", 2: "EN CONSIGNA", 3: "EMERGENCIA", 4: "FALLA"}


def _construir() -> list[Campo]:
    campos, off = [], 0
    for d in _DEF:
        nombre, tipo, com = d[:3]
        dueno = d[3] if len(d) > 3 else "plc"
        if TAM[tipo] >= 2 and off % 2:
            off += 1
        campos.append(Campo(nombre, tipo, com, dueno, off))
        off += TAM[tipo]
    return campos


CAMPOS: list[Campo] = _construir()
POR_NOMBRE = {c.nombre: c for c in CAMPOS}
TAMANO_DB = CAMPOS[-1].offset + TAM[CAMPOS[-1].tipo]
GW_INICIO = min(c.offset for c in CAMPOS if c.dueno == "gw")
GW_CAMPOS = [c for c in CAMPOS if c.dueno == "gw"]

assert all(c.offset >= GW_INICIO for c in GW_CAMPOS)
assert all(c.offset < GW_INICIO for c in CAMPOS if c.dueno == "plc"), "campos gw deben ir al final"


def decodificar(buf: bytes | bytearray) -> dict:
    """Bytes del DB -> diccionario {campo: valor} + bits expandidos."""
    if len(buf) < TAMANO_DB:
        raise ValueError(f"se esperaban {TAMANO_DB} bytes, llegaron {len(buf)}")
    d = {}
    for c in CAMPOS:
        (v,) = struct.unpack_from(FMT[c.tipo], buf, c.offset)
        d[c.nombre] = round(v, 4) if c.tipo == "Real" else v
    for bit, nombre in BITS_ESTADO.items():
        d[nombre] = bool((d["Bits_Estado"] >> bit) & 1)
    return d


def codificar(valores: dict) -> bytearray:
    """Diccionario -> bytes con el layout del DB (lo usa el PLC simulado y las pruebas)."""
    buf = bytearray(TAMANO_DB)
    for c in CAMPOS:
        v = valores.get(c.nombre, 0)
        if c.tipo != "Real":
            v = int(v)
        struct.pack_into(FMT[c.tipo], buf, c.offset, v)
    return buf


def codificar_gw(valores: dict) -> bytearray:
    """Solo el bloque escrito por el gateway (desde GW_INICIO hasta el final)."""
    buf = bytearray(TAMANO_DB - GW_INICIO)
    for c in GW_CAMPOS:
        v = max(-32768, min(32767, int(valores.get(c.nombre, 0))))
        struct.pack_into(FMT[c.tipo], buf, c.offset - GW_INICIO, v)
    return buf


def alarmas_activas(palabra: int) -> list[str]:
    return [txt for bit, txt in BITS_ALARMA.items() if (palabra >> bit) & 1]
