"""UI de evaluación en vivo - Detector de barcos para UAV (Proyecto 2, IA UMNG).

Flujo el día de la prueba:
  1. "Abrir carpeta de test"  -> carga todas las imágenes (cualquier tamaño/formato; se llevan a 80x80).
  2. Inferencia inmediata con el modelo seleccionado (CNN ensamble + TTA por defecto).
  3. Etiquetado en vivo: botones o teclas  B / 1 = barco,  N / 0 = no barco,  <- -> navegar.
     (Opcional: ocultar la predicción hasta etiquetar para no sesgar al etiquetador.)
  4. Las métricas se recalculan en tiempo real: accuracy, precisión, recall, F1, especificidad,
     IC 95 % (Wilson), matriz de confusión, curva de accuracy acumulado vs. banda de validación cruzada.
  5. "Exportar reporte" guarda CSV por imagen + JSON de métricas + PNG del tablero.

Ejecutar:  python app.py
"""
import os
import sys
import csv
import json
import math
import time
import threading
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
from PIL import Image, ImageTk, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from common import load_image, label_from_name, IMG_EXT, RESULTS_DIR, ROOT  # noqa: E402
from predictor import Predictor, MODEL_CHOICES  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("TkAgg")
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402

C_OK, C_BAD, C_SHIP, C_SEA = "#1a7f37", "#c62828", "#0b5cad", "#5f6b7a"
POS_NAMES = {"1", "ship", "ships", "barco", "barcos", "positivo", "pos"}
NEG_NAMES = {"0", "no_ship", "noship", "no-ship", "no_barco", "nobarco", "no barco", "negativo", "neg"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


def penalty(acc):
    """Penalización del enunciado: 0.5 por cada 2 % por debajo de 98 %."""
    return 0.5 * math.ceil(round((0.98 - acc) * 100, 6) / 2) if acc < 0.98 else 0.0


def load_cv_reference():
    """Resultados de validación cruzada (para contraste en vivo)."""
    ref = {}
    try:
        with open(os.path.join(RESULTS_DIR, "cnn.json"), encoding="utf-8") as f:
            ref["cnn"] = json.load(f)["final_cv_metrics"]
    except Exception:
        pass
    try:
        with open(os.path.join(RESULTS_DIR, "classic.json"), encoding="utf-8") as f:
            ref["svm"] = json.load(f)["best_classic"]["cv"]
    except Exception:
        pass
    return ref


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("UAV Ship Detector · Evaluación en vivo — Proyecto 2 IA (UMNG)")
        self.geometry("1500x900")
        self.minsize(1280, 800)
        self.configure(bg="#eef2f6")
        self.files, self.X, self.proba = [], None, None
        self.truth = []           # etiqueta real (None si no etiquetada)
        self.order = []           # orden de etiquetado (para curva acumulada)
        self.idx = 0
        self.folder = ""
        self.predictor = None
        self.cv_ref = load_cv_reference()
        self.autoplay = False
        self._visible = set()
        self._style()
        self._build()
        self._bind_keys()
        self.after(100, lambda: self.load_model(self.model_var.get()))

    # ------------------------------------------------------------------ UI
    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("TFrame", background="#eef2f6")
        s.configure("Card.TFrame", background="white")
        s.configure("TLabel", background="#eef2f6", font=("Segoe UI", 10))
        s.configure("Card.TLabel", background="white", font=("Segoe UI", 10))
        s.configure("H.TLabel", background="white", font=("Segoe UI", 11, "bold"))
        s.configure("Big.TLabel", background="white", font=("Segoe UI", 30, "bold"))
        s.configure("Metric.TLabel", background="white", font=("Segoe UI", 15, "bold"))
        s.configure("Small.TLabel", background="white", foreground="#5f6b7a", font=("Segoe UI", 9))
        s.configure("TButton", font=("Segoe UI", 10), padding=6)
        s.configure("Ship.TButton", font=("Segoe UI", 13, "bold"), padding=10, foreground="white", background=C_SHIP)
        s.map("Ship.TButton", background=[("active", "#0a4a8c")])
        s.configure("Sea.TButton", font=("Segoe UI", 13, "bold"), padding=10, foreground="white", background=C_SEA)
        s.map("Sea.TButton", background=[("active", "#46505c")])
        s.configure("Treeview", font=("Consolas", 9), rowheight=20)
        # workaround Tk 8.6: permitir colores por etiqueta en filas del Treeview
        s.map("Treeview", background=[("selected", "#0b5cad")], foreground=[("selected", "white")])

    def _build(self):
        # ---- barra superior
        top = ttk.Frame(self, padding=(10, 8))
        top.pack(fill="x")
        ttk.Button(top, text="📂 Abrir carpeta de test", command=self.open_folder).pack(side="left")
        ttk.Label(top, text="  Modelo:").pack(side="left")
        self.model_var = tk.StringVar(value=list(MODEL_CHOICES)[0])
        cb = ttk.Combobox(top, textvariable=self.model_var, values=list(MODEL_CHOICES), width=32, state="readonly")
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.load_model(self.model_var.get()))
        self.tta_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="TTA (8 rot./espejos)", variable=self.tta_var, command=self.run_inference).pack(side="left", padx=8)
        ttk.Label(top, text="Umbral:").pack(side="left")
        self.thr_var = tk.DoubleVar(value=0.5)
        self.thr_lbl = ttk.Label(top, text="0.50", width=4)
        ttk.Scale(top, from_=0.05, to=0.95, variable=self.thr_var, length=110,
                  command=lambda v: (self.thr_lbl.config(text=f"{float(v):.2f}"), self.refresh_all())).pack(side="left")
        self.thr_lbl.pack(side="left")
        self.hide_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Ocultar predicción hasta etiquetar", variable=self.hide_var,
                        command=self.show_current).pack(side="left", padx=8)
        ttk.Button(top, text="💾 Exportar reporte", command=self.export).pack(side="right")
        mb = ttk.Menubutton(top, text="🏷 Etiquetas automáticas")
        m = tk.Menu(mb, tearoff=0)
        m.add_command(label="Desde nombre de archivo (1__ / 0__) o subcarpeta", command=self.labels_from_names)
        m.add_command(label="Desde archivo CSV (archivo,etiqueta)", command=self.labels_from_csv)
        m.add_separator()
        m.add_command(label="▶ Reproducir evaluación (usa etiquetas del CSV/nombre)", command=self.toggle_autoplay)
        m.add_command(label="Borrar todas las etiquetas", command=self.clear_labels)
        mb["menu"] = m
        mb.pack(side="right", padx=6)

        self.status = ttk.Label(self, text="Seleccione la carpeta con las imágenes de test.", padding=(10, 0))
        self.status.pack(fill="x")

        body = ttk.Frame(self, padding=8)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=0)
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)

        # ---- columna 1: visor + etiquetado
        left = ttk.Frame(body, style="Card.TFrame", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ttk.Label(left, text="Imagen actual", style="H.TLabel").pack(anchor="w")
        self.canvas_img = tk.Label(left, bg="#0d1b2a", width=320, height=320)
        self.canvas_img.pack(pady=6)
        self.lbl_name = ttk.Label(left, text="—", style="Small.TLabel", wraplength=330)
        self.lbl_name.pack(anchor="w")
        self.lbl_pred = ttk.Label(left, text="Predicción: —", style="Metric.TLabel")
        self.lbl_pred.pack(anchor="w", pady=(6, 0))
        self.pbar = ttk.Progressbar(left, length=330, maximum=100)
        self.pbar.pack(pady=2)
        self.lbl_truth = ttk.Label(left, text="Etiqueta real: sin etiquetar", style="Card.TLabel")
        self.lbl_truth.pack(anchor="w", pady=(4, 8))
        bf = ttk.Frame(left, style="Card.TFrame")
        bf.pack(fill="x")
        ttk.Button(bf, text="🚢 BARCO  [B/1]", style="Ship.TButton", takefocus=False, command=lambda: self.set_label(1)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(bf, text="🌊 NO BARCO  [N/0]", style="Sea.TButton", takefocus=False, command=lambda: self.set_label(0)).pack(side="left", expand=True, fill="x", padx=2)
        nf = ttk.Frame(left, style="Card.TFrame")
        nf.pack(fill="x", pady=6)
        ttk.Button(nf, text="◀ Anterior", takefocus=False, command=lambda: self.go(-1)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(nf, text="Siguiente sin etiquetar ⏭", takefocus=False, command=self.next_unlabeled).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(nf, text="Siguiente ▶", takefocus=False, command=lambda: self.go(1)).pack(side="left", expand=True, fill="x", padx=2)
        self.lbl_prog = ttk.Label(left, text="0 / 0 etiquetadas", style="Card.TLabel")
        self.lbl_prog.pack(anchor="w")
        ttk.Label(left, text="Teclas: B/1 barco · N/0 no barco · ←/→ navegar · Espacio: aceptar predicción",
                  style="Small.TLabel", wraplength=330).pack(anchor="w", pady=(4, 0))

        # ---- columna 2: lista de imágenes
        mid = ttk.Frame(body, style="Card.TFrame", padding=8)
        mid.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        ttk.Label(mid, text="Imágenes de la carpeta", style="H.TLabel").pack(anchor="w")
        ff = ttk.Frame(mid, style="Card.TFrame")
        ff.pack(fill="x", pady=(2, 4))
        ttk.Label(ff, text="Mostrar:", style="Card.TLabel").pack(side="left")
        self.filter_var = tk.StringVar(value="Todas")
        fcb = ttk.Combobox(ff, textvariable=self.filter_var, state="readonly", width=20,
                           values=["Todas", "Solo errores (✘)", "Real = barco", "Real = no barco", "Sin etiquetar"])
        fcb.pack(side="left", padx=4)
        fcb.bind("<<ComboboxSelected>>", lambda e: (self.apply_filter(), self.focus_set()))
        self.lbl_filter = ttk.Label(ff, text="", style="Small.TLabel")
        self.lbl_filter.pack(side="left", padx=4)
        cols = ("n", "file", "pred", "p", "real", "ok")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=30)
        for c, w, t in zip(cols, (40, 150, 60, 50, 60, 30), ("#", "Archivo", "Pred.", "P(b)", "Real", "")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center" if c != "file" else "w", stretch=False)
        self.tree.tag_configure("ok", background="#e3f4e6")
        self.tree.tag_configure("bad", background="#fbe0e0")
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # ---- columna 3: métricas en vivo
        right = ttk.Frame(body, style="Card.TFrame", padding=12)
        right.grid(row=0, column=2, sticky="nsew")
        ttk.Label(right, text="Métricas en vivo", style="H.TLabel").pack(anchor="w")
        kf = ttk.Frame(right, style="Card.TFrame")
        kf.pack(fill="x", pady=4)
        self.kpi = {}
        for i, (k, t) in enumerate([("acc", "Accuracy"), ("prec", "Precisión"), ("rec", "Recall"),
                                    ("f1", "F1"), ("spec", "Especificidad"), ("n", "N etiquetadas")]):
            fr = ttk.Frame(kf, style="Card.TFrame", padding=(6, 2))
            fr.grid(row=0, column=i, sticky="w", padx=4)
            ttk.Label(fr, text=t, style="Small.TLabel").pack(anchor="w")
            lab = ttk.Label(fr, text="—", style="Big.TLabel" if k == "acc" else "Metric.TLabel")
            lab.pack(anchor="w")
            self.kpi[k] = lab
        self.lbl_goal = ttk.Label(right, text="", style="Card.TLabel", font=("Segoe UI", 11, "bold"))
        self.lbl_goal.pack(anchor="w")
        self.lbl_cv = ttk.Label(right, text="", style="Small.TLabel", wraplength=700, justify="left")
        self.lbl_cv.pack(anchor="w", pady=(2, 4))
        self.fig = Figure(figsize=(8, 5.6), dpi=90, facecolor="white")
        self.ax_cm = self.fig.add_subplot(2, 2, 1)
        self.ax_bar = self.fig.add_subplot(2, 2, 2)
        self.ax_curve = self.fig.add_subplot(2, 1, 2)
        self.fig.subplots_adjust(hspace=0.45, wspace=0.35, left=0.08, right=0.97, top=0.93, bottom=0.1)
        self.mpl = FigureCanvasTkAgg(self.fig, master=right)
        self.mpl.get_tk_widget().pack(fill="both", expand=True)
        self.refresh_metrics()

    def _bind_keys(self):
        for k in ("b", "B", "1", "<KP_1>"):
            self.bind(k if k.startswith("<") else k, lambda e: self.set_label(1))
        for k in ("n", "N", "0", "<KP_0>"):
            self.bind(k if k.startswith("<") else k, lambda e: self.set_label(0))
        self.bind("<Left>", lambda e: self.go(-1))
        self.bind("<Right>", lambda e: self.go(1))
        self.bind("<space>", lambda e: (self.accept_pred(), "break")[1])
        # tras un clic, devolver el foco a la ventana para que las teclas no activen otro widget
        self.bind_all("<ButtonRelease-1>", lambda e: self.after(1, self.focus_set)
                      if isinstance(e.widget, ttk.Button) else None, add="+")

    # ------------------------------------------------------------------ modelo / datos
    def load_model(self, choice):
        self.status.config(text=f"Cargando modelo: {choice} ...")
        self.update_idletasks()
        try:
            t = time.time()
            self.predictor = Predictor(choice)
            self.status.config(text=f"Modelo listo: {choice}  ({time.time() - t:.1f} s)")
        except Exception as ex:
            messagebox.showerror("Modelo", f"No se pudo cargar {choice}:\n{ex}")
            return
        self.run_inference()

    def open_folder(self):
        d = filedialog.askdirectory(title="Carpeta con imágenes de test",
                                    initialdir=os.path.join(ROOT, "test_ciego") if os.path.isdir(os.path.join(ROOT, "test_ciego")) else ROOT)
        if d:
            self.load_folder(d)

    def load_folder(self, d):
        d = os.path.abspath(d)
        paths = []
        for r, _, fs in os.walk(d):
            paths += [os.path.join(r, f) for f in sorted(fs) if f.lower().endswith(IMG_EXT)]
        if not paths:
            messagebox.showwarning("Carpeta", "No se encontraron imágenes.")
            return
        self.folder = d
        self.files = paths
        self.status.config(text=f"Cargando {len(paths)} imágenes ...")
        self.update_idletasks()
        imgs = []
        for p in paths:
            try:
                imgs.append(load_image(p))
            except Exception:
                imgs.append(np.zeros((80, 80, 3), np.uint8))
        self.X = np.stack(imgs)
        self.truth = [None] * len(paths)
        self.order = []
        self.idx = 0
        self.run_inference()

    def run_inference(self):
        if self.X is None or self.predictor is None:
            return
        t = time.perf_counter()
        self.proba = self.predictor.predict_proba(self.X, tta=self.tta_var.get())
        dt = (time.perf_counter() - t) * 1000
        self.status.config(text=f"{self.folder}  ·  {len(self.files)} imágenes  ·  inferencia {self.predictor.name}"
                                f"{' + TTA' if self.tta_var.get() and self.predictor.kind == 'cnn' else ''}: "
                                f"{dt:.0f} ms total ({dt / len(self.files):.2f} ms/img)")
        self.fill_tree()
        self.refresh_all()

    # ------------------------------------------------------------------ etiquetado
    def pred(self, i):
        return int(self.proba[i] >= self.thr_var.get())

    def set_label(self, lab, i=None, advance=True):
        if not self.files:
            return
        i = self.idx if i is None else i
        if self.truth[i] is None:
            self.order.append(i)
        self.truth[i] = lab
        self.update_row(i)
        if advance and i == self.idx:
            if any(t is None for t in self.truth):
                self.next_unlabeled(refresh=False)
            else:
                self.go(1, refresh=False)
        self.refresh_all()

    def accept_pred(self):
        if self.files:
            self.set_label(self.pred(self.idx))

    def clear_labels(self):
        self.truth = [None] * len(self.files)
        self.order = []
        self.fill_tree()
        self.refresh_all()

    def auto_labels(self):
        out = []
        for p in self.files:
            lab = label_from_name(p)
            if lab is None:
                parent = os.path.basename(os.path.dirname(p)).strip().lower()
                lab = 1 if parent in POS_NAMES else 0 if parent in NEG_NAMES else None
            out.append(lab)
        return out

    def labels_from_names(self):
        labs = self.auto_labels()
        n = sum(l is not None for l in labs)
        if n == 0:
            messagebox.showinfo("Etiquetas", "Los nombres/subcarpetas no contienen etiquetas (1__/0__, ship/no_ship).")
            return
        self.truth = labs
        self.order = [i for i, l in enumerate(labs) if l is not None]
        self.fill_tree(); self.refresh_all()
        self.status.config(text=f"{n} etiquetas tomadas de nombres/subcarpetas.")

    def labels_from_csv(self):
        f = filedialog.askopenfilename(title="CSV de etiquetas (archivo,etiqueta)", filetypes=[("CSV", "*.csv")],
                                       initialdir=self.folder or ROOT)
        if f:
            self.load_csv_labels(f)

    def load_csv_labels(self, f):
        m = {}
        with open(f, encoding="utf-8-sig") as fh:
            for row in csv.reader(fh):
                if len(row) >= 2 and row[1].strip() in ("0", "1"):
                    m[os.path.basename(row[0].strip())] = int(row[1])
        labs = [m.get(os.path.basename(p)) for p in self.files]
        self.truth = labs
        self.order = [i for i, l in enumerate(labs) if l is not None]
        self.fill_tree(); self.refresh_all()
        self.status.config(text=f"{sum(l is not None for l in labs)} etiquetas cargadas de {os.path.basename(f)}.")

    def toggle_autoplay(self):
        """Simula el etiquetado en vivo imagen por imagen usando etiquetas conocidas (demo)."""
        if not self.files:
            return
        if self.autoplay:
            self.autoplay = False
            return
        labs = [l if l is not None else a for l, a in zip(self.truth, self.auto_labels())]
        if all(l is None for l in labs):
            messagebox.showinfo("Reproducir", "Cargue primero un CSV o use una carpeta con nombres etiquetados.")
            return
        self.play_labels = labs
        self.truth = [None] * len(self.files); self.order = []
        self.fill_tree()
        self.autoplay = True
        self.play_i = 0
        self._play_step()

    def _play_step(self):
        if not self.autoplay:
            return
        while self.play_i < len(self.files) and self.play_labels[self.play_i] is None:
            self.play_i += 1
        if self.play_i >= len(self.files):
            self.autoplay = False
            return
        i = self.play_i
        self.truth[i] = self.play_labels[i]
        self.order.append(i)
        self.idx = i
        self.play_i += 1
        self.update_row(i)
        self.show_current(); self.sync_tree(); self.refresh_metrics()
        self.after(40, self._play_step)

    # ------------------------------------------------------------------ navegación
    def go(self, d, refresh=True):
        if not self.files:
            return
        vis = self.visible_rows()
        if not vis:
            return
        k = int(np.clip(vis.index(self.idx) + d, 0, len(vis) - 1)) if self.idx in vis else 0
        self.idx = vis[k]
        if refresh:
            self.show_current(); self.sync_tree()

    def next_unlabeled(self, refresh=True):
        n = len(self.files)
        for k in range(1, n + 1):
            j = (self.idx + k) % n
            if self.truth[j] is None:
                self.idx = j
                break
        if refresh:
            self.show_current(); self.sync_tree()

    def on_select(self, _):
        sel = self.tree.selection()
        if sel:
            self.idx = int(sel[0])
            self.show_current()

    def sync_tree(self):
        if self.files and self.idx in self._visible:
            iid = str(self.idx)
            self.tree.selection_set(iid)
            self.tree.see(iid)

    # ------------------------------------------------------------------ tabla
    def row_values(self, i):
        pr = self.pred(i)
        t = self.truth[i]
        ok = "" if t is None else ("✔" if t == pr else "✘")
        return (i + 1, os.path.basename(self.files[i])[:24], "barco" if pr else "no",
                f"{self.proba[i]:.2f}", "—" if t is None else ("barco" if t else "no"), ok), \
            () if t is None else (("ok",) if t == pr else ("bad",))

    def row_visible(self, i):
        f = self.filter_var.get()
        t = self.truth[i]
        if f.startswith("Solo errores"):
            return t is not None and t != self.pred(i)
        if f.startswith("Real = barco"):
            return t == 1
        if f.startswith("Real = no barco"):
            return t == 0
        if f.startswith("Sin etiquetar"):
            return t is None
        return True

    def visible_rows(self):
        return [i for i in range(len(self.files)) if i in self._visible]

    def fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i in range(len(self.files)):
            v, tag = self.row_values(i)
            self.tree.insert("", "end", iid=str(i), values=v, tags=tag)
        self.apply_filter()

    def apply_filter(self, *_):
        if not self.files:
            return
        pos = 0
        self._visible = set()
        for i in range(len(self.files)):
            if self.row_visible(i):
                self.tree.reattach(str(i), "", pos)
                pos += 1
                self._visible.add(i)
            else:
                self.tree.detach(str(i))
        self.lbl_filter.config(text=f"{pos} de {len(self.files)} filas")
        if self._visible and self.idx not in self._visible:
            self.idx = min(self._visible)
        self.show_current()
        self.sync_tree()

    def update_row(self, i):
        v, tag = self.row_values(i)
        self.tree.item(str(i), values=v, tags=tag)

    # ------------------------------------------------------------------ refresco
    def refresh_all(self):
        if self.files and self.proba is not None:
            for i in range(len(self.files)):
                self.update_row(i)
        self.show_current()
        self.sync_tree()
        self.refresh_metrics()

    def show_current(self):
        if not self.files or self.proba is None:
            return
        i = self.idx
        img = Image.fromarray(self.X[i]).resize((320, 320), Image.NEAREST)
        pr, p, t = self.pred(i), float(self.proba[i]), self.truth[i]
        hide = self.hide_var.get() and t is None
        d = ImageDraw.Draw(img)
        if not hide:
            col = (26, 127, 55) if t is None or t == pr else (198, 40, 40)
            d.rectangle([2, 2, 317, 317], outline=col, width=4)
            d.rectangle([6, 6, 180, 26], fill=(0, 0, 0))
            d.text((10, 10), f"PRED: {'BARCO' if pr else 'NO BARCO'} ({p:.2f})", fill=(255, 255, 255))
        if t is not None:
            d.rectangle([6, 292, 180, 312], fill=(11, 92, 173) if t else (95, 107, 122))
            d.text((10, 296), f"REAL: {'BARCO' if t else 'NO BARCO'}", fill=(255, 255, 255))
        self.tkimg = ImageTk.PhotoImage(img)
        self.canvas_img.config(image=self.tkimg)
        self.lbl_name.config(text=f"[{i + 1}/{len(self.files)}] {os.path.relpath(self.files[i], self.folder)}")
        if hide:
            self.lbl_pred.config(text="Predicción: (oculta)", foreground="#5f6b7a")
            self.pbar["value"] = 0
        else:
            self.lbl_pred.config(text=f"Predicción: {'🚢 BARCO' if pr else '🌊 NO BARCO'}   P(barco)={p:.3f}",
                                 foreground=C_SHIP if pr else C_SEA)
            self.pbar["value"] = p * 100
        if t is None:
            self.lbl_truth.config(text="Etiqueta real: sin etiquetar", foreground="#5f6b7a")
        else:
            self.lbl_truth.config(text=f"Etiqueta real: {'BARCO' if t else 'NO BARCO'}  →  "
                                       f"{'ACIERTO ✔' if t == pr else 'ERROR ✘'}",
                                  foreground=C_OK if t == pr else C_BAD)
        n = sum(x is not None for x in self.truth)
        self.lbl_prog.config(text=f"{n} / {len(self.files)} etiquetadas")

    def compute(self):
        idx = [i for i in self.order if self.truth[i] is not None]
        if not idx:
            return None
        y = np.array([self.truth[i] for i in idx])
        yh = np.array([self.pred(i) for i in idx])
        tp = int(((y == 1) & (yh == 1)).sum()); tn = int(((y == 0) & (yh == 0)).sum())
        fp = int(((y == 0) & (yh == 1)).sum()); fn = int(((y == 1) & (yh == 0)).sum())
        n = len(y)
        acc = (tp + tn) / n
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / (tp + fn) if tp + fn else float("nan")
        f1 = 2 * prec * rec / (prec + rec) if tp and (prec + rec) else (0.0 if tp + fp + fn else float("nan"))
        spec = tn / (tn + fp) if tn + fp else float("nan")
        curve = np.cumsum(y == yh) / np.arange(1, n + 1)
        return dict(n=n, tp=tp, tn=tn, fp=fp, fn=fn, acc=acc, prec=prec, rec=rec, f1=f1, spec=spec,
                    ci=wilson(tp + tn, n), curve=curve)

    def cv_key(self):
        if self.predictor is None:
            return None
        return "cnn" if self.predictor.kind == "cnn" else "svm"

    def refresh_metrics(self):
        M = self.compute()
        fmt = lambda v: "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v * 100:.2f}%"
        for ax in (self.ax_cm, self.ax_bar, self.ax_curve):
            ax.clear()
        ref = self.cv_ref.get(self.cv_key() or "", {})
        if M is None:
            for k in self.kpi:
                self.kpi[k].config(text="—", foreground="black")
            self.lbl_goal.config(text="Meta: accuracy > 98 % en test ciego")
        else:
            self.kpi["acc"].config(text=fmt(M["acc"]), foreground=C_OK if M["acc"] > 0.98 else C_BAD)
            self.kpi["prec"].config(text=fmt(M["prec"]))
            self.kpi["rec"].config(text=fmt(M["rec"]))
            self.kpi["f1"].config(text=fmt(M["f1"]))
            self.kpi["spec"].config(text=fmt(M["spec"]))
            self.kpi["n"].config(text=str(M["n"]))
            pen = penalty(M["acc"])
            self.lbl_goal.config(
                text=(f"IC95% (Wilson): [{M['ci'][0] * 100:.1f}%, {M['ci'][1] * 100:.1f}%]   ·   "
                      + ("META > 98 %: CUMPLE ✔ (sin penalización)" if M["acc"] > 0.98
                         else f"Debajo de 98 % → penalización estimada: −{pen:.1f}")),
                foreground=C_OK if M["acc"] > 0.98 else C_BAD)
        if ref:
            txt = "Validación cruzada 5-fold (desarrollo): " + "  ·  ".join(
                f"{n} {ref[k][0] * 100:.2f}±{ref[k][1] * 100:.2f}%" for k, n in
                (("accuracy", "Acc"), ("precision", "Prec"), ("recall", "Rec"), ("f1", "F1")) if k in ref)
            if M is not None and "accuracy" in ref:
                d = (M["acc"] - ref["accuracy"][0]) * 100
                inside = M["ci"][0] <= ref["accuracy"][0] <= M["ci"][1]
                txt += (f"\nContraste en vivo vs CV: Δacc = {d:+.2f} pp  →  "
                        + ("consistente: la media de CV cae dentro del IC95 % del test (generaliza)."
                           if inside else ("el test supera la CV." if d > 0 else "posible cambio de dominio en el test.")))
            self.lbl_cv.config(text=txt)

        # matriz de confusión
        cm = np.array([[M["tn"], M["fp"]], [M["fn"], M["tp"]]]) if M else np.zeros((2, 2), int)
        self.ax_cm.imshow(cm, cmap="Blues", vmin=0, vmax=max(1, cm.max()))
        for (r, c), v in np.ndenumerate(cm):
            self.ax_cm.text(c, r, str(v), ha="center", va="center", fontsize=14, fontweight="bold",
                            color="white" if v > cm.max() / 2 and v > 0 else "#1f2d3d")
        self.ax_cm.set_xticks([0, 1]); self.ax_cm.set_xticklabels(["no barco", "barco"])
        self.ax_cm.set_yticks([0, 1]); self.ax_cm.set_yticklabels(["no barco", "barco"])
        self.ax_cm.set_xlabel("Predicción"); self.ax_cm.set_ylabel("Real")
        self.ax_cm.set_title("Matriz de confusión (en vivo)", fontsize=10)

        # barras vivo vs CV
        names = ["Acc", "Prec", "Rec", "F1"]
        keys = ["accuracy", "precision", "recall", "f1"]
        live = [M[k] if M else 0 for k in ("acc", "prec", "rec", "f1")]
        live = [0 if (isinstance(v, float) and math.isnan(v)) else v for v in live]
        xs = np.arange(4)
        self.ax_bar.bar(xs - 0.2, [v * 100 for v in live], 0.4, label="En vivo", color="#0b5cad")
        if ref:
            self.ax_bar.bar(xs + 0.2, [ref[k][0] * 100 for k in keys], 0.4,
                            yerr=[ref[k][1] * 100 for k in keys], capsize=3, label="CV 5-fold", color="#9bb7d4")
        self.ax_bar.axhline(98, color=C_BAD, ls="--", lw=1)
        self.ax_bar.set_xticks(xs); self.ax_bar.set_xticklabels(names)
        self.ax_bar.set_ylim(85, 100.5); self.ax_bar.set_title("En vivo vs. validación cruzada (%)", fontsize=10)
        self.ax_bar.legend(fontsize=8, loc="lower right")

        # curva acumulada
        if M:
            n = np.arange(1, M["n"] + 1)
            self.ax_curve.plot(n, M["curve"] * 100, color="#0b5cad", lw=2, label="Accuracy acumulado (en vivo)")
        if ref and "accuracy" in ref:
            m, s = ref["accuracy"][0] * 100, ref["accuracy"][1] * 100
            xmax = max(10, M["n"] if M else 10)
            self.ax_curve.axhspan(m - s, m + s, color="#9bb7d4", alpha=0.4, label=f"CV media ± std ({m:.2f}%)")
            self.ax_curve.set_xlim(1, xmax)
        self.ax_curve.axhline(98, color=C_BAD, ls="--", lw=1, label="Meta 98 %")
        self.ax_curve.set_ylim(80, 100.5)
        self.ax_curve.set_xlabel("Imágenes etiquetadas"); self.ax_curve.set_ylabel("Accuracy (%)")
        self.ax_curve.set_title("Evolución del accuracy en tiempo real", fontsize=10)
        self.ax_curve.legend(fontsize=8, loc="lower right")
        self.ax_curve.grid(alpha=0.3)
        self.mpl.draw_idle()

    # ------------------------------------------------------------------ exportar
    def export(self):
        if not self.files:
            return
        M = self.compute()
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(ROOT, "reportes", f"evaluacion_{stamp}")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "predicciones.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["archivo", "p_barco", "prediccion", "etiqueta_real", "correcto"])
            for i, p in enumerate(self.files):
                t = self.truth[i]
                w.writerow([os.path.relpath(p, self.folder), f"{self.proba[i]:.4f}", self.pred(i),
                            "" if t is None else t, "" if t is None else int(t == self.pred(i))])
        summ = {"fecha": stamp, "carpeta": self.folder, "modelo": self.predictor.name,
                "tta": self.tta_var.get(), "umbral": self.thr_var.get(), "n_imagenes": len(self.files)}
        if M:
            summ.update({k: M[k] for k in ("n", "tp", "tn", "fp", "fn", "acc", "prec", "rec", "f1", "spec")})
            summ["ic95"] = M["ci"]; summ["penalizacion"] = penalty(M["acc"])
        summ["cv_referencia"] = self.cv_ref.get(self.cv_key(), {})
        with open(os.path.join(out, "metricas.json"), "w", encoding="utf-8") as f:
            json.dump(summ, f, indent=2, ensure_ascii=False, default=float)
        self.fig.savefig(os.path.join(out, "tablero.png"), dpi=130)
        try:
            self.lift(); self.attributes("-topmost", True); self.update(); time.sleep(0.4); self.update()
            from PIL import ImageGrab
            full = ImageGrab.grab()
            k = full.size[0] / self.winfo_screenwidth()      # factor de escala de Windows (DPI)
            x, y = self.winfo_rootx() * k, self.winfo_rooty() * k
            full.crop((int(x), int(y), int(x + self.winfo_width() * k), int(y + self.winfo_height() * k))).save(os.path.join(out, "captura_ui.png"))
        except Exception:
            pass
        finally:
            self.attributes("-topmost", False)
        messagebox.showinfo("Reporte", f"Reporte guardado en:\n{out}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="UI de evaluación en vivo")
    ap.add_argument("--carpeta", help="carpeta de imágenes de test a cargar al iniciar")
    ap.add_argument("--etiquetas", help="CSV archivo,etiqueta con las marcas reales")
    ap.add_argument("--modelo", choices=["final", "dev", "svm"], default="final")
    a = ap.parse_args()
    app = App()
    app.model_var.set(list(MODEL_CHOICES)[["final", "dev", "svm"].index(a.modelo)])
    if a.carpeta:
        def _auto():
            if app.predictor is None or app.predictor.name != app.model_var.get():
                app.after(200, _auto)
                return
            app.load_folder(a.carpeta)
            if a.etiquetas:
                app.load_csv_labels(a.etiquetas)
        app.after(300, _auto)
    app.mainloop()
