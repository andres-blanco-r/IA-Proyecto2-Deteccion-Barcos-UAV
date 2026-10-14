# 1. Proceso propuesto y arquitectura

## 1.1 El proceso: incubadora de yogur con agitador

La guía pide que cada grupo formule **su propio proceso** controlando **temperatura** con una RTD y
manejando un **variador de velocidad**. Se propone una **línea de yogur batido** (si su proyecto final
es otro, cambie la narrativa y los datos de costos, pero la lógica sirve igual):

| Etapa industrial real | Cómo se representa en el laboratorio |
|---|---|
| Tanque de incubación con camisa de calentamiento | Cámara impresa en PETG con calefactor de ~19 W y ventilador |
| Temperatura de incubación 42–45 °C | Control ON-OFF con histéresis, SP = 43 °C |
| Agitador para homogeneizar mientras se calienta | Motor del banco accionado por el SINAMICS G120 por PROFINET |
| La fermentación necesita **reposo** (agitar rompe el gel) | El agitador **frena al acercarse al SP y se detiene al alcanzarlo** |
| Lote de 4–6 h | Lote de 5 min (parámetro `T_Lote_s`) para poder demostrarlo |
| Venta de vasos de 200 mL | Pedidos simulados + ventas manuales desde el panel de gerencia |

Este proceso **justifica físicamente** el requisito de la guía sobre el variador: la velocidad depende de
lo lejos que esté la temperatura de la consigna y se detiene al llegar, porque así lo exige el producto.

### Roles

| Rol | Necesidad | Panel |
|---|---|---|
| Operador | Arrancar y parar, fijar el SP, manejar el agitador, ver si todo va bien | Operador |
| Supervisor | Tendencias, indicadores de calidad del control, reportes en el PC y en la nube | Supervisor |
| Gerencia | Costos, inventario, ventas, tiempos muertos, KPI y reporte en la nube | Gerencia |

## 1.2 P&ID simplificado

![P&ID](img/pid.png)

| Tag | Descripción | Señal |
|---|---|---|
| TT-101 | RTD Pt100 + transmisor 4-20 mA | `AI_Temperatura` (%IW64) |
| TIC-101 | Control ON-OFF en el PLC (`FB_OnOffHist`) | — |
| TAH-101 / TAHH-101 | Alarma de temperatura alta (SP+4 °C) / muy alta (60 °C, disparo) | Alarmas HMI |
| TSH-102 | Termostato bimetálico KSD301 de 60 °C (protección cableada, independiente del PLC) | `DI_CadenaSeguridad` |
| E-101 | Calefactor (2 × RH25 15 Ω en serie sobre placa de aluminio) | `DQ_Calefactor` |
| K-101 | Ventilador de recirculación interna | `DQ_Ventilador` |
| SC-101 / M-101 | Variador G120 / motor del agitador | Telegrama 1 por PROFINET |
| HS-101 | Hongo de paro de emergencia (2 contactos NC) | `DI_ParoEmergencia` + corte de potencia |

## 1.3 Arquitectura

![Arquitectura](img/arquitectura.png)

* **Nivel de campo:** planta + tarjeta de borneras (lazo 4-20 mA, calefactor, cadena de seguridad).
* **Nivel de control:** S7-1500 con el programa de `plc/fuentes_scl`. El G120 cuelga del PLC por PROFINET.
* **Nivel de supervisión (local):** PC con WinCC Runtime (3 paneles con usuarios por rol) y el
  *gateway* Python, que registra en una base de datos local y genera los reportes en PDF.
* **Nivel remoto (nube):** PostgreSQL gestionado (Supabase, plan gratuito). El gateway sube los datos
  y los reportes; si se cae Internet, guarda la cola en local y la sube cuando vuelve.

> **¿Por qué un gateway y no Ubidots o Node-RED?** La guía aclara que Ubidots y Node-RED **no son bases
> de datos**. Aquí la base local es SQLite (o SQL Server) y la de la nube es PostgreSQL: ambas son
> motores de bases de datos relacionales de verdad, y se consultan con SQL.

### Plan de direcciones IP (ejemplo, ajústelo al banco)

| Equipo | Nombre PROFINET | IP |
|---|---|---|
| CPU S7-1500 | `plc-incubadora` | 192.168.0.1 /24 |
| SINAMICS G120 | `g120-agitador` | 192.168.0.2 /24 |
| PC SCADA (WinCC + gateway) | — | 192.168.0.10 /24 |

## 1.4 Señales

Tabla completa (importable en TIA Portal): [`plc/tablas/Variables_PLC.xlsx`](../plc/tablas/Variables_PLC.xlsx) ·
versión legible: [`plc/tablas/Variables_PLC.md`](../plc/tablas/Variables_PLC.md).

| Señal | Tipo | Dirección | Nota |
|---|---|---|---|
| `DI_ParoEmergencia` | DI | %I0.0 | Contacto NC: 1 = sano |
| `DI_Start` / `DI_Stop` | DI | %I0.1 / %I0.2 | Stop es NC |
| `DI_CadenaSeguridad` | DI | %I0.3 | 24 V después del paro y del termostato |
| `DQ_Calefactor` | DQ | %Q0.0 | A la compuerta del MOSFET (tarjeta) |
| `DQ_Ventilador` | DQ | %Q0.1 | Ventilador 24 V |
| `DQ_LuzVerde/Amarilla/Roja` | DQ | %Q0.2–%Q0.4 | Pilotos del banco (IEC 60073) |
| `AI_Temperatura` | AI | %IW64 | 1..5 V sobre 250 Ω |
| `VFD_STW1`, `VFD_NSOLL` | PROFINET | %QW256, %QW258 | Telegrama 1 (salidas) |
| `VFD_ZSW1`, `VFD_NIST` | PROFINET | %IW256, %IW258 | Telegrama 1 (entradas) |
