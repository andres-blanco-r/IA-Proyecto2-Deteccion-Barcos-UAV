"""Envoltorio único de inferencia para la UI (CNN ensamble o SVM + descriptores)."""
import os
import numpy as np
from common import MODELS_DIR, extract_features

MODEL_CHOICES = {
    "CNN ensamble (final, 4000 img)": "cnn_final.pt",
    "CNN ensamble (dev, 80%)": "cnn_dev.pt",
    "SVM + HOG/HSV/LBP (clásico)": "svm_descriptores.joblib",
}


class Predictor:
    def __init__(self, choice):
        self.name = choice
        path = os.path.join(MODELS_DIR, MODEL_CHOICES[choice])
        self.kind = "cnn" if path.endswith(".pt") else "svm"
        if self.kind == "cnn":
            import torch
            from cnn import load_models
            self.dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model, self.extra = load_models(path, self.dev)
        else:
            import joblib
            d = joblib.load(path)
            self.pipe, self.ppc, self.orient = d["pipe"], d["hog_ppc"], d["hog_orient"]
            self.use, self.clahe = tuple(d.get("use", ("hog", "hsv", "lbp"))), d.get("clahe", True)
            self.extra = {}

    def predict_proba(self, X, tta=True):
        """X: uint8 (N,80,80,3) -> prob. de barco (N,)"""
        if self.kind == "cnn":
            return self.model.predict_proba(X, tta=tta)
        F = np.stack([extract_features(x, use=self.use, clahe=self.clahe, hog_ppc=self.ppc, hog_orient=self.orient) for x in X])
        if hasattr(self.pipe, "decision_function"):
            s = self.pipe.decision_function(F)
            return 1 / (1 + np.exp(-2 * s))   # margen SVM -> pseudo-probabilidad
        return self.pipe.predict_proba(F)[:, 1]
