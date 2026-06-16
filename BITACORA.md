# BITÁCORA X1-ARCHITECT

> Hallazgos y decisiones entre sesiones (notebook ↔ blanca). Lo más nuevo arriba.

> 🖼️ **NUEVO — log de desarrollo VISUAL en `docs/desarrollo.html`** (pedido de Mariano): cada avance
> numérico deja su gráfico ahí. Las preguntas abiertas también están ahí. Regenerar con
> `python tools/graficar_desarrollo.py`.

## 2026-06-16 — [BLANCA] B1 CONFIG CERRADA: barrido + validación EURGBP → **n=1000 + Q25**

Ejecutado el barrido que pidió NOTEBOOK con el JUEZ JUSTO (EURGBP sin tendencia, donde la beta no
contamina). Ingerí EURGBP (gate WARN benigno: las 31 costuras son del colapso real de la libra 2008,
en Z0 sellada; assets.csv con Z1_Start 2015 / Z2_Start 2022, fricción forex aprox). Pools LONG MOM+TREND
minados en Z1. Gráfico: `docs/desarrollo/v108_b1_tuning.png`.

**Barrido n∈{400,1000} × {mediana,Q25}, juez = Spearman(fit,mk_z2) + de-sesgo beta (top %largo) + EURGBP:**

| config | rho XAUUSD | rho EURGBP | top %largo XAUUSD | top %largo EURGBP |
|---|---|---|---|---|
| pf_is (naive) | +0,161 | +0,156 | 78% | 12% |
| fitness mediana (n=1000) | +0,192 | +0,041 | 56% | **64%** ⚠️ |
| **fitness Q25 (n=1000)** | +0,183 | +0,092 | 56% | **14%** ✅ |

**Decisión (regla de NOTEBOOK "Q25 solo si EURGBP lo respalda"): Q25 GANA claro.** En EURGBP la mediana
NO de-sesga (top 64% horizonte largo) y Q25 sí (14%), con mejor coherencia (rho +0,09 vs +0,04). n=400 y
n=1000 dan casi igual en Q25 (+0,091 vs +0,092); elijo **n=1000** (menor varianza por fold, como sugirió
NOTEBOOK). **`fitness_v108.py` queda con `agg='q25'` por default.** n_monkeys sigue per-call (300-500
evolución / 5000 finalistas, según spec).

**Honestidad (R4):** el fitness le gana al naive **donde la beta contamina** (XAUUSD bull: de-sesga
78%→56%, Spearman +0,18 vs +0,16). En el mercado limpio (EURGBP) ambos van parejos en rho (Q25 +0,09 vs
pf_is +0,16, pero pf_is ahí ya tiene 12% largo = no necesita de-sesgo). O sea: el fitness **se gana el
sueldo exactamente cuando hace falta** (régimen con beta), que es el caso realista del GA. P1/P2/P3
respondidas y reflejadas en `docs/desarrollo.html`.

**Siguiente:** B2 (gramática formulaica) — lo arranca NOTEBOOK cuando vuelva Mariano (spec abajo). Herramientas:
`tools/barrido_b1.py`, `experimentos/barrido_b1.csv`.

## 2026-06-16 — [NOTEBOOK] B2: especificación de la GRAMÁTICA FORMULAICA (operadores TS + factory on-demand)

Diseño tras estudiar `x1_engine.py` (motor) y `translator_mql5.py` (registro). **El motor NO se toca**
(compara COLUMNAS, semántica única calibrada a MT5); se amplía el VOCABULARIO de tokens vía un
**feature factory on-demand**. Hallazgo: el ADN v106 ya tiene operadores formulaicos "disfrazados"
(`mom`=delta precio, `roc`, `slope`=pendiente EMA, `linreg`, `efficiency`, `vol_z`) pero SIEMPRE sobre
precio/EMA. Falta aplicarlos a CUALQUIER indicador.

**OPERADORES v1 (4; `cross`→v2 por requerir estado t-1/t-2):**
- `delta_K(x)`  = x[t] − x[t−K]
- `slope_K(x)`  = pendiente OLS de x sobre K barras (como linreg pero del indicador)
- `ts_rank_W(x)` = #{ x[t−i] < x[t] , i=1..W−1 } / (W−1) ∈ [0,1]   ⭐ (normaliza nivel → robusto a régimen)
- `dist_max_W(x)` = x[t] − max(x[t−W+1..t]) ; `dist_min_W(x)` = x[t] − min(...)

**BASES (6):** rsi, natr, adx, cci, mom, close. **VENTANAS:** K∈{3,5,10} (delta/slope); W∈{20,50,100}
(ts_rank/dist). **TOKEN:** `{op}{param}_{base}_sft` — ej. `tsrank100_natr_14_sft`, `delta5_rsi_14_sft`.

**CLAVE DEL SHIFT (paridad):** el factory computa el operador SOBRE la columna `_sft` que ya está en
el Parquet → el resultado ES la versión `_sft` del operador (porque `x_sft[t]=x[t−1]` ⇒ `op(x_sft)=op(x)_sft`).
No hace falta la serie cruda. El minero usa el token `_sft` directamente; el motor lo compara como una
columna más.

**B2a (AHORA — Python, para experimentar):**
1. `modules/formulaic.py`: `expand_formulaic(data, col_map, tokens)` → computa SOLO las columnas
   formulaicas que la población usa, las agrega a la matriz en memoria + col_map (numpy/numba). NO
   pre-computar todo en L1 (evita explotar el Parquet).
2. Integrar antes de simular en L2 (minero) y en el fitness B1 / L3 (expandir los tokens de la población).
3. Tests de cómputo de cada operador (valores correctos vs numpy de referencia) + determinismo.
4. **CONTROL (¿aporta?):** aplicar el fitness B1 a un pool con vocabulario AMPLIADO vs gramática vieja
   → ¿aparecen candidatos con mejor fitness/transferencia? Reportar (mismo juez beta-neutral: Spearman
   + de-sesgo + EURGBP).

**B2b (SOLO si B2a aporta):** helpers `X1_*` MQL5 de cada operador (componiendo sobre el indicador base)
+ test de PARIDAD Python↔MQL5 + extender `_resolve_operand`. Cierra la regla de oro.

**REGLA DE ORO (matizada, decisión notebook):** se mina en Python (B2a) para EXPERIMENTAR barato, pero
NINGUNA alpha con operadores formulaicos se COSECHA/DESPLIEGA sin su traducción+paridad (B2b). El gate de
oro pasa de "antes de minar" a "antes de cosechar" — no se pierde la garantía de deploy, y no traducimos
operadores que no demuestren aportar. (Si Mariano prefiere la regla estricta, hacemos B2a+B2b juntos.)

Orden de trabajo en blanca: primero cerrar el barrido de B1 (abajo), después B2a. Pushear con tests + control.

## 2026-06-16 — [NOTEBOOK] Respuestas a P1/P2/P3 + B1 tuning: barrido + validación EURGBP (juez beta-neutral)

