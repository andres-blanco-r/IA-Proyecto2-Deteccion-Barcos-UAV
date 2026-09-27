"""C1 - Metodología de optimización (ruta clásica: descriptores visuales + clasificador).

Etapas:
  0. Baseline: píxeles crudos + Regresión Logística / SVM por defecto.
  1. Ablación de preprocesamiento (CLAHE) y descriptores (HOG, HSV, LBP y combinaciones).
  2. Sensibilidad de parámetros del descriptor HOG (pixels_per_cell x orientaciones).
  3. Búsqueda sistemática de hiperparámetros (GridSearchCV, 5 pliegues) para SVM, RF y LR.
  4. Evaluación del mejor pipeline en el hold-out (test ciego simulado) + latencia.
Salida: results/classic.json, models/svm_descriptores.joblib
"""
import os
import sys
import time
import numpy as np
import joblib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from common import *  # noqa
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

CV = StratifiedKFold(5, shuffle=True, random_state=SEED)
SCORING = ["accuracy", "precision", "recall", "f1"]
NJ = 6  # procesos paralelos (limitado para controlar temperatura del equipo)


def cv_eval(pipe, F, y):
    r = cross_validate(pipe, F, y, cv=CV, scoring=SCORING, n_jobs=NJ)
    return {k: [float(np.mean(r["test_" + k])), float(np.std(r["test_" + k]))] for k in SCORING}


def holdout(pipe, Ftr, ytr, Fte, yte):
    pipe.fit(Ftr, ytr)
    p = pipe.predict(Fte)
    return {"accuracy": accuracy_score(yte, p), "precision": precision_score(yte, p),
            "recall": recall_score(yte, p), "f1": f1_score(yte, p),
            "cm": confusion_matrix(yte, p).tolist()}, p


