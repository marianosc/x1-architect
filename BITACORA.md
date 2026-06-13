# BITÁCORA X1-ARCHITECT

> Hallazgos y decisiones entre sesiones (notebook ↔ blanca). Lo más nuevo arriba.

## 2026-06-13 — [NOTEBOOK] Gate de calidad de datos + set multi-activo Dukascopy validado

**Herramienta nueva:** `tools/check_data_quality.py` — gate PASS/WARN/FAIL para data M1 antes de
minar. Chequea estructura/columnas, monotonía y duplicados de tiempo, sanidad OHLC, cobertura por
año, DST (hora de apertura tras finde, verano vs invierno) y **costuras intra-sesión** distinguidas
de los gaps legítimos de fin de semana (la firma del defecto que pudrió al EURUSD viejo: 81 saltos
>1%/año por CSV concatenado). Umbrales: costuras >10/año WARN, >40/año FAIL; volumen como INFO (no
afecta veredicto). Uso: `python tools/check_data_quality.py [archivos...]` o glob en `data/`.

**Data nueva de Mariano (Dukascopy M1, EST+7 = UTC+2 FIJO sin DST, 2003→2026):** 7 activos bajados
y pasados por el gate:
- **XAUUSD → PASS** (7,85M filas, OHLC perfecto, peor año 8 costuras; apertura hora 1 = la sesión
  del oro abre 1h más tarde que forex, sin DST). La casa de calibración con historia completa 2003+.
- **EURUSD → PASS** (re-descarga limpia: 4 costuras totales vs los 81/año del podrido de Darwinex).
- **USDJPY → PASS.**
- **EURGBP → WARN** (31 costuras en 2008 = colapso real de la libra; termina 09-jun, 3 días corto).
- **GBPUSD / GBPJPY / EURJPY → WARN**, todos por costuras que al inspeccionar son EVENTOS REALES:
  Brexit (2016-06-24 02:17, idéntico en los 3 pares), flash crash de la libra (2016-10-07), crisis
  2009. Ninguno es corrupción.

**Veredicto:** set multi-activo COMPLETO y validado, todos UTC+2 fijo (confirma EST+7 sin DST).
**Flag de volumen:** Dukascopy lo entrega en escala propia (~1e8 forex, ~2e4 oro) → genes con
volumen (MFI/force) NO comparables con el tick del broker; calibrar o usar volumen solo relativo.
Para minar (diversidad > cantidad por multiplicidad/DSR): **XAUUSD + EURUSD + GBPUSD + USDJPY +
EURGBP**; EURJPY/GBPJPY quedan archivados (correlacionados).

**Para blanca:** el gate ya está en el repo; pasá toda data nueva por él antes de minar. Pendiente de
diseño (notebook + Mariano): ingestión de estos CSV en L1 (nombres `2026.6.13<PAR>_M1_*`, formato
`DateTime,Bid,Ask,Volume,Open,High,Low,Close`) + zonificación con el sello pre-2015.

## 2026-06-12 — [NOTEBOOK] DIRECTIVAS v108: el cuello de botella es el MINERO — minero evolutivo + gramática formulaica

**Diagnóstico (aprobado por Mariano):** el tribunal v107 quedó validado; lo que bloquea el
descubrimiento de alpha es el GENERADOR de hipótesis. Tres debilidades del L2 actual:
1. **Búsqueda uniforme-aleatoria**: 500k tiradas independientes sin aprendizaje entre
   candidatos — eficiencia de búsqueda casi nula en un espacio astronómico.
2. **Gramática pobre**: solo `indicador OP umbral/indicador`. No puede expresar conceptos
   relacionales: "RSI subiendo" (delta), "ATR en su percentil 90 de 100 velas" (ts_rank),
   "cruce de EMAs", "distancia al máximo de N velas". Nota: el único tema que llegó a
   asomar (dip-buy en tendencia) es justamente un concepto RELACIONAL.
3. **Fitness = PF en Z1 entero**: selecciona picos de suerte (maldición del ganador medida:
   decil alto de mk_IS → peor OOS).

**Estado del arte público relevante (revisado por notebook):** WorldQuant "101 Formulaic
Alphas" (gramática de operadores temporales), gplearn/DEAP (programación genética),
AlphaGen (RL-MLDM, generación de alphas formulaicos por RL), Genetic-Alpha, GeneTrader.
Veredicto: NO importar codebases (perderíamos la calibración MT5); PORTAR los conceptos
al motor X1, como se hizo con monkey/XS/DSR.

