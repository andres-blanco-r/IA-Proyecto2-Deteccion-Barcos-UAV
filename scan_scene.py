"""Integración en el sistema de percepción del UAV: detección por ventana deslizante.

El clasificador binario 80x80 se desliza sobre una escena completa (imagen satelital/aérea del
puerto); las ventanas con P(barco) alta se fusionan por NMS y se dibujan como detecciones.
Uso:  python scan_scene.py [ruta_escena.png] [--stride 10] [--thr 0.9]
"""
import os
import sys
import time
import argparse
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from common import ROOT, MODELS_DIR, RESULTS_DIR
from cnn import load_models


def nms(boxes, scores, iou=0.3):
    order = np.argsort(-scores); keep = []
    while len(order):
        i = order[0]; keep.append(i)
        xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0]); yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
        xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2]); yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        a = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        order = order[1:][inter / (a[i] + a[order[1:]] - inter) < iou]
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene", nargs="?", default=os.path.join(ROOT, "data", "scenes", "scenes", "sfbay_4.png"))
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--thr", type=float, default=0.9)
    a = ap.parse_args()
    model, _ = load_models(os.path.join(MODELS_DIR, "cnn_final.pt"))
    img = np.asarray(Image.open(a.scene).convert("RGB"))
    H, W, _ = img.shape
    ys, xs = np.arange(0, H - 80, a.stride), np.arange(0, W - 80, a.stride)
    t = time.time()
    boxes, scores = [], []
    for y0 in ys:
        row = np.stack([img[y0:y0 + 80, x0:x0 + 80] for x0 in xs])
        p = model.predict_proba(row)
        for x0, pp in zip(xs, p):
            if pp >= a.thr:
                boxes.append([x0, y0, x0 + 80, y0 + 80]); scores.append(pp)
    dt = time.time() - t
    boxes, scores = np.array(boxes), np.array(scores)
    keep = nms(boxes, scores) if len(boxes) else []
    out = Image.fromarray(img); d = ImageDraw.Draw(out)
    for i in keep:
        d.rectangle(boxes[i].tolist(), outline=(255, 40, 40), width=3)
    name = os.path.splitext(os.path.basename(a.scene))[0]
    path = os.path.join(RESULTS_DIR, f"escena_{name}.png")
    out.save(path)
    print(f"{name}: {W}x{H}px, {len(ys) * len(xs)} ventanas en {dt:.1f}s -> {len(keep)} barcos detectados. {path}")


if __name__ == "__main__":
    main()
