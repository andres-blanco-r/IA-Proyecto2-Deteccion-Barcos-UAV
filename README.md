# Detector de barcos para UAV — Proyecto 2 IA (UMNG, 2026-2)

**Andrés Felipe Blanco Romero · 7004096** · Repositorio: https://github.com/andres-blanco-r/IA-Proyecto2-Deteccion-Barcos-UAV

Clasificador binario *barco / no barco* sobre imágenes satelitales 80×80 RGB (ShipsNet, Kaggle) para el
sistema de percepción de un dron de inspección portuaria (caso Rotterdam), con UI de evaluación en vivo.

## Resultados (hold-out ciego simulado, n = 800, nunca usado para entrenar ni sintonizar)

| Modelo | CV 5-fold | Hold-out |
|---|---|---|
| Baseline: píxeles + Regresión logística | 91.12 ± 1.00 % | 89.62 % |
| SVM-RBF + HOG + LBP (GridSearchCV) | 99.44 ± 0.21 % | 99.38 % |
| **CNN ShipNet-Lite (w=0.5) ensamble ×5 + TTA** | **99.28 ± 0.08 %** | **99.38 %** (IC95 % 98.55–99.73) |

La CNN con aumento de datos mantiene 99.25 % con rotación arbitraria y 97.25 % con perturbación combinada
(el SVM cae a ~77 % con desenfoque/JPEG) → se despliega la CNN. Latencia CPU 1 hilo: 5.4 ms/img.

## Uso rápido (día de la prueba)

```
pip install -r requirements.txt
python app.py          # o doble clic en EJECUTAR_UI.bat
```

1. **Abrir carpeta de test** (lee subcarpetas; PNG/JPG/TIF/BMP de cualquier tamaño → 80×80).
2. Modelo: **CNN ensamble (final, 4000 img)** + TTA (por defecto).
3. Etiquetar: `B`/`1` barco · `N`/`0` no barco · `Espacio` aceptar predicción · `←/→` navegar.
   Opcional: *Ocultar predicción hasta etiquetar*, o cargar etiquetas desde CSV / nombre / subcarpetas.
4. Métricas en tiempo real: accuracy, precisión, recall, F1, especificidad, IC95 %, matriz de confusión,
   contraste con la validación cruzada, alerta de meta > 98 % y penalización estimada.
5. **Exportar reporte** → `reportes/evaluacion_<fecha>/` (CSV, JSON, PNG, captura).

Ensayo: `python make_blind_test.py` crea `test_ciego/` (hold-out anonimizado) y `clave_test_ciego.csv`;
usar el modelo *CNN ensamble (dev, 80%)* para una evaluación honesta.

## Reproducir los experimentos

| Script | Qué hace |
|---|---|
| `train_classic.py` | baseline, ablación CLAHE × {HOG, HSV, LBP}, sensibilidad HOG, GridSearchCV SVM/RF/LR |
| `train_cnn.py` | rejilla lr × dropout × wd, sensibilidad (ancho/épocas/aumento), Pareto exactitud–latencia, CV final, hold-out, modelo final |
| `robustness.py` | robustez ante perturbaciones del UAV (rotación, brillo, desenfoque, ruido, JPEG) |
| `make_figures.py` | figuras `results/fig_*.png`, McNemar, IC Wilson |
| `scan_scene.py` | detección por ventana deslizante + NMS sobre escenas completas |
| `fill_docx.py` | diligencia el formato ABET con los resultados |

Dataset: descargar *Ships in Satellite Imagery* de Kaggle y extraer en `data/` (`data/shipsnet/shipsnet/*.png`).
