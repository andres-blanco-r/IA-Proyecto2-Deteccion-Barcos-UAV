"""Cambio de dominio: ShipsNet (Planet, 3 m/px) -> imágenes de otra fuente (TestSet2, estilo Google Earth).

Entrena variantes SOLO con el conjunto de desarrollo de ShipsNet y evalúa en:
  - hold-out de ShipsNet (800, mismo dominio)          -> no debe empeorar
  - TestSet2 (40 imágenes externas, etiquetas visuales) -> validación externa de generalización
TestSet2 nunca se usa para entrenar. Salida: results/domain_shift.json
"""
import os
import sys
import csv
import json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from common import load_dataset, dev_test_split, load_image, save_json, load_json, ROOT
from cnn import train_model, predict_proba, Ensemble

EXT_DIR = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\ANDRES\Downloads\TestSet2\TestSet2"
EXT_LAB = os.path.join(ROOT, "testset2_etiquetas.csv")


def load_external():
    lab = {r[0]: int(r[1]) for r in csv.reader(open(EXT_LAB, encoding="utf-8")) if r and r[1] in ("0", "1")}
    fs = sorted(lab)
    return np.stack([load_image(os.path.join(EXT_DIR, f)) for f in fs]), np.array([lab[f] for f in fs]), fs


def main():
    X, y, _ = load_dataset()
    dev, te = dev_test_split(y)
    Xe, ye, fe = load_external()
    base = load_json("cnn.json")["final_cfg"]
    variants = {
        "base (actual)":              dict(aug=True, norm="global"),
        "base + norm. por imagen":    dict(aug=True, norm="instance"),
        "aumento de dominio":         dict(aug="domain", norm="global"),
        "aumento de dominio + norm.": dict(aug="domain", norm="instance"),
    }
    R = {}
    for name, v in variants.items():
        cfg = dict(base, **v)
        ms = [train_model(X[dev], y[dev], seed=11 + s, **cfg)[0] for s in range(2)]
        ens = Ensemble(ms)
        ph, pe = ens.predict_proba(X[te], tta=True), ens.predict_proba(Xe, tta=True)
        R[name] = {"cfg": {k: str(val) for k, val in v.items()},
                   "holdout_acc": float(((ph >= .5) == y[te]).mean()),
                   "ext_acc": float(((pe >= .5) == ye).mean()),
                   "ext_recall": float(((pe >= .5) & (ye == 1)).sum() / max(1, (ye == 1).sum())),
                   "ext_fp": int(((pe >= .5) & (ye == 0)).sum()),
                   "ext_misses": [f for f, p, t in zip(fe, pe, ye) if (p >= .5) != t]}
        print(f"{name:30s} hold-out {R[name]['holdout_acc']*100:6.2f}%  | externo {R[name]['ext_acc']*100:6.2f}% "
              f"(recall {R[name]['ext_recall']*100:.0f}%, FP {R[name]['ext_fp']})  errores: {R[name]['ext_misses']}", flush=True)
    save_json(R, "domain_shift.json")


if __name__ == "__main__":
    main()