B1 VALIDADO (notebook reprodujo los números exactos: fitness +0,202 > pf_is +0,168 vs mk_oos_z2;
de-sesga beta = 38% Ret_96 en el top vs 80% del pool). Mecanismo de `fitness_v108.py` aprobado.

**INSIGHT del top-50 (clave):** pf_is gana el top-50 (58 vs 47) **porque Z2 2022-26 es un bull y pf_is es
más beta-pesado (58% Ret_96)**. La "verdad" `mk_z2` sobre un Z2 alcista está **sesgada a favor de la
beta** → NO es juez justo del fitness beta-neutral; tunear B1 para ganar ese top-50 sería overfittear el
fitness al régimen alcista. El fitness de-sesga beta correctamente = robustez.

**RESPUESTAS:**
- **P3 → ROBUSTEZ** (no pico). El fitness (mediana de mk_oos sobre folds, beta-neutral) ya prioriza
  robustez/consistencia. Mantener. El "pico" es la maldición del ganador / la beta.
- **P2 → NO reabre el rumbo, seguimos B2.** El +0,168 es señal débil **REAL** (no anti-edge absoluto;
  parte del anti-edge previo era artefacto de la data vieja: Z2 2023-25 re-usada + costuras). Rumbo
  igual (cuello = generador), pronóstico mejor (hay base débil que B2/B3 pueden amplificar).
- **P1 → SÍ al barrido, pero con el JUEZ correcto.**

**TAREA BLANCA — cerrar la config de B1:**
1. Barrido `n∈{400,1000}×{mediana,Q25}` sobre el pool fresco.
2. **Validación cruzada en EURGBP** (sin tendencia → la beta no contamina → juez JUSTO del fitness).
   Ingerirlo con L1 si falta (agregar Z1_Start=2015-01-01 / Z2_Start=2022-01-01 a assets.csv; fricción
   forex APROXIMADA alcanza para validar, no es deploy; el gate ya dio EURGBP sano-WARN-benigno).
3. **JUEZ del barrido (NO el top-50 `mk_z2` del Z2 alcista):** (a) Spearman global vs mk_oos_z2, (b)
   de-sesgo de beta (% horizonte largo bajo en el top), (c) coherencia en EURGBP. Elegir la config que
   maximice robustez/de-sesgo, no el pico alcista.
4. **Config base recomendada:** n=1000 + mediana (n alto baja la varianza por fold); Q25 solo si EURGBP
   lo respalda. Reportar la tabla + la config elegida y pushear.

**B2 (gramática formulaica) lo arranca la NOTEBOOK cuando Mariano vuelva** (se mueve a la oficina).

## ❓ PREGUNTAS ABIERTAS PARA NOTEBOOK (Mariano contesta desde la notebook) — 2026-06-15

- **P1 (B1 tuning):** el fitness bate al naive en lo grueso (+0,20 vs +0,17) pero su top-50 no supera al de
  pf_is (mk_z2 47 vs 58). Knobs: n_monkeys (400→800/1000), agregación mediana vs **Q25** (Q25 afinó: top 52,
  5/50 pasan ≥90), la regla `n_valid<K/2⇒0`, y λ. **¿Corro el barrido n∈{400,1000}×{mediana,Q25} y traigo la
  tabla, o fijás la config vos?**
- **P2 (diagnóstico):** en terreno fresco Dukascopy pf_is tiene **+0,168 de transferencia Z1→Z2 real** (no
  ~0/neg como en la data vieja). ¿Reabre algo del rumbo o seguimos firmes con B2 (gramática)?
- **P3 (objetivo):** ¿la brújula del GA prioriza **robustez** (consistencia en folds, lo actual) o **pico**
  (candidatos altos aunque menos consistentes)? Define qué optimiza B3.

## 2026-06-15 — [BLANCA] B1 CONSTRUIDO: fitness CPCV+monkey funciona, pero el terreno fresco cambió el diagnóstico — DECISIÓN PARA NOTEBOOK

**Módulo `modules/fitness_v108.py`** según spec: CPCV-purgado K=6 sobre Z1 (cada bloque = test-fold
OOS-interno; purga de N+embargo en el borde derecho por el solape de Ret_N), cascada (pre-filtro
barato: min_t por fold + PF_fold≤1.0 ⇒ 0 sin gastar monkey; supervivientes → monkey n=400 vía
`monkey_batch` B0), `fitness_core` = mediana de mk_oos por fold (o Q25, knob agregado), parsimonia
`− λ·complejidad`, semilla por **crc32 de la regla** (mismo candidato = mismo fitness siempre).

**Tests `tests/test_fitness_v108.py` (5/5):** candidato SKILL (entra antes de spikes) → 100;
candidato BETA (solo deriva, el monkey LONG lo iguala) → 0; purga del borde → folds inválidos;
determinismo bit-idéntico; parsimonia. **El mecanismo hace EXACTAMENTE lo pedido.** Gracias a B0,
4.000 candidatos × 6 folds × 400 monos = **6 s**.

**Control empírico (spec NOTEBOOK) en pool FRESCO Dukascopy (3.938 cands LONG MOM+TREND, Z1 2015-21,
verdad = monkey honesto Z2 n=1000 — Z2 sólo se usa ACÁ para validar, jamás en el GA):**

| métrica (solo-Z1) → predice mk_oos_z2 | Spearman |
|---|---|
| **pf_is** (lo que el minero usa hoy) | **+0,168** |
| **fitness B1** (mediana) | **+0,202** |
| fitness B1 (Q25) | +0,192 |
| _pf_oos (ve Z2, referencia)_ | _+0,790_ |

- ✅ **El fitness B1 predice la honestidad Z2 MEJOR que el pf_is naive** (+0,20 vs +0,17), siendo
  ambos solo-Z1 — la mejora que NOTEBOOK pedía, y **de-sesga el horizonte beta** (top-fitness 38-40%
  Ret_96 vs 80% del pool).
- ⚠️ **PERO en el top-50** (donde la selección importa) el config actual NO domina: top-por-fitness
  mk_z2 medio 47 (mediana) / 52 (Q25) **< top-por-pf_is 58**. Con n=400/mediana el fitness ordena
  mejor en lo grueso pero no afina el extremo.

**HALLAZGO QUE CAMBIA EL CUADRO (R4, honestidad):** en el terreno fresco/limpio/largo, **pf_is tiene
+0,168 de transferencia Z1→Z2 real** (no ~0/negativo como en el diagnóstico viejo). El "anti-edge
absoluto / todo-beta" era en parte artefacto de la data vieja (Z2 2023-25 re-usada + costuras). Acá
hay señal débil pero REAL, y tanto pf_is como fitness la capturan parcialmente.

**DECISIÓN PARA NOTEBOOK (B1 es tu brújula, no la cierro yo):** el mecanismo está correcto y
unit-probado; globalmente bate al naive; pero la nitidez en el top depende de knobs ya expuestos:
(a) **n_monkeys** (400→1000+ baja la varianza por fold), (b) **agregación** mediana vs Q25 (Q25
afina el top), (c) la regla **n_valid<K/2 ⇒ 0** (quizá muy dura), (d) **λ** de parsimonia.
Mi sugerencia: subir n a 800-1000 y Q25 antes de cablearlo al GA (B3), o aceptar el +0,20 como
brújula "de lo grueso" si la prioridad es robustez sobre pico. Artefacto: `experimentos/
validate_fitness_b1.csv`, runner `tools/validate_fitness_b1.py`.

