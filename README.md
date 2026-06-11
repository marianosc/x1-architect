# X1-ARCHITECT

Granja de minería de estrategias (alphas) de trading sobre datos M1, con pipeline de 6 capas:

- **L0_setup.py** — genera/sincroniza `data/assets.csv` (la Constitución: filtros, fricción, zonificación)
- **L1.py** — refinería: resamplea M1 a H1/H4/M30/M15 y calcula features TA-Lib (períodos Fibonacci, anti-lookahead con columnas `_sft`)
- **L2.py** — minero genético: 500k hipótesis aleatorias por silo (TREND / MOMENTUM / VOLATILITY / CYCLE × LONG / SHORT)
- **L3.py** — auditor: filtros IS/OOS, fricción, estancamiento, ranking Health
- **L5.py** — unificador: fusión de silos y eliminación de clones por Jaccard
- **L4.py** — exportador de inyectores SQX (StrategyQuant)
- **commander.py** — orquestador del ciclo completo en la PC dedicada
- **pulse.py** — telemetría en tiempo real (Streamlit)
- **app.py** — dashboard maestro: auditoría, composición de portafolios (IA Greedy + manual), export MQL5 y Reality Check contra MT5

## Infraestructura

- El código vive en este repo, con copia de trabajo local en cada máquina.
- Los datos pesados (CSV M1, Parquet, COSECHA) viven en el G-Drive compartido (Z:) y en `C:/temp` (SSD local), **fuera de git**.
- Ejecución pesada: PC dedicada ("blanca"). Administración: notebook.

## Estado

**v106 — saneamiento en curso.** Hecho:
- **Motor Único** (`modules/x1_engine.py`): intérprete de reglas, cooldown, salidas (fijas + sintética con rotura bar-a-bar) y fricción consolidados. Todas las capas (L2, L3, L5, optimizer, dashboard) miden con el mismo metro. Corregidos: bug de la sintética en L3 (auditaba 48 velas fijas) y cooldown desigual entre minero y auditor.
- **Validadores** (`modules/x1_validators.py`): Monkey Test data-driven (metodología Tomillero, port del motor de Marc Cortázar, umbrales 99% IS / 90% OOS, corrección de cadencia) implementado como fusible real en L3; Excursion Score (XS = |MFE|/(|MFE|+|MAE|)) como columnas XS_IS/XS_OOS.
- L1 conserva High/Low (necesario para el XS — **regenerar los Parquet**).
- Tests: `python tests/test_x1_engine.py` y `python tests/test_x1_validators.py` (18 pruebas, sin dependencias de pytest/numba). Smoke test sobre datos reales: `python tools/smoke_audit_real.py`.

Pendiente: salida por tiempo y cobertura completa de indicadores en el generador de EAs MQL5; higiene OOS (zona virgen de validación final); rutas por máquina en config; Análisis de Transición como diagnóstico del dashboard; UI nueva (última fase).
