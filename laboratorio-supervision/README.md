# Laboratorio de Automatización Industrial: práctica "Supervisión" (UMNG)

Solución completa de la guía GL-AA-F-1 *Supervisión* (Ingeniería Mecatrónica, IX semestre): sistema de
supervisión local y remota de una **incubadora de yogur** con control ON-OFF de temperatura (RTD), agitador
movido por un **SINAMICS G120 por PROFINET**, **tres paneles SCADA por rol**, **base de datos local y en la nube**
y **reportes bajo demanda**.

| Panel de operador | Panel de supervisor | Panel de gerencia |
|---|---|---|
| ![](docs/img/hmi_operador.png) | ![](docs/img/hmi_supervisor.png) | ![](docs/img/hmi_gerencia.png) |

## Qué hay en esta carpeta

| Carpeta | Contenido | Estado |
|---|---|---|
| [`informe/`](informe/) | Informe en Markdown y Word (.docx), con la estructura de la guía (secciones 5–16) y las 8 preguntas respondidas | Listo; faltan las **mediciones** marcadas [COMPLETAR] |
| [`plc/fuentes_scl/`](plc/fuentes_scl/) | Programa del S7-1500 en SCL, importable como fuentes externas en TIA Portal | Verificado estáticamente; **compilar en TIA Portal** |
| [`plc/tablas/`](plc/tablas/) | Tabla de variables para importar (`Variables_PLC.xlsx`) | Ajustar direcciones al banco |
| [`gateway/`](gateway/) | Gateway Python: PLC → BD local (SQLite) → nube (PostgreSQL/Supabase) + reportes PDF | Probado (12 pruebas automáticas) |
| [`scada/mockups/`](scada/mockups/) | Maquetas de los 3 paneles (ISA-101) para dibujar en WinCC | Dibujar en WinCC |
| [`hardware/carcasa/`](hardware/carcasa/) | Carcasa paramétrica en OpenSCAD + STL (base, tapa, bandeja, soporte) | Imprimir en PETG |
| [`hardware/pcb/`](hardware/pcb/) | Esquemáticos de la tarjeta de borneras (lazo 4-20 mA, potencia, seguridad) | Fabricar y soldar |
| [`docs/`](docs/) | Documentación técnica paso a paso (8 capítulos) | — |
| [`herramientas/`](herramientas/) | Scripts que generan y verifican todo lo anterior | — |

## Documentación

1. [Proceso propuesto y arquitectura](docs/01_proceso_y_arquitectura.md): roles, P&ID, red, señales
2. [Hardware de la planta](docs/02_hardware_planta.md): carcasa, calefactor, lazo 4-20 mA (XTR105), PCB, materiales
3. [Programa del PLC](docs/03_programa_plc.md): TIA Portal paso a paso, G120, estados, ON-OFF, ley de velocidad, alarmas
4. [Paneles SCADA](docs/04_scada_paneles.md): WinCC, norma de colores, objetos y variables, usuarios, avisos
5. [Bases de datos y reportes](docs/05_bases_datos_y_reportes.md): gateway, Supabase, esquema, consultas
6. [Gerencia y KPI](docs/06_gerencia_kpis.md): modelo de costos, OEE, margen, costo unitario
7. [Parte emulada en Factory IO](docs/07_factory_io_nivel.md): ON-OFF de nivel
8. [Pruebas y puesta en marcha](docs/08_pruebas_y_puesta_en_marcha.md): protocolo con tablas para llenar

## Lo que tiene que hacer el grupo en el laboratorio

- [ ] **Cambiar los datos de negocio** (`DB_Param.Costos`) y el nombre del grupo: la guía exige que sean distintos entre grupos.
- [ ] Imprimir la carcasa en PETG, montar el calefactor, la RTD, el ventilador, el termostato y el hongo.
- [ ] Fabricar y soldar la tarjeta de borneras; calibrar el lazo con una década de resistencias.
- [ ] TIA Portal: configurar la CPU y el G120 del banco, importar variables y fuentes, compilar y cargar.
- [ ] WinCC: dibujar los 3 paneles según `docs/04` y las maquetas, crear usuarios y avisos.
- [ ] Crear el proyecto en Supabase, configurar y arrancar el gateway.
- [ ] Ejecutar el protocolo de pruebas (`docs/08`) y llenar las [COMPLETAR] del informe con las mediciones.
- [ ] En Word: clic derecho sobre "Contenido" → *Actualizar campos* para generar el índice.

## Uso rápido sin hardware

```bash
cd gateway
pip install -r requirements.txt
python -m pytest -q tests                      # 12 pruebas (PLC simulado, BD local, "nube", reportes)
python -m scada_gateway --simular -v           # gateway con el gemelo de la planta
python -m scada_gateway reporte local          # genera un reporte PDF desde la BD local
```

Regenerar artefactos: `python herramientas/gen_db_gateway.py`, `gen_tabla_variables.py`, `simular_diseno.py`,
`gen_esquematicos.py`, `gen_diagramas.py`, `gen_mockups.py` (+ `node herramientas/capturar_mockups.js`).
Verificar las fuentes SCL: `python herramientas/verificar_scl.py`.