### TAREA v108 PARA BLANCA (en orden, commit por bloque):

**v108.1 — GRAMÁTICA FORMULAICA (regla de oro intacta: nada sin traducción MQL5):**
Operadores nuevos sobre los genes existentes, cada uno con helper X1_* en el traductor:
- `delta_K(x)` = x_hoy − x_hace_K velas (K ∈ {3,8,21})
- `ts_rank_W(x)` = percentil de x en sus últimas W velas (W ∈ {50,100,250})
- `dist_max_W` / `dist_min_W` = distancia % del Close al máximo/mínimo de W velas
- `cross(a,b)` = a cruzó por encima de b en las últimas K velas
- `slope_K(x)` = pendiente OLS de x en K velas (ya existe X1_LINREG para Close; generalizar)
Implementación L1: columnas derivadas precalculadas (el Parquet crece — elegir subconjunto
con criterio, ~30-50 columnas nuevas máx). Tests de paridad TA-Lib/NumPy↔MQL5 por operador.

**v108.2 — MINERO EVOLUTIVO (reemplaza la tirada uniforme):**
- Población por silo (~2.000), torneo, cruce de condiciones, mutación de umbral/período/
  operador, ~30-50 generaciones, islas por familia con migración baja.
- **FITNESS ANTI-MALDICIÓN (clave): mediana del PF neto en los 8 bloques de Z1** (los del
  PBO/CSCV ya implementados) − penalización por complejidad (nº condiciones). PROHIBIDO
  mirar Z2 en el fitness: Z2 sigue siendo del tribunal, no del minero.
- Presupuesto comparable al actual (~500k evaluaciones/silo) para autopsias comparables.
- DEAP permitido como dependencia si acelera; si no, GA propio en numba.

**v108.3 — EXPERIMENTO DE VALIDACIÓN DEL MINERO:**
Mismo tribunal v107, XAUUSD H1 y H4: ciclo con minero evolutivo vs baseline aleatorio
(0 PASS). La pregunta NO es solo "¿pasa algo?" sino "¿el embudo se puebla mejor?"
(candidatos que crucen gap, lleguen al monkey, distribución de mk_oos). Autopsia comparable.

**GOBERNANZA DE DATOS (recordatorio):** los CSV nuevos que baje Mariano (ver abajo) pasan
TODOS por el gate de calidad ANTES de cualquier uso. XAUUSD 2003-2015 y el tramo análogo
de los activos nuevos quedan SELLADOS para minería (solo validación final ex-ante).

**DATA ENCARGADA A MARIANO (Dukascopy, M1, UTC+2 FIJO sin DST, formato flat CSV idéntico
al actual, sin filtro de sesión, destino Z:\...\38_42_X1_V_105 SISTEMA X1 PYTHON\data\):**
1. XAUUSD — historia COMPLETA disponible (~2003→hoy) en un solo archivo consistente
   (reemplaza al actual: un solo origen, sin costuras).
2. XAGUSD (plata) — historia completa (el metal pedido).
3. USA500.IDX/USD (S&P 500) — historia completa (el índice; más historia y liquidez que
   el tech en Dukascopy).
4. EURGBP — historia completa (la divisa SIN tendencia histórica: el par lateral clásico,
   test perfecto para edges que no sean surfear deriva).
5. EURUSD — re-descarga completa limpia (para desbloquear el pipeline y, de paso,
   confirmar contra el CSV podrido dónde estaban las costuras).

## 2026-06-12 — FASE 3: M30 nulo limpio + EURUSD H4 "9.928 PASS" = DATOS PODRIDOS (descartado entero)

**M30 XAUUSD** (escala ×2 desde H1: Stag 10000, Min_Trades 600, cooldown 50, señales 400):
**0 PASS.** El prior bajo se confirma: con fricción realista el peaje relativo ahoga a M30
(SHORT colapsa a 1-19 candidatos en L2). Mapa de timeframes XAUUSD cerrado: M30 muerto,
H1 estéril, H4 vivo-pero-vacío bajo lente honesto.

