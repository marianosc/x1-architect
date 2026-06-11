# BITÁCORA X1-ARCHITECT

> Hallazgos y decisiones entre sesiones (notebook ↔ blanca). Lo más nuevo arriba.

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
