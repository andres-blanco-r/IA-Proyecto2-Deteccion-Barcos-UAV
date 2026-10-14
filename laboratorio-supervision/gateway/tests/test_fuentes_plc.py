import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "herramientas"))

import gen_db_gateway  # noqa: E402
import verificar_scl  # noqa: E402


def test_fuentes_scl_consistentes():
    assert verificar_scl.verificar() == []


def test_db_gateway_generado_al_dia():
    actual = gen_db_gateway.SALIDA.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    assert actual == gen_db_gateway.generar().replace("\r\n", "\n"), \
        "Ejecute python herramientas/gen_db_gateway.py"
