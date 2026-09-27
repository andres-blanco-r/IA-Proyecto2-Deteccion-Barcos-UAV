"""Genera las figuras y el resumen estadístico del informe (results/*.png, results/summary.json)."""
import os
import sys
import json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from common import *  # noqa
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import binomtest, chi2

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150, "savefig.bbox": "tight"})
BLUE, LBLUE, RED, GRAY, GREEN = "#0b5cad", "#9bb7d4", "#c62828", "#7a8591", "#1a7f37"
C = load_json("classic.json")
N = load_json("cnn.json")
out = lambda n: os.path.join(RESULTS_DIR, n)
S = {}

# 1. Ablación de descriptores ------------------------------------------------------
ab = C["ablation"]
descs = [d["desc"] for d in ab if not d["clahe"]]
fig, ax = plt.subplots(figsize=(7, 3))
x = np.arange(len(descs))
for k, (cl, col, lab) in enumerate([(False, LBLUE, "sin CLAHE"), (True, BLUE, "con CLAHE")]):
    v = [d for d in ab if d["clahe"] == cl]
    ax.bar(x + (k - 0.5) * 0.38, [d["accuracy"][0] * 100 for d in v], 0.38,
           yerr=[d["accuracy"][1] * 100 for d in v], capsize=2, color=col, label=lab)
base = C["baseline"]["LR_pixeles"]["accuracy"][0] * 100
ax.axhline(base, color=RED, ls="--", lw=1, label=f"Baseline píxeles+LR ({base:.2f}%)")
ax.set_xticks(x); ax.set_xticklabels(descs, rotation=15)
ax.set_ylim(85, 100); ax.set_ylabel("Accuracy CV 5-fold (%)")
ax.set_title("Ablación: preprocesamiento y descriptores visuales (SVM-RBF por defecto)")
ax.legend(fontsize=7, loc="lower right")
fig.savefig(out("fig_ablacion.png")); plt.close(fig)

# 2. Sensibilidad HOG -----------------------------------------------------------------
hs = C["hog_sensitivity"]
ppcs = sorted({d["ppc"] for d in hs}); ors = sorted({d["orient"] for d in hs})
M = np.array([[next(d for d in hs if d["ppc"] == p and d["orient"] == o)["accuracy"][0] * 100 for o in ors] for p in ppcs])
fig, ax = plt.subplots(figsize=(3.6, 3))
im = ax.imshow(M, cmap="Blues")
for (i, j), v in np.ndenumerate(M):
    ax.text(j, i, f"{v:.2f}", ha="center", va="center", color="white" if v > M.mean() else "black", fontsize=8)
ax.set_xticks(range(len(ors))); ax.set_xticklabels(ors); ax.set_xlabel("Orientaciones HOG")
ax.set_yticks(range(len(ppcs))); ax.set_yticklabels(ppcs); ax.set_ylabel("Píxeles por celda")
ax.set_title("Sensibilidad HOG (acc CV %)")
fig.savefig(out("fig_hog_sens.png")); plt.close(fig)

# 3. GridSearch SVM (corte C x gamma con el mejor preprocesado/pesos) ---------------------
g = C["gridsearch"]["SVM_RBF"]
bp = g["best_params"]
rows = [r for r in g["table"] if r["params"]["pca"] == bp["pca"] and r["params"]["clf__class_weight"] == bp["clf__class_weight"]]
Cs = sorted({float(r["params"]["clf__C"]) for r in rows})
gs = sorted({r["params"]["clf__gamma"] for r in rows}, key=lambda s: -1 if s == "scale" else float(s))
M = np.array([[next(r["mean"] for r in rows if float(r["params"]["clf__C"]) == c and r["params"]["clf__gamma"] == ga) * 100
               for ga in gs] for c in Cs])
fig, ax = plt.subplots(figsize=(4, 3.2))
ax.imshow(M, cmap="Blues", vmin=M.min() - 0.5)
for (i, j), v in np.ndenumerate(M):
    ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7, color="white" if v > np.median(M) else "black")
ax.set_xticks(range(len(gs))); ax.set_xticklabels(gs); ax.set_xlabel("gamma")
ax.set_yticks(range(len(Cs))); ax.set_yticklabels([f"{c:g}" for c in Cs]); ax.set_ylabel("C")
ax.set_title("GridSearchCV SVM-RBF (acc CV %)")
fig.savefig(out("fig_grid_svm.png")); plt.close(fig)

