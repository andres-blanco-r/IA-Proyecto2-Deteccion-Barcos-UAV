import struct
from datetime import datetime, timedelta

import pytest

from scada_gateway import layout
from scada_gateway.database import BaseDatos
from scada_gateway.main import CONFIG_POR_DEFECTO, Gateway
from scada_gateway.plc import PlcSimulado
from scada_gateway.simulador import (CALENTANDO, EMERGENCIA, EN_CONSIGNA, PARADO,
                                     LeyVelocidad, OnOffHisteresis, Parametros, PlantaSimulada)


# ----------------------------------------------------------------- layout
def test_layout_alineado_y_gw_al_final():
    for c in layout.CAMPOS:
        if layout.TAM[c.tipo] >= 2:
            assert c.offset % 2 == 0, c
    offs = [c.offset for c in layout.CAMPOS]
    assert offs == sorted(offs) and len(set(offs)) == len(offs)
    assert layout.GW_CAMPOS[0].offset == layout.GW_INICIO
    assert layout.TAMANO_DB == layout.GW_INICIO + 2 * len(layout.GW_CAMPOS)


def test_codificar_decodificar_ida_y_vuelta():
    v = {"PV_Temp": 42.5, "Lotes_Total": 123456, "Estado": 2, "Sentido": -1,
         "Bits_Estado": 0b10000000011, "Alarmas": 0x8001, "GW_Heartbeat": 7}
    d = layout.decodificar(layout.codificar(v))
    assert d["PV_Temp"] == pytest.approx(42.5)
    assert d["Lotes_Total"] == 123456 and d["Estado"] == 2 and d["Sentido"] == -1
    assert d["ProcesoEnMarcha"] and d["Calefactor"] and d["TurnoActivo"] and not d["VFD_Falla"]
    assert d["Alarmas"] == 0x8001 and d["GW_Heartbeat"] == 7


def test_big_endian_como_s7():
    buf = layout.codificar({"PV_Temp": 1.0})
    assert buf[0:4] == struct.pack(">f", 1.0) == b"\x3f\x80\x00\x00"


def test_bloque_gw_no_pisa_campos_plc():
    gw = layout.codificar_gw({"GW_Heartbeat": 5, "AckCnt_RepNubeGer": 3})
    assert len(gw) == layout.TAMANO_DB - layout.GW_INICIO
    full = bytearray(layout.codificar({"PV_Temp": 30.0}))
    full[layout.GW_INICIO:] = gw
    d = layout.decodificar(full)
    assert d["PV_Temp"] == pytest.approx(30.0) and d["GW_Heartbeat"] == 5 and d["AckCnt_RepNubeGer"] == 3


# ----------------------------------------------------------------- lógica
def test_onoff_histeresis():
    f = OnOffHisteresis()
    assert f(40.0, 43.0, 1.0, True)          # frío -> enciende
    assert f(43.2, 43.0, 1.0, True)          # dentro de la banda mantiene
    assert not f(43.6, 43.0, 1.0, True)      # sobre SP+0.5 apaga
    assert not f(42.8, 43.0, 1.0, True)      # dentro de la banda mantiene apagado
    assert f(42.4, 43.0, 1.0, True)
    assert not f(20.0, 43.0, 1.0, False)     # deshabilitado = apagado


def test_ley_velocidad_proporcional_y_parada():
    p, ley = Parametros(), LeyVelocidad()
    assert ley(20.0, 43.0, True, p) == pytest.approx(100.0)          # |e|=23 >= 15 -> Vmax
    assert ley(35.5, 43.0, True, p) == pytest.approx(20 + 80 * 0.5)  # |e|=7.5 -> mitad
    assert ley(42.8, 43.0, True, p) == 0.0                            # llega al SP -> para
    assert ley(41.0, 43.0, True, p) == 0.0                            # oscilación ON-OFF: sigue parado
    assert ley(38.0, 43.0, True, p) > 0.0                             # |e|>banda_reinicio -> arranca
    assert ley(20.0, 43.0, False, p) == 0.0


def test_planta_llega_al_sp_y_produce():
    sim = PlantaSimulada(semilla=3)
    vistos = set()
    vel_max_inicio = 0.0
    for i in range(int(3600 / 0.2)):
        sim.paso(0.2)
        vistos.add(sim.estado)
        if i < 50:
            vel_max_inicio = max(vel_max_inicio, sim.vel_ref)
    s = sim.salidas()
    assert vel_max_inicio == pytest.approx(100.0)
    assert {CALENTANDO, EN_CONSIGNA} <= vistos
    assert abs(s["Error_Temp"]) < 2.5
    assert s["Lotes_Total"] >= 5 and s["Lotes_Buenos"] == s["Lotes_Total"]
    assert 0 < s["OEE_pct"] <= 100 and s["Ingresos"] > 0
    assert s["VelRef_pct"] == 0.0  # en consigna el agitador está parado


