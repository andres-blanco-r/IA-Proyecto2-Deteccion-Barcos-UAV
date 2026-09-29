"""v2 del modelo: misma arquitectura e hiperparámetros, + aumento de dominio (aug="domain").

Repite las etapas C-E de train_cnn.py (CV 5 pliegues, hold-out, modelo final con 4000 imágenes)
y guarda los resultados previos en cnn.json["v1"] para poder compararlos.
"""
import os
import sys
import json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from common import *  # noqa
from cnn import *  # noqa
from sklearn.model_selection import StratifiedKFold
from train_cnn import metrics


def main():
    X, y, files = load_dataset()
    dev, te = dev_test_split(y)
    Xd, yd, Xt, yt = X[dev], y[dev], X[te], y[te]
    R = load_json("cnn.json")
    if "v1" not in R:
        R["v1"] = {k: R[k] for k in ("final_cfg", "final_cv", "final_cv_metrics", "final_cv_folds", "final_cv_oof", "holdout",
                                     "holdout_errors", "threshold_sweep") if k in R}
    cfg = dict(R["v1"]["final_cfg"], aug="domain", epochs=80)   # ver domain_capacity.json
    R["final_cfg"] = cfg
    print("CFG", cfg, flush=True)
    K = 5
    skf = StratifiedKFold(K, shuffle=True, random_state=SEED)
    oof = np.zeros(len(yd)); models = []; folds = []
    for f, (tr, va) in enumerate(skf.split(Xd, yd)):
        m, _ = train_model(Xd[tr], yd[tr], seed=SEED + f, **cfg)
        oof[va] = predict_proba(m, Xd[va]); models.append(m)
        fm = metrics(yd[va], oof[va]); fm.pop("cm"); folds.append(fm)
        print("fold", f, fm["accuracy"], flush=True)
    R["final_cv_folds"] = folds
    R["final_cv_metrics"] = {k: [float(np.mean([m[k] for m in folds])), float(np.std([m[k] for m in folds]))] for k in folds[0]}
    R["final_cv"] = {"acc_mean": R["final_cv_metrics"]["accuracy"][0], "acc_std": R["final_cv_metrics"]["accuracy"][1]}
    R["final_cv_oof"] = metrics(yd, oof)
    thr = np.linspace(0.05, 0.95, 19)
    R["threshold_sweep"] = [{"thr": float(t), "acc": float(((oof >= t) == yd).mean())} for t in thr]
    from sklearn.metrics import roc_curve, precision_recall_curve
    fpr, tpr, _ = roc_curve(yd, oof); pr, rc, _ = precision_recall_curve(yd, oof)
    np.savez(os.path.join(RESULTS_DIR, "cnn_oof.npz"), oof=oof, y=yd, fpr=fpr, tpr=tpr, pr=pr, rc=rc)
    save_models(models, os.path.join(MODELS_DIR, "cnn_dev.pt"),
                extra={"cfg": cfg, "cv": R["final_cv_metrics"], "trained_on": "dev (80%)"})
    ens = Ensemble(models)
    variants = {"cnn_single": predict_proba(models[0], Xt), "cnn_single_tta": predict_proba(models[0], Xt, tta=True),
                "cnn_ensemble": ens.predict_proba(Xt), "cnn_ensemble_tta": ens.predict_proba(Xt, tta=True)}
    R["holdout"] = {k: metrics(yt, v) for k, v in variants.items()}
    np.save(os.path.join(RESULTS_DIR, "pred_holdout_cnn.npy"), (variants["cnn_ensemble_tta"] >= 0.5).astype(int))
    np.save(os.path.join(RESULTS_DIR, "proba_holdout_cnn.npy"), variants["cnn_ensemble_tta"])
    R["holdout_errors"] = [files[te[i]] for i in np.where((variants["cnn_ensemble_tta"] >= 0.5) != yt)[0]]
    print("CV", R["final_cv_metrics"]["accuracy"], "HOLDOUT", {k: v["accuracy"] for k, v in R["holdout"].items()}, flush=True)
    save_json(R, "cnn.json")
    finals = [train_model(X, y, seed=100 + s, **cfg)[0] for s in range(K)]
    save_models(finals, os.path.join(MODELS_DIR, "cnn_final.pt"),
                extra={"cfg": cfg, "cv": R["final_cv_metrics"], "trained_on": "dataset completo (4000)"})
    print("OK", flush=True)


if __name__ == "__main__":
    main()