## 2026-06-15 — [NOTEBOOK] B1: especificación del FITNESS v108 (monkey-OOS + CPCV + cascada + parsimonia)

B0 cerrado y aprobado (monkey paralelo bit-idéntico, `monkey_batch`, ~16×). Diseño del fitness
APROBADO por Mariano (las 5 decisiones + esquema en cascada). Spec para construir B1:

**OBJETIVO:** un fitness por candidato (regla) que mida *cuánto le gana al azar en el OOS-interno de Z1,
robusto y simple*, **neutral a la beta de régimen**. **Z2 (2022-26) INTOCABLE** — holdout final.

**COMPONENTES:**
1. **CPCV sobre Z1 (2015-21):** partir en **K=6** bloques contiguos; folds combinatorios (test = grupos
   de bloques, resto = contexto); **purging** por el solape de Ret_N (purgar velas a ≤N del borde de cada
   test-block) + **embargo**. Cada fold → un OOS-interno.
2. **Cascada por candidato:**
   a. **Pre-filtro barato** (sin monkey): descarta si no pasa el `min_t` dinámico (ya existe) o si PF_IS en
      los folds ≤ ~1.0. Es un colador GRUESO (solo basura obvia), NO el juez.
   b. Los que pasan → **monkey REAL reducido (n=300-500)** vía `monkey_batch` (B0) en cada test-fold OOS
      → un `mk_oos` por fold.
3. **Agregación:** `fitness_core` = **mediana** de los `mk_oos` sobre folds (mediana al inicio; Q25 si
   queremos más exigencia de consistencia).
4. **Parsimonia:** `fitness = fitness_core − λ·complejidad` (complejidad = nº de nodos de la regla); λ
   chico al inicio, a calibrar.
5. **n escala:** n=300-500 en evolución; **n=5.000 en finalistas** (selección B4).
6. **Determinismo:** semilla de monos por candidato (RNG thread-local de B0) → fitness reproducible, el GA
   no persigue ruido.

**VALIDACIÓN de B1 ANTES de meterlo en el GA (control barato):** aplicar este fitness a los candidatos
del diagnóstico (`experimentos/transfer_xauusd_h1.csv` o re-minado con gramática vieja) y confirmar que
**ordena bien**: los que tenían `pf_oos` alto por **beta al bull** deben quedar con **fitness BAJO** (el
monkey los mata). Reportar: correlación fitness↔mk_oos real, y que la beta-LONG-larga ya NO lidera el
ranking. Si el fitness honesto manda la beta al fondo, B1 queda validado.

**Restricciones:** no tocar Z2; no meter SL/TP (alpha pura); pushear con tests. Tras B1 validado → B2
(gramática formulaica) y B3 (GA + warm-start).

## 2026-06-15 — [BLANCA] B0 LISTO: monkey paralelo con paridad BIT-IDÉNTICA → 5,5 h pasa a ~14 min

Tomé el camino recomendado (menor riesgo de paridad): **`nogil=True` en `_monkey_core`**
(único njit del path del monkey) + runner `monkey_batch()` con `ThreadPoolExecutor`.

**Determinismo (lo crítico):** NO hizo falta cambiar el RNG. `_monkey_core` ya re-siembra
`np.random.seed(seed)` al inicio de cada llamada, y el estado np.random de Numba es
**thread-local**, así que cada llamada consume su propia secuencia independiente del thread y
del orden. Resultado: el paralelo es **bit-idéntico al serial Y al histórico** (no cambia
ningún veredicto ya emitido — la cola 0,6%, los 10.931, etc. siguen reproducibles).

**Paridad verificada (`tests/test_monkey_parity.py`, 4/4):** mk_is/mk_oos de 60 jobs
heterogéneos (distinta serie/cadencia/exposición/side/fricción) **idénticos bit a bit** entre
serial y paralelo a {2,4,8,16} threads; orden preservado; determinismo de repetición.
**Suites existentes 4/4 verdes** (validators 13, engine, traductor, L3-zona0) — el `nogil` no
tocó la semántica.

**Speedup (Ryzen 9 9950X3D, 32 cores), 5000 monos × jobs de zona Z1 (~41k velas):**
| threads | ms/job | speedup |
|---|---|---|
| 1 (serial) | 590 | 1.0× |
| 8 | 75 | 7.9× |
| 16 | 42 | 14.0× |
| 32 | 37 | **15.9×** |

→ Los **10.931 × 2 zonas** que tardaban ~3,6–5,5 h serial pasan a **~14 min**. `monkey_tail.py`
ya cableado a dos pasadas (simulate serial → `monkey_batch` paralelo) para cuando se re-corra
sobre el terreno Dukascopy nuevo.

**Nota de método:** loky quedó descartado como diagnosticó NOTEBOOK (pickleaba el G_DF de 162 MB
por tarea); con `nogil`+threading los arrays se comparten en memoria, cero disco. Si en B1 el
monkey se llama desde dentro de otra capa njit, `monkey_batch` sigue sirviendo desde Python.
**B0 cerrado → desbloquea el fitness B1.**

## 2026-06-15 — [NOTEBOOK] RUMBO = Python puro (opción C) + B0: paralelizar el monkey CON PARIDAD (prerequisito del fitness v108)

Mariano decidió el rumbo: **OPCIÓN C — Python puro** (SQX y el curso Quantdemy quedan archivados como
referencia; no se construye sobre SQX aunque haya conectores MCP). **Plan del minero en 5 bloques:**
**B0** paralelizar el monkey · **B1** fitness = monkey-OOS + CPCV + parsimonia (⭐ la brújula, diseño
notebook) · **B2** gramática formulaica (el v108.1) · **B3** motor GA + warm-start (el v108.2) · **B4**
selección DSR + Z2 holdout intocable + reality check MT5. Arrancamos **B0 (blanca)** en paralelo con el
diseño del fitness B1 (notebook + Mariano).

**TAREA BLANCA — B0: que el monkey escale (hoy 5,5 h single-thread).** Es prerequisito: el fitness B1 va
a correr el monkey muchísimas veces, así que tiene que ser barato.
- **Diagnóstico previo:** bajo backend `threading` los kernels `@njit` del monkey corren GIL-serializados
  en 1 core; `loky` paraleliza pero crashea el disco serializando el G_DF de 162 MB.
- **Camino recomendado (menor riesgo de paridad):** `nogil=True` en los kernels njit del monkey
  (`_monkey_core` y los que llame en `modules/x1_validators.py`) → bajo `threading` liberan el GIL → los
  threads paralelizan **a nivel de candidatos** compartiendo G_DF en memoria (cero pickle/disco). Cada
  candidato corre su monkey igual que antes; solo cambia que corren en paralelo.
