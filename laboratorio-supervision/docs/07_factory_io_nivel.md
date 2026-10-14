# 7. Parte emulada: control ON-OFF de nivel en Factory IO

El objetivo específico 1 de la guía habla de un control ON-OFF de **nivel** "tanto en un proceso físico como
en uno emulado", y la introducción menciona Factory IO. El procedimiento pide temperatura en la planta física,
así que esta parte cubre el proceso **emulado** con la escena **"Level control"** de Factory IO, reutilizando el
mismo bloque `FB_OnOffHist` del calefactor. Confirme con el docente si la evalúan.

## 7.1 Pasos

1. Factory IO → escena *Level control* (tanque con válvula de llenado, válvula de descarga, medidor de nivel,
   potenciómetro de SP, botones Start/Stop).
2. *Drivers* → **Siemens S7-1200/1500** (PLC real por Ethernet) o el driver de PLCSIM / PLCSIM Advanced.
   Valores analógicos como **entero 0..27648 = 0..10 V**. Asigne las direcciones de la tabla `Tabla_FactoryIO`
   (o cambie la tabla para que coincida):

   | Factory IO | Variable PLC | Dirección |
   |---|---|---|
   | Level meter | `FIO_Nivel` | %IW100 |
   | Setpoint (potenciómetro) | `FIO_Setpoint` | %IW102 |
   | Start | `FIO_Start` | %I100.0 |
   | Stop (NC) | `FIO_Stop` | %I100.1 |
   | Fill valve | `FIO_ValvulaLlenado` | %QW100 |
   | Discharge valve | `FIO_ValvulaDescarga` | %QW102 |
   | Display nivel / SP | `FIO_DisplayNivel` / `FIO_DisplaySP` | %QW104 / %QW106 |
   | Luz Start / Stop | `FIO_LuzStart` / `FIO_LuzStop` | %Q100.0 / %Q100.1 |

3. Importe `05_FactoryIO_Nivel.scl` y, en `04_Main.scl`, quite el comentario de `"IDB_NivelFactoryIO"();`.
4. Start: la válvula de llenado abre al 100 % cuando el nivel baja de SP − 2 % y cierra por encima de SP + 2 %.
   La descarga queda fija en 30 % (`Descarga_pct`) como perturbación; cámbiela en caliente para ver el efecto.

## 7.2 Qué comparar en el informe

| Aspecto | Temperatura (física) | Nivel (emulado) |
|---|---|---|
| Dinámica | Lenta (τ ≈ 18 min), con inercia y retardo → sobrepico tras apagar | Integradora, casi sin retardo → se queda en la banda |
| Efecto de la histéresis | Oscilación mayor que H por la inercia térmica | Oscilación ≈ H |
| Perturbación | Abrir la tapa (pérdidas ×2) | Apertura de la válvula de descarga |
| Frecuencia de conmutación | Pocas veces por hora (ciclos de ~5 min) | Depende del caudal de descarga |
