| Nombre | Tipo | Dirección | Tabla | Comentario |
|---|---|---|---|---|
| `DI_ParoEmergencia` | Bool | `%I0.0` | Planta | Hongo de paro de emergencia (NC): TRUE = no accionado |
| `DI_Start` | Bool | `%I0.1` | Planta | Pulsador de marcha (NA) |
| `DI_Stop` | Bool | `%I0.2` | Planta | Pulsador de parada (NC): TRUE = no accionado |
| `DI_CadenaSeguridad` | Bool | `%I0.3` | Planta | 24 V después del paro y del termostato KSD301 (TRUE = cadena cerrada) |
| `DQ_Calefactor` | Bool | `%Q0.0` | Planta | Calefactor PTC 24 V (vía MOSFET de la tarjeta) |
| `DQ_Ventilador` | Bool | `%Q0.1` | Planta | Ventilador de recirculación de la cámara |
| `DQ_LuzVerde` | Bool | `%Q0.2` | Planta | Piloto verde: proceso en marcha |
| `DQ_LuzAmarilla` | Bool | `%Q0.3` | Planta | Piloto amarillo: calentando / alarma |
| `DQ_LuzRoja` | Bool | `%Q0.4` | Planta | Piloto rojo: emergencia (fijo) / falla (intermitente) |
| `AI_Temperatura` | Int | `%IW64` | Planta | Lazo 4-20 mA de la RTD sobre 250 ohm (1..5 V) |
| `VFD_ZSW1` | Word | `%IW256` | Variador | G120 telegrama 1: palabra de estado ZSW1 |
| `VFD_NIST` | Int | `%IW258` | Variador | G120 telegrama 1: velocidad real NIST_A (16#4000 = 100 %) |
| `VFD_STW1` | Word | `%QW256` | Variador | G120 telegrama 1: palabra de mando STW1 |
| `VFD_NSOLL` | Int | `%QW258` | Variador | G120 telegrama 1: consigna de velocidad NSOLL_A |
| `FIO_Nivel` | Int | `%IW100` | FactoryIO | Factory IO: Level meter (0..27648 = 0..10 V) |
| `FIO_Setpoint` | Int | `%IW102` | FactoryIO | Factory IO: potenciómetro de set point |
| `FIO_Start` | Bool | `%I100.0` | FactoryIO | Factory IO: botón Start |
| `FIO_Stop` | Bool | `%I100.1` | FactoryIO | Factory IO: botón Stop (NC) |
| `FIO_ValvulaLlenado` | Int | `%QW100` | FactoryIO | Factory IO: Fill valve (0..27648 = 0..10 V) |
| `FIO_ValvulaDescarga` | Int | `%QW102` | FactoryIO | Factory IO: Discharge valve |
| `FIO_DisplayNivel` | Int | `%QW104` | FactoryIO | Factory IO: display de nivel |
| `FIO_DisplaySP` | Int | `%QW106` | FactoryIO | Factory IO: display de set point |
| `FIO_LuzStart` | Bool | `%Q100.0` | FactoryIO | Factory IO: luz del botón Start |
| `FIO_LuzStop` | Bool | `%Q100.1` | FactoryIO | Factory IO: luz del botón Stop |
