"""Verificador estático de las fuentes SCL (no reemplaza compilar en TIA Portal).

Comprueba:
  * IF/CASE/FOR/WHILE/REGION balanceados.
  * Toda variable local #x está declarada en su bloque.
  * #inst.miembro existe en la interfaz del FB (o del temporizador IEC).
  * Los parámetros de cada llamada a un FB/FC propio existen en su interfaz.
  * "DB".ruta existe en el DB global; "Tag" existe en la tabla de variables.
  * Todos los campos de DB_Gateway que escribe el PLC se asignan en FB_Planta,
    y ninguno de los que escribe el gateway.
  * Los valores iniciales de DB_Param coinciden con el gemelo Python (simulador.py).

    python herramientas/verificar_scl.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FUENTES = RAIZ / "plc" / "fuentes_scl"
sys.path.insert(0, str(RAIZ / "gateway"))
sys.path.insert(0, str(RAIZ / "herramientas"))

from scada_gateway import layout  # noqa: E402
from scada_gateway.simulador import Parametros  # noqa: E402
from variables_plc import VARIABLES  # noqa: E402

TIMERS = {"TON_TIME": {"IN", "PT", "Q", "ET"}, "TP_TIME": {"IN", "PT", "Q", "ET"},
          "TOF_TIME": {"IN", "PT", "Q", "ET"}}
FUNCIONES_SISTEMA = {"LIMIT", "MIN", "MAX", "ABS", "FRAC", "RUNTIME", "SQRT"}

# campo de Parametros (Python) -> ruta en DB_Param (SCL)
GEMELO = {
    "sp": "Proceso.SP", "sp_min": "Proceso.SP_Min", "sp_max": "Proceso.SP_Max",
    "histeresis": "Proceso.Histeresis", "tol_consigna": "Proceso.TolConsigna",
    "t_estabilizacion_s": "Proceso.T_Estabilizacion_s", "t_alta_delta": "Proceso.T_Alta_Delta",
    "t_baja_delta": "Proceso.T_Baja_Delta", "t_disparo": "Proceso.T_Disparo",
    "tol_calidad": "Proceso.TolCalidad", "max_fuera_tol_s": "Proceso.MaxFueraTol_s",
    "t_lote_s": "Proceso.T_Lote_s", "banda_reinicio": "Variador.BandaReinicio",
    "vmin_pct": "Variador.Vmin_pct", "vmax_pct": "Variador.Vmax_pct",
    "error_vel_max": "Variador.ErrorVelMax", "vel_nominal_rpm": "Variador.VelNominal_rpm",
    "rampa_s": "Sim.Rampa_s", "sim_potencia_w": "Sim.Potencia_W", "sim_c_placa": "Sim.C_Placa",
    "sim_r_placa": "Sim.R_Placa", "sim_c_camara": "Sim.C_Camara", "sim_r_camara": "Sim.R_Camara",
    "sim_tamb": "Sim.T_Amb", "sim_tau_sensor": "Sim.Tau_Sensor",
    "und_por_lote": "Costos.UnidadesPorLote", "leche_l_lote": "Costos.Leche_L_Lote",
    "precio_leche_l": "Costos.Precio_Leche_L", "cultivo_g_lote": "Costos.Cultivo_g_Lote",
    "precio_cultivo_g": "Costos.Precio_Cultivo_g", "azucar_kg_lote": "Costos.Azucar_kg_Lote",
    "precio_azucar_kg": "Costos.Precio_Azucar_kg", "precio_envase": "Costos.Precio_Envase",
    "potencia_planta_kw": "Costos.Potencia_Planta_kW", "precio_kwh": "Costos.Precio_kWh",
    "costo_hora_parada": "Costos.CostoHoraParada", "precio_venta_und": "Costos.Precio_Venta_Und",
    "t_ciclo_ideal_s": "Costos.T_CicloIdeal_s", "inventario_min": "Costos.Inventario_Min",
    "t_entre_pedidos_s": "Costos.T_EntrePedidos_s", "pedido_max": "Costos.PedidoMax",
}


def _sin_comentarios(txt: str) -> str:
    txt = re.sub(r"\(\*.*?\*\)", " ", txt, flags=re.S)
    return re.sub(r"//[^\n]*", "", txt)


def leer_fuentes() -> str:
    return "\n".join(_sin_comentarios(p.read_text(encoding="utf-8-sig"))
                     for p in sorted(FUENTES.glob("*")) if p.suffix in (".scl", ".db"))


def parsear_dbs(txt: str):
    """Devuelve {db: {ruta: (tipo, valor_inicial)}} para los DB globales con STRUCT."""
    dbs = {}
    for m in re.finditer(r'DATA_BLOCK\s+"(\w+)"(.*?)END_DATA_BLOCK', txt, re.S):
        nombre, cuerpo = m.group(1), m.group(2)
        if "STRUCT" not in cuerpo.split("BEGIN")[0]:
            continue  # DB de instancia
        rutas, pila = {}, []
        decl = cuerpo.split("BEGIN")[0]
        decl = decl[decl.index("STRUCT") + len("STRUCT"):]
        for linea in decl.splitlines():
            linea = linea.strip()
            if not linea:
                continue
            if linea.startswith("END_STRUCT"):
                if pila:
                    pila.pop()
                continue
            ms = re.match(r"(\w+)\s*:\s*Struct\b", linea, re.I)
            if ms:
                pila.append(ms.group(1))
                rutas[".".join(pila)] = ("Struct", None)
                continue
            mv = re.match(r"(\w+)\s*:\s*(\w+)\s*(?::=\s*([^;]+))?;", linea)
            if mv:
                rutas[".".join(pila + [mv.group(1)])] = (mv.group(2), mv.group(3))
        dbs[nombre] = rutas
    return dbs


def parsear_bloques(txt: str):
    """{nombre: {"tipo", "vars": {nombre: tipo}, "interfaz": set, "codigo": str}}"""
    bloques = {}
    patron = r'(FUNCTION_BLOCK|FUNCTION|ORGANIZATION_BLOCK)\s+"(\w+)"(.*?)END_\1'
    for m in re.finditer(patron, txt, re.S):
        tipo, nombre, cuerpo = m.groups()
        decl, _, codigo = cuerpo.partition("BEGIN")
        vars_, interfaz = {}, set()
        for sec in re.finditer(r"\b(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR)\b(.*?)END_VAR", decl, re.S):
            for mv in re.finditer(r"(\w+)\s*:\s*(\"\w+\"|\w+)", sec.group(2)):
                vars_[mv.group(1)] = mv.group(2).strip('"')
                if sec.group(1) != "VAR_TEMP":
                    interfaz.add(mv.group(1))
        bloques[nombre] = {"tipo": tipo, "vars": vars_, "interfaz": interfaz, "codigo": codigo}
    return bloques


def _argumentos(codigo: str, inicio: int) -> tuple[list[str], int]:
    """Nombres de parámetros de primer nivel de la llamada que abre en codigo[inicio] == '('."""
    prof, i, nombres, actual = 0, inicio, [], ""
    while i < len(codigo):
        c = codigo[i]
        if c == "(":
            prof += 1
            if prof == 1:
                i += 1
                continue
        elif c == ")":
            prof -= 1
            if prof == 0:
                nombres.append(actual)
                break
        if prof == 1 and c == ",":
            nombres.append(actual)
            actual = ""
        elif prof == 1:
            actual += c
        i += 1
    params = []
    for a in nombres:
        ma = re.match(r"\s*(\w+)\s*(:=|=>)", a)
        if ma:
            params.append(ma.group(1))
    return params, i


def verificar() -> list[str]:
    txt = leer_fuentes()
    errores: list[str] = []
    dbs = parsear_dbs(txt)
    bloques = parsear_bloques(txt)
    tags = {v[0] for v in VARIABLES}
    instancias = set(re.findall(r'DATA_BLOCK\s+"(\w+)"\s*\{[^}]*\}\s*VERSION[^\n]*\n\s*NON_RETAIN\s*\n\s*"\w+"', txt))

    for nombre, b in bloques.items():
        # los títulos de REGION son texto libre
        cod = re.sub(r"\bREGION\b[^\n]*", "REGION", b["codigo"])
        for kw, fin in (("IF", "END_IF"), ("CASE", "END_CASE"), ("FOR", "END_FOR"),
                        ("WHILE", "END_WHILE"), ("REGION", "END_REGION")):
            a, z = len(re.findall(rf"\b{kw}\b", cod)), len(re.findall(rf"\b{fin}\b", cod))
            if a != z:
                errores.append(f"{nombre}: {kw}={a} pero {fin}={z}")
        if cod.count("(") != cod.count(")"):
            errores.append(f"{nombre}: paréntesis desbalanceados")
        # ';' faltante: dos asignaciones de primer nivel en la misma sentencia
        for sent in cod.split(";"):
            prof, n = 0, 0
            for i, c in enumerate(sent):
                prof += (c == "(") - (c == ")")
                if prof == 0 and sent.startswith(":=", i):
                    n += 1
            if n > 1:
                errores.append(f"{nombre}: ¿falta ';'? -> {' '.join(sent.split())[:90]}")

        for m in re.finditer(r"(?<![\w#])#(\w+)((?:\.\w+)*)", cod):
            var, resto = m.group(1), m.group(2)
            if var not in b["vars"]:
                errores.append(f"{nombre}: variable #{var} no declarada")
                continue
            if resto:
                miembro = resto.split(".")[1]
                t = b["vars"][var]
                if t in TIMERS:
                    if miembro not in TIMERS[t]:
                        errores.append(f"{nombre}: #{var}.{miembro} no existe en {t}")
                elif t in bloques:
                    if miembro not in bloques[t]["interfaz"]:
                        errores.append(f"{nombre}: #{var}.{miembro} no existe en {t}")
        for m in re.finditer(r"(?<![\w#])#\w+\.%X(\d+)", cod):
            if int(m.group(1)) > 15:
                errores.append(f"{nombre}: acceso a bit {m.group(0)} fuera de un Word")

        for m in re.finditer(r'"(\w+)"((?:\.\w+)*)', cod):
            ref, resto = m.group(1), m.group(2).lstrip(".")
            if ref in dbs:
                if resto and resto not in dbs[ref]:
                    errores.append(f'{nombre}: "{ref}".{resto} no existe')
            elif ref in bloques or ref in instancias:
                pass
            elif ref not in tags:
                errores.append(f'{nombre}: "{ref}" no es DB, bloque ni variable de la tabla')

        # parámetros de llamadas a bloques propios
        for m in re.finditer(r'((?<![\w#])#(\w+)|"(\w+)")\s*\(', cod):
            local, glob = m.group(2), m.group(3)
            if local:
                t = b["vars"].get(local)
                interfaz = (TIMERS.get(t) or bloques.get(t, {}).get("interfaz")) if t else None
            else:
                interfaz = bloques.get(glob, {}).get("interfaz")
            if interfaz is None:
                continue
            params, _ = _argumentos(cod, m.end() - 1)
            for p_ in params:
                if p_ not in interfaz:
                    errores.append(f"{nombre}: parámetro {p_} no existe en la llamada {m.group(1)}")

        for m in re.finditer(r"\b([A-Z_]+)\s*\(", cod):
            f = m.group(1)
            if f.isupper() and "_TO_" not in f and f not in FUNCIONES_SISTEMA and f not in ("IF", "ELSIF", "WHILE", "UNTIL", "AND", "OR", "XOR", "NOT", "MOD"):
                errores.append(f"{nombre}: función desconocida {f}()")

    # DB_Gateway <-> layout.py
    if "DB_Gateway" in dbs:
        declarados = set(dbs["DB_Gateway"])
        esperados = {c.nombre for c in layout.CAMPOS}
        if declarados != esperados:
            errores.append(f"DB_Gateway desactualizado: {sorted(declarados ^ esperados)}")
    cod_planta = bloques.get("FB_Planta", {}).get("codigo", "")
    asignados = re.findall(r'"DB_Gateway"\.(\w+)\s*:=', cod_planta)
    for c in layout.CAMPOS:
        n = asignados.count(c.nombre)
        if c.dueno == "plc" and n < 1:
            errores.append(f"FB_Planta no escribe DB_Gateway.{c.nombre}")
        if c.dueno == "gw" and n:
            errores.append(f"FB_Planta escribe DB_Gateway.{c.nombre}, que es del gateway")

    # valores iniciales DB_Param == gemelo Python
    p = Parametros()
    for campo, ruta in GEMELO.items():
        if ruta not in dbs.get("DB_Param", {}):
            errores.append(f"DB_Param.{ruta} no existe (gemelo: {campo})")
            continue
        ini = dbs["DB_Param"][ruta][1]
        if ini is None or abs(float(ini) - float(getattr(p, campo))) > 1e-9:
            errores.append(f"DB_Param.{ruta} = {ini} pero simulador.{campo} = {getattr(p, campo)}")
    return errores


if __name__ == "__main__":
    errs = verificar()
    for e in errs:
        print("ERROR:", e)
    print("OK: sin errores" if not errs else f"{len(errs)} error(es)")
    sys.exit(1 if errs else 0)
