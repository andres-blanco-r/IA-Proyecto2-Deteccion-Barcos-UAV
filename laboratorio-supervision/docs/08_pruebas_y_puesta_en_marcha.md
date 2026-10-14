# 8. Protocolo de pruebas y puesta en marcha

Llene la columna **Resultado** durante la práctica: esas tablas son la evidencia de la sección
"Resultados" del informe. Tome capturas de pantalla y guarde los PDF que genere el gateway.

## 8.1 Pruebas en oficina (sin planta: PLCSIM + gateway simulado)

| # | Prueba | Criterio de aceptación | Resultado |
|---|---|---|---|
| F1 | `python herramientas/verificar_scl.py` | "OK: sin errores" | |
| F2 | Generar bloques desde las fuentes y compilar en TIA Portal | 0 errores | |
| F3 | PLCSIM, `Sim.Activa = TRUE`, Start | Estado 0 → 1, calefactor ON, agitador a 100 % | |
| F4 | Esperar a que llegue al SP (FactorTiempo = 10) | Estado 2, agitador detenido, ON-OFF oscilando | |
| F5 | Cambiar el SP a 50 °C | Estado 1, el agitador vuelve a girar y frena al acercarse | |
| F6 | Paro de emergencia del HMI | Estado 3, calefactor OFF, variador OFF1; Start no hace nada; Rearme → 0 | |
| F7 | Gateway `--simular` + pruebas `pytest` | 12 pruebas pasan | |

## 8.2 Pruebas en el banco (planta real)

| # | Prueba | Criterio de aceptación | Resultado |
|---|---|---|---|
| S1 | Cableado: continuidad, polaridad, sin cortos a 24 V | Medido con multímetro antes de energizar | |
| S2 | Lazo con década: 100,00 / 119,40 / 138,51 Ω | 4,00 / 12,00 / 20,00 mA (±0,1 mA); PV = 0 / 50 / 100 °C (±0,5 °C) | |
| S3 | Abrir el lazo (desconectar la RTD o el transmisor) | Alarma "Falla del sensor", estado 4, calefactor OFF | |
| S4 | Pulsar el hongo físico | Calefactor sin tensión (medido), `DI_ParoEmergencia` = 0, estado 3 | |
| S5 | Puentear el termostato abierto (o calentar el KSD301) | Alarma "Cadena de seguridad abierta", estado 4 | |
| S6 | Variador: Arranque, Adelante/Reversa, Parada | Gira en ambos sentidos; ZSW1 = listo/en marcha; rpm en el HMI = rpm del BOP | |
| S7 | Falla del variador (p. ej. quitar el habilitador) y Rearme | Alarma de falla y acuse con el Rearme | |
| S8 | Arranque en frío con SP = 43 °C | Anotar: tiempo hasta SP − 0,5 °C ____ min, sobrepico ____ °C | |
| S9 | Régimen (10 min en consigna) | Oscilación pico a pico ____ °C, período ON-OFF ____ s, ciclo de trabajo ____ % | |
| S10 | Velocidad vs. error durante el calentamiento | Tabla de 5 puntos (PV, rpm) que siga la ley lineal | |
| S11 | Abrir la tapa 2 min en consigna | Caída de ____ °C; ¿se reactivó el agitador? ¿se rechazó el lote? | |
| S12 | Reporte en el PC | PDF generado en < 10 s, con tendencia y eventos | |
| S13 | Reporte del supervisor en la nube | Fila nueva en `reportes` (Supabase) con `origen_datos = nube` | |
| S14 | Reporte de gerencia en la nube | PDF con materiales, inventario, ventas, tiempos muertos y KPI | |
| S15 | Desconectar Internet 2 min y reconectar | Pendientes > 0 durante el corte y 0 después; no faltan filas en la nube | |
| S16 | Cerrar el gateway 15 s | Alarma "Gateway sin comunicación" en el HMI | |
| S17 | Usuarios: entrar como operador e intentar abrir Gerencia | Pide credenciales / acceso denegado | |

## 8.3 Datos para comparar el diseño con lo implementado (sección 13 de la guía)

| Métrica | Modelo (diseño) | Medido | Diferencia y causa |
|---|---|---|---|
| Tiempo hasta SP − 0,5 °C | 15,1 min | | |
| Sobrepico | 0,95 °C | | |
| Oscilación en régimen (p-p) | 1,87 °C | | |
| Período ON-OFF | ~300 s | | |
| Ciclo de trabajo en régimen | 51 % | | |
| Caída con la tapa abierta 2 min | ~4 °C (a SP = 48 °C) | | |

Los valores del modelo salen de `python herramientas/simular_diseno.py` (archivo `docs/img/sim_metricas.md`).
Si lo medido difiere mucho, identifique el modelo (sección 2.2), actualice `DB_Param.Sim` y repita la simulación:
esa iteración es justamente el análisis de "diseño inicial vs solución implementada".
