# EXPERIMENTOS NOCTURNOS — 2026-06-12

> Baseline: H1 XAUUSD, listones oficiales (PF 1.25, monkey 99/90, fricción 1.0) → **0/212 pasan MONKEY_OOS**.
> Regla de honestidad (R4): la Zona 2 ya fue reutilizada N veces — NADA de esta noche queda "validado";
> techo = "prometedor, a confirmar con datos frescos + MT5". Candidato con listón rebajado = FRONTERA, no DIAMANTE.

| ID | Hipótesis | Cambio exacto | Resultado | Veredicto (1 línea) |
|----|-----------|---------------|-----------|---------------------|
| A2.5 | (descubierto, no planeado) ¿el monkey mide timing? | Auditoría del fantasma por tipo de salida | mk_oos escala con el solape: Ret_12 pasa 10,3% (=azar), Ret_96 pasa 94,2% (4× piramidación). El motor apila posiciones que el EA real no puede abrir | **EL HALLAZGO DE LA NOCHE: bug semántico motor-apila/EA-no; invalida cosechas de salidas largas; el monkey premiaba apalancamiento** |
| A3 | Algo de IS predice OOS | Spearman+deciles sobre fantasma 20k, pool completo vs subset honesto (expo≤cooldown) | Pool completo: pf_is ANTI-predice (−0.26, gradiente de solape). **Subset honesto (n=389): xs_is +0.36, pf_is +0.31, beta_is +0.36 contra pf_oos** | **XS_IS es el primer predictor IS→OOS real — el filtro que faltaba — pero solo vale en el espacio sin solape** |
| A4 | Mapa de listones | Matriz mk_oos{90..50}×pf{1.25,1.15,1.05} sobre fantasma | Pool completo: 4-5 "pasan" (espejismo apalancado). **Honesto: 0/389 cruzan ni los gates fijos** (trades≥300 + mk_is≥99 inalcanzables sin apilar) | **El embudo oficial excluye lo implementable y cosecha lo no-implementable; rediseño de salidas/cooldown para NOTEBOOK** |
| B1 | Métricas institucionales separan mejor | DSR/PSR/t-stat + PBO(CSCV 8 bloques) como columnas fantasma | DSR≥0.95: solo 813/20k aun con apalancamiento (SR0=0.20/trade @N=1M). PBO=0.29. t/PSR/DSR son OOS→veredicto final, no filtro | **DSR confirma la multiplicidad como problema central; PBO moderado; el filtro accionable sigue siendo XS_IS** |
| A1 | H4 respira donde H1 se ahoga (menos ruido, menos peaje relativo) | TF=H4, escala tiempo-equivalente ÷4: Stag 1250, Min_Trades 75, cooldown 6, señales L2 50. Listones OFICIALES intactos (PF 1.25, 99/90, fricción 1.0) | **7 PASS / 5 cosechados** de 1.35M — todos LONG dip-buy, sintética, XS_OOS 0.63-0.68, mk_OOS 90.2-92.6. **Post-A2.5: los 4 MOMENTUM tienen solape 2× (FRONTERA*); el de TREND es limpio 1.0×** | **Primeros PASS oficiales; tras la enmienda queda 1 finalista honesto (`adx_34>=27 & minus_di_8>=19.7`); C1 + MT5 obligatorios** |

## Detalle por experimento → BITACORA.md (entrada por experimento)