# 4. Grid CNN (lr x dropout por weight decay) ------------------------------------------
gr = N["grid"]
lrs = sorted({r["cfg"]["lr"] for r in gr}); dos = sorted({r["cfg"]["dropout"] for r in gr}); wds = sorted({r["cfg"]["wd"] for r in gr})
fig, axs = plt.subplots(1, len(wds), figsize=(3.3 * len(wds), 3))
allv = [r["acc_mean"] * 100 for r in gr]
for ax, wd in zip(np.atleast_1d(axs), wds):
    M = np.array([[next(r["acc_mean"] for r in gr if r["cfg"]["lr"] == lr and r["cfg"]["dropout"] == do and r["cfg"]["wd"] == wd) * 100
                   for do in dos] for lr in lrs])
    ax.imshow(M, cmap="Blues", vmin=min(allv), vmax=max(allv))
    for (i, j), v in np.ndenumerate(M):
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8, color="white" if v > np.median(allv) else "black")
    ax.set_xticks(range(len(dos))); ax.set_xticklabels(dos); ax.set_xlabel("dropout")
    ax.set_yticks(range(len(lrs))); ax.set_yticklabels([f"{l:g}" for l in lrs]); ax.set_ylabel("learning rate")
    ax.set_title(f"weight decay = {wd:g}")
fig.suptitle("Sintonización multivariada CNN (acc CV 3-fold %)", y=1.02)
fig.savefig(out("fig_grid_cnn.png")); plt.close(fig)
S["grid_cnn_range"] = [min(allv), max(allv)]

# 5. Pareto exactitud vs costo (inferencia embarcada) ------------------------------------
sw = N["sens_width"]
fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.2))
lat = [r["lat_ms"] for r in sw]; acc = [r["acc_mean"] * 100 for r in sw]; err = [r["acc_std"] * 100 for r in sw]
ax[0].errorbar(lat, acc, yerr=err, fmt="o-", color=BLUE, capsize=3, label="CNN (ancho variable)")
for r in sw:
    ax[0].annotate(f"w={r['cfg']['width']}\n{r['params'] / 1e3:.0f}k par.", (r["lat_ms"], r["acc_mean"] * 100),
                   textcoords="offset points", xytext=(5, -18), fontsize=7)
ax[0].scatter([C["latency_ms_classic"]], [C["best_classic"]["cv"]["accuracy"][0] * 100], marker="s", color=GRAY, label="SVM+descriptores")
sel = N["final_cfg"]["width"]
rs = next(r for r in sw if r["cfg"]["width"] == sel)
ax[0].scatter([rs["lat_ms"]], [rs["acc_mean"] * 100], s=160, facecolors="none", edgecolors=RED, lw=2, label="seleccionado")
ax[0].axhline(98, color=RED, ls="--", lw=1)
ax[0].set_xscale("log"); ax[0].set_xlabel("Latencia CPU 1 hilo (ms/img, log)"); ax[0].set_ylabel("Accuracy CV 5-fold (%)")
ax[0].set_title("Frente exactitud–costo (UAV)"); ax[0].legend(fontsize=7, loc="lower right")
se = N["sens_epochs"]
ax[1].errorbar([r["cfg"]["epochs"] for r in se], [r["acc_mean"] * 100 for r in se], yerr=[r["acc_std"] * 100 for r in se],
               fmt="o-", color=BLUE, capsize=3, label="épocas")
sa = N["sens_aug"]
ax[1].set_xlabel("Épocas"); ax[1].set_ylabel("Accuracy CV 5-fold (%)")
ax[1].set_title(f"Épocas · aumento: sin {sa[0]['acc_mean'] * 100:.2f}% / con {sa[1]['acc_mean'] * 100:.2f}%")
ax[1].axhline(98, color=RED, ls="--", lw=1)
fig.tight_layout(); fig.savefig(out("fig_pareto_sens.png")); plt.close(fig)

# 6. ROC / PR / umbral (OOF) -------------------------------------------------------------
d = np.load(out("cnn_oof.npz"))
fig, ax = plt.subplots(1, 3, figsize=(10, 3))
ax[0].plot(d["fpr"], d["tpr"], color=BLUE); ax[0].plot([0, 1], [0, 1], ":", color=GRAY)
ax[0].set_title(f"ROC (OOF)  AUC={N['final_cv_oof']['auc']:.4f}"); ax[0].set_xlabel("FPR"); ax[0].set_ylabel("TPR")
ax[1].plot(d["rc"], d["pr"], color=BLUE); ax[1].set_title("Precisión–Recall (OOF)"); ax[1].set_xlabel("Recall"); ax[1].set_ylabel("Precisión")
ts = N["threshold_sweep"]
ax[2].plot([t["thr"] for t in ts], [t["acc"] * 100 for t in ts], "o-", color=BLUE, ms=3)
ax[2].axvline(0.5, color=RED, ls="--", lw=1); ax[2].set_xlabel("Umbral de decisión"); ax[2].set_ylabel("Accuracy OOF (%)")
ax[2].set_title("Sensibilidad al umbral")
fig.tight_layout(); fig.savefig(out("fig_roc_pr_umbral.png")); plt.close(fig)

