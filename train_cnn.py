"""C1/C2 - Optimización de la CNN (ShipNet-Lite) y validación cruzada.

Etapas:
  A. Sintonización fina multivariada (grid factorial lr x dropout x weight_decay, CV 3 pliegues).
  B. Análisis de sensibilidad OFAT alrededor del óptimo: ancho de red (costo computacional),
     épocas, aumento de datos on/off (CV 5 pliegues) + métricas de eficiencia (params, MACs,
     latencia CPU 1 hilo) => frente de Pareto exactitud vs. costo para inferencia embarcada.
  C. CV 5 pliegues del modelo final (todas las métricas, predicciones OOF, umbral).
  D. Hold-out (test ciego simulado): modelo individual vs. ensamble de pliegues vs. TTA.
  E. Modelo de despliegue: ensamble entrenado con TODO el dataset (4000) para el día de la prueba.
Salida: results/cnn.json, models/cnn_dev.pt, models/cnn_final.pt
"""
import os
import sys
import time
import itertools
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from common import *  # noqa
from cnn import *  # noqa
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             confusion_matrix, roc_auc_score, roc_curve, precision_recall_curve)

QUICK = "--quick" in sys.argv


def metrics(y, p, thr=0.5):
    yh = (p >= thr).astype(int)
    return {"accuracy": accuracy_score(y, yh), "precision": precision_score(y, yh, zero_division=0),
            "recall": recall_score(y, yh), "f1": f1_score(y, yh), "auc": roc_auc_score(y, p),
            "cm": confusion_matrix(y, yh).tolist()}


def cv_run(X, y, k, cfg, seed=SEED, keep=False):
    skf = StratifiedKFold(k, shuffle=True, random_state=seed)
    oof = np.zeros(len(y)); accs = []; models = []; t = time.time()
    for f, (tr, va) in enumerate(skf.split(X, y)):
        m, _ = train_model(X[tr], y[tr], seed=seed + f, **cfg)
        oof[va] = predict_proba(m, X[va])
        accs.append(float(((oof[va] > 0.5) == y[va]).mean()))
        if keep:
            models.append(m)
        else:
            del m
    return {"cfg": {k_: v for k_, v in cfg.items()}, "acc_mean": float(np.mean(accs)),
            "acc_std": float(np.std(accs)), "fold_acc": accs, "time_s": time.time() - t}, oof, models