def main():
    X, y, files = load_dataset()
    dev, te = dev_test_split(y)
    Xd, yd = X[dev], y[dev]
    R = {"n_dev": int(len(dev)), "n_test": int(len(te)), "class_balance_dev": np.bincount(yd).tolist()}

    # ---- 0. Baselines ---------------------------------------------------------
    print("[0] Baseline")
    raw = X.reshape(len(X), -1).astype(np.float32) / 255.0
    R["baseline"] = {
        "LR_pixeles": cv_eval(Pipeline([("sc", StandardScaler()), ("clf", LogisticRegression(max_iter=2000))]), raw[dev], yd),
        "SVM_pixeles_default": cv_eval(Pipeline([("sc", StandardScaler()), ("clf", SVC())]), raw[dev], yd),
    }
    print(R["baseline"])

    # ---- 1. Ablación preprocesamiento + descriptores --------------------------
    print("[1] Ablación descriptores")
    combos = [("hog",), ("hsv",), ("lbp",), ("hog", "hsv"), ("hog", "lbp"), ("hsv", "lbp"), ("hog", "hsv", "lbp")]
    R["ablation"] = []
    feats_cache = {}
    for clahe in (False, True):
        for c in combos:
            t = time.time()
            F = extract_batch(X, use=c, clahe=clahe)
            feats_cache[(c, clahe)] = F
            r = cv_eval(Pipeline([("sc", StandardScaler()), ("clf", SVC())]), F[dev], yd)
            R["ablation"].append({"desc": "+".join(c).upper(), "clahe": clahe, "dim": int(F.shape[1]),
                                  "t_extract_ms": (time.time() - t) / len(X) * 1000, **r})
            print(R["ablation"][-1]["desc"], clahe, r["accuracy"])

    # Selección guiada por datos: mejor combinación descriptor/preprocesado de la ablación
    bab = max(R["ablation"], key=lambda d: d["accuracy"][0])
    USE, CLAHE = tuple(bab["desc"].lower().split("+")), bab["clahe"]
    R["selected_features"] = {"use": list(USE), "clahe": CLAHE, "cv_acc": bab["accuracy"]}
    print("Seleccionado:", USE, CLAHE)

    # ---- 2. Sensibilidad HOG ---------------------------------------------------
    print("[2] Sensibilidad HOG")
    R["hog_sensitivity"] = []
    for ppc in (6, 8, 10, 16):
        for orient in (6, 9, 12):
            F = extract_batch(X, use=USE, clahe=CLAHE, hog_ppc=ppc, hog_orient=orient)
            r = cv_eval(Pipeline([("sc", StandardScaler()), ("clf", SVC())]), F[dev], yd)
            R["hog_sensitivity"].append({"ppc": ppc, "orient": orient, "dim": int(F.shape[1]), **r})
            print(ppc, orient, r["accuracy"])
    best_h = max(R["hog_sensitivity"], key=lambda d: d["accuracy"][0])
    R["best_hog"] = {"ppc": best_h["ppc"], "orient": best_h["orient"]}

    # ---- 3. GridSearch de hiperparámetros --------------------------------------
    print("[3] GridSearchCV")
    F = extract_batch(X, use=USE, clahe=CLAHE, hog_ppc=best_h["ppc"], hog_orient=best_h["orient"])
    Fd = F[dev]
    grids = {
        "SVM_RBF": (Pipeline([("sc", StandardScaler()), ("pca", "passthrough"), ("clf", SVC(probability=False))]),
                    {"pca": ["passthrough", PCA(0.95, random_state=SEED)],
                     "clf__C": [0.3, 1, 3, 10, 30, 100],
                     "clf__gamma": ["scale", 3e-4, 1e-3, 3e-3],
                     "clf__class_weight": [None, "balanced"]}),
        "RandomForest": (Pipeline([("clf", RandomForestClassifier(random_state=SEED, n_jobs=1))]),
                         {"clf__n_estimators": [200, 500], "clf__max_depth": [None, 20],
                          "clf__max_features": ["sqrt", 0.1]}),
        "LogReg_L2": (Pipeline([("sc", StandardScaler()), ("clf", LogisticRegression(max_iter=5000))]),
                      {"clf__C": [0.001, 0.01, 0.1, 1]}),
    }
    R["gridsearch"] = {}
    best = None
    for name, (pipe, grid) in grids.items():
        t = time.time()
        gs = GridSearchCV(pipe, grid, cv=CV, scoring="accuracy", n_jobs=NJ, refit=True)
        gs.fit(Fd, yd)
        res = gs.cv_results_
        table = [{"params": {k: str(v) for k, v in p.items()}, "mean": float(m), "std": float(s)}
                 for p, m, s in zip(res["params"], res["mean_test_score"], res["std_test_score"])]
        R["gridsearch"][name] = {"best_params": {k: str(v) for k, v in gs.best_params_.items()},
                                 "best_cv_acc": float(gs.best_score_),
                                 "best_cv_std": float(res["std_test_score"][gs.best_index_]),
                                 "n_configs": len(table), "time_s": time.time() - t, "table": table}
        print(name, gs.best_params_, gs.best_score_)
        if best is None or gs.best_score_ > best[1]:
            best = (name, gs.best_score_, gs.best_estimator_)

    # CV completo (todas las métricas) del mejor
    name, _, est = best
    R["best_classic"] = {"name": name, "cv": cv_eval(est, Fd, yd)}

    # ---- 4. Hold-out + latencia ---------------------------------------------------
    print("[4] Hold-out")
    hb, _ = holdout(Pipeline([("sc", StandardScaler()), ("clf", LogisticRegression(max_iter=2000))]), raw[dev], yd, raw[te], y[te])
    R["holdout_baseline"] = hb
    ho, pred = holdout(est, Fd, yd, F[te], y[te])
    R["holdout_best_classic"] = ho
    np.save(os.path.join(RESULTS_DIR, "pred_holdout_classic.npy"), pred)
    t = time.perf_counter()
    for x in X[te[:200]]:
        est.predict(extract_features(x, use=USE, clahe=CLAHE, hog_ppc=best_h["ppc"], hog_orient=best_h["orient"])[None])
    R["latency_ms_classic"] = (time.perf_counter() - t) / 200 * 1000
    print(ho, R["latency_ms_classic"])
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump({"pipe": est, "use": USE, "clahe": CLAHE, "hog_ppc": best_h["ppc"], "hog_orient": best_h["orient"]},
                os.path.join(MODELS_DIR, "svm_descriptores.joblib"))
    save_json(R, "classic.json")


if __name__ == "__main__":
    main()
