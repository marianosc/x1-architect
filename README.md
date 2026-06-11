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

Snapshot inicial: estado v105 tal como quedó al pausar el proyecto.
Fase actual: saneamiento (ver auditoría — fusibles de L3 sin implementar, divergencia de salida sintética, EA MQL5 sin salida por tiempo, higiene OOS).
