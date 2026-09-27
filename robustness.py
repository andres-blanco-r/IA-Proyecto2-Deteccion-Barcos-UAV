"""Robustez ante cambio de dominio (condiciones reales del UAV) sobre el hold-out.

Compara CNN con / sin aumento de datos (misma configuración final) y el SVM+descriptores bajo
perturbaciones: rotación arbitraria, cambio de brillo/contraste, desenfoque (movimiento/altura),
ruido de sensor y compresión JPEG (enlace de video). Salida: results/robustness.json, fig_robustez.png
"""
import os
import sys
import io
import numpy as np
import cv2
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from common import *  # noqa
from cnn import train_model, Ensemble
from predictor import Predictor
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

rng = np.random.default_rng(0)


def rot(x):
    a = rng.uniform(0, 360)
    M = cv2.getRotationMatrix2D((40, 40), a, 1.0)
    return cv2.warpAffine(x, M, (80, 80), borderMode=cv2.BORDER_REFLECT)


def bright(x):
    return np.clip(x.astype(np.float32) * rng.uniform(0.6, 1.4) + rng.uniform(-40, 40), 0, 255).astype(np.uint8)


def blur(x):
    return cv2.GaussianBlur(x, (5, 5), 1.2)


def noise(x):
    return np.clip(x + rng.normal(0, 12, x.shape), 0, 255).astype(np.uint8)


def jpeg(x):
    b = io.BytesIO(); Image.fromarray(x).save(b, "JPEG", quality=30)
    return np.asarray(Image.open(b).convert("RGB"))


def combo(x):
    return jpeg(noise(bright(rot(x))))


PERT = {"limpio": lambda x: x, "rotación libre": rot, "brillo/contraste": bright, "desenfoque": blur,
        "ruido σ=12": noise, "JPEG q=30": jpeg, "combinado": combo}


def main():
    X, y, _ = load_dataset()
    dev, te = dev_test_split(y)
    cfg = load_json("cnn.json")["final_cfg"]
    models = {}
    for aug in (False, True):
        ms = [train_model(X[dev], y[dev], seed=7 + s, **dict(cfg, aug=aug))[0] for s in range(3)]
        models["CNN con aumento" if aug else "CNN sin aumento"] = Ensemble(ms)
    svm = Predictor("SVM + HOG/HSV/LBP (clásico)")
    R = {}
    for pname, f in PERT.items():
        Xp = np.stack([f(x) for x in X[te]])
        R[pname] = {}
        for mname, m in models.items():
            R[pname][mname] = float(((m.predict_proba(Xp) >= 0.5) == y[te]).mean())
        R[pname]["SVM + descriptores"] = float(((svm.predict_proba(Xp) >= 0.5) == y[te]).mean())
        print(pname, R[pname])
    save_json(R, "robustness.json")
    names = list(R["limpio"])
    fig, ax = plt.subplots(figsize=(8, 3.2))
    xs = np.arange(len(PERT))
    cols = ["#9bb7d4", "#0b5cad", "#7a8591"]
    for k, n in enumerate(names):
        ax.bar(xs + (k - 1) * 0.27, [R[p][n] * 100 for p in PERT], 0.27, label=n, color=cols[k])
    ax.axhline(98, color="#c62828", ls="--", lw=1, label="Meta 98 %")
    ax.set_xticks(xs); ax.set_xticklabels(list(PERT), fontsize=8)
    lo = min(min(v.values()) for v in R.values()) * 100
    ax.set_ylim(max(50, lo - 3), 100.5); ax.set_ylabel("Accuracy hold-out (%)")
    ax.set_title("Robustez ante perturbaciones de dominio (UAV) — hold-out n=800")
    ax.legend(fontsize=7, loc="lower left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.savefig(os.path.join(RESULTS_DIR, "fig_robustez.png"), dpi=150, bbox_inches="tight")


if __name__ == "__main__":
    main()