- **⚠️ CRÍTICO — paridad/determinismo:** el RNG del monkey debe ser **local por llamada** (semilla
  derivada determinísticamente, p.ej. seed base + índice/zona del candidato), NO un estado global
  compartido entre threads (data race → no determinista).
- **Validar:** (a) **test de paridad serial-vs-paralelo** — `mk_is`/`mk_oos` de un set de candidatos
  IDÉNTICO entre la versión vieja serial y la nueva paralela; (b) suite 4/4 verde; (c) reportar el
  speedup (objetivo: los 10.931×5000×2 que tardaban 5,5 h → minutos).
- Si `nogil` no alcanza: alternativa `prange` dentro de `_monkey_core` (paraleliza los N monos) — pero
  cambia la secuencia RNG → re-validar paridad con más cuidado. Pushear el resultado + el test de paridad.

## 2026-06-14 — [NOTEBOOK] DIAGNÓSTICO CERRADO: anti-edge VALIDADO → el cuello es el GENERADOR; foco en diseñar el minero

Notebook **reprodujo los números de blanca de forma independiente** sobre `experimentos/*.csv` (sin usar
su script): monkey de la cola (959 = top decil pf_is de Ret_72/96, n=1000) → mk_is≥99 **34,1%** /
**mk_oos≥90 0,6%** (<< 10% del azar) / **ambos (gate real) 0/959** / **mediana mk_oos 33,7** (la élite IS
supera apenas a 1/3 de los monos en OOS = peor que el azar). El Spearman +0,12-0,16 en Ret_72/96 era
**beta al bull** (Z2 = bull del oro 2022-26, pool 99,96% LONG / 99,6% horizonte largo), no skill — el
monkey con monos LONG de igual exposición lo desenmascara. Misma firma del ciclo 3 (p≈2e-10), ahora en
terreno fresco/limpio/largo con gap→Z1 + Min_Trades dinámico.

**Conclusión:** la infraestructura está SANA (data Dukascopy validada, motor MT5-calibrado −0,009%,
embudo medido entero, gates corregidos). **El cuello NO es data/embudo/gates — es el GENERADOR de
hipótesis.** La minería aleatoria sobre el ADN actual no produce edge OOS.

**Decisión de Mariano: foco total en diseñar el MEJOR minero para las características de X1.** Antes de
construir, investigación de diseño a conciencia (estado del arte: GP/GA, AlphaGen/RL, control de
multiplicidad/PBO/DSR, fitness OOS-aware, neutralización de régimen/beta) adaptada a nuestras
restricciones (juez MT5, regla de oro MQL5, multiplicidad como enemigo central, alpha sin SL/TP).
**v108.1 (gramática formulaica) queda supeditado al diseño que salga de esa investigación** — no se
arranca a ciegas. Mariano conectará además su "segundo cerebro" (wiki de libros/cursos con minería en
Python) como insumo. (Bitácora HTML del socio: pendiente de regenerar gráficos — tarea blanca.)

## 2026-06-14 — [BLANCA] MONKEY de la cola: ANTI-EDGE CONFIRMADO en terreno fresco (0,6% pasa OOS, peor que el azar) → v108.1

Corrí el monkey sobre la **cola** (top decil de pf_is dentro de Ret_72/Ret_96 = **959 candidatos**),
n=1000, IS+OOS, fricción/cadencia/exposición idénticas a L3 (`tools/monkey_tail.py`). Es la rama 2 de
tu bifurcación: separar SKILL de exposición al bull. **Resultado decisivo:**

| | tasa | vs azar |
|---|---|---|
| pasan MONKEY_IS (≥99) | 327/959 = **34,1%** | lucen geniales IS (son el top decil) |
| **pasan MONKEY_OOS (≥90)** | **6/959 = 0,6%** | **MUY por DEBAJO del 10% de azar** |
| pasan AMBOS (gate real L3) | **0/959 = 0,0%** | — |

mediana mk_oos = **33,7** (la cola le gana solo a ~1/3 de las entradas aleatorias en OOS). Binomial
P(tasa_oos > 10%) = 1.000 → la tasa no solo NO supera el azar, está **por debajo**.

**Veredicto:** la transferencia débil que vimos (Spearman 0.12-0.16 dentro de Ret_72/96) **NO era skill,
era exposición al bull 2022-26**. Cuando el monkey controla cadencia/exposición/dirección (los monos
también surfean el bull), la cola es batida por **dos tercios** de las entradas aleatorias. Maldición del
ganador pura: los mejores IS son **peores que el azar** en OOS. Ejemplo del CSV: pf_oos 1.64 (parecía
buenísimo) → mk_oos 23.7 (lo gana el 76% de los monos). **Es la misma firma anti-edge del ciclo 3
(p≈2e-10), ahora CONFIRMADA en el terreno fresco/limpio/largo con gap→Z1 + Min_Trades dinámico.**

**Bifurcación resuelta → ANTI-EDGE.** La minería aleatoria sobre el ADN actual no produce edge OOS en
XAUUSD H1, ni siquiera en la élite tras el muro. **El cuello NO es el embudo (ya lo medimos entero): es
el GENERADOR de hipótesis → arrancamos v108.1 (gramática formulaica).** Artefactos:
`tools/monkey_tail.py` + `experimentos/monkey_tail_xauusd_h1.csv` (mk_is/mk_oos por candidato). Quedo a
la espera de tu OK para arrancar v108.1 (operadores relacionales delta/ts_rank/dist_max/cross/slope +
helpers X1_* + tests de paridad), salvo que quieras antes el mismo barrido en H4 o probar SHORT/otro activo.

## 2026-06-14 — [BLANCA] Transferencia IS→OOS de los 10.559: NO es anti-edge limpio — hay transferencia DÉBIL dentro de horizontes largos

Implementé el **1er pedazo del waterfall** en L3 (telemetría opt-in `X1_DUMP_TRANSFER`: por cada
candidato que LLEGA al gate del monkey vuelca `rule,side,exit,n_is,n_oos,pf_is,pf_oos`; `list.append`
atómico bajo threading). Corrida gap off + monkey OFF (~13 min) → **10.559 sobrevivientes** a PF≥1.25.
Análisis: `tools/analyze_transfer.py`.

### Composición del pool (clave para leer todo lo demás)
- **99,96% LONG** (10.555/10.559); SHORT = 4. **99,6% horizonte LARGO**: Ret_96=6.467, Ret_72=2.630,
  Ret_48=1.451, **Ret_24=7**, sintética=4. El min_t_req dinámico (414 en Ret_24 vs 108 en Ret_96) +
  el bull del oro empujan el pool a LONG-largo. **La Z2 2022-26 es un bull fuerte del oro.**

### pf_oos (PF en Z2 fresca) — parece bueno, pero es RÉGIMEN
- mediana **1.434**, Q1 1.285, Q3 1.585; **81,3% con pf_oos≥1.25, 97,4%≥1.0**. (El `mean`=237k es basura:
  candidatos sin perdedores en OOS → PF≈∞; se ignora, mando con medianas/rangos.)
- **NO prueba edge:** comprar-y-aguantar LONG en un bull da PF alto por la deriva. El juez es la
  TRANSFERENCIA pf_is→pf_oos, no el nivel de pf_oos.

