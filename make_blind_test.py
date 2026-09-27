"""Genera la carpeta test_ciego/ con el hold-out (20 %, nunca usado en entrenamiento ni sintonización)
con nombres anonimizados (sin la etiqueta 1__/0__) y la clave en clave_test_ciego.csv.
Sirve para ensayar la prueba en vivo con el modelo 'CNN ensamble (dev, 80%)'."""
import os
import sys
import csv
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from common import load_dataset, dev_test_split, DATA_DIR, ROOT

X, y, files = load_dataset()
_, te = dev_test_split(y)
out = os.path.join(ROOT, "test_ciego")
shutil.rmtree(out, ignore_errors=True)
os.makedirs(out)
rows = []
for k, i in enumerate(te):
    name = f"img_{k + 1:04d}.png"
    shutil.copy(os.path.join(DATA_DIR, files[i]), os.path.join(out, name))
    rows.append((name, int(y[i])))
with open(os.path.join(ROOT, "clave_test_ciego.csv"), "w", newline="") as f:
    csv.writer(f).writerows([("archivo", "etiqueta")] + rows)
print(len(rows), "imágenes en", out, "| barcos:", sum(r[1] for r in rows))
