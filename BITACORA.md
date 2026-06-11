# BITÁCORA X1-ARCHITECT

> Hallazgos y decisiones entre sesiones (notebook ↔ blanca). Lo más nuevo arriba.

## 2026-06-11 — Ciclo 1 del commander (XAUUSD @ H1): AUTOPSIA COMPLETA

**Ejecución:** un ciclo entero (L1 → 8 silos LONG/SHORT × MOMENTUM/TREND/VOLATILITY/CYCLE
→ L5 → L4) vía `tools/run_commander_cycle.py` (mismo pipeline que `commander.py` pero un
solo ciclo, sin `input()` y con cronómetro por capa). Fusible `monkey_test` activado en
`audit_config.json` (estaba en `false`; sin eso el monkey no corre). Fricción 1.0 pt
(calibrada hoy) y cooldown 25 en minero y auditor. NO se encadenó ciclo 2.

### Resultado global: mortalidad 100% — 1.050.495 candidatos, 0 cosechados

| Silo | Candidatos L2 | FAIL_GAP | Otros | PASS |
|---|---|---|---|---|
| LONG MOMENTUM   | 270.450 | 270.450 | 0 | 0 |
| LONG TREND      | 238.445 | 238.444 | 1 FAIL_PF_NET | 0 |
| LONG VOLATILITY | 245.779 | 245.779 | 0 | 0 |
| LONG CYCLE      | 288.291 | 288.290 | 1 FAIL_TRADES | 0 |
| SHORT MOMENTUM  | 1.381   | 1.381   | 0 | 0 |
| SHORT TREND     | 4.587   | 4.587   | 0 | 0 |
| SHORT VOLATILITY| 1.278   | 1.278   | 0 | 0 |
| SHORT CYCLE     | 284     | 284     | 0 | 0 |

- **FAIL_MONKEY_IS / FAIL_MONKEY_OOS / FAIL_OOS_EMPTY / FAIL_NEG_PROFIT: 0 en todos** —
  nadie llegó vivo a esos gates.
- **XS_IS / XS_OOS de los que pasen: N/A** (cero PASS).
- Cosecha cero = dato válido (ley pasos.txt). MASTER nuevos: ninguno.

### Causa de muerte: el muro FAIL_GAP (diagnóstico, no especulación)

El embudo de L3 evalúa el gap ANTES que PF/trades/monkey, así que con este muro los demás
contadores no informan nada. Mecanismo verificado con `tools/diag_failgap.py`:

- L2 selecciona por PF neto > 1.05 **solo en Zona 1** (2018-2023). L3 simula la historia
  completa de 59.531 velas: Zona 0 (2015-2018) + Z1 + Z2 (2023-2025).
- Con fricción 1.0 (3,3× la 0.3 de la era v105), las equity curves no hacen máximos nuevos
  durante tramos larguísimos: en 10 reglas de muestra del MASTER viejo, el gap máximo entre
  picos fue de **22.046 a 59.531 velas** (la mayoría: "sin picos en toda la historia"),
  contra `Stag_Global = 5000` velas (~10 meses de H1). Ejecución sumaria garantizada.
- Asimetría SHORT brutal en L2: 284–4.587 candidatos vs 238k–288k LONG. El histórico
  alcista del oro + fricción 1.0 deja casi sin reglas SHORT netas > 1.05.

**Decisión pendiente para NOTEBOOK (no toqué nada):** ¿el listón es el deseado?
Opciones que se desprenden del diagnóstico: (a) dejarlo así y aceptar cosechas casi nulas
con fricción realista; (b) medir el gap desde el primer trade o por zona (hoy un candidato
muere por no operar/ganar en Zona 0, régimen en el que nunca fue seleccionado);
(c) recalibrar Stag_Global para fricción 1.0.

### Tiempos por capa (Ryzen 9 9950X3D, numba activa, monkey_n=5000)

| Capa | Tiempo |
|---|---|
| L1 refinería | 12,1 s |
| L2 por silo (500k hipótesis) | 20,0–21,2 s (×8 = 165,6 s) |
| L3 silos LONG (~240-290k candidatos) | 32,6–37,9 s |
| L3 silos SHORT (0,3-4,6k candidatos) | 4,9–6,9 s |
| L5 + L4 | 0,9 s |
| **Ciclo completo** | **341,5 s (~5,7 min)** |

- **El monkey NO es cuello de botella en este ciclo: ejecutó 0 veces** (nadie superó los
  gates previos). Su costo real queda sin medir; el tiempo de L3 es ~100% `simulate()`
  masivo: ~250-290k simulaciones en ~33-38 s ≈ **7.500 sims/s** con 32 procesos.
  Si algún día el embudo deja pasar miles de candidatos al monkey, ahí sí habrá que
  medirlo de nuevo (5000 monos × 2 zonas por candidato superviviente).
- Primera corrida del día: 493,5 s por compilación JIT fría (L3 LONG_CYCLE tardó 159,5 s
  la primera vez vs 32,6 s la segunda).

### Incidencias de infraestructura encontradas y corregidas en esta corrida