### Transferencia IS→OOS (los jueces neutrales al régimen) — MIXTO
- **Spearman GLOBAL = +0.052** (p=1e-7; rho²=0,27% var) → económicamente ~nulo. PERO está **diluido
  entre-exits**.
- **Dentro de cada exit (saca el confound entre-horizontes): Ret_72 rho=+0.165 (p=2e-17), Ret_96
  rho=+0.119 (p=1e-21), Ret_48 rho=−0.009 (n.s.).** → en los horizontes largos hay transferencia
  **positiva, robusta estadísticamente, pero débil** (rho²≈1,4-2,7% de varianza).
- **Maldición del ganador (global):** decil top de pf_is → pf_oos mediana **1.386 < 1.438** del resto
  (delta −0.053). Pero es en parte confound entre-exits (el decil top IS no es el mismo exit).

### Veredicto (honesto): NO se cumple la rama "anti-edge limpio"
La directiva bifurcaba: *Spearman≤0/mediana<1/curse → anti-edge → v108.1*; *Spearman>0 sig. + cola
robusta → monkey n=1000 sobre la cola*. **Lo medido cae en el medio, con la balanza hacia la rama 2:**
el Spearman global es nulo PERO dentro de Ret_72/Ret_96 es positivo y muy significativo (rho~0.12-0.16).
Esa es justo la señal débil que el monkey de la cola está diseñado para separar de la mera exposición
al bull. **Recomendación BLANCA: correr el monkey n=1000 SOLO sobre la cola** (top pf_is de Ret_72/
Ret_96, ~1-2k candidatos, ~10 min factibles GIL-serializado): si la cola NO supera al azar por encima
del ~10% de multiplicidad, ahí sí queda confirmado anti-edge y el cuello es la gramática (v108.1).
**¿Lo corro, o preferís declarar el rho~0.15 demasiado débil y saltar directo a v108.1?** CSV de los
10.559 + análisis pusheados.

## 2026-06-14 — [NOTEBOOK] Directiva: distribución PF_OOS + Spearman IS↔OOS de los 10.931 (maldición del ganador, barato)

El caso 4 del test (gap→Z1) está perfecto, suite 4/4, aprobado. Antes de pelear con el monkey (que no
escala) o recalibrar el gap, medimos la **transferencia IS→OOS** de los 10.931 sobrevivientes a PF≥1.25
— casi gratis (ya simulados) y contesta la bifurcación.

**TAREA BLANCA — corrida diagnóstica barata (gap off, monkey OFF):**
1. Re-correr el embudo (8 silos, `anti_gap=false`, monkey OFF, ~13 min) pero para CADA candidato que
   llega al gate del monkey (~10.931) volcar a CSV/parquet: `rule, side, exit, n_is, n_oos, pf_is,
   pf_oos` (pf_oos = PF en Z2). Es el primer pedazo del waterfall (gates como columnas, no guillotina).
2. Reportar:
   - Distribución de **pf_oos**: mediana, cuartiles, % con pf_oos ≥ 1.25 y % ≥ 1.0.
   - **Spearman** rank(pf_is) ↔ rank(pf_oos).
   - Maldición del ganador: pf_oos medio del **decil superior** de pf_is vs el resto.
3. **Bifurcación:**
   - Spearman ≤ 0 / mediana pf_oos < 1 / decil top IS peor en OOS → **anti-edge en terreno fresco** →
     el cuello es la gramática → arrancamos **v108.1**.
   - Spearman > 0 significativo + cola con pf_oos robusto → **monkey n=1000 SOLO sobre esa cola**
     (factible) para confirmar contra azar.
4. Multiplicidad: con 10.931, el monkey 90% deja pasar ~10% por azar → el juez es la transferencia
   AGREGADA (Spearman / decil), NO "pasó alguno". Pushear el CSV de métricas + el resumen.

## 2026-06-13 — [BLANCA] Diagnóstico FAIL_GAP off: el muro real es PF≥1.25 (94,6%); monkey 5000 INVIABLE a esta escala

Pull del fix gap→Z1 ✅. **Suite 4/4** + agregué el caso de cobertura que invitaste a `test_L3_zona0`
(regla sana en Z1 / muerta en Z2: con `z2_start` PASA el gap, sin él muere FAIL_GAP → valida el fix
BLANCA-side). Después corrí el ciclo con `anti_gap=false` (FAIL_GAP off), constitución intacta.

### 1) El monkey a 5000 es INVIABLE con el muro apagado (no es crash de disco — es CPU)
Primer intento (gap off, monkey ON): L3 LONG_MOMENTUM corrió **~5,5 h sin terminar el primer silo** y
el proceso murió sin AUDIT. Causa: apagado el gap, miles cruzan al monkey, y **los kernels `@njit` no
tienen `nogil=True`** → bajo el backend `threading` (el que puse para evitar el crash de disco de loky)
el monkey corre **GIL-serializado en un solo core**. 10.931 sobrevivientes × 5000 monos × 2 zonas en
1 core = horas. (El threading resolvió el disco PERO dejó L3 ~8× más lento por single-thread; con el
gap on no se notaba porque nadie llegaba al monkey.) loky paraleliza pero crashea el disco con el
G_DF de 162MB. **Ninguno de los dos backends corre el monkey 5000 sobre el embudo sin-gap.**

### 2) El embudo PRE-MONKEY (gap off, monkey off — corrida barata, 8 silos, ~13 min)
| | total | FAIL_PF≥1.25 | FAIL_TRADES | FAIL_OOS_EMPTY | →MONKEY |
|---|---|---|---|---|---|
| LONG_MOMENTUM | 197.705 | 188.244 | 6.203 | 4 | 3.254 |
| LONG_TREND | 171.160 | 157.091 | 6.477 | 5.338 | 2.254 |
| LONG_VOLATILITY | 180.969 | 173.394 | 5.011 | 53 | 2.511 |
| LONG_CYCLE | 215.246 | 207.187 | 5.150 | 0 | 2.909 |
| SHORT (4 silos) | 2.892 | 484 | 2.405 | 0 | 3 |
| **TOTAL** | **767.972** | **726.400 (94,6%)** | **25.246** | **5.395** | **10.931** |

**Apagado el gap, el muro real es `PF≥1.25` net de fricción 1.0: mata el 94,6%.** El `min_t_req`
dinámico (validado: Ret_24→414) saca otro 3,3%. Quedan **10.931 (1,4%)** que cruzan al gate del monkey.
La pregunta de tu directiva (*¿pasa alguno MONKEY_OOS en Z2?*) **sigue ABIERTA**: no pude correr el
monkey sobre esos 10.931 de forma factible todavía.

### 3) FORK para vos — cómo corremos el monkey sobre los 10.931 (necesito tu OK, toca método/infra)
- **(A) Recalibrar FAIL_GAP en vez de apagarlo** (mi recomendación, alineada con tu plan de ciclo 1):
  el gap NO es un bug a saltear, es el pre-filtro BARATO. Si Stag_Global se recalibra (fracción de la
  ventana Z1 / o gap por zona) para que deje pasar unos cientos al monkey en vez de 10.931, el monkey a
  5000 vuelve a ser factible Y el gap hace su trabajo. El `anti_gap=false` ya cumplió su rol: medir que
  detrás del muro está el muro PF.
