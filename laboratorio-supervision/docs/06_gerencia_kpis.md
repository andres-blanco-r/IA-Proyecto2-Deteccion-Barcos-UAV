# 6. Modelo de negocio y KPI (panel de gerencia)

> La guía exige que los datos de ingresos, materias primas y KPI **los proponga cada grupo y sean distintos**
> entre grupos. Los valores de abajo son un ejemplo coherente: **cámbielos** en `DB_Param.Costos`
> (o desde el panel de gerencia) antes de presentar.

## 6.1 Datos del proceso (por lote)

| Concepto | Valor de ejemplo | Parámetro |
|---|---|---|
| Producto | Vaso de yogur de 200 mL | — |
| Tamaño del lote | 20 L de leche → 100 vasos | `UnidadesPorLote`, `Leche_L_Lote` |
| Leche | 3 200 COP/L | `Precio_Leche_L` |
| Cultivo láctico liofilizado | 5 g/lote a 3 000 COP/g | `Cultivo_g_Lote`, `Precio_Cultivo_g` |
| Azúcar | 1,6 kg/lote (8 %) a 4 500 COP/kg | `Azucar_kg_Lote`, `Precio_Azucar_kg` |
| Envase con tapa | 350 COP/und | `Precio_Envase` |
| Calefactor equivalente a escala industrial | 3 kW (energía = tiempo ON × 3 kW) | `Potencia_Planta_kW` |
| Energía | 950 COP/kWh (tarifa comercial de referencia en Bogotá) | `Precio_kWh` |
| Costo de una hora de parada | 85 000 COP/h (mano de obra + costos fijos) | `CostoHoraParada` |
| Precio de venta | 3 800 COP/vaso | `Precio_Venta_Und` |
| Tiempo de ciclo ideal | 300 s por lote (lote de demostración) | `T_CicloIdeal_s` |
| Demanda simulada | 1 pedido cada 60 s de 1 a 40 vasos | `T_EntrePedidos_s`, `PedidoMax` |

Costo variable de un lote: 20 × 3 200 + 5 × 3 000 + 1,6 × 4 500 + 100 × 350 = **121 200 COP**
(1 212 COP/vaso + energía). Ingreso de un lote vendido completo: 380 000 COP.

## 6.2 Lo que mide el PLC (`FB_Produccion`)

* **Turno:** empieza con el primer Start y termina con *Reiniciar turno*.
* **Tiempo muerto:** tiempo del turno con el proceso PARADO, en EMERGENCIA o en FALLA.
* **Lote:** corre solo EN CONSIGNA. Al cumplir `T_Lote_s` se cuenta; si estuvo más de `MaxFueraTol_s`
  (60 s) con |e| > 2 °C se **rechaza**: no suma unidades ni inventario, pero sí consume materiales.
* **Ventas:** pedidos automáticos y ventas manuales, limitados por el inventario.

## 6.3 KPI (la guía pide al menos 3; hay 6)

| KPI | Fórmula | Por qué importa en este proceso |
|---|---|---|
| **OEE** | D × R × C | Indicador global de la eficacia de la línea |
| Disponibilidad D | (T turno − T muerto) / T turno | Penaliza paradas y emergencias |
| Rendimiento R | min(1, lotes × T ciclo ideal / T operando) | Penaliza el calentamiento y las reentradas a CALENTANDO |
| Calidad C | lotes buenos / lotes | Une el control con el negocio: un mal control rechaza lotes |
| **Margen sobre ventas** | (ingresos − materiales − energía − paradas) / ingresos | Rentabilidad del turno |
| **Costo unitario** | (materiales + energía) / unidades buenas | Sube cuando hay rechazos |
| **Energía específica** | kWh / unidad buena | Eficiencia energética (sube con la tapa abierta o una mala histéresis) |

**Ejemplo con el gemelo** (3 h de turno con una emergencia de 8 min, ver la maqueta de gerencia): OEE ≈ 81 %
(D 95,5 % × R 84,4 % × C 100 %), margen ≈ 68 %, costo unitario ≈ 1 214 COP/vaso.

El experimento sobre el SP del panel de supervisor muestra el vínculo entre el control y el negocio: con un
cambio de SP de 43 a 47 °C en plena fermentación (|e| = 4 °C, justo en la banda de reinicio) el proceso sigue
EN CONSIGNA pero fuera de tolerancia más de 60 s, y ese lote se rechaza (Calidad < 100 %).
