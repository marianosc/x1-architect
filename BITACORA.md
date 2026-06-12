# BITÁCORA X1-ARCHITECT

> Hallazgos y decisiones entre sesiones (notebook ↔ blanca). Lo más nuevo arriba.

## 2026-06-12 (noche) — PROGRAMA NOCTURNO en rama `experimentos-nocturnos` (entradas incrementales abajo)

### A1 — Ciclo H4 XAUUSD: LOS PRIMEROS 7 PASS OFICIALES DEL PROYECTO

**Hipótesis:** H4 respira donde H1 se ahoga (4× menos velas → menos peaje relativo de fricción
por unidad de movimiento, menos ruido microestructural).
**Cambio exacto:** TF=H4 con escala tiempo-equivalente ÷4 de la Constitución vía overrides
X1_* (Stag_Global 1250, Min_Trades 75, cooldown 6, señales L2 50). **Listones del tribunal
INTACTOS:** PF 1.25, monkey 99/90 con fricción justa 1.0. Artefactos: `experimentos/A1_H4/`.

**Resultado (1.345.493 candidatos, ciclo 268,7 s):**
| Silo | Candidatos | Llegan a MK_OOS | PASS |
|---|---|---|---|
| LONG MOMENTUM | 325.774 | 2.783 | **6** (4 cosechados tras Jaccard) |
| LONG TREND | 306.130 | 2.123 | **1** |
| LONG VOLATILITY / CYCLE | 636.704 | 1.347 | 0 |
| SHORT (4 silos) | 76.885 | 0 | 0 |

- El embudo H4 está VIVO: ~6.250 candidatos llegaron al monkey OOS (vs 212 en H1).
- Tasa de paso en MK_OOS ≈ 0,11% — sigue MUY por debajo del 10% del azar (el grueso de la
  minería random sigue siendo anti-edge), pero la cola extrema EXISTE en H4 y en H1 no existía.
- **Los 5 cosechados son UN solo patrón económico:** comprar la caída profunda del oro
  (`roc_55_sft <= -2.79`, ~9 días de caída) con confirmación suave de momentum, o su variante
  trend (`adx_34>=27 & minus_di_8>=19.7`), TODOS salida `SINTETICA_REVERSE`, TODOS LONG.
  XS_OOS 0.63-0.68 (entrada con edge fuerte), OER>1 (mejora en OOS), PF 2.96-5.34.
- **Cautela R4:** monkey_OOS 90.2-92.6 = apenas sobre el listón; con 1.35M de pruebas estos 7
  pueden ser la cola afortunada (curse of multiplicity → el DSR de B1 habla de esto).
  Etiqueta: **PROMETEDOR, no validado.** Pendiente C1: estabilidad por semilla + .mq5 listos.

**Veredicto (1 línea):** H4 produce los primeros PASS oficiales; un único patrón "comprar la
caída"; borderline en OOS → obligatorio C1 (semillas) y Reality Check MT5 antes de creer.

## 2026-06-12 — Ciclo 3 (monkey con fricción justa): 0/212 pasan MONKEY_OOS → se abre fase de hipótesis

**Implementación del veredicto:** `monkey_test()` acepta `friction_per_trade` (retorno
fraccional): cada entrada del mono paga `fwd[i] - friction`. La herramienta original de Marc
compara la estrategia NETA contra monos BRUTOS — ese sesgo castigaba a las estrategias reales
(debían superar al azar Y pagar un spread que los monos no pagaban). L3 pasa
`f_points / mean(Close de la zona)`: el mismo peaje normalizado que la estrategia paga vía
`simulate()`. Tests 13/13 en `test_x1_validators.py`, incluidos los 3 nuevos:
(a) la beta de los monos cae exactamente `trades × fricción` (mismo seed → diferencia exacta);
(b) estrategia sin edge pero neta vs monos CON fricción → p-value ~uniforme (0.098; el modo
sesgado la castigaba a 0.041); (c) regresión: `friction_per_trade=0` reproduce el original.

### EL NÚMERO: de 212 que llegaron a MONKEY_OOS, pasaron 0 (0,0%)

| Silo | Candidatos | Cruzan gap | Llegan a MONKEY_OOS | Pasan |
|---|---|---|---|---|
| LONG MOMENTUM   | 270.669 | 137 | 81 | 0 |
| LONG TREND      | 238.705 | 88  | 43 | 0 |
| LONG VOLATILITY | 245.891 | 124 | 76 | 0 |
| LONG CYCLE      | 288.079 | 26  | 12 | 0 |
| **Total** | **1.050.995** | **375** | **212** | **0** |

**Lectura estadística (la pregunta del veredicto era ~10% = azar):** bajo puro azar, un
candidato sin edge pasa el listón OOS del 90% un ~10% de las veces → se esperaban ~21 pases
en 212 intentos. **Cero pases tiene probabilidad ≈ 0,9²¹² ≈ 2×10⁻¹⁰: no es azar, es ANTI-edge.**
Los finalistas son la élite IS (sobrevivieron PF≥1.25 y monkey IS 99%), y en OOS rinden PEOR
que entradas aleatorias con su misma cadencia y dirección: la firma clásica del overfitting
del minero — lo aprendido en Z1 no solo no generaliza, sino que estorba en Z2.