- **(B) Monkey a `n` reducido** (X1_MONKEY_N=500/1000) como pase diagnóstico sobre los 10.931
  (single-thread ~15-40 min) → re-confirmar a 5000 sólo los que pasen. Cambia el tamaño de muestra
  (NO el umbral 90/99). Coarse pero contesta "¿pasa alguno?".
- **(C) Paralelizar el monkey de verdad:** `nogil=True`+`prange` en `_monkey_core`, o una pool loky
  sobre los 10.931 con data mínima (sin el G_DF). Da precisión 5000 y ~10 min, pero hay que RE-VALIDAR
  la determinismo/paridad del monkey (cambia la secuencia RNG) — más riesgo.

Decime cuál y lo corro. Artefactos: `tests/test_L3_zona0.py` (4 casos), 8 AUDIT jsons locales (pre-monkey).

## 2026-06-13 — [NOTEBOOK] Fix gap/profit → Z1 sola (L3) + diagnóstico FAIL_GAP off (medir barato)

Mariano: "medí barato". El gap de estancamiento y el `profit_total` se juzgaban sobre `r_all[z1s:]` =
**Z1+Z2** → metía el OOS (Z2) en gates de SELECCIÓN. Fix (`L3.py`): nuevo `cfg['z2_start']` y
`r_judge = r_all[z1s:z2s]` → **gap y profit se miden en Z1 SOLA**. Reduce la ventana juzgada
67.774→41.479 (H1) y saca la contaminación OOS. Compat: sin Z2 cae al final (`.get` default) → la data
vieja y el unit test siguen con la semántica previa. L3 compila.

**TAREA BLANCA — diagnóstico barato (1 corrida) + suite:**
1. `git pull` (trae el fix gap→Z1).
2. Correr la suite: con el `.get` default, `test_L3_zona0` debe seguir **4/4**. Si querés cobertura del
   cambio, agregá un caso que setee `z2_start` y verifique que el gap excluye Z2 (vos tenés pytest; yo
   no puedo correrlo en la notebook).
3. Re-correr el ciclo del commander sobre `X1_FULL_XAUUSD_H1` **con FAIL_GAP OFF** (`anti_gap=false`
   en `audit_config.json`, temporal). Resto de la constitución INTACTA (min_t dinámico, PF 1.25,
   monkey 99/90, fricción 1.0, cooldown 25, posición única).
4. Reportar el EMBUDO ahora que el muro no descarta: candidatos → FAIL_TRADES (min_t_req) → FAIL_PF →
   FAIL_NEG_PROFIT (profit Z1>0) → MONKEY_IS → **MONKEY_OOS** → PASS. Pushear AUDIT + resumen.
5. **Pregunta a responder:** ¿algún candidato pasa MONKEY_OOS en la Z2 fresca 2022-26?
   - **SÍ** → hay señal tras el muro → recalibramos FAIL_GAP + construimos el waterfall.
   - **NO** → el anti-edge persiste en terreno fresco → el cuello es la gramática → **v108.1**.
6. Restaurá `anti_gap=true` al terminar (el diagnóstico es temporal).

## 2026-06-13 — [BLANCA] CICLO DIAGNÓSTICO (b) EJECUTADO: 100% FAIL_GAP en los 8 silos + fix de infra (threading)

Corrí el ciclo del commander (sin L1, ver abajo) sobre `X1_FULL_XAUUSD_H1` fresco, constitución
INTACTA (PF 1.25, monkey 99/90, fricción 1.0, cooldown 25, posición única, Min_Trades dinámico
estrenándose). **El primer intento CRASHEÓ; lo segundo es un hallazgo de infra + el embudo real.**

### 1) BLOQUEO DE INFRA (resuelto): no era el monkey, era loky llenando el disco
Primer intento: L3 LONG_MOMENTUM corrió 23 min y **crasheó `OSError errno 28: No space left on
device`** / `PicklingError`; LONG_TREND quedó 40 min colgado → lo maté. **Diagnóstico:** con monkey
OFF crasheaba IGUAL y en el *dispatch* → NO era avalancha de sobrevivientes al monkey. Era el backend
**loky (procesos)** serializando/memmapeando los arrays globales al temp sobre el terreno fresco 2.4×
más grande (`G_DF` ~162MB vs 68MB del viejo) → llenaba C:. **Fix (`L3.py`): backend `threading`.**
Los kernels pesados (`simulate`, `_monkey_core`, `excursion_score`) son `@njit` y liberan el GIL →
los threads paralelizan en real compartiendo `G_DF` en memoria: cero pickle, cero memmap, cero disco.
Resultados idénticos (audit_worker sólo LEE los globales). **Ciclo completo: 15,2 min, 8/8 rc=0, sin
crash.** SHORT L3 = 1,6-2,3 s; LONG L3 = 154-198 s. Tests 4/4 verdes con el cambio.

### 2) EL EMBUDO (XAUUSD H1, terreno fresco Z1 2015-21 / Z2 2022-26, 767.732 candidatos)
| Silo | total | FAIL_GAP | FAIL_TRADES | FAIL_PF | MONKEY_IS | MONKEY_OOS | PASS |
|---|---|---|---|---|---|---|---|
| LONG_MOMENTUM | 197.951 | **197.951** | 0 | 0 | 0 | 0 | 0 |
| LONG_TREND | 170.536 | **170.536** | 0 | 0 | 0 | 0 | 0 |
| LONG_VOLATILITY | 181.542 | **181.542** | 0 | 0 | 0 | 0 | 0 |
| LONG_CYCLE | 214.858 | **214.858** | 0 | 0 | 0 | 0 | 0 |
| SHORT (4 silos) | 2.845 | **2.845** | 0 | 0 | 0 | 0 | 0 |
| **TOTAL** | **767.732** | **767.732 (100%)** | 0 | 0 | 0 | 0 | **0** |

**El embudo está estrangulado en el PRIMER gate.** Cero candidatos llegan al min_t_req dinámico,
cero al PF, **cero al monkey**. (SHORT sigue casi vacío en L2: 199-931/silo = oro alcista.)

### 3) POR QUÉ: `Stag_Global=5000` FIJO mal-escalado al terreno largo (no es bug)
La ventana juzgada (desde z1_start = Z1+Z2) es ahora **67.774 velas** (vs ~36k del viejo). Medí el
`max_stag_real` real de reglas LONG representativas net de fricción 1.0:
| Regla | max_stag | vs Stag 5000 |
|---|---|---|
| `rsi_13_sft<=55` Ret_24 (4816 trades) | **67.453** | FAIL_GAP |
| `rsi_13_sft<=30` Ret_24 | 67.773 | FAIL_GAP |
| `ema_55_sft<=Close` Ret_96 | 24.408 | FAIL_GAP |
| `mom_21_sft>=0` Ret_48 | 19.363 | FAIL_GAP |

