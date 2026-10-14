"""Genera plc/fuentes_scl/02_DB_Gateway.db desde gateway/scada_gateway/layout.py.

    python herramientas/gen_db_gateway.py
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "gateway"))
from scada_gateway import layout  # noqa: E402

SALIDA = RAIZ / "plc" / "fuentes_scl" / "02_DB_Gateway.db"


def generar() -> str:
    ancho = max(len(c.nombre) for c in layout.CAMPOS)
    lineas = [
        "// ARCHIVO GENERADO por herramientas/gen_db_gateway.py desde gateway/scada_gateway/layout.py",
        "// NO lo edite a mano: si cambia el layout, vuelva a generarlo e impórtelo de nuevo.",
        "// Acceso NO optimizado: el gateway Python lo lee por dirección absoluta (snap7).",
        f"// Tamaño: {layout.TAMANO_DB} bytes. Zona escrita por el gateway: bytes "
        f"{layout.GW_INICIO}..{layout.TAMANO_DB - 1}.",
        "// Después de generarlo asígnele el número 100 (o el que ponga en config.toml).",
        'DATA_BLOCK "DB_Gateway"',
        "{ S7_Optimized_Access := 'FALSE' }",
        "VERSION : 0.1",
        "NON_RETAIN",
        "   STRUCT ",
    ]
    for c in layout.CAMPOS:
        quien = "GATEWAY escribe" if c.dueno == "gw" else "PLC escribe"
        lineas.append(f"      {c.nombre.ljust(ancho)} : {c.tipo};   // +{c.offset:<3} {quien}: {c.comentario}")
    lineas += ["   END_STRUCT;", "", "", "BEGIN", "", "END_DATA_BLOCK", ""]
    return "\r\n".join(lineas)


if __name__ == "__main__":
    SALIDA.write_text(generar(), encoding="utf-8-sig")
    print(f"{SALIDA} ({layout.TAMANO_DB} bytes)")
