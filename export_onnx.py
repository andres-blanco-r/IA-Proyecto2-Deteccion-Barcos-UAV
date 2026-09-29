"""Exporta los ensambles CNN a ONNX para la UI web (docs/, GitHub Pages) y verifica equivalencia.

Entrada del grafo: float32 [N,3,80,80] ya normalizado (mean/std de src/cnn.py).
Salida: P(barco) [N] = promedio del softmax de los 5 modelos del ensamble.
La TTA (8 transformaciones diedrales) se hace en JavaScript armando el lote.
"""
import os
import sys
import json
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from common import MODELS_DIR, ROOT, RESULTS_DIR, load_image, list_images
from cnn import load_models, to_tensor, MEAN, STD

OUT = os.path.join(ROOT, "docs", "models")


class EnsembleNet(nn.Module):
    def __init__(self, models):
        super().__init__()
        self.ms = nn.ModuleList(models)

    def forward(self, x):
        return torch.stack([F.softmax(m(x), 1)[:, 1] for m in self.ms]).mean(0)


def main():
    os.makedirs(OUT, exist_ok=True)
    X = np.stack([load_image(os.path.join(ROOT, "test_ciego", f)) for f in list_images(os.path.join(ROOT, "test_ciego"))[:64]])
    meta = {"mean": MEAN.view(-1).tolist(), "std": STD.view(-1).tolist(), "size": 80, "models": {}}
    for name in ("cnn_final", "cnn_dev"):
        ens, extra = load_models(os.path.join(MODELS_DIR, name + ".pt"), torch.device("cpu"))
        net = EnsembleNet(ens.models).eval()
        path = os.path.join(OUT, name + ".onnx")
        torch.onnx.export(net, torch.zeros(1, 3, 80, 80), path, input_names=["x"], output_names=["p"],
                          dynamic_axes={"x": {0: "n"}, "p": {0: "n"}}, opset_version=13, do_constant_folding=True)
        import onnxruntime as ort
        s = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        xt = to_tensor(X).numpy().astype(np.float32)
        p_onnx = s.run(None, {"x": xt})[0]
        p_torch = ens.predict_proba(X, tta=False)
        diff = float(np.abs(p_onnx - p_torch).max())
        print(name, "size %.1f MB" % (os.path.getsize(path) / 1e6), "max|diff| = %.2e" % diff)
        assert diff < 1e-4
        meta["models"][name] = {"file": "models/" + name + ".onnx", "trained_on": extra.get("trained_on", ""),
                                "cfg": extra.get("cfg", {})}
    cnn = json.load(open(os.path.join(RESULTS_DIR, "cnn.json"), encoding="utf-8"))
    meta["cv"] = cnn["final_cv_metrics"]
    meta["holdout"] = {k: {kk: v[kk] for kk in ("accuracy", "precision", "recall", "f1", "cm")} for k, v in cnn["holdout"].items()}
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    print("OK", OUT)


if __name__ == "__main__":
    main()