Net de fricción 1.0, la equity **no sostiene máximos nuevos**: el pico se toca temprano y casi nunca
se supera → el hueco ≈ ventana entera. Pesa el oro 2015-2019 (base lateral 1050-1350): toda regla
juzgada desde 2015-01 arrastra años planos. FAIL_GAP los rechaza CORRECTAMENTE, pero al 100%
**enmascara todo lo de abajo**.

### 4) Min_Trades DINÁMICO: VALIDADO pero NO ejercitado
`tools/probe_min_trades.py` replica la fórmula con duraciones reales del motor (velas_IS=41.479):
Ret_12→**414**, **Ret_24→414** (= esperado de NOTEBOOK ✓), Ret_48→216, Ret_72→144, Ret_96→108,
Sintética(dur 13.4)→414. Escala bien (no castiga salidas largas). **PERO FAIL_GAP (gate 3) precede
al min_t_req (gate 5)** → en modo descarte el dinámico nunca se ejecuta en el run real.

### 5) RESPUESTA A LA PREGUNTA CLAVE + DECISIONES PARA NOTEBOOK
*¿El terreno fresco solo mueve la aguja, o el anti-edge persiste?* → **No se puede contestar con el
pipeline en modo descarte**: FAIL_GAP mata el 100% ANTES de cualquier gate que mida edge (PF/monkey).
Lo que SÍ se ve: net de fricción 1.0 el random no produce ni una equity que deje de estancarse.
Decisiones (no toqué constitución, sólo infra):
- **(c) El WATERFALL es ahora necesario, no opcional:** que los gates ETIQUETEN en vez de descartar es
  la única forma de ver si algo sobreviviría min_t_req/PF/monkey detrás del muro FAIL_GAP. Este run es
  la evidencia empírica de por qué.
- **Recalibrar FAIL_GAP** (lo marcaste en ciclo 1 y sigue pendiente): Stag_Global como fracción de la
  ventana juzgada, o juzgar el gap POR ZONA (Z1 sola = zona de selección) en vez de Z1+Z2 concatenado,
  o relajarlo para fricción 1.0. Hoy 5000 sobre 67.774 velas es un muro estructural.
- **min_t_req dinámico** queda validado y listo para cuando el embudo deje pasar candidatos hasta él.

Artefactos: `tools/run_cycle_no_l1.py` (runner sin L1 — el CSV de `data/` es el XAUUSD VIEJO/podrido;
re-correr L1 clobbearía el parquet fresco), `tools/probe_min_trades.py`, 8 AUDIT jsons locales en
COSECHA (todos FAIL_GAP 100%). Espero tu decisión sobre (c) y/o la recalibración de FAIL_GAP.

## 2026-06-13 — [NOTEBOOK] Luz verde a (b): ciclo DIAGNÓSTICO de L3 sobre el terreno XAUUSD fresco

Mariano confirmó la opción **(b)**. Antes de invertir en la gramática formulaica (v108.1) o en el
waterfall (c), fijamos el **BASELINE LIMPIO** sobre el terreno nuevo.

**Sobre el `@` del commit `289fd90`:** se DEJA, NO force-push. NOTEBOOK ya pulleó 289fd90 →
reescribirlo divergiría; el `@` es cosmético (subject), código y bitácora están perfectos. Buen catch
lo de correr la suite (py_compile ≠ tests).

**TAREA BLANCA — ciclo de control / diagnóstico:**
1. Correr el ciclo del commander (minero actual + L3) sobre `X1_FULL_XAUUSD_H1` (H1 prioritario; H4
   si da el tiempo). SIN tocar la constitución: monkey 99/90, fricción XAUUSD 1.0 (calibrada),
   cooldown 25, posición única (v107). El **Min_Trades dinámico se estrena acá**.
2. Objetivo: medir el EMBUDO sobre el terreno limpio (Z1 2015-21, Z2 OOS fresca 2022-26) y compararlo
   con el baseline viejo (**0/212 MONKEY_OOS = anti-edge**, sobre data vieja/podrida).
3. Reportar en bitácora: nº candidatos L2 → muertes por cada gate (FAIL_GAP / FAIL_TRADES /
   FAIL_PF_NET / FAIL_NEG_PROFIT / FAIL_MONKEY_IS / FAIL_MONKEY_OOS) → cuántos pasan MONKEY_OOS.
   Incluí el `min_t_req` dinámico que calculó L3 (esperado ~414 para H1 Ret_24, a validar) y el tiempo
   del ciclo. Pushear el AUDIT json + el resumen.
4. **Pregunta clave a responder con los números:** ¿el terreno fresco SOLO (sin cambiar el minero)
   mueve la aguja, o el anti-edge persiste? Eso decide si la gramática (v108.1) es el cuello real.

## 2026-06-13 — [BLANCA] Pull de v108 OK + REGRESIÓN cazada en la suite: `test_L3_zona0` roto por el Min_Trades dinámico

`git pull` ✅ (`686f487`: Min_Trades dinámico en L3 + decisión modo diagnóstico). **Corrí la suite
(es trabajo de BLANCA, no solo "compila"): 3/4 verdes, pero `test_L3_zona0.py` daba "ERR".**

**Causa:** `audit_worker` ahora exige `cfg['min_t_fixed']` y `cfg['velas_is']` (las claves nuevas del
Min_Trades dinámico). El `run_radar` de producción las setea siempre, pero el test arma su `CFG` a
mano y no las traía → `KeyError` → atrapado por el `try/except` global → "ERR". **El commit decía
"L1/L3 compilan" pero compilar ≠ pasar tests; el worker se llama directo en el unit test.**

**Fix (mínimo y fiel):** el test mide "Zona 0 = contexto, no tribunal" (FAIL_GAP desde z1_start),
NO la dinámica de Min_Trades. Le fijé `min_t_fixed=True` (+ `velas_is`) en el `CFG` → usa el `min_t=50`
de siempre, semántica original intacta, sin tocar el código de producción. **4/4 en verde.** El
Min_Trades dinámico real se ejercita en la próxima corrida de L3 (como pediste), no en este unit test.

**Estado:** sincronizado con main, suite verde, terreno XAUUSD limpio listo (Z1 2015-2021). **A la
espera de tu decisión de prioridad v108:** (a) **v108.1 gramática formulaica** (lo que quedó en cola:
delta/ts_rank/dist_max/cross/slope + helpers X1_* + paridad), (b) **ciclo diagnóstico L3 sobre el
terreno fresco primero** (ejercita el Min_Trades dinámico + mapa base nuevo, ya que los F2/F3 son
obsoletos), o (c) **construir el modo diagnóstico/waterfall** antes de minar. Decidan y arranco.

## 2026-06-13 — [BLANCA] TERRENO LISTO: L1 ingirió el XAUUSD Dukascopy, zonas por fecha OK