1. **L2 moría en silencio por emojis** al redirigir stdout a archivo (Windows cp1252 no
   codifica 🚀): el `except` global de L2 convertía el `UnicodeEncodeError` en "0 alphas"
   sin error visible. El runner fuerza `PYTHONUTF8=1`. Ojo: cualquier automatización
   futura que capture la salida de L2 necesita lo mismo.
2. **L3 no escribía el AUDIT json cuando la cosecha era 0** → la autopsia se perdía
   justo en el caso más informativo. Parcheado en `L3.py`: la telemetría se escribe
   SIEMPRE (el MASTER csv sigue escribiéndose solo si hay élite).
3. Fusible `monkey_test` estaba apagado en `data/audit_config.json` → activado.

**Push a Z:** los 8 `AUDIT_XAUUSD_*.json` subidos a `COSECHA` de Z: (los de la era v105
quedaron respaldados como `.v105.bak`). MASTER nuevos: no hay (cosecha cero).

## 2026-06-11 — Calibración Python ↔ MT5 del canario (CERRADA, luz verde al commander)

**Contexto:** primer backtest de CANARIO01 en el Strategy Tester de Darwinex (XAUUSD H1,
Zona 2 OOS 2023-06-05→2025-12-09, modelo open-prices) comparado trade-a-trade contra
`x1_engine.simulate`. Herramientas nuevas: `tools/compare_canario01.py` (empareja por índice
de barra), `tester_canario01.ini`, instrumentación de `OnDeinit` en el EA para volcar trades
a `Common\Files\X1_TRUTH_CANARIO01.csv`.

**Correcciones previas para que la calibración tuviera sentido:**
- La ADN v106 no tiene `rsi_14` (períodos 5,8,13,21,34,55,89,144,200,24,48,120) → se usó `rsi_13`.
- La regla de ejemplo del checklist `rsi_13<=30 | ema_55<=Close` es **contradictoria** (0 entradas
  en motor y en MT5). La desigualdad de la EMA estaba al revés; la correcta es
  `rsi_13_sft <= 30 | ema_55_sft >= Close_sft` (122 entradas en Z2).

**Veredicto de la notebook sobre los 3 fixes propuestos y su resolución:**

1. **SHIFT_SIGNAL 2→1: RECHAZADO y refutado con datos.** El motor entra a `Close[i]`
   (Ret_N[i] mide desde `Close[i]`), que en MT5 es el **open de la vela i+1**. Por eso el EA
   etiqueta la entrada en i+1: el "offset +1" es la **firma de sincronía correcta**, no un bug.
   Prueba decisiva por precio: el fill del EA = `Close[i]` **+0.189 pts** de media (mediana 0.170,
   std 0.087, **100% dentro de 0.5 pt**) = medio-spread del ask.
   **Match de precio |fill−Close[i]| ≤ 1 pt: 96.7% (117/121).**

2. **Fricción: APROBADA (Mariano) y aplicada.** `data/assets.csv` XAUUSD subido a **1.0 pt total**
   (Slippage 0.1, Avg_Spread 0.6, Broker_Comm 0.3) vs el 0.3 viejo. El coste real Darwinex medido
   fue 0.97 pt/trade. Con fricción 1.0, **divergencia residual de equity = −0.009 pts%** sobre los
   107 pares sincronizados (motor −3.862% vs MT5 −3.871%).

3. **Cooldown: alineado.** `tools/generate_ea.py` ahora toma el default desde `Min_Dist_Bars`
   de assets.csv (XAUUSD = 25); antes hardcodeaba 24. Canario regenerado con cooldown 25.

4. **Grupo desfasado (offset ≥ 2, 12 trades): documentado como slippage real, sin fix de código.**
   Son jitter de umbral RSI(13) entre TA-Lib (Parquet) e iRSI (MT5) — dispara 1 barra distinta
   cerca de 30 — más 2 gaps reales (overnight −10.5 pt el 2024-07-19; +19.8 pt en barra volátil
   el 2025-12-02). **DST descartado:** 0 timestamps MT5 fuera del grid UTC+2 y el offset +1 abarca
   verano e invierno por igual (estructural, no huso horario).

**Objetivo de la calibración (cumplido):** match de precios > 95% (96.7%) y divergencia residual
de equity < 0.5 pts% (−0.009). → **Luz verde al ciclo del commander.**

---

## 2026-06-11 — Deploy en blanca (Fases 0–7 del DEPLOY_BLANCA.md)

- Python del sistema 3.14 inservible (numba/TA-Lib sin wheels) → venv con `py -3.12` (3.12.10 x64).
  TA-Lib 0.6.8 y numba 0.65.1 instalaron directo de pip.
- 26/26 tests OK. Parquet v106 regenerado (287 cols, High/Low, ADN nuevo) y subido a
  `Z:\...\COSECHA\DATOS_MERCADO\` → XS deja de ser NaN en el audit.
- Prueba de fuego: CANARIO01/02 compilan `0 errors, 0 warnings` → `.ex5`.
- `modules/mt5_bridge.py`: rutas reales de blanca (usuario `Pc`). El hash del terminal Darwinex
  (`6C3C6A11...`) es determinista por ruta de instalación, por eso ya coincidía.