**EURUSD H4 — LA TRAMPA DE LA NOCHE:** 9.928 PASS con PF de 24-26 y pf_oos de 114 (!).
Demasiado bueno para ser verdad, y lo era. Auditoría (`tools/audit_eurusd_anomalia.py`):
- Retorno medio **+287 bps por trade** con 8 velas de tenencia — imposible para EURUSD.
- **893 saltos >1% en H4**, repartidos uniformes (80-118 POR AÑO, 2015-2025).
- Top saltos: **±12-16% en costuras de fin de mes** (2015-11-30→12-01: 1.056→1.186;
  2022-09-30→10-01: 0.980→1.135; 2025 con reversas de −12% mensuales). EURUSD jamás cotizó
  esos niveles en esas fechas: el CSV fuente es una **concatenación con bases distintas por
  tramo** (¿futuros con roll sin ajustar? ¿mezcla de fuentes?).
- Mecanismo del falso edge: los escalones revierten en la serie pegada → las reglas de
  `roc` extremo los cosechan en AMBAS direcciones; los monos (timing aleatorio) no.
**Veredicto: cosecha EURUSD descartada al 100%. Pipeline EURUSD BLOQUEADO hasta re-descargar
datos limpios.** Ojo: el `X1_FULL_EURUSD_H1.parquet` histórico de la COSECHA de Z: viene del
MISMO CSV — cualquier resultado EURUSD previo está bajo la misma sombra.

**Dos pendientes de Constitución EURUSD para Mariano:** (1) la fricción de assets.csv
(0.5+0.2+0.3 = 1.0 pts sobre precio ~1.1 = 83%/trade) está mal escalada — esta noche se usó
override provisional 0.0001 (~1 pip); falta calibración canario EURUSD. (2) Propuesta: gate
de CALIDAD DE DATOS en L1 (abortar/alertar si saltos>1% superan un umbral por año — XAUUSD
tiene 9/año, este EURUSD 81/año).

## 2026-06-12 — FASE 2: RE-MAPEO CON EL LENTE CORREGIDO — la cosecha de la semana queda en CERO real

**Verificación del fix (fantasma v107, 20k LONG MOMENTUM H1):** el artefacto desapareció —
Spearman solape↔mk_oos colapsó de **+0.425 a +0.036**, y la tasa de paso OOS por salida quedó
en 2-17% en todos los cohortes (antes: 94% en Ret_96). El instrumento ya mide timing.

**Los tres mapas, todos 0 PASS (artefactos en experimentos/F2_*):**
| Mapa | Candidatos | Nota |
|---|---|---|
| H1 oficial v107 | 977.087 | Frontera VACÍA incluso a mk_oos≥50 + PF 1.05 + XS: H1 es estéril |
| H4 escalado v107 | 1.250.093 | Embudo más rico (miles cruzan el gap) pero **mk_IS ahora mata de verdad** (antes la palanca regalaba IS=100): 0 PASS |
| H1C4 re-test B3 limpio | 971.487 | **El null de B3 ahora es real, no condicionado**: el contexto H4 no desbloquea H1 |

**Re-auditoría dirigida de los 2 "honestos" de C1 bajo v107:**
| Regla | trades v107 (viejo) | mk_is | mk_oos | Veredicto |
|---|---|---|---|---|
| `adx_34>=27 & minus_di_8>=19.7` | 111 (177) | 94.4 | **79.5** | FAIL |
| `aroon_120>=-3.4 & plus_di_34<=17.8` | 160 (229) | 78.1 | **40.2** | FAIL |

La "media de solape 1.0×" escondía la distribución: trades individuales con duración > cooldown
apilaban igual. **Nada de lo cosechado esta semana sobrevive al motor honesto.** El Reality
Check MT5 queda sin candidatos (los EAs H4TREND01/02 se conservan como referencia histórica).

**Honestidad R4 sobre XS_IS:** bajo v107 su poder predictivo NO es robusto (+0.076 global,
+0.026 n.s. en el subset corto). El +0.36 de anoche era en gran parte gradiente de palanca
entre cohortes. El umbral 0.55 en la frontera tampoco rescata nada (0 en todas las celdas).
Lo que SÍ queda visible con el lente limpio: la **maldición del ganador** (decil 9 de
monkey_is → el PEOR pf_oos: 1.652 vs 1.865 del decil 0) y que expo/beta/oer altos = surfear
el régimen alcista, no habilidad.

