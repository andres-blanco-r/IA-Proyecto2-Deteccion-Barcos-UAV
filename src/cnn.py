"""CNN ligera para inferencia embarcada (UAV): ShipNet-Lite.

Arquitectura parametrizada por ancho (width) para estudiar el balance exactitud / costo
computacional. Entrenamiento con aumento de datos en GPU (rotaciones 90°, espejos,
brillo/contraste, ruido), AdamW + OneCycle, label smoothing.
"""
import time
import copy
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MEAN = torch.tensor([0.412, 0.424, 0.372]).view(1, 3, 1, 1)
STD = torch.tensor([0.190, 0.157, 0.152]).view(1, 3, 1, 1)


def conv_bn(cin, cout):
    return nn.Sequential(nn.Conv2d(cin, cout, 3, padding=1, bias=False),
                         nn.BatchNorm2d(cout), nn.ReLU(inplace=True))


class ShipNetLite(nn.Module):
    def __init__(self, width=1.0, dropout=0.3, depth=4):
        super().__init__()
        chs = [max(8, int(c * width)) for c in (32, 64, 128, 256)][:depth]
        layers, cin = [], 3
        for c in chs:                       # 80 -> 40 -> 20 -> 10 -> 5
            layers += [conv_bn(cin, c), conv_bn(c, c), nn.MaxPool2d(2)]
            cin = c
        self.features = nn.Sequential(*layers)
        self.head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(),
                                  nn.Dropout(dropout), nn.Linear(cin, 2))
        self.cfg = dict(width=width, dropout=dropout, depth=depth)

    def forward(self, x):
        return self.head(self.features(x))


def to_tensor(X):
    """uint8 NHWC -> float NCHW normalizado."""
    t = torch.from_numpy(np.ascontiguousarray(X)).permute(0, 3, 1, 2).float() / 255.0
    return (t - MEAN) / STD


def augment(x):
    """Aumento de datos en GPU. Imágenes cenitales => invariancia a rotación/espejo."""
    n = x.shape[0]
    k = np.random.randint(4)
    x = torch.rot90(x, k, dims=(2, 3))
    if np.random.rand() < 0.5:
        x = torch.flip(x, dims=(3,))
    # rotación/traslación leve por muestra (affine)
    ang = (torch.rand(n, device=x.device) - 0.5) * (np.pi / 6)
    tx = (torch.rand(n, 2, device=x.device) - 0.5) * 0.15
    cos, sin = torch.cos(ang), torch.sin(ang)
    theta = torch.stack([torch.stack([cos, -sin, tx[:, 0]], 1),
                         torch.stack([sin, cos, tx[:, 1]], 1)], 1)
    grid = F.affine_grid(theta, x.shape, align_corners=False)
    x = F.grid_sample(x, grid, padding_mode="reflection", align_corners=False)
    # brillo / contraste / ruido (condiciones atmosféricas y de sensor del dron)
    b = (torch.rand(n, 1, 1, 1, device=x.device) - 0.5) * 0.6
    c = 1 + (torch.rand(n, 1, 1, 1, device=x.device) - 0.5) * 0.4
    x = x * c + b
    x = x + torch.randn_like(x) * 0.05
    return x


def train_model(Xtr, ytr, Xva=None, yva=None, width=1.0, dropout=0.3, lr=3e-3, wd=5e-4,
                epochs=30, batch=128, aug=True, smoothing=0.05, seed=0, verbose=False):
    torch.manual_seed(seed); np.random.seed(seed)
    model = ShipNetLite(width, dropout).to(DEVICE)
    xt = to_tensor(Xtr).to(DEVICE); yt = torch.from_numpy(ytr).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    steps = int(np.ceil(len(xt) / batch))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=epochs * steps)
    crit = nn.CrossEntropyLoss(label_smoothing=smoothing)
    hist = []
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(xt), device=DEVICE)
        tl = 0.0
        for i in range(steps):
            idx = perm[i * batch:(i + 1) * batch]
            xb, yb = xt[idx], yt[idx]
            if aug:
                xb = augment(xb)
            loss = crit(model(xb), yb)
            opt.zero_grad(set_to_none=True); loss.backward(); opt.step(); sched.step()
            tl += loss.item() * len(idx)
        rec = {"epoch": ep + 1, "train_loss": tl / len(xt)}
        if Xva is not None:
            p = predict_proba(model, Xva, tta=False)
            rec["val_acc"] = float(((p > 0.5).astype(int) == yva).mean())
        hist.append(rec)
        if verbose:
            print(rec)
    model.eval()
    return model, hist


@torch.no_grad()
def predict_proba(model, X, tta=False, batch=512, device=None):
    """Probabilidad de 'barco'. TTA = promedio sobre las 8 transformaciones diedrales."""
    device = device or next(model.parameters()).device
    model.eval()
    out = []
    for i in range(0, len(X), batch):
        xb = to_tensor(X[i:i + batch]).to(device)
        if tta:
            ps = []
            for k in range(4):
                for fl in (False, True):
                    v = torch.rot90(xb, k, dims=(2, 3))
                    if fl:
                        v = torch.flip(v, dims=(3,))
                    ps.append(F.softmax(model(v), 1)[:, 1])
            out.append(torch.stack(ps).mean(0).cpu())
        else:
            out.append(F.softmax(model(xb), 1)[:, 1].cpu())
    return torch.cat(out).numpy()


class Ensemble:
    """Ensamble de k CNN (modelos de los k pliegues)."""
    def __init__(self, models):
        self.models = models

    def predict_proba(self, X, tta=False):
        return np.mean([predict_proba(m, X, tta=tta) for m in self.models], axis=0)


def count_params(model):
    return sum(p.numel() for p in model.parameters())


def count_flops(model, size=80):
    """MACs de convoluciones y lineales (1 imagen)."""
    macs = [0]

    def hook(m, i, o):
        if isinstance(m, nn.Conv2d):
            macs[0] += o.numel() * (m.in_channels // m.groups) * m.kernel_size[0] * m.kernel_size[1]
        elif isinstance(m, nn.Linear):
            macs[0] += m.in_features * m.out_features
    hs = [m.register_forward_hook(hook) for m in model.modules() if isinstance(m, (nn.Conv2d, nn.Linear))]
    with torch.no_grad():
        model(torch.zeros(1, 3, size, size, device=next(model.parameters()).device))
    for h in hs:
        h.remove()
    return macs[0]


def cpu_latency_ms(model, n=200, threads=1, tta=False):
    """Latencia por imagen en CPU con 1 hilo (aproxima un computador embarcado tipo Jetson/RPi)."""
    m = copy.deepcopy(model).cpu().eval()
    old = torch.get_num_threads(); torch.set_num_threads(threads)
    x = np.random.randint(0, 255, (1, 80, 80, 3), dtype=np.uint8)
    for _ in range(10):
        predict_proba(m, x, tta=tta, device=torch.device("cpu"))
    t = time.perf_counter()
    for _ in range(n):
        predict_proba(m, x, tta=tta, device=torch.device("cpu"))
    dt = (time.perf_counter() - t) / n * 1000
    torch.set_num_threads(old)
    return dt


def save_models(models, path, extra=None):
    torch.save({"cfg": models[0].cfg, "states": [m.state_dict() for m in models],
                "extra": extra or {}}, path)


def load_models(path, device=None):
    device = device or DEVICE
    ck = torch.load(path, map_location=device, weights_only=False)
    ms = []
    for s in ck["states"]:
        m = ShipNetLite(**ck["cfg"]).to(device)
        m.load_state_dict(s); m.eval(); ms.append(m)
    return Ensemble(ms), ck.get("extra", {})