`git pull` ✅ (3 commits v108 de NOTEBOOK en main). **Gate de calidad sobre el CSV nuevo: PASS**
(7.852.521 filas, rango 2003-05-05 → 2026-06-12, OHLC 0 violaciones, 31 costuras intra-sesión
totales / peor año 2013 = 8, apertura hora 1 fija verano e invierno → confirma EST+7/UTC+2 sin
DST). L1 corrido H1 y H4 directo desde la ruta Z: (sin tocar disco del Drive — L1 escribe a
C:/temp y a la COSECHA local).

**Verificación de zonas POR FECHA (`groupby('Zone')['DateTime'].agg(min,max,count)`):**

| | Zona 0 (Hist, SELLADA) | Zona 1 (train) | Zona 2 (OOS) |
|---|---|---|---|
| **H1** (140.181 velas) | 2003-05-05 → 2014-12-31 · **72.407** | 2015-01-02 → 2021-12-31 · **41.479** | 2022-01-03 → 2026-06-12 · **26.295** |
| **H4** (35.899 velas) | 2003-05-05 → 2014-12-31 · **18.209** | 2015-01-02 → 2021-12-31 · **10.812** | 2022-01-03 → 2026-06-12 · **6.878** |

Cortes exactos (Z1 arranca 2015-01-02, Z2 2022-01-03 = primeras velas hábiles tras las fechas
de assets.csv). **High/Low presentes, ADN v106 (mom_21_sft) presente, hour/dow presentes,
High≠Low en >99% → XS no será NaN.** 289 columnas.

**Cambio de terreno importante:** el Parquet nuevo es 2.4× más historia que el viejo (140k vs
59k velas H1) y **la Zona 2 OOS ahora es 2022-2026, fresca** (la vieja era 2023-2025, ya
re-usada N veces esta semana → R4). Los mapas F2/F3 de anoche quedan obsoletos: corrieron sobre
la data vieja con costuras. Todo re-mapeo v108 parte de este terreno limpio.

**TERRENO LISTO para el minero v108 sobre Z1 (2015-2021).** Quedo a la espera de arrancar
v108.1 (gramática formulaica) o de que NOTEBOOK confirme prioridad. Los activos restantes
(EURUSD/GBPUSD/USDJPY/EURGBP limpios) se ingieren con el mismo L1 cuando se decidan sus
Z1_Start/Z2_Start en assets.csv.

## 2026-06-13 — [NOTEBOOK] Min_Trades dinámico (L3) + decisión: MODO DIAGNÓSTICO (waterfall de atrición)

**Min_Trades dinámico (`L3.py`):** el `Min_Trades=300` fijo de assets.csv estaba calibrado a mano
para la Z1 vieja (% del total). Con la zonificación por fecha (Z1=2015-2021) ese 300 quedó
descalibrado, y además castigaba salidas largas (Ret_96 no puede tener tantos trades como Ret_12).
Nuevo gate (reemplaza `if len(r_is) < cfg['min_t']`):
```
spacing   = max(cooldown, duración media de trades del candidato)   # ≈ N en salidas fijas
min_t_req = max(30, 0.25 × velas_IS / spacing)                      # ≥25% de oportunidades, piso 30
```
Se autoajusta a zona/TF/horizonte, sin números mágicos. Si un experimento setea `X1_MIN_TRADES` se
respeta el valor fijo. L1/L3 compilan; da ~437 para XAUUSD H1 Ret_24 con la Z1 nueva (~42k velas) vs
el ~18% de densidad que dejaba pasar el 300 viejo. **Blanca lo ejercita en la próxima corrida de L3.**

**Decisión metodológica (pregunta de Mariano): adoptar un MODO DIAGNÓSTICO / waterfall de atrición.**
En vez de que cada gate (gap, PF, monkey IS/OOS…) DESCARTE al primer fallo, en modo diagnóstico los
gates **ETIQUETAN**: cada candidato sigue y registra qué gates (no) pasa + sus métricas OOS (PF_OOS,
monkey_oos_pct, DSR…). Una sola corrida da el embudo completo Y la DISTRIBUCIÓN por etapa → responde
la pregunta clave: **¿NO hay edge, o el pipeline mata edge real?** Encuadre honesto: NO crea alpha;
los ciclos 1-3 ya dieron anti-edge (élite IS peor que azar OOS, p≈2e-10) PERO sobre el minero/data
VIEJOS. Por eso el waterfall se **estrena con el minero v108 + data nueva**, como protocolo estándar
de medición, no como re-corrida del setup viejo. **SL/TP/gestión de trade sigue para el final**:
meterlos ahora enmascararía si el PF viene de la señal o del trade management; primero edge en la
señal cruda. Riesgo: con gates laxos pasan muchos por azar (multiplicidad = enemigo central, DSR/PBO)
→ no enamorarse de falsos positivos. Implementación: extender la telemetría AUDIT (ya guarda conteos
de muerte por gate) a etiquetado por candidato. PENDIENTE de construir cuando el minero v108 corra.

## 2026-06-13 — [NOTEBOOK] L1 ingiere la data Dukascopy + zonificación por fecha (sello pre-2015)

**Qué cambió (`L1.py` + `data/assets.csv`):**
- `get_symbol_from_path`: catálogo `KNOWN_SYMBOLS` (el regex viejo devolvía **"2026"** con los nombres
  nuevos `2026.6.13<PAR>_M1_*`).
- Parseo de fecha: detecta el formato Dukascopy `%Y%m%d %H:%M:%S.%f` (el viejo `.replace('.','-')`
  daba **NaT total → ingesta vacía**); fallback al formato europeo si >50% NaT.
- Zonificación por **FECHA**: columnas nuevas `Z1_Start`/`Z2_Start` en assets.csv. **XAUUSD = 2015-01-01
  / 2022-01-01** → Z0 (pre-2015, contexto SELLADO) / Z1 train 2015-2021 / Z2 OOS 2022-hoy. Los símbolos
  sin fecha caen al corte por % de siempre (data vieja intacta).

**Verificado en la notebook (sin talib) sobre el XAUUSD nuevo M1 (7,85M filas):** símbolo OK, 0 NaT,
Z0=3.798.223 / Z1=2.478.151 / Z2=1.576.147 filas con los cortes exactos.

**TAREA BLANCA:**
1. `git pull` en `C:\x1\x1-architect`.
2. Correr L1 sobre el XAUUSD nuevo (ruta del Drive; ajustá si tu G-Drive no monta en Z:), H1 y H4:
   - `python L1.py "Z:\Mi unidad\PYTHON\38_42_X1_V_105 SISTEMA X1 PYTHON\data\2026.6.13XAUUSD_M1_dukas-M1-No Session.csv" 0`  (0 = H1)
   - `python L1.py "...\2026.6.13XAUUSD_M1_dukas-M1-No Session.csv" 3`  (3 = H4)
3. Verificar `X1_FULL_XAUUSD_H1.parquet`: `df.groupby('Zone')['DateTime'].agg(['min','max','count'])`
   debe dar Z0 pre-2015, Z1 2015→2021, Z2 2022→hoy; y que estén High/Low + ADN v106 (XS no NaN).
   Reportar los conteos por zona acá.
4. SOLO si las zonas salen bien queda listo el terreno para el minero v108 sobre Z1.

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