**Conclusión Fase 2:** con el instrumento ya confiable, la minería aleatoria sobre este ADN
no produce NADA en XAUUSD H1 ni H4, ni con listones oficiales ni de frontera. La vía que
queda es la fase de hipótesis dirigidas (y/o ADN nuevo), midiendo con este lente.

## 2026-06-12 — FASE 1 (opción B aprobada): POSICIÓN ÚNICA en el motor — v107

**Cambio:** `x1_engine.simulate()` con `single_position=True` por DEFAULT.
- **Fijas Ret_N:** espaciado ≥ max(cooldown, **N+1**) — la vela de cierre consume la
  oportunidad porque el EA hace `return` tras `PositionClose`. El +1 está verificado contra
  MT5: la calibración del canario (Ret_24, cooldown 25 → espaciado 25) coincidió 96,7% con
  el tester, y este fix la deja intacta.
- **Sintética:** caminata busy-until en numba (`_synthetic_single_core`) con duración
  dinámica: una entrada aceptada bloquea hasta su cierre real + cooldown desde la entrada.
- **L2 mina con la misma semántica** (espaciado por salida + sintética busy-walk): el minero
  ya solo selecciona lo que el EA puede ejecutar.
- `single_position=False` conserva la semántica vieja (regresión/comparaciones históricas).
- **Tests 36/36** (12 motor incl. 4 nuevos: espaciado fijas, busy sintética, regresión modo
  viejo, simetría estrategia-mono p=0.080 no extremo; 13 validators; 8 traductor; 3 zona0).

**PROPUESTA Min_Trades (pendiente de aprobación de Mariano):** con posición única el máximo
de trades es ≈ velas/espaciado, así que un Min_Trades global castiga a las salidas largas.
Propongo **Min_Trades dinámico por candidato = max(30, 25% × velas_Z1 / espaciado)**, donde
espaciado = max(cooldown, N+1) (fijas) o duración_media+1 (sintética). El 25% de ocupación
está calibrado para reproducir el 300 oficial de H1-Ret_24 (0.25×29.766/25 = 298 ≈ 300):

| Salida | H1 (Z1=29.766) | H4 (Z1=7.441) | M30 (Z1≈59.5k) |
|---|---|---|---|
| Ret_12 | 573 | 143 | 1.145 |
| Ret_24 | **298 (≈300 actual)** | 74 (≈75 usado anoche) | 595 |
| Ret_48 | 152 | 38 | 304 |
| Ret_96 | 77 | 30 (floor) | 153 |
| Sintética (dur media d) | 0.25×Z1/(d+1) | ídem | ídem |

Hasta esa aprobación, los ciclos de Fase 2-3 corren con los Min_Trades actuales (300 H1 /
75 H4 escalado) — la asimetría contra salidas largas queda documentada y el modo fantasma
captura todo igual.

## 2026-06-12 (noche) — PROGRAMA NOCTURNO en rama `experimentos-nocturnos` (entradas incrementales abajo)

### A2+A3+A4+B1 — EL HALLAZGO DE LA NOCHE: el monkey premia apilamiento, no timing — y al corregirlo, XS_IS se vuelve EL predictor

**A2 (modo fantasma):** `tools/ghost_audit.py` auditó 20.000 candidatos LONG MOMENTUM H1 SIN
early-returns (todos los gates + momentos OOS + 8 bloques Z1), 26 s. Parquet en C:\temp.

**EL ARTEFACTO (descubierto auditando la sonda A4):** el motor imputa `Ret_N` en cada entrada
con cooldown 25: si N>25 simula una cartera PIRAMIDADA (Ret_96 = ~4 posiciones concurrentes)
que el EA real (una posición por vez) **nunca va a ejecutar**. El mono usa `busyUntil` y no
puede apilar → el p-value escala con el solape, no con el timing:

| Exit | solape | mediana mk_oos | % pasa 90 |
|---|---|---|---|
| Ret_12 | 0.5x | 54.6 | **10,3% = azar** |
| Ret_24 | 1.0x | 69.6 | 32,8% |
| Ret_48 | 1.9x | 94.1 | 55,8% |
| Ret_72 | 2.9x | 100 | 67,1% |
| Ret_96 | 3.8x | 100 | **94,2% = apalancamiento** |
| SINTETICA (expo~18) | 0.7x | 67.5 | 13,3% |