def test_emergencia_y_rearme():
    sim = PlantaSimulada()
    sim.paso(0.1)
    sim.comando("paro_emergencia")
    sim.paso(0.1)
    assert sim.estado == EMERGENCIA and not sim.calefactor and not sim.vfd_habilitado
    sim.comando("start")
    sim.paso(0.1)
    assert sim.estado == EMERGENCIA          # Start no saca de emergencia
    sim.comando("rearme")
    sim.paso(0.1)
    assert sim.estado == PARADO


# ------------------------------------------------------- gateway completo
@pytest.fixture
def cfg(tmp_path):
    c = {k: dict(v) for k, v in CONFIG_POR_DEFECTO.items()}
    c["bd_local"]["url"] = f"sqlite:///{tmp_path / 'local.db'}"
    c["bd_nube"]["url"] = f"sqlite:///{tmp_path / 'nube.db'}"   # SQLite hace de "nube" en pruebas
    c["reportes"]["carpeta"] = str(tmp_path / "reportes")
    c["muestreo"].update(gerencia_s=0.0, sync_s=0.0)
    return c


def _correr(gw, plc, n, dt_sim=2.0):
    for _ in range(n):
        plc.avanzar(dt_sim)
        gw._t_prueba = getattr(gw, "_t_prueba", 0.0) + 1.0
        gw.ciclo(gw._t_prueba)


def test_gateway_guarda_sincroniza_y_reporta(cfg, tmp_path):
    plc = PlcSimulado(factor_tiempo=0.0)       # el tiempo lo avanza la prueba
    bd = BaseDatos(cfg["bd_local"]["url"], cfg["bd_nube"]["url"], "Grupo Test")
    gw = Gateway(cfg, plc=plc, bd=bd)
    _correr(gw, plc, 600)                      # 1200 s simulados
    assert bd.estado_nube == 1 and bd.pendientes() == 0
    ahora = datetime.now()
    local = bd.consultar("proceso", ahora - timedelta(hours=1), ahora)
    nube = bd.consultar("proceso", ahora - timedelta(hours=1), ahora, en_nube=True)
    assert len(local) == len(nube) == 600
    assert plc.gw["GW_Heartbeat"] == 600 and plc.gw["GW_EstadoNube"] == 1

    # El HMI pide los tres reportes -> el gateway los genera y devuelve el ack
    for k in ("local", "nube_sup", "nube_ger"):
        plc.sim.comando(f"reporte_{k}")
    _correr(gw, plc, 1)
    assert plc.gw["AckCnt_RepLocal"] == 1 and plc.gw["AckCnt_RepNubeSup"] == 1
    assert plc.gw["AckCnt_RepNubeGer"] == 1
    pdfs = sorted((tmp_path / "reportes").glob("*.pdf"))
    assert len(pdfs) == 3 and all(p.read_bytes()[:4] == b"%PDF" for p in pdfs)
    rep_nube = bd.consultar("reportes", ahora - timedelta(hours=1), datetime.now(), en_nube=True)
    assert sorted(r["tipo"] for r in rep_nube) == ["nube_ger", "nube_sup"]   # el local no se sube
    assert all(r["origen_datos"] == "nube" and r["archivo"][:4] == b"%PDF" for r in rep_nube)
    ev = bd.consultar("eventos", ahora - timedelta(hours=1), datetime.now(), en_nube=True)
    assert any(e["tipo"] == "ESTADO" for e in ev) and any(e["tipo"] == "REPORTE" for e in ev)


def test_sin_internet_acumula_y_luego_sube(cfg, tmp_path):
    plc = PlcSimulado(factor_tiempo=0.0)
    bd = BaseDatos(cfg["bd_local"]["url"], "", "G")
    gw = Gateway(cfg, plc=plc, bd=bd)
    _correr(gw, plc, 20)
    assert bd.estado_nube == 0 and bd.pendientes() > 0
    # vuelve la nube
    from sqlalchemy import create_engine
    bd.nube = create_engine(cfg["bd_nube"]["url"])
    _correr(gw, plc, 1)
    assert bd.pendientes() == 0 and bd.estado_nube == 1
