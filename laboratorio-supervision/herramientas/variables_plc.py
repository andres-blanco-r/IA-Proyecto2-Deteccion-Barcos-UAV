"""Tabla de variables del PLC (E/S físicas y del variador).

Las direcciones son las típicas del banco con CPU 1512C-1 PN / módulos de E/S
y SINAMICS G120 por PROFINET. AJÚSTELAS a la configuración de hardware de su banco
(Vista de dispositivos > propiedades de cada módulo > Direcciones E/S).
"""

# (nombre, tipo, dirección, comentario, tabla)
VARIABLES = [
    ("DI_ParoEmergencia", "Bool", "%I0.0", "Hongo de paro de emergencia (NC): TRUE = no accionado", "Planta"),
    ("DI_Start", "Bool", "%I0.1", "Pulsador de marcha (NA)", "Planta"),
    ("DI_Stop", "Bool", "%I0.2", "Pulsador de parada (NC): TRUE = no accionado", "Planta"),
    ("DI_CadenaSeguridad", "Bool", "%I0.3", "24 V después del paro y del termostato KSD301 (TRUE = cadena cerrada)", "Planta"),
    ("DQ_Calefactor", "Bool", "%Q0.0", "Calefactor PTC 24 V (vía MOSFET de la tarjeta)", "Planta"),
    ("DQ_Ventilador", "Bool", "%Q0.1", "Ventilador de recirculación de la cámara", "Planta"),
    ("DQ_LuzVerde", "Bool", "%Q0.2", "Piloto verde: proceso en marcha", "Planta"),
    ("DQ_LuzAmarilla", "Bool", "%Q0.3", "Piloto amarillo: calentando / alarma", "Planta"),
    ("DQ_LuzRoja", "Bool", "%Q0.4", "Piloto rojo: emergencia (fijo) / falla (intermitente)", "Planta"),
    ("AI_Temperatura", "Int", "%IW64", "Lazo 4-20 mA de la RTD sobre 250 ohm (1..5 V)", "Planta"),
    ("VFD_ZSW1", "Word", "%IW256", "G120 telegrama 1: palabra de estado ZSW1", "Variador"),
    ("VFD_NIST", "Int", "%IW258", "G120 telegrama 1: velocidad real NIST_A (16#4000 = 100 %)", "Variador"),
    ("VFD_STW1", "Word", "%QW256", "G120 telegrama 1: palabra de mando STW1", "Variador"),
    ("VFD_NSOLL", "Int", "%QW258", "G120 telegrama 1: consigna de velocidad NSOLL_A", "Variador"),
    # --- Parte emulada en Factory IO (escena "Level control") ---
    ("FIO_Nivel", "Int", "%IW100", "Factory IO: Level meter (0..27648 = 0..10 V)", "FactoryIO"),
    ("FIO_Setpoint", "Int", "%IW102", "Factory IO: potenciómetro de set point", "FactoryIO"),
    ("FIO_Start", "Bool", "%I100.0", "Factory IO: botón Start", "FactoryIO"),
    ("FIO_Stop", "Bool", "%I100.1", "Factory IO: botón Stop (NC)", "FactoryIO"),
    ("FIO_ValvulaLlenado", "Int", "%QW100", "Factory IO: Fill valve (0..27648 = 0..10 V)", "FactoryIO"),
    ("FIO_ValvulaDescarga", "Int", "%QW102", "Factory IO: Discharge valve", "FactoryIO"),
    ("FIO_DisplayNivel", "Int", "%QW104", "Factory IO: display de nivel", "FactoryIO"),
    ("FIO_DisplaySP", "Int", "%QW106", "Factory IO: display de set point", "FactoryIO"),
    ("FIO_LuzStart", "Bool", "%Q100.0", "Factory IO: luz del botón Start", "FactoryIO"),
    ("FIO_LuzStop", "Bool", "%Q100.1", "Factory IO: luz del botón Stop", "FactoryIO"),
]