Spearman solape↔mk_oos = +0.425. El 91% del pool elige Ret_96 como mejor salida (L2 ama la
piramidación del bull). **La calibración del canario no lo vio porque Ret_24 < cooldown 25.**
Esto también re-lee el ciclo 3 (0/212): los que llegaban al gate eran mezcla; el resultado
"anti-edge" del pool completo estaba contaminado en ambas direcciones.

**A3 (correlaciones IS→OOS):** en el pool completo las correlaciones están dominadas por el
gradiente de apalancamiento (pf_is ANTI-predice mk_oos −0.26). Pero en el **subset honesto
sin solape (expo≤25, n=389 — lo único EA-implementable tal cual)** los signos SE INVIERTEN:

| metrica IS | vs pf_oos (honesto) |
|---|---|
| **xs_is** | **+0.359** (p=3e-13) — y +0.509 contra xs_oos |
| beta_is | +0.359 |
| PF_L2 / pf_is | +0.31 |
| stag | −0.18 (menos estancamiento, mejor) |

**El filtro que faltaba existe y es XS_IS (Tomillero)** — pero solo vale en el espacio sin
solape. En la cohorte Ret_96 (apalancamiento constante) pf_is/xs_is vuelven a anti-predecir:
ahí adentro solo hay overfitting.

**A4 (frontera):** pool completo: 5 cruzan gates fijos, 4 "pasan" todo (espejismo apalancado).
**Subset honesto: 0 de 389 cruzan siquiera los gates fijos** (trades_is≥300 + mk_is≥99 son
inalcanzables sin apilar). → El embudo oficial estructuralmente EXCLUYE lo implementable y
cosecha lo no-implementable. Decisión de diseño para NOTEBOOK: (a) salidas ≤ cooldown en L2,
o (b) motor con `busyUntil` (semántica EA), o (c) EA piramidal; y recalibrar Min_Trades para
el espacio honesto.

**B1 (institucionales):** t-stat/PSR/DSR computadas (columnas fantasma). DSR con N=1M pruebas:
solo 813/20.000 sobreviven DSR≥0.95 aun CON apalancamiento (SR0=0.20/trade es el listón de
multiplicidad). PBO (CSCV, 8 bloques Z1) = **0.29** — overfitting moderado a nivel pool.
Caveat honesto: t-stat/PSR/DSR acá están computadas SOBRE OOS → sirven como veredicto final,
no como filtro de selección (sería lookahead). La accionable para seleccionar es XS_IS.

**Veredicto (1 línea):** el bug semántico motor-apila/EA-no-apila invalida el grueso de la
cosecha histórica de salidas largas; corregido el lente, XS_IS es el primer predictor IS→OOS
real del proyecto.

### B3 — ADN inter-timeframe (contexto H4 sobre H1): NULO bajo listones oficiales — pero condicionado al bug de solape

**Hipótesis (prior alto de Mariano):** el contexto de tendencia H4 (ema/adx/linreg/efficiency
×{21,55,120}) desbloquea a H1. **Cambio exacto:** `tools/build_h4_context.py` construye
`X1_FULL_XAUUSD_H1C4.parquet` (301 cols) con merge_asof backward — la vela H4 usada está
SIEMPRE cerrada al momento de la vela H1 (**verificación anti-lookahead: 0 violaciones**).
Los 12 genes `*_h4x*_sft` entraron al pool TREND (132 genes, verificado). 8 silos con
constitución H1 oficial.

**Resultado: 0 PASS en los 8 silos.** LONG TREND (donde vive el contexto): 234.873 candidatos,
56 llegaron a MK_OOS, 0 pasaron. El muro FAIL_GAP de H1 sigue intacto: el contexto H4 no
cambia que el espacio honesto H1 no alcanza los gates (A4) y que el espacio apalancado es
espejismo (A2.5).

**Veredicto (1 línea):** nulo bajo el embudo actual — PERO la hipótesis merece re-test
después del fix de solape: B3 se midió con un embudo que estructuralmente no puede cosechar
H1 honesto, así que este nulo es del embudo, no necesariamente de la hipótesis.

### B2 — Features de sesión (hour/dow): RESULTADO NULO bajo listones oficiales

