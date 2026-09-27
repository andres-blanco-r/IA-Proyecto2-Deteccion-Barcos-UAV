"""Utilidades comunes: carga de imágenes, preprocesamiento y descriptores visuales.

Proyecto 2 - IA (UMNG) - Clasificación barco / no barco (ShipsNet, 80x80 RGB).
"""
import os
import re
import json
import numpy as np
from PIL import Image
import cv2
from skimage.feature import hog, local_binary_pattern

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "shipsnet", "shipsnet")
RESULTS_DIR = os.path.join(ROOT, "results")
MODELS_DIR = os.path.join(ROOT, "models")
IMG_SIZE = 80
IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")
SEED = 42


def load_image(path, size=IMG_SIZE):
    """Carga cualquier imagen como RGB uint8 (size x size). Soporta rutas con tildes."""
    img = Image.open(path).convert("RGB")
    if img.size != (size, size):
        img = img.resize((size, size), Image.BILINEAR)
    return np.asarray(img, dtype=np.uint8)


def label_from_name(fname):
    """ShipsNet codifica la etiqueta al inicio del nombre: '1__...' barco, '0__...' no barco."""
    m = re.match(r"^([01])__", os.path.basename(fname))
    return int(m.group(1)) if m else None


def list_images(folder):
    return sorted(f for f in os.listdir(folder) if f.lower().endswith(IMG_EXT))


def load_dataset(folder=DATA_DIR, cache=True):
    cpath = os.path.join(ROOT, "data", "shipsnet_cache.npz")
    if cache and folder == DATA_DIR and os.path.exists(cpath):
        d = np.load(cpath)
        return d["X"], d["y"], list(d["files"])
    files = list_images(folder)
    X = np.stack([load_image(os.path.join(folder, f)) for f in files])
    y = np.array([label_from_name(f) for f in files], dtype=np.int64)
    if cache and folder == DATA_DIR:
        np.savez_compressed(cpath, X=X, y=y, files=np.array(files))
    return X, y, files


def dev_test_split(y, test_frac=0.2, seed=SEED):
    """Partición estratificada fija: 80% desarrollo (CV) / 20% test ciego simulado (hold-out)."""
    from sklearn.model_selection import train_test_split
    idx = np.arange(len(y))
    dev, test = train_test_split(idx, test_size=test_frac, stratify=y, random_state=seed)
    return np.sort(dev), np.sort(test)


# ----------------------------------------------------------------------------
# Preprocesamiento
# ----------------------------------------------------------------------------
def to_gray(img):
    return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)


_clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))


def preprocess_gray(img, clahe=True, blur=False):
    """Gris + CLAHE (ecualización adaptativa: compensa brillo/contraste del mar y la neblina)."""
    g = to_gray(img)
    if blur:
        g = cv2.GaussianBlur(g, (3, 3), 0)
    if clahe:
        g = _clahe.apply(g)
    return g


# ----------------------------------------------------------------------------
# Descriptores visuales
# ----------------------------------------------------------------------------
def feat_hog(gray, ppc=8, orient=9, cpb=2):
    """HOG: forma/contorno alargado del casco y la estela."""
    return hog(gray, orientations=orient, pixels_per_cell=(ppc, ppc),
               cells_per_block=(cpb, cpb), block_norm="L2-Hys", feature_vector=True)


def feat_hsv(img, bins=(8, 4, 4)):
    """Histograma de color HSV normalizado (agua vs. casco metálico/blanco) + momentos."""
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], None, list(bins), [0, 180, 0, 256, 0, 256]).ravel()
    h /= (h.sum() + 1e-8)
    # momentos de color del centro (el barco suele estar centrado en el parche)
    c = img[20:60, 20:60].reshape(-1, 3).astype(np.float32) / 255.0
    a = img.reshape(-1, 3).astype(np.float32) / 255.0
    mom = np.concatenate([c.mean(0), c.std(0), a.mean(0), a.std(0), c.mean(0) - a.mean(0)])
    return np.concatenate([h, mom])


def feat_lbp(gray, P=8, R=1, grid=2):
    """LBP uniforme por celdas (textura: oleaje vs. cubierta/contenedores)."""
    lbp = local_binary_pattern(gray, P, R, method="uniform")
    nb = P + 2
    H, W = gray.shape
    out = []
    for i in range(grid):
        for j in range(grid):
            blk = lbp[i * H // grid:(i + 1) * H // grid, j * W // grid:(j + 1) * W // grid]
            h, _ = np.histogram(blk, bins=nb, range=(0, nb))
            out.append(h / (h.sum() + 1e-8))
    return np.concatenate(out)


def extract_features(img, use=("hog", "hsv", "lbp"), clahe=True, hog_ppc=8, hog_orient=9):
    g = preprocess_gray(img, clahe=clahe)
    parts = []
    if "hog" in use:
        parts.append(feat_hog(g, ppc=hog_ppc, orient=hog_orient))
    if "hsv" in use:
        parts.append(feat_hsv(img))
    if "lbp" in use:
        parts.append(feat_lbp(g))
    if "raw" in use:
        parts.append(cv2.resize(img, (20, 20), interpolation=cv2.INTER_AREA).ravel() / 255.0)
    return np.concatenate(parts).astype(np.float32)


def extract_batch(X, **kw):
    return np.stack([extract_features(x, **kw) for x in X])


def save_json(obj, name):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=float)


def load_json(name):
    with open(os.path.join(RESULTS_DIR, name), encoding="utf-8") as f:
        return json.load(f)