def main():
    X, y, files = load_dataset()
    dev, te = dev_test_split(y)
    Xd, yd, Xt, yt = X[dev], y[dev], X[te], y[te]
    R = {}
    base = dict(width=1.0, dropout=0.3, lr=3e-3, wd=5e-4, epochs=30, aug=True)
    E_SEARCH = 6 if QUICK else 20

    # ---- A. Grid multivariado --------------------------------------------------
    print("[A] grid multivariado")
    grid = list(itertools.product([1e-3, 3e-3, 1e-2], [0.1, 0.3, 0.5], [1e-4, 5e-3]))
    if QUICK:
        grid = grid[:2]
    R["grid"] = []
    for lr, do, wd in grid:
        r, _, _ = cv_run(Xd, yd, 3, dict(base, lr=lr, dropout=do, wd=wd, epochs=E_SEARCH))
        R["grid"].append(r); print(lr, do, wd, r["acc_mean"], r["acc_std"])
    # criterio: mayor media, desempate por menor std
    bestg = max(R["grid"], key=lambda r: (round(r["acc_mean"], 4), -r["acc_std"]))
    best = dict(base, lr=bestg["cfg"]["lr"], dropout=bestg["cfg"]["dropout"], wd=bestg["cfg"]["wd"])
    R["best_grid_cfg"] = best
    save_json(R, "cnn.json")

    # ---- B. Sensibilidad OFAT + eficiencia -------------------------------------
    print("[B] sensibilidad")
    K = 2 if QUICK else 5
    R["sens_width"] = []
    for w in ([0.25, 1.0] if QUICK else [0.125, 0.25, 0.5, 1.0]):
        cfg = dict(best, width=w, epochs=6 if QUICK else 30)
        r, _, ms = cv_run(Xd, yd, K, cfg, keep=True)
        m = ms[0]
        r.update(params=count_params(m), macs=count_flops(m), lat_ms=cpu_latency_ms(m, 100),
                 lat_tta_ms=cpu_latency_ms(m, 30, tta=True),
                 size_kb=count_params(m) * 4 / 1024)
        R["sens_width"].append(r); print("width", w, r["acc_mean"], r["params"], r["lat_ms"])
        del ms
    R["sens_epochs"] = []
    for e in ([4, 8] if QUICK else [10, 20, 30, 45]):
        r, _, _ = cv_run(Xd, yd, K, dict(best, epochs=e))
        R["sens_epochs"].append(r); print("epochs", e, r["acc_mean"])
    R["sens_aug"] = []
    for a in (False, True):
        r, _, _ = cv_run(Xd, yd, K, dict(best, aug=a, epochs=6 if QUICK else 30))
        R["sens_aug"].append(r); print("aug", a, r["acc_mean"])
    save_json(R, "cnn.json")

    # Selección del ancho: el más pequeño cuya exactitud esté dentro de 1 std del mejor
    wbest = max(R["sens_width"], key=lambda r: r["acc_mean"])
    cand = [r for r in R["sens_width"] if r["acc_mean"] >= wbest["acc_mean"] - wbest["acc_std"] / 2]
    wsel = min(cand, key=lambda r: r["macs"])
    ebest = max(R["sens_epochs"], key=lambda r: (round(r["acc_mean"], 4), -r["cfg"]["epochs"]))
    final_cfg = dict(best, width=wsel["cfg"]["width"], epochs=ebest["cfg"]["epochs"], aug=True)
    R["final_cfg"] = final_cfg
    print("FINAL CFG", final_cfg)

    # ---- C. CV 5 pliegues del modelo final ------------------------------------------
    print("[C] CV final")
    r, oof, models = cv_run(Xd, yd, K, final_cfg, keep=True)
    R["final_cv"] = r
    fold_metrics = []
    skf = StratifiedKFold(K, shuffle=True, random_state=SEED)
    for f, (tr, va) in enumerate(skf.split(Xd, yd)):
        fm = metrics(yd[va], oof[va]); fm.pop("cm"); fold_metrics.append(fm)
    R["final_cv_metrics"] = {k: [float(np.mean([m[k] for m in fold_metrics])),
                                 float(np.std([m[k] for m in fold_metrics]))] for k in fold_metrics[0]}
    R["final_cv_folds"] = fold_metrics
    R["final_cv_oof"] = metrics(yd, oof)
    # análisis de umbral sobre OOF
    thr = np.linspace(0.05, 0.95, 19)
    R["threshold_sweep"] = [{"thr": float(t), "acc": float(((oof >= t) == yd).mean())} for t in thr]
    fpr, tpr, _ = roc_curve(yd, oof); pr, rc, _ = precision_recall_curve(yd, oof)
    np.savez(os.path.join(RESULTS_DIR, "cnn_oof.npz"), oof=oof, y=yd, fpr=fpr, tpr=tpr, pr=pr, rc=rc)
    save_models(models, os.path.join(MODELS_DIR, "cnn_dev.pt"),
                extra={"cfg": final_cfg, "cv": R["final_cv_metrics"], "trained_on": "dev (80%)"})

    # ---- D. Hold-out: individual vs ensamble vs TTA -----------------------------
    print("[D] hold-out")
    ens = Ensemble(models)
    variants = {"cnn_single": predict_proba(models[0], Xt),
                "cnn_single_tta": predict_proba(models[0], Xt, tta=True),
                "cnn_ensemble": ens.predict_proba(Xt),
                "cnn_ensemble_tta": ens.predict_proba(Xt, tta=True)}
    R["holdout"] = {k: metrics(yt, v) for k, v in variants.items()}
    lat1 = cpu_latency_ms(models[0], 100)
    R["holdout_latency_ms"] = {"cnn_single": lat1, "cnn_single_tta": cpu_latency_ms(models[0], 30, tta=True),
                               "cnn_ensemble": lat1 * K, "cnn_ensemble_tta": cpu_latency_ms(models[0], 30, tta=True) * K}
    np.save(os.path.join(RESULTS_DIR, "pred_holdout_cnn.npy"), (variants["cnn_ensemble_tta"] >= 0.5).astype(int))
    np.save(os.path.join(RESULTS_DIR, "proba_holdout_cnn.npy"), variants["cnn_ensemble_tta"])
    errs = [files[te[i]] for i in np.where((variants["cnn_ensemble_tta"] >= 0.5) != yt)[0]]
    R["holdout_errors"] = errs
    print(R["holdout"])
    save_json(R, "cnn.json")

    # ---- E. Modelo de despliegue (todo el dataset) --------------------------------
    print("[E] modelo final (4000 imágenes)")
    finals = [train_model(X, y, seed=100 + s, **final_cfg)[0] for s in range(K)]
    save_models(finals, os.path.join(MODELS_DIR, "cnn_final.pt"),
                extra={"cfg": final_cfg, "cv": R["final_cv_metrics"], "trained_on": "dataset completo (4000)"})
    save_json(R, "cnn.json")
    print("OK")


if __name__ == "__main__":
    main()