**Hipótesis:** la estructura horaria del oro (Asia/Londres/NY) tiene edge que los osciladores
no capturan. **Cambio exacto:** `hour`/`dow` como genes minables en L1 (con shift _sft;
dow en convención MQL5 1=Lun..5=Vie), asignados a la familia CYCLE en L2, y traducción MQL5
vía `TimeToStruct` (MQL5 no tiene TimeHour/TimeDayOfWeek — eran MQL4). Cadena completa
validada: EA de prueba con `hour_sft<=8|dow_sft>=2` compila 0 errors (`experimentos/EAs/
SESIONTEST.mq5`); tests del traductor 8/8.

**Resultado:**
- **H1 (constitución oficial): 0 PASS en los 8 silos** — la sesión no rescata a H1.
- **H4 (escala ÷4): 0 reglas con hour/dow entre los PASS.** El silo CYCLE (único lugar donde
  hour/dow pueden liderar una regla) dio 0 PASS en ambos TF. Los 10+2 PASS de MOMENTUM/TREND
  H4 son (a) el dip-buy `roc_55<=-2.79` de siempre + variación de semilla y (b) conteo
  inflado por la re-auditoría retroactiva de los MASTERs que dejó C1 (no comparable con A1).

**Veredicto (1 línea):** bajo listones oficiales la hipótesis de sesión NO aporta finalistas
en XAUUSD H1/H4; queda el ADN y la traducción listos por si se quiere sondear con listón
FRONTERA u otra familia de salida.

### C1 — Estabilidad por semilla de los finalistas H4: el TEMA es estable, las reglas no

**Cambio exacto:** re-minado virgen (MASTER borrado antes de cada corrida para evitar la
re-auditoría retroactiva) de LONG TREND y LONG MOMENTUM H4, 2 semillas frescas cada uno.
Artefactos: `experimentos/C1_seeds/`.

| Semilla | TREND PASS | MOMENTUM PASS |
|---|---|---|
| A1 (original) | 1 | 6 |
| seed 1 | 2 | 5 |
| seed 2 | 2 | 6 |

- **MOMENTUM: `roc_55_sft <= -2.79` reaparece en TODAS las semillas** (con confirmaciones
  variables). Patrón estable del paisaje — pero sigue con solape ~2× (FRONTERA*).
- **TREND: el tema reaparece, la regla no.** Las 5 reglas PASS entre semillas comparten la
  estructura "ADX/aroon presente + presión alcista DÉBIL (plus_di≤18 / minus_di alto /
  macdh<0) → comprar" pero ninguna se repite literal. De las 4 nuevas, solo
  `aroon_120>=-3.42 & plus_di_34<=17.77` es limpia de solape (1.0×).
- **Set honesto final de la noche: 2 reglas** (`adx_34>=27 & minus_di_8>=19.7` de A1 y
  `aroon_120>=-3.42 & plus_di_34<=17.77` de C1-s1), mismo tema económico, solape 1.0×,
  mk_OOS 92.6 / 91.1. Con 1.35M de pruebas por ciclo siguen siendo FRONTERA (multiplicidad).
- **EAs listos y compilados (0 errors):** `experimentos/EAs/H4TREND01.mq5` y `H4TREND02.mq5`
  (cooldown 6). **Plan Reality Check MT5 (no corrido desatendido):** Strategy Tester XAUUSD
  H4 2023-06-05→2025-12-09, comparar trades vs `x1_engine.simulate` con el comparador del
  canario adaptado; criterio: match >95% y residual <0.5 pts%.

**Veredicto (1 línea):** el tema "comprar debilidad en contexto de tendencia H4" es estable
por semilla y honesto de solape; las reglas individuales son intercambiables → es un
CANDIDATO A HIPÓTESIS DIRIGIDA, no un alpha puntual.

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

**ENMIENDA post-A2 (artefacto de solape):** medidas las duraciones reales de los 5 finalistas
contra cooldown 6: los 4 de MOMENTUM tienen solape **2.0-2.1x** (duración media ~12 velas H4)
→ su monkey_OOS 90-91 es sospechoso de apalancamiento implícito, se degradan a FRONTERA*.
**El de TREND (`adx_34>=27 & minus_di_8>=19.7`) es LIMPIO: solape 1.0x (duración media 6.2)**,
PF 5.34, R2 0.97, mk_OOS 92.6 — el único finalista honesto de la noche. Sigue siendo 1 entre
1.35M de pruebas (multiplicidad): prometedor, no validado.

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