# 7. Progresión de la optimización (hold-out) ----------------------------------------------
H = N["holdout"]
steps = [("Baseline\npíxeles+LR", C["holdout_baseline"]["accuracy"], C["baseline"]["LR_pixeles"]["accuracy"][0]),
         ("SVM\ndescriptores\n+GridSearch", C["holdout_best_classic"]["accuracy"], C["best_classic"]["cv"]["accuracy"][0]),
         ("CNN\nindividual", H["cnn_single"]["accuracy"], N["final_cv_metrics"]["accuracy"][0]),
         ("CNN\n+TTA", H["cnn_single_tta"]["accuracy"], None),
         ("Ensamble 5\nCNN", H["cnn_ensemble"]["accuracy"], None),
         ("Ensamble\n+TTA (final)", H["cnn_ensemble_tta"]["accuracy"], None)]
fig, ax = plt.subplots(figsize=(7.5, 3.2))
x = np.arange(len(steps))
b = ax.bar(x, [s[1] * 100 for s in steps], color=[GRAY, LBLUE, BLUE, BLUE, BLUE, GREEN])
for i, s in enumerate(steps):
    ax.text(i, s[1] * 100 + 0.1, f"{s[1] * 100:.2f}%", ha="center", fontsize=8, fontweight="bold")
    if s[2] is not None:
        ax.plot(i, s[2] * 100, "D", color=RED, ms=5)
ax.plot([], [], "D", color=RED, label="media CV 5-fold (desarrollo)")
ax.axhline(98, color=RED, ls="--", lw=1, label="Meta 98 %")
ax.set_xticks(x); ax.set_xticklabels([s[0] for s in steps], fontsize=7.5)
ax.set_ylim(min(s[1] for s in steps) * 100 - 2, 100.5); ax.set_ylabel("Accuracy hold-out (%)")
ax.set_title("Mejora demostrable: de la línea base al modelo final (test ciego simulado, n=800)")
ax.legend(fontsize=7, loc="lower right")
fig.savefig(out("fig_progresion.png")); plt.close(fig)

# 8. Matriz de confusión hold-out + errores --------------------------------------------------
X, y, files = load_dataset()
dev, te = dev_test_split(y)
cm = np.array(H["cnn_ensemble_tta"]["cm"])
fig, ax = plt.subplots(figsize=(3, 2.8))
ax.imshow(cm, cmap="Blues")
for (i, j), v in np.ndenumerate(cm):
    ax.text(j, i, v, ha="center", va="center", fontsize=13, fontweight="bold", color="white" if v > cm.max() / 2 else "black")
ax.set_xticks([0, 1]); ax.set_xticklabels(["no barco", "barco"]); ax.set_yticks([0, 1]); ax.set_yticklabels(["no barco", "barco"])
ax.set_xlabel("Predicción"); ax.set_ylabel("Real"); ax.set_title("Hold-out: ensamble+TTA")
fig.savefig(out("fig_cm_holdout.png")); plt.close(fig)
errs = N.get("holdout_errors", [])
if errs:
    proba = np.load(out("proba_holdout_cnn.npy"))
    fi = {f: k for k, f in enumerate(files)}
    tpos = {i: k for k, i in enumerate(te)}
    n = min(len(errs), 8)
    fig, axs = plt.subplots(1, n, figsize=(1.4 * n, 1.8))
    for ax, e in zip(np.atleast_1d(axs), errs[:n]):
        i = fi[e]
        ax.imshow(X[i]); ax.axis("off")
        ax.set_title(f"real={'barco' if y[i] else 'no'}\np={proba[tpos[i]]:.2f}", fontsize=7)
    fig.suptitle("Errores del modelo final en hold-out", fontsize=9)
    fig.savefig(out("fig_errores.png")); plt.close(fig)

# 9. Estadística: McNemar CNN vs SVM, IC Wilson -------------------------------------------------
pc = np.load(out("pred_holdout_classic.npy")); pn = np.load(out("pred_holdout_cnn.npy")); yt = y[te]
b01 = int(((pc == yt) & (pn != yt)).sum()); b10 = int(((pc != yt) & (pn == yt)).sum())
p_mc = binomtest(min(b01, b10), b01 + b10, 0.5).pvalue if b01 + b10 else 1.0


def wilson(k, n, z=1.96):
    p = k / n; dd = 1 + z * z / n; c = (p + z * z / (2 * n)) / dd
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / dd
    return [c - h, c + h]


k = int((pn == yt).sum())
S.update({"mcnemar": {"svm_ok_cnn_err": b01, "svm_err_cnn_ok": b10, "p_value_exact": p_mc},
          "holdout_final_acc": k / len(yt), "holdout_final_ci95": wilson(k, len(yt)),
          "baseline_holdout_acc": C["holdout_baseline"]["accuracy"],
          "classic_holdout_acc": C["holdout_best_classic"]["accuracy"]})
save_json(S, "summary.json")
print(json.dumps(S, indent=1))
