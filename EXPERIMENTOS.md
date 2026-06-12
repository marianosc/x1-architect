# EXPERIMENTOS NOCTURNOS — 2026-06-12

# ═══ ACTUALIZACIÓN POST-FIX v107 (Fases 1-4, opción B aprobada) ═══

## TOP-3 HALLAZGOS (versión final, post-fix)

1. **v107 implementado y verificado** (posición única, default; 36/36 tests; mergeado a main):
   el artefacto desapareció (Spearman solape↔mk_oos +0.425 → +0.036) y bajo el lente honesto
   **la cosecha completa de la semana era espejismo: CERO supervivientes** — caen los 7 PASS
   oficiales de H4, caen los 2 "honestos" de C1 re-auditados (mk_oos 79.5/40.2), y los mapas
   H1/H4/M30/H1C4 dan 0 PASS sobre ~4,5M de candidatos.
2. **XS_IS no es robusto bajo v107** (+0.076 global, n.s. en el subset corto): el +0.36 de
   anoche era en gran parte gradiente de palanca entre cohortes; lo que el lente limpio deja
   visible es la **maldición del ganador** en estado puro (decil más alto de monkey_is → el
   PEOR pf_oos: 1.652 vs 1.865).
3. **EURUSD H4 "9.928 PASS" = datos podridos**: costuras de ±12-16% en fines de mes (el CSV
   es una concatenación con bases distintas), 81 saltos >1% por año — descartado el 100% de
   la cosecha, pipeline EURUSD bloqueado hasta datos limpios, y propuesto un gate de calidad
   de datos en L1.

## TABLA COMPARATIVA: viejo lente (apilado) vs nuevo lente (v107 posición única)

| Mapa | Viejo lente | Nuevo lente v107 | Lectura |
|---|---|---|---|
| H1 XAUUSD oficial | 0/212 en MK_OOS (mezcla contaminada) | 0 PASS; frontera vacía hasta mk_oos≥50/PF 1.05/XS | H1 estéril — confirmado con instrumento limpio |
| H4 XAUUSD escalado | **7 PASS** (A1) + tema estable (C1) | **0 PASS**; mk_IS ahora mata (la palanca regalaba IS=100) | Los primeros "PASS oficiales" eran apilamiento |
| 2 honestos C1 (solape 1.0×) | PASS 99/90 | **FAIL** (mk_oos 79.5 y 40.2; −37% de trades) | La media de solape escondía trades apilados |
| H1C4 (B3, prior de Mariano) | 0 PASS (nulo condicionado al bug) | 0 PASS (**nulo real**) | El contexto H4 no desbloquea H1 |
| M30 XAUUSD | no corrido | 0 PASS | Prior bajo confirmado; mapa de TFs cerrado |
| EURUSD H4 | no corrido | 9.928 "PASS" → **artefacto de DATOS** | CSV con costuras mensuales; descartado entero |
| Fantasma/correlaciones | XS_IS +0.36 "el filtro que faltaba" | XS_IS +0.076 / n.s. — no robusto | El predictor era en parte la palanca |

## RECOMENDACIÓN FINAL

1. **Aprobar el Min_Trades dinámico** (25% de ocupación de Z1 / espaciado, floor 30 — tabla
   en BITACORA): sin esto, el embudo v107 castiga estructuralmente a las salidas largas.
2. **Gate de calidad de datos en L1** (umbral de saltos >1%/año) + re-descargar EURUSD limpio
   + calibración canario EURUSD (la fricción de assets.csv está mal escalada: 83%/trade).
3. **La minería aleatoria sobre este ADN está agotada** — medida con instrumento ya confiable.
   El siguiente paso con mejor relación señal/esfuerzo: **hipótesis dirigidas formuladas
   ex-ante** (la primera candidata: el tema "comprar debilidad en tendencia H4", que fue
   estable por semilla, re-formulado como hipótesis y testeado en datos frescos + MT5 — no
   re-minado), y recién después ADN nuevo.
4. **Reality Check MT5: SIN candidatos** tras el re-mapeo (los EAs H4TREND01/02 quedan en
   `experimentos/EAs/` como referencia histórica del artefacto).

# ═══ INFORME ORIGINAL DE LA NOCHE (pre-fix, para trazabilidad) ═══

## TOP-3 HALLAZGOS DE LA NOCHE (3 frases)

1. **El monkey premiaba apilamiento, no timing:** el motor imputa Ret_N en cada entrada con
   cooldown 25, así que con N>25 simula una cartera piramidada que el EA real no puede ejecutar
   y que el mono (busyUntil) no puede replicar — la tasa de paso OOS escala del 10% (sin solape,
   = azar) al 94% (Ret_96, 4×), o sea que **gran parte de la cosecha histórica de salidas largas
   es un espejismo de apalancamiento** y el embudo oficial excluye estructuralmente lo implementable
   (0/389 honestos cruzan los gates fijos).
2. **Corregido el lente, XS_IS es el primer predictor IS→OOS real del proyecto:** en el subset
   honesto sin solape, xs_is (+0.36), pf_is (+0.31) y beta_is (+0.36) predicen pf_oos con
   p<1e-9 — el filtro que faltaba existe, pero solo vale en el espacio EA-implementable.
3. **H4 produce los primeros PASS oficiales (7) y un tema estable por semilla:** "comprar
   debilidad/caída en el oro" reaparece en todas las semillas; tras filtrar solape quedan
   **2 reglas honestas de tendencia** (mk_OOS 92.6/91.1, EAs compilados listos para MT5),
   mientras que sesión (B2) dio nulo y H1 sigue en cero.

## RECOMENDACIÓN — próximo experimento que más vale la pena

