"""Con aumento de dominio la tarea es más difícil: ¿más capacidad (ancho) o más épocas recuperan el hold-out?
Entrena con el conjunto de desarrollo; evalúa hold-out ShipsNet y TestSet2 (externo). Salida: results/domain_capacity.json"""
import os
import sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from common import load_dataset, dev_test_split, save_json, load_json
from cnn import train_model, Ensemble, count_params, cpu_latency_ms
from domain_shift import load_external

X, y, _ = load_dataset()
dev, te = dev_test_split(y)
Xe, ye, fe = load_external()
base = load_json("cnn.json")["final_cfg"]
R = {}
for w, ep in [(0.5, 45), (0.5, 80), (1.0, 45), (1.0, 80)]:
    cfg = dict(base, width=w, epochs=ep, aug="domain")
    ms = [train_model(X[dev], y[dev], seed=21 + s, **cfg)[0] for s in range(2)]
    ens = Ensemble(ms)
    ph, pe = ens.predict_proba(X[te], tta=True), ens.predict_proba(Xe, tta=True)
    k = f"ancho {w}, {ep} épocas"
    R[k] = {"width": w, "epochs": ep, "holdout_acc": float(((ph >= .5) == y[te]).mean()),
            "ext_acc": float(((pe >= .5) == ye).mean()), "params": count_params(ms[0]), "lat_ms": cpu_latency_ms(ms[0], 50),
            "ext_misses": [f for f, p, t in zip(fe, pe, ye) if (p >= .5) != t]}
    print(f"{k:22s} hold-out {R[k]['holdout_acc']*100:.2f}%  externo {R[k]['ext_acc']*100:.1f}%  lat {R[k]['lat_ms']:.1f} ms  {R[k]['ext_misses']}", flush=True)
save_json(R, "domain_capacity.json")
