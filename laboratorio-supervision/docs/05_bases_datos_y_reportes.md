# 5. Bases de datos (local y nube) y reportes

## 5.1 Cómo funciona

```
S7-1500 ──(snap7, cada 1 s)──► gateway ──► BD local (SQLite)  ──(cada 5 s, en lotes)──► BD nube (PostgreSQL)
   ▲                              │
   └──── latido + acks ◄──────────┘──► reportes PDF (PC)  /  tabla "reportes" en la nube
```

* El gateway (`gateway/scada_gateway`) lee los 166 bytes de `DB_Gateway`, guarda una fila de **proceso** por
  segundo y una de **gerencia** cada 10 s, y registra **eventos** (cambios de estado, alarmas que entran y
  salen, cambios de sentido, lotes terminados, reportes).
* La base local es la **fuente de verdad**: cada fila nace con `sincronizado = 0` y se sube a la nube en lotes.
  Si se cae Internet no se pierde nada; el número de filas pendientes se ve en el panel de supervisor.
* Los **reportes** se piden desde el HMI (handshake por contadores, sección 3.4):
  * *Reporte en PC* (supervisor): PDF en `gateway/reportes/` con estadísticas, tendencia y eventos de los
    últimos 30 min. En Windows se abre solo.
  * *Reporte en la nube* (supervisor): igual, pero con los datos **consultados a la nube**. El PDF queda
    guardado en la tabla `reportes` de la nube.
  * *Reporte en la nube* (gerencia): materiales, costos, inventario, ventas, tiempos muertos y KPI, con gráficos.

## 5.2 Instalación en el PC de supervisión

```bat
:: Python 3.11 o superior (marcar "Add to PATH")
cd laboratorio-supervision\gateway
pip install -r requirements.txt
copy config.example.toml config.toml
:: edite config.toml: IP del PLC, número del DB, nombre de la estación
python -m scada_gateway --config config.toml
```

* `ejecutar_gateway.bat` hace lo mismo con doble clic. `ejecutar_simulado.bat` corre sin PLC (gemelo).
* Para dejarlo como servicio: Programador de tareas de Windows → al iniciar sesión → `ejecutar_gateway.bat`.
* Pruebas automáticas: `python -m pytest -q tests` (simulan PLC, BD local, "nube" y reportes).

## 5.3 Base de datos en la nube (Supabase, gratis)

1. Cree una cuenta en supabase.com → *New project* (región São Paulo o us-east), con una contraseña de BD fuerte.
2. *Project Settings → Database → Connection string → URI*, modo **Session pooler** (puerto 5432).
3. En el PC, defina la URL como **variable de entorno** (así la contraseña no queda en el archivo):
   ```bat
   setx BD_NUBE_URL "postgresql+psycopg2://postgres.XXXX:CLAVE@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
   ```
4. Arranque el gateway: crea solo las tablas `proceso`, `gerencia`, `eventos` y `reportes`.
5. Para **visualizar**: *Table Editor* (tablas) o *SQL Editor* con consultas como las de 5.5.

Cualquier PostgreSQL sirve (Neon, Azure, AWS RDS, un servidor de la universidad): solo cambia la URL.
La red del laboratorio debe permitir salida al puerto 5432; si está bloqueado, use el *Transaction pooler* (6543).

## 5.4 Esquema

| Tabla | Columnas principales |
|---|---|
| `proceso` | `ts`, `estado`, `pv_c`, `sp_c`, `error_c`, `senal_ma`, `calefactor`, `duty_calefactor_pct`, `tiempo_en_banda_pct`, `vel_ref_pct`, `vel_pct`, `vel_rpm`, `sentido`, `vfd_en_marcha`, `vfd_falla`, `en_consigna`, `progreso_lote_pct`, `alarmas` |
| `gerencia` | `ts`, lotes, unidades, vendidas, inventario, materiales (`leche_l`, `cultivo_g`, `azucar_kg`, `envases_usados`), costos, energía, tiempos, `ingresos`, `utilidad`, `margen_pct`, `oee_pct` y componentes, `costo_unitario`, `kwh_por_unidad` |
| `eventos` | `ts`, `tipo` (INICIO, ESTADO, ALARMA, VARIADOR, LOTE, REPORTE), `descripcion` |
| `reportes` | `ts`, `tipo` (local, nube_sup, nube_ger), `origen_datos`, `desde`, `hasta`, `resumen` (JSON), `nombre_archivo`, `archivo` (PDF) |

En local cada tabla tiene además `sincronizado`; en la nube, `estacion` (para que varios grupos compartan un proyecto).

## 5.5 Consultas útiles (PostgreSQL, en el SQL Editor de Supabase)

En SQLite (DB Browser for SQLite) cambie `now() - interval '10 minutes'` por `datetime('now','localtime','-10 minutes')` y `date_trunc('hour', ts)` por `strftime('%Y-%m-%d %H:00', ts)`.

```sql
-- Últimos 10 minutos de la variable de proceso y del variador
SELECT ts, pv_c, sp_c, vel_rpm, sentido, calefactor
FROM proceso WHERE ts > now() - interval '10 minutes' ORDER BY ts;

-- Indicadores por hora: error medio, % en tolerancia, ciclo de trabajo del calefactor
SELECT date_trunc('hour', ts) AS hora,
       avg(abs(error_c)) AS error_abs_medio,
       100.0 * avg(CASE WHEN abs(error_c) <= 2 THEN 1 ELSE 0 END) AS en_tolerancia_pct,
       100.0 * avg(CASE WHEN calefactor THEN 1 ELSE 0 END) AS duty_pct
FROM proceso GROUP BY 1 ORDER BY 1;

-- Último estado de gerencia de mi estación
SELECT * FROM gerencia WHERE estacion = 'Grupo 1 - Banco 3' ORDER BY id DESC LIMIT 1;

-- Reportes guardados en la nube
SELECT id, ts, tipo, nombre_archivo, resumen FROM reportes ORDER BY ts DESC;
```

## 5.6 Problemas frecuentes

| Síntoma | Causa probable |
|---|---|
| `Connection refused` / timeout al PLC | IP incorrecta, PC en otra subred, firewall del puerto 102 |
| `CPU: Function not available` | Falta habilitar PUT/GET en la CPU |
| `Address out of range` | Número de DB distinto al de `config.toml`, o el DB no tiene 166 bytes |
| Valores absurdos (p. ej. 1e-38) | `DB_Gateway` quedó con acceso **optimizado**: desactívelo y vuelva a cargar |
| Alarma "Gateway sin comunicación" | El gateway no está corriendo o no puede escribir (PUT/GET) |
| Estado de nube = 2 | Sin Internet, URL o contraseña mal; las filas se acumulan y se suben al volver |