**Arreglar la semántica de solape y re-mapear el terreno con el lente corregido** (es la
madre de todos los resultados de esta semana): decidir entre (a) L2 limitado a salidas
≤ cooldown, (b) motor con `busyUntil` igual al EA, o (c) EA piramidal que materialice lo
que el motor simula — y re-correr UN ciclo H1+H4 con la opción elegida + filtro XS_IS como
gate blando. Recién después, Reality Check MT5 de los 2 honestos H4 (EAs ya compilados) y,
si sobreviven, la fase de hipótesis dirigida sobre el tema "comprar debilidad en tendencia".

---

> Baseline: H1 XAUUSD, listones oficiales (PF 1.25, monkey 99/90, fricción 1.0) → **0/212 pasan MONKEY_OOS**.
> Regla de honestidad (R4): la Zona 2 ya fue reutilizada N veces — NADA de esta noche queda "validado";
> techo = "prometedor, a confirmar con datos frescos + MT5". Candidato con listón rebajado = FRONTERA, no DIAMANTE.
> Tabla ordenada por valor de hallazgo (no por orden de ejecución).

| ID | Hipótesis | Cambio exacto | Resultado | Veredicto (1 línea) |
|----|-----------|---------------|-----------|---------------------|
| A2.5 | (descubierto, no planeado) ¿el monkey mide timing? | Auditoría del fantasma por tipo de salida | mk_oos escala con el solape: Ret_12 pasa 10,3% (=azar), Ret_96 pasa 94,2% (4× piramidación). El motor apila posiciones que el EA real no puede abrir | **EL HALLAZGO DE LA NOCHE: bug semántico motor-apila/EA-no; invalida cosechas de salidas largas; el monkey premiaba apalancamiento** |
| A3 | Algo de IS predice OOS | Spearman+deciles sobre fantasma 20k, pool completo vs subset honesto (expo≤cooldown) | Pool completo: pf_is ANTI-predice (−0.26, gradiente de solape). **Subset honesto (n=389): xs_is +0.36, pf_is +0.31, beta_is +0.36 contra pf_oos** | **XS_IS es el primer predictor IS→OOS real — el filtro que faltaba — pero solo vale en el espacio sin solape** |
| A4 | Mapa de listones | Matriz mk_oos{90..50}×pf{1.25,1.15,1.05} sobre fantasma | Pool completo: 4-5 "pasan" (espejismo apalancado). **Honesto: 0/389 cruzan ni los gates fijos** (trades≥300 + mk_is≥99 inalcanzables sin apilar) | **El embudo oficial excluye lo implementable y cosecha lo no-implementable; rediseño de salidas/cooldown para NOTEBOOK** |
| B1 | Métricas institucionales separan mejor | DSR/PSR/t-stat + PBO(CSCV 8 bloques) como columnas fantasma | DSR≥0.95: solo 813/20k aun con apalancamiento (SR0=0.20/trade @N=1M). PBO=0.29. t/PSR/DSR son OOS→veredicto final, no filtro | **DSR confirma la multiplicidad como problema central; PBO moderado; el filtro accionable sigue siendo XS_IS** |
| A1 | H4 respira donde H1 se ahoga (menos ruido, menos peaje relativo) | TF=H4, escala tiempo-equivalente ÷4: Stag 1250, Min_Trades 75, cooldown 6, señales L2 50. Listones OFICIALES intactos (PF 1.25, 99/90, fricción 1.0) | **7 PASS / 5 cosechados** de 1.35M — todos LONG dip-buy, sintética, XS_OOS 0.63-0.68, mk_OOS 90.2-92.6. **Post-A2.5: los 4 MOMENTUM tienen solape 2× (FRONTERA*); el de TREND es limpio 1.0×** | **Primeros PASS oficiales; tras la enmienda queda 1 finalista honesto (`adx_34>=27 & minus_di_8>=19.7`); C1 + MT5 obligatorios** |

| C1 | ¿Los finalistas H4 sobreviven a la semilla? | Re-minado virgen ×2 semillas de TREND y MOMENTUM H4 | MOMENTUM: `roc_55<=-2.79` reaparece SIEMPRE (estable, pero solape 2×). TREND: el tema reaparece (5 PASS en 2 semillas), la regla literal nunca; 2 reglas honestas de solape en total | **El TEMA "comprar debilidad en tendencia H4" es estable y honesto → candidato a hipótesis dirigida; EAs compilados listos para Reality Check MT5** |

| B2 | La estructura horaria del oro tiene edge propio | hour/dow como genes (L1+L2 familia CYCLE+traductor MQL5 vía TimeToStruct); ciclos H1 y H4 | H1: 0 PASS (8 silos). H4: **0 reglas con hour/dow** entre los PASS; CYCLE=0 en ambos TF. Cadena MQL5 validada (EA compila) | **NULO bajo listones oficiales — la sesión no aporta finalistas; infraestructura queda lista** |

| B3 | El contexto de tendencia H4 desbloquea H1 (prior alto de Mariano) | 12 genes `*_h4x*_sft` (ema/adx/linreg/efficiency ×{21,55,120}) vía merge_asof sin lookahead (0 violaciones, verificado); 8 silos H1C4, constitución oficial | **0 PASS en 8 silos**; los genes SÍ estaban en el pool TREND (verificado) | **Nulo bajo el embudo actual — re-testear DESPUÉS del fix de solape: este nulo es del embudo, no necesariamente de la hipótesis** |
| C2 | M30 / EURUSD H4 | — | NO CORRIDO (sin tiempo: gap de 5h sin reinvocación tras B2) | Pendiente |

## Detalle por experimento → BITACORA.md (entrada por experimento)