**Conclusión operativa (criterio del veredicto): la minería random NO tiene edge → se abre
FASE DE HIPÓTESIS** (familias/ADN/targets dirigidos en vez de 500k reglas aleatorias por silo).
La corrección de fricción era necesaria para la integridad del test, pero no cambió el
resultado: con pelea sesgada (ciclo 2) 0/166; con pelea justa (ciclo 3) 0/212. El embudo,
el monkey y la telemetría quedan validados y listos para medir hipótesis dirigidas.

Tiempos: ciclo 327,6 s. L MOM 45,6 s (re-JIT del kernel por la firma nueva, cacheado);
resto de L3 LONG 23,7-29,1 s. AUDITs ciclo 3 en Z: (ciclo 2 respaldado `.ciclo2.bak`).

## 2026-06-11 — Ciclo 2 (Zona 0 = contexto): el embudo fluye, el monkey ejecuta, verdugo final = MONKEY_OOS

**Implementación del veredicto (opción b):** `L3.py` ahora juzga estancamiento (FAIL_GAP)
y profit total sobre `r_all[z1_start:]` (primer índice de Zona 1, pasado vía
`G_CFG['z1_start']`). Señales/indicadores siguen usando toda la historia: Zona 0 = contexto
("Hist"), no tribunal. Test nuevo `tests/test_L3_zona0.py` (3/3): sana-en-Z1+Z2 que pierde
en Z0 sobrevive (stag 30); estancada DENTRO de Z1/Z2 muere FAIL_GAP; con el criterio viejo
(z1_start=0) la primera moría — regresión confirmada.

### Autopsia ciclo 2: 1.050.122 candidatos, 0 cosechados — pero el embudo cambió de forma

| Silo | Candidatos | FAIL_GAP | FAIL_TRADES | FAIL_PF_NET | MONKEY_IS | MONKEY_OOS | PASS |
|---|---|---|---|---|---|---|---|
| LONG MOMENTUM   | 270.204 | 270.093 | 39 | 8  | 25 | 39 | 0 |
| LONG TREND      | 238.076 | 237.972 | 44 | 1  | 2  | 57 | 0 |
| LONG VOLATILITY | 245.877 | 245.741 | 35 | 21 | 16 | 64 | 0 |
| LONG CYCLE      | 288.381 | 288.357 | 18 | 0  | 0  | 6  | 0 |
| SHORT (4 silos) | 7.584   | 7.584   | 0  | 0  | 0  | 0  | 0 |

- **El muro se desplazó como esperaba la notebook:** 375 candidatos LONG cruzaron el gap
  (vs 2 en el ciclo 1) y recorrieron el resto del embudo: 136 FAIL_TRADES, 30 FAIL_PF_NET,
  43 FAIL_MONKEY_IS y **166 FAIL_MONKEY_OOS — el verdugo final. Todo el que llegó al último
  gate murió en el listón OOS de 90%.** Cosecha cero de nuevo = dato válido: el monkey está
  haciendo exactamente su trabajo (nada de lo minado tiene edge OOS que supere al azar).
- FAIL_GAP sigue matando al 99,95% **pero ya por la razón correcta**: con fricción 1.0,
  la mayoría de candidatos se estanca >5000 velas dentro del propio Z1+Z2 (no por Zona 0).
- SHORT: sin cambios (7.584 candidatos, todos FAIL_GAP; el oro alcista no da reglas SHORT
  netas que progresen).
- XS_IS/XS_OOS: N/A otra vez (cero PASS).

### Costo real del monkey a 5000 monos: NO es cuello de botella

Primera medición empírica (209 candidatos llegaron al monkey, ~375 invocaciones de
`monkey_test` de 5000 monos × 2 zonas):

| Silo | L3 ciclo 1 (sin monkey) | L3 ciclo 2 (con monkey) | Llamadas monkey |
|---|---|---|---|
| LONG MOMENTUM | 35,7 s | 67,9 s | ~103 |
| LONG TREND | 33,7 s | 35,9 s | ~116 |
| LONG VOLATILITY | 37,9 s | 34,0 s | ~144 |
| LONG CYCLE | 32,6 s | 40,6 s | ~12 |

El +32 s de LONG_MOMENTUM es **compilación JIT de primera vez** del kernel del monkey
(cacheada en disco después): los silos siguientes corrieron cientos de monkey-calls por
~0-8 s extra (~20-80 ms por llamada de 5000 monos). **Veredicto: a esta tasa de
supervivientes el monkey cuesta segundos por silo; no hay nada que optimizar.** Ciclo
completo: 379,4 s (~6,3 min; +38 s vs ciclo 1).

**Para la lectura de NOTEBOOK:** el sistema está sano (embudo ordenado, monkey activo y
letal, telemetría completa). La pregunta ya no es infraestructura sino minería: si tras N
ciclos el MONKEY_OOS al 90% sigue matando al 100% de los finalistas, lo que falta es
calidad de hipótesis (familias/ADN/targets), no más candidatos.

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
